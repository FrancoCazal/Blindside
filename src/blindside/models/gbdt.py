"""LightGBM y XGBoost globales, incluida la version cuantilica.

`LightGBMForecaster` es el caballo de batalla: un modelo para todas las series,
con las jerarquias como categoricas nativas. En demanda retail con muchas series
cortas es el que suele ganar, y es el que escala.

`LightGBMQuantileForecaster` es la pieza que conecta con la capa de decision. Se
entrena con **perdida cuantilica** en el cuantil critico del newsvendor
`q* = Cu / (Cu + Co)`, y entonces su prediccion **es** la cantidad a reponer. El
modelo deja de emitir un numero abstracto que alguien tiene que interpretar y
emite una orden.

Nota sobre el objetivo de entrenamiento: se usa `objective="tweedie"` como opcion
para el modelo puntual. En demanda de perecederos hay muchos ceros y una cola
derecha larga, que es exactamente la forma de una Tweedie; el L2 sobre esa
distribucion tira las predicciones por encima del cero incluso donde no hay
demanda. Se deja configurable y se compara, no se asume.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from blindside import config as cfg
from blindside.features import build as fb
from blindside.models.base import quantile_col
from blindside.models.tabular import TabularForecaster, prepare_categoricals

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

#: Hiperparametros de partida. Conservadores a proposito: el punto de comparacion
#: tiene que ser un LightGBM razonable sin tunear, para que despues se pueda
#: mostrar cuanto aporto Optuna en vez de mezclar las dos cosas.
DEFAULT_LGBM_PARAMS: dict[str, Any] = {
    "objective": "regression_l1",
    "metric": "mae",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_child_samples": 40,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "num_threads": 0,
    "verbosity": -1,
    "seed": cfg.SEED,
}

#: L1 y no L2 por defecto. La perdida absoluta estima la **mediana**, que en una
#: distribucion con cola derecha larga es lo que se quiere para un pronostico
#: puntual; L2 estima la media y queda arrastrada por los picos promocionales.


class LightGBMForecaster(TabularForecaster):
    """LightGBM global, un modelo para todas las series."""

    name = "lgbm_global"
    supports_quantiles = False

    def __init__(
        self,
        *,
        params: dict[str, Any] | None = None,
        n_estimators: int = 600,
        categorical_features: Sequence[str] = fb.CATEGORICAL_FEATURES,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.params = {**DEFAULT_LGBM_PARAMS, **(params or {})}
        self.n_estimators = n_estimators
        self.categorical_features = tuple(categorical_features)
        self._booster = None

    def _fit_matrix(self, X: pd.DataFrame, y: np.ndarray, *, features: list[str]) -> None:
        import lightgbm as lgb

        Xc = prepare_categoricals(X, self.categorical_features)
        cats = [c for c in self.categorical_features if c in Xc.columns]
        dataset = lgb.Dataset(Xc, label=y, categorical_feature=cats, free_raw_data=True)
        self._booster = lgb.train(self.params, dataset, num_boost_round=self.n_estimators)

    def _predict_matrix(self, X: pd.DataFrame) -> np.ndarray:
        if self._booster is None:
            raise RuntimeError(f"{self.name}: booster no entrenado")
        Xc = prepare_categoricals(X, self.categorical_features)
        return np.asarray(self._booster.predict(Xc), dtype="float64")

    def feature_importance(self) -> pd.Series:
        if self._booster is None:
            return pd.Series(dtype="float64")
        return pd.Series(
            self._booster.feature_importance(importance_type="gain"),
            index=self._booster.feature_name(),
            name="gain",
        ).sort_values(ascending=False)

    @property
    def booster(self):
        """El booster crudo, para SHAP."""
        return self._booster


class LightGBMQuantileForecaster(TabularForecaster):
    """Un LightGBM por cuantil, con perdida cuantilica.

    Es la pieza que convierte el pronostico en decision. Entrenar directamente en
    `q*` en vez de estimar la media y sumarle un stock de seguridad heuristico es
    la diferencia entre una politica derivada de la economia y una regla de dedo.

    Existe un resultado que prueba que los pronosticos cuantilicos calibrados son
    **equivalentes** a la solucion optima del newsvendor
    (https://www.mdpi.com/1911-8074/19/3/173), asi que esto no es una
    aproximacion conveniente: es la solucion, siempre que el cuantil este
    calibrado. Por eso la cobertura empirica se mide y se reporta.

    Costo: un booster por cuantil. Con cuatro cuantiles el entrenamiento se
    cuadruplica, y es la razon de que el modelo puntual y el cuantilico esten
    separados en vez de ser el mismo objeto.
    """

    name = "lgbm_quantile"
    supports_quantiles = True

    def __init__(
        self,
        *,
        quantiles: Sequence[float] = cfg.FORECAST.quantiles,
        params: dict[str, Any] | None = None,
        n_estimators: int = 400,
        categorical_features: Sequence[str] = fb.CATEGORICAL_FEATURES,
        point_quantile: float | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.quantiles = tuple(sorted(quantiles))
        if not all(0 < q < 1 for q in self.quantiles):
            raise ValueError("los cuantiles deben estar en (0, 1)")
        base = {**DEFAULT_LGBM_PARAMS, "objective": "quantile", "metric": "quantile"}
        self.params = {**base, **(params or {})}
        self.n_estimators = n_estimators
        self.categorical_features = tuple(categorical_features)
        #: Cuantil que se devuelve como prediccion puntual. Por defecto la
        #: mediana si esta, y si no el mas cercano a 0,5.
        self.point_quantile = point_quantile or min(self.quantiles, key=lambda q: abs(q - 0.5))
        self._boosters: dict[float, Any] = {}

    def _fit_matrix(self, X: pd.DataFrame, y: np.ndarray, *, features: list[str]) -> None:
        import lightgbm as lgb

        Xc = prepare_categoricals(X, self.categorical_features)
        cats = [c for c in self.categorical_features if c in Xc.columns]
        self._boosters = {}
        for q in self.quantiles:
            dataset = lgb.Dataset(Xc, label=y, categorical_feature=cats, free_raw_data=False)
            self._boosters[q] = lgb.train(
                {**self.params, "alpha": q}, dataset, num_boost_round=self.n_estimators
            )
            log.info("%s: cuantil %.2f entrenado", self.name, q)

    def _predict_matrix(self, X: pd.DataFrame) -> np.ndarray:
        return self._predict_q(X, self.point_quantile)

    def _predict_q(self, X: pd.DataFrame, q: float) -> np.ndarray:
        booster = self._boosters.get(q)
        if booster is None:
            raise RuntimeError(f"{self.name}: no hay booster para el cuantil {q}")
        Xc = prepare_categoricals(X, self.categorical_features)
        return np.asarray(booster.predict(Xc), dtype="float64")

    def predict_quantile(self, future: pd.DataFrame, quantiles: Sequence[float]) -> pd.DataFrame:
        """Cuantiles nativos. Se ordenan por fila para que no se cruzen.

        Los boosters se entrenan de forma independiente, asi que nada garantiza
        que el de 0,9 quede por encima del de 0,5 en cada fila. El cruce se
        arregla ordenando, que es la solucion estandar y no introduce sesgo.
        """
        self._check_ready(future)
        X = self._assemble(future)
        missing = [q for q in quantiles if q not in self._boosters]
        if missing:
            raise ValueError(f"{self.name} se entreno con {self.quantiles} y se piden {missing}")
        wanted = sorted(quantiles)
        arr = np.column_stack([np.clip(self._predict_q(X, q), 0.0, None) for q in wanted])
        arr = np.sort(arr, axis=1)
        return pd.DataFrame(
            {quantile_col(q): arr[:, i] for i, q in enumerate(wanted)}, index=future.index
        )

    def reorder_quantity(
        self, future: pd.DataFrame, *, economics: cfg.EconomicsConfig
    ) -> pd.Series:
        """Cantidad a reponer: el cuantil critico del newsvendor.

        Si `q*` no esta entre los cuantiles entrenados se interpola linealmente
        entre los dos vecinos, y se avisa. Interpolar es preferible a fallar,
        pero un `q*` entrenado directamente es mejor que uno interpolado.
        """
        q_star = economics.critical_fraction
        if q_star in self._boosters:
            return self.predict_quantile(future, [q_star])[quantile_col(q_star)]
        log.warning(
            "%s: q* = %.3f no esta entre los cuantiles entrenados %s; se interpola",
            self.name,
            q_star,
            self.quantiles,
        )
        preds = self.predict_quantile(future, self.quantiles)
        arr = preds.to_numpy(dtype="float64")
        interpolated = np.array(
            [np.interp(q_star, self.quantiles, row) for row in arr], dtype="float64"
        )
        return pd.Series(interpolated, index=future.index, name="reorder_qty")


#: Hiperparametros de XGBoost. `reg:absoluteerror` para que la comparacion con
#: LightGBM sea de arquitectura y no de funcion de perdida.
DEFAULT_XGB_PARAMS: dict[str, Any] = {
    "objective": "reg:absoluteerror",
    "learning_rate": 0.05,
    "max_depth": 8,
    "min_child_weight": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "tree_method": "hist",
    "random_state": cfg.SEED,
    "n_jobs": 0,
}


class XGBoostForecaster(TabularForecaster):
    """XGBoost global. Contraste de arquitectura contra LightGBM.

    Se le pasa `enable_categorical=True` para que consuma las jerarquias como
    categoricas, igual que LightGBM: si una usara one-hot y la otra particion
    nativa, la comparacion mediria el encoding y no el modelo.
    """

    name = "xgb_global"

    def __init__(
        self,
        *,
        params: dict[str, Any] | None = None,
        n_estimators: int = 600,
        categorical_features: Sequence[str] = fb.CATEGORICAL_FEATURES,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.params = {**DEFAULT_XGB_PARAMS, **(params or {})}
        self.n_estimators = n_estimators
        self.categorical_features = tuple(categorical_features)
        self._model = None

    def _fit_matrix(self, X: pd.DataFrame, y: np.ndarray, *, features: list[str]) -> None:
        import xgboost as xgb

        Xc = prepare_categoricals(X, self.categorical_features)
        self._model = xgb.XGBRegressor(
            n_estimators=self.n_estimators, enable_categorical=True, **self.params
        )
        self._model.fit(Xc, y, verbose=False)

    def _predict_matrix(self, X: pd.DataFrame) -> np.ndarray:
        if self._model is None:
            raise RuntimeError(f"{self.name}: modelo no entrenado")
        Xc = prepare_categoricals(X, self.categorical_features)
        return np.asarray(self._model.predict(Xc), dtype="float64")

    def feature_importance(self) -> pd.Series:
        if self._model is None:
            return pd.Series(dtype="float64")
        return pd.Series(
            self._model.feature_importances_, index=self._features, name="gain"
        ).sort_values(ascending=False)


__all__ = [
    "DEFAULT_LGBM_PARAMS",
    "DEFAULT_XGB_PARAMS",
    "LightGBMForecaster",
    "LightGBMQuantileForecaster",
    "XGBoostForecaster",
]
