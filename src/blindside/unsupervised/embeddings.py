"""Proyeccion 2D del catalogo de productos.

Existe para que el mapa de la interfaz muestre una proyeccion **medida** en vez de
un scatter sintetico. El diseno la contemplaba simulada porque no habia endpoint;
con seis features por producto y PCA alcanza para tenerla de verdad, y la varianza
explicada viaja en la respuesta para que la pantalla pueda declarar cuanto del
fenomeno cabe en dos dimensiones.

PCA y no UMAP a proposito: `umap-learn` arrastra `numba` y queda afuera de la
imagen de servicio, y sobre todo PCA es **lineal y reproducible**. Un UMAP con
otra semilla dibuja otro mapa, y un grafico que cambia de forma entre corridas no
sirve como evidencia de nada. Si mas adelante se quiere una proyeccion no lineal,
va en el pipeline y se persiste, no se calcula por request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from blindside.data import schema as S

if TYPE_CHECKING:
    from collections.abc import Sequence

#: Features por producto. Son las que separan el catalogo en terminos de
#: comportamiento de demanda, no de categoria administrativa.
FEATURES: tuple[str, ...] = (
    "demanda_media",
    "coef_variacion",
    "tasa_quiebre",
    "tasa_ceros",
    "amplitud_semanal",
    "horas_quiebre",
)


def product_features(panel: pd.DataFrame, *, target: str = S.DEMAND_LATENT) -> pd.DataFrame:
    """Una fila por producto, agregando sus series de todas las tiendas."""
    df = panel.copy()
    df["dow"] = pd.to_datetime(df[S.DATE]).dt.dayofweek

    por_producto = df.groupby(S.PRODUCT_ID, observed=True)
    media = por_producto[target].mean()
    desvio = por_producto[target].std(ddof=1)

    # Amplitud semanal: dispersion de las medias por dia de semana, normalizada
    # por el nivel. Es la senal que el modelo usa y la que distingue un producto
    # de fin de semana de uno de consumo parejo.
    por_dow = df.groupby([S.PRODUCT_ID, "dow"], observed=True)[target].mean()
    amplitud = por_dow.groupby(S.PRODUCT_ID).std(ddof=1) / media.replace(0, np.nan)

    out = pd.DataFrame(
        {
            "demanda_media": media,
            "coef_variacion": (desvio / media.replace(0, np.nan)),
            "tasa_quiebre": por_producto[S.IS_CENSORED].mean(),
            "tasa_ceros": por_producto[S.SALE_AMOUNT].apply(lambda s: float((s <= 0).mean())),
            "amplitud_semanal": amplitud,
            "horas_quiebre": por_producto[S.OOS_HOURS_OPEN].mean(),
            "n_series": por_producto[S.SERIES_ID].nunique(),
        }
    )
    return out.fillna(0.0)


def rotation_band(
    demanda_media: pd.Series, *, quantiles: tuple[float, float] = (0.5, 0.85)
) -> pd.Series:
    """Banda de rotacion por producto, con los mismos cortes que el backtest.

    La cola de baja rotacion es **un tercio del catalogo, no la mayoria**. El plan
    del proyecto asume lo contrario, y esta pantalla es la que lo hace visible.
    """
    lo, hi = demanda_media.quantile(list(quantiles))
    bands = pd.Series("media", index=demanda_media.index, dtype="object")
    bands[demanda_media <= lo] = "baja"
    bands[demanda_media > hi] = "alta"
    return bands.rename("rotation_band")


def project_products(
    panel: pd.DataFrame,
    *,
    target: str = S.DEMAND_LATENT,
    features: Sequence[str] = FEATURES,
) -> tuple[pd.DataFrame, list[float]]:
    """Proyeccion 2D del catalogo. Devuelve los puntos y la varianza explicada.

    Las features se estandarizan antes de proyectar porque estan en unidades
    incomparables — una demanda media contra una tasa entre 0 y 1 — y sin eso la
    primera componente seria simplemente la variable de mayor escala.
    """
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    tabla = product_features(panel, target=target)
    X = tabla[list(features)].to_numpy(dtype="float64")
    Xs = StandardScaler().fit_transform(X)

    pca = PCA(n_components=2, random_state=0)
    coords = pca.fit_transform(Xs)

    puntos = pd.DataFrame(
        {
            S.PRODUCT_ID: tabla.index.astype("int64"),
            "x": coords[:, 0],
            "y": coords[:, 1],
            "rotation_band": rotation_band(tabla["demanda_media"]).to_numpy(),
            "demanda_media": tabla["demanda_media"].to_numpy(),
            "tasa_quiebre": tabla["tasa_quiebre"].to_numpy(),
            "n_series": tabla["n_series"].to_numpy(),
        }
    ).reset_index(drop=True)

    return puntos, [float(v) for v in pca.explained_variance_ratio_]


__all__ = ["FEATURES", "product_features", "project_products", "rotation_band"]
