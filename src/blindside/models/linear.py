"""Regresion regularizada dentro de un `Pipeline` de sklearn.

Cubre M2 de forma explicita: imputacion, escalado y encoding viven **dentro** del
`Pipeline`, asi que se ajustan solo con el train de cada fold. Ese es el punto,
no un detalle de implementacion. El error clasico del modulo es escalar todo el
dataset y despues partirlo: la media del escalador ya contiene informacion del
test, y no se nota en ninguna metrica.

`assert_pipeline_fitted_on_train` en `validation.leakage` comprueba que la media
aprendida por el escalador se parezca a la del train del fold y no a la del panel
completo. Es lo que vuelve la afirmacion verificable.

Estos modelos tambien son el puente entre M2 y M3: mismas features que LightGBM,
misma matriz, misma validacion, y una familia de modelos completamente distinta.
Si el lineal queda cerca del boosting, la conclusion es que la senal esta en las
features de calendario y rezago, no en la no linealidad. Eso es informacion util,
no un resultado pobre.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from blindside import config as cfg
from blindside.features import build as fb
from blindside.models.tabular import SklearnTabularForecaster

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sklearn.pipeline import Pipeline


def _build_pipeline(estimator, *, categorical: Sequence[str]) -> Pipeline:
    """Pipeline comun: imputacion, escalado y one-hot de la jerarquia.

    El imputador va primero porque los lags mas largos son nulos al comienzo de
    cada serie por construccion, no por un dato faltante. Se imputa con la
    mediana y se agrega la bandera `add_indicator`, para que el modelo pueda
    distinguir "no habia historia" de "la historia valia la mediana".
    """
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline as SkPipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    numeric = SkPipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    # La jerarquia entra one-hot con `min_frequency` para no generar una columna
    # por cada uno de los 865 productos: los raros se agrupan en "infrequent".
    categoric = SkPipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            (
                "encode",
                OneHotEncoder(
                    handle_unknown="infrequent_if_exist",
                    min_frequency=0.01,
                    sparse_output=True,
                ),
            ),
        ]
    )
    pre = ColumnTransformer(
        [
            ("cat", categoric, list(categorical)),
            ("num", numeric, _remaining),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    return SkPipeline([("pre", pre), ("model", estimator)])


def _remaining(X) -> list[str]:
    """Selector de columnas numericas que no son de jerarquia."""
    cats = set(fb.CATEGORICAL_FEATURES)
    return [c for c in X.columns if c not in cats]


class RidgeForecaster(SklearnTabularForecaster):
    """Ridge. El puente entre M2 y M3, y un piso lineal honesto."""

    name = "ridge"

    def __init__(self, *, alpha: float = 1.0, **kwargs) -> None:
        from sklearn.linear_model import Ridge

        super().__init__(
            pipeline_factory=lambda: _build_pipeline(
                Ridge(alpha=alpha, random_state=cfg.SEED),
                categorical=fb.CATEGORICAL_FEATURES,
            ),
            **kwargs,
        )
        self.alpha = alpha


class LassoForecaster(SklearnTabularForecaster):
    """Lasso. Sirve de seleccion de features: los coeficientes en cero dicen
    cuales de las setenta features no aportan nada."""

    name = "lasso"

    def __init__(self, *, alpha: float = 0.01, **kwargs) -> None:
        from sklearn.linear_model import Lasso

        super().__init__(
            pipeline_factory=lambda: _build_pipeline(
                Lasso(alpha=alpha, random_state=cfg.SEED, max_iter=5000),
                categorical=fb.CATEGORICAL_FEATURES,
            ),
            **kwargs,
        )
        self.alpha = alpha


class ElasticNetForecaster(SklearnTabularForecaster):
    """ElasticNet. Punto medio entre Ridge y Lasso; con features de lag muy
    correlacionadas entre si suele ser la mejor de las tres."""

    name = "elasticnet"

    def __init__(self, *, alpha: float = 0.01, l1_ratio: float = 0.5, **kwargs) -> None:
        from sklearn.linear_model import ElasticNet

        super().__init__(
            pipeline_factory=lambda: _build_pipeline(
                ElasticNet(alpha=alpha, l1_ratio=l1_ratio, random_state=cfg.SEED, max_iter=5000),
                categorical=fb.CATEGORICAL_FEATURES,
            ),
            **kwargs,
        )
        self.alpha = alpha
        self.l1_ratio = l1_ratio


class QuantileRegressionForecaster(SklearnTabularForecaster):
    """Regresion cuantilica lineal.

    Contraste del LightGBM cuantilico: responde si la capa de decision necesita
    no linealidad o si un lineal cuantilico ya alcanza. Es lento con muchas
    filas, asi que se usa con un subconjunto de origenes.
    """

    name = "quantile_linear"

    def __init__(self, *, quantile: float = 0.9, alpha: float = 0.001, **kwargs) -> None:
        from sklearn.linear_model import QuantileRegressor

        super().__init__(
            pipeline_factory=lambda: _build_pipeline(
                QuantileRegressor(quantile=quantile, alpha=alpha, solver="highs"),
                categorical=fb.CATEGORICAL_FEATURES,
            ),
            **kwargs,
        )
        self.quantile = quantile


def make_linear_models(**kwargs) -> list[SklearnTabularForecaster]:
    """Las tres regularizadas de M3, con la misma configuracion de muestreo."""
    return [
        RidgeForecaster(**kwargs),
        LassoForecaster(**kwargs),
        ElasticNetForecaster(**kwargs),
    ]


__all__ = [
    "ElasticNetForecaster",
    "LassoForecaster",
    "QuantileRegressionForecaster",
    "RidgeForecaster",
    "make_linear_models",
]
