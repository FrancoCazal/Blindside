"""Base para modelos tabulares globales (un modelo para todas las series).

Un modelo global aprende de las 3000 series a la vez en vez de ajustar una por
serie. Con series de 97 dias eso no es una comodidad, es la unica opcion viable:
90 puntos no alcanzan para estimar nada por separado, y la estructura compartida
entre productos de la misma categoria es justamente lo que hay para explotar.

La condicion para que un modelo global gane esta documentada — funciona cuando
hay jerarquia con estructura cruzada fuerte, y FreshRetailNet la tiene
(https://theses.liacs.nl/pdf/2025-2026-MciszKPKamil.pdf). Vale decirlo asi en la
defensa, con la condicion incluida, en vez de afirmar que los modelos globales
siempre ganan.

Como encaja con el contrato de `Forecaster`
-------------------------------------------
El contrato entrega ``history`` al entrenar y un ``future`` sin target al
predecir. Un modelo tabular necesita features, asi que:

* En ``_fit`` construye el estado de origen sobre ``history``, arma la matriz
  supervisada con muchos origenes internos y entrena. Ademas **guarda la fila de
  features del ultimo dia de train** por serie.
* En ``_predict`` toma ese estado guardado, lo cruza con ``future`` y agrega el
  calendario del dia objetivo y las covariables conocidas de antemano.

O sea que en inferencia no vuelve a mirar la historia: usa el estado congelado en
el origen. Eso hace imposible que una feature de prediccion contenga algo
posterior al origen, que es la propiedad que los tests antifugas verifican.

Estrategia **directa**: `h` es una feature y un solo modelo cubre todo el
horizonte. La alternativa recursiva realimenta sus propias predicciones y acumula
error; con horizonte 7 la directa es mejor y mucho mas simple de auditar.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from dfcore import config as cfg
from dfcore.data import schema as S
from dfcore.features import build as fb
from dfcore.features import calendar as cal
from dfcore.models.base import Forecaster

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

#: Dias de calentamiento antes del primer origen de entrenamiento: hace falta
#: que los lags mas largos existan, si no las primeras filas son todo nulos.
WARMUP_DAYS = max(fb.lg.DEFAULT_LAGS) + 1


class TabularForecaster(Forecaster):
    """Modelo global sobre la matriz supervisada anclada en el origen.

    Parametros de muestreo de entrenamiento:
        max_train_origins: tope de origenes internos. Con 3000 series, 60
            origenes y horizonte 7 la matriz llega a 1,4 M de filas y el
            backtest de 8 folds no entra en memoria. Un tope de 20 origenes
            recientes conserva la senal util y hace el arnes corrible en una
            maquina de trabajo. Es una decision de alcance declarada.
        origin_stride: separacion entre origenes internos.
    """

    supports_quantiles = False

    def __init__(
        self,
        *,
        horizon: int = cfg.FORECAST.horizon,
        max_train_origins: int = 20,
        origin_stride: int = 2,
        season_length: int = cfg.FORECAST.season_length,
    ) -> None:
        super().__init__()
        self.horizon = horizon
        self.max_train_origins = max_train_origins
        self.origin_stride = origin_stride
        self.season_length = season_length
        self._features: list[str] = []
        self._origin_state: pd.DataFrame | None = None

    # -- Ganchos de la subclase -------------------------------------------
    @abstractmethod
    def _fit_matrix(self, X: pd.DataFrame, y: np.ndarray, *, features: list[str]) -> None:
        """Entrena sobre la matriz ya armada."""

    @abstractmethod
    def _predict_matrix(self, X: pd.DataFrame) -> np.ndarray:
        """Predice sobre la matriz ya armada."""

    # -- Contrato de Forecaster -------------------------------------------
    def _fit(self, history: pd.DataFrame, *, target: str) -> None:
        state = fb.add_origin_features(history, target=target, season_length=self.season_length)
        origins = self._training_origins(state)
        supervised = fb.build_supervised(
            state, origins, horizon=self.horizon, target=target, include_target=True
        )
        if supervised.empty:
            raise ValueError(f"{self.name}: la matriz de entrenamiento quedo vacia")

        self._features = fb.feature_columns(supervised)
        X = supervised[self._features]
        y = supervised[fb.Y].to_numpy(dtype="float64")
        log.info(
            "%s: entrenando con %d filas x %d features (%d origenes internos)",
            self.name,
            len(X),
            len(self._features),
            len(origins),
        )
        self._fit_matrix(X, y, features=self._features)

        # Estado congelado del ultimo dia de train, uno por serie. Es lo unico
        # que se lleva a la inferencia.
        last = state[state[S.DATE] == self.last_train_date].copy()
        self._origin_state = last.rename(columns={S.DATE: fb.ORIGIN_DATE}).drop(
            columns=[
                c
                for c in (*S.KNOWN_FUTURE_COLS, *S.WEATHER_COLS, S.SALE_AMOUNT, target, S.INFLATION)
                if c in last.columns
            ]
        )

    def _predict(self, future: pd.DataFrame) -> np.ndarray:
        if self._origin_state is None:
            raise RuntimeError(f"{self.name}: no hay estado de origen")
        X = self._assemble(future)
        return self._predict_matrix(X)

    # -- Internos ---------------------------------------------------------
    def _training_origins(self, state: pd.DataFrame) -> pd.DatetimeIndex:
        """Origenes internos de entrenamiento, los mas recientes del train."""
        dates = pd.DatetimeIndex(sorted(state[S.DATE].unique()))
        if len(dates) <= WARMUP_DAYS + 1:
            raise ValueError(
                f"{self.name}: hacen falta mas de {WARMUP_DAYS + 1} dias de historia "
                f"para que los lags existan, llegaron {len(dates)}"
            )
        # El ultimo origen util deja al menos un dia de objetivo dentro del train.
        usable = dates[WARMUP_DAYS:-1]
        strided = usable[:: self.origin_stride]
        return strided[-self.max_train_origins :]

    def _assemble(self, future: pd.DataFrame) -> pd.DataFrame:
        """Cruza el estado congelado del origen con el indice de futuro."""
        assert self._origin_state is not None
        keep = [c for c in future.columns if c in (S.SERIES_ID, S.DATE, "h", *S.KNOWN_FUTURE_COLS)]
        grid = future[keep].copy()
        merged = grid.merge(self._origin_state, on=S.SERIES_ID, how="left")
        merged = cal.add_calendar_features(merged)

        missing = [c for c in self._features if c not in merged.columns]
        for col in missing:
            merged[col] = np.nan
        if missing:
            log.debug(
                "%s: %d features ausentes en inferencia, se rellenan", self.name, len(missing)
            )
        return merged[self._features]

    def feature_importance(self) -> pd.Series:
        """Importancia de features. La subclase la sobreescribe si la tiene."""
        return pd.Series(dtype="float64")


class SklearnTabularForecaster(TabularForecaster):
    """Envuelve un `Pipeline` de scikit-learn.

    El `Pipeline` completo — imputacion, escalado, encoding, estimador — se
    ajusta **dentro** de este `_fit`, que a su vez solo ve el train del fold. Eso
    es lo que exige el checklist antifugas del item 5, y es la razon por la que
    el preprocesamiento vive en un `Pipeline` y no en pasos suelto antes del
    `train_test_split` (que es el error clasico de M2).
    """

    def __init__(self, *, pipeline_factory, **kwargs) -> None:
        super().__init__(**kwargs)
        self._factory = pipeline_factory
        self._pipeline = None

    def _fit_matrix(self, X: pd.DataFrame, y: np.ndarray, *, features: list[str]) -> None:
        self._pipeline = self._factory()
        self._pipeline.fit(X, y)

    def _predict_matrix(self, X: pd.DataFrame) -> np.ndarray:
        if self._pipeline is None:
            raise RuntimeError(f"{self.name}: pipeline no ajustado")
        return np.asarray(self._pipeline.predict(X), dtype="float64")

    @property
    def pipeline(self):
        """Acceso al pipeline ajustado, para los tests antifugas del item 5."""
        return self._pipeline


def prepare_categoricals(X: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """Pasa las columnas de jerarquia a `category` para LightGBM.

    LightGBM las trata como categoricas nativas, sin one-hot. Con 865 productos
    el one-hot generaria 865 columnas casi vacias; la particion categorica nativa
    encuentra los mismos cortes sin inflar la matriz.
    """
    out = X.copy()
    for col in columns:
        if col in out.columns:
            out[col] = out[col].astype("category")
    return out


__all__ = [
    "WARMUP_DAYS",
    "SklearnTabularForecaster",
    "TabularForecaster",
    "prepare_categoricals",
]
