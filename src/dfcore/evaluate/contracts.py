"""CONTRATO 3 de 4 · forma del resultado de backtest.

Todo modelo, corrido contra el arnes, devuelve **el mismo DataFrame**. Las
metricas, el simulador de politica, el reporte de ROI y el dashboard consumen
esta forma y nada mas. Es lo que permite agregar un modelo sin tocar la
evaluacion, y comparar catorce modelos en una sola tabla.

Una fila = una prediccion = (modelo, origen, serie, fecha objetivo).

Detalle que evita un error frecuente y silencioso: `naive_scale` — el
denominador de MASE — se calcula **con el train de cada origen**, nunca con la
serie completa. Si el denominador viera el test, MASE se contaminaria de forma
invisible en el numero final. Por eso viaja en el resultado y no se recalcula
despues.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import numpy as np
import pandas as pd

from dfcore.data import schema as S

if TYPE_CHECKING:
    from collections.abc import Iterable

# --- Columnas ------------------------------------------------------------
MODEL: Final = "model"
ORIGIN: Final = "origin"
ORIGIN_DATE: Final = "origin_date"
HORIZON_STEP: Final = "h"

#: Verdad de terreno en la escala del target evaluado (latente o observada).
Y_TRUE: Final = "y_true"
#: Prediccion puntual.
Y_PRED: Final = "y_pred"
#: Venta observada (censurada) de la misma celda. Se necesita para el sesgo de
#: demanda re-censurada y para el simulador de politica.
Y_OBSERVED: Final = "y_observed"
#: Limites del intervalo. Nulos si el modelo corrio sin envoltorio conformal.
PRED_LO: Final = "pred_lo"
PRED_HI: Final = "pred_hi"
#: Denominador de MASE, del train de ese origen. Constante por (origen, serie).
NAIVE_SCALE: Final = "naive_scale"

BACKTEST_REQUIRED: Final[tuple[str, ...]] = (
    MODEL,
    ORIGIN,
    ORIGIN_DATE,
    S.SERIES_ID,
    S.DATE,
    HORIZON_STEP,
    Y_TRUE,
    Y_PRED,
    Y_OBSERVED,
    S.IS_CENSORED,
    # Fraccion del dia comercial sin quiebre. Viaja en el resultado porque es lo
    # que permite **re-censurar** la prediccion y medir el sesgo de censura. Es
    # informacion de evaluacion, del mismo tipo que `y_true`: el modelo no la ve.
    S.AVAILABLE_WEIGHT,
    NAIVE_SCALE,
)

BACKTEST_OPTIONAL: Final[tuple[str, ...]] = (PRED_LO, PRED_HI)

BACKTEST_DTYPES: Final[dict[str, str]] = {
    MODEL: "string",
    ORIGIN: "int16",
    ORIGIN_DATE: "datetime64[ns]",
    S.SERIES_ID: "string",
    S.DATE: "datetime64[ns]",
    HORIZON_STEP: "int16",
    Y_TRUE: "float64",
    Y_PRED: "float64",
    Y_OBSERVED: "float64",
    S.IS_CENSORED: "bool",
    S.AVAILABLE_WEIGHT: "float64",
    NAIVE_SCALE: "float64",
    PRED_LO: "float64",
    PRED_HI: "float64",
}


def empty_result() -> pd.DataFrame:
    """DataFrame vacio con el contrato aplicado. Util para concatenar."""
    return pd.DataFrame({c: pd.Series(dtype=BACKTEST_DTYPES[c]) for c in BACKTEST_REQUIRED})


def cast_result(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col, dtype in BACKTEST_DTYPES.items():
        if col in out.columns:
            out[col] = out[col].astype(dtype)
    return out


def validate_result(df: pd.DataFrame, *, quantiles: Iterable[float] = ()) -> pd.DataFrame:
    """Verifica el contrato del resultado de backtest.

    Chequea, en orden de gravedad:

    1. Columnas obligatorias presentes.
    2. Sin duplicados por (modelo, origen, serie, fecha).
    3. Ninguna fecha objetivo cae en o antes de su propio origen — si eso pasa,
       el modelo esta prediciendo algo que ya vio.
    4. El paso de horizonte concuerda con la distancia real a su origen.
    5. `naive_scale` positivo y constante dentro de (origen, serie).
    6. Sin nulos en verdad ni prediccion.
    7. Los cuantiles pedidos existen y son monotonos crecientes.
    """
    from dfcore.models.base import quantile_col

    missing = [c for c in BACKTEST_REQUIRED if c not in df.columns]
    if missing:
        raise S.SchemaError(f"el resultado de backtest no trae {missing}")
    if df.empty:
        raise S.SchemaError("el resultado de backtest esta vacio")

    keys = [MODEL, ORIGIN, S.SERIES_ID, S.DATE]
    dup = int(df.duplicated(subset=keys).sum())
    if dup:
        raise S.SchemaError(f"{dup} predicciones duplicadas por {keys}")

    in_train = int((df[S.DATE] <= df[ORIGIN_DATE]).sum())
    if in_train:
        raise S.SchemaError(
            f"{in_train} predicciones con fecha <= origen: el modelo esta "
            "prediciendo dentro de su propio train"
        )

    expected_h = (df[S.DATE] - df[ORIGIN_DATE]).dt.days
    mismatch = int((expected_h != df[HORIZON_STEP]).sum())
    if mismatch:
        raise S.SchemaError(
            f"{mismatch} filas donde {HORIZON_STEP} no coincide con la distancia "
            f"real a {ORIGIN_DATE}"
        )

    if (df[NAIVE_SCALE] <= 0).any() or df[NAIVE_SCALE].isna().any():
        raise S.SchemaError(f"{NAIVE_SCALE} debe ser positivo y sin nulos")
    varying = df.groupby([ORIGIN, S.SERIES_ID], observed=True)[NAIVE_SCALE].nunique()
    if (varying > 1).any():
        raise S.SchemaError(
            f"{NAIVE_SCALE} varia dentro de (origen, serie): se calculo con datos "
            "de test en vez del train del fold"
        )

    for col in (Y_TRUE, Y_PRED):
        if df[col].isna().any():
            raise S.SchemaError(f"{col} tiene nulos")

    qcols = [quantile_col(q) for q in sorted(quantiles)]
    absent = [c for c in qcols if c not in df.columns]
    if absent:
        raise S.SchemaError(f"faltan columnas de cuantil {absent}")
    if len(qcols) > 1:
        arr = df[qcols].to_numpy(dtype="float64")
        crossed = int((np.diff(arr, axis=1) < -1e-9).sum())
        if crossed:
            raise S.SchemaError(
                f"{crossed} cruces de cuantiles: q_alto < q_bajo. Ordenar los "
                "cuantiles predichos antes de devolverlos"
            )

    if PRED_LO in df.columns and PRED_HI in df.columns:
        inverted = int((df[PRED_HI] < df[PRED_LO] - 1e-9).sum())
        if inverted:
            raise S.SchemaError(f"{inverted} intervalos invertidos ({PRED_HI} < {PRED_LO})")

    return cast_result(df).sort_values([MODEL, ORIGIN, S.SERIES_ID, S.DATE]).reset_index(drop=True)


def n_origins(df: pd.DataFrame) -> int:
    return int(df[ORIGIN].nunique())


def coverage_of_origins(df: pd.DataFrame, *, required: int) -> None:
    """Falla si el backtest no alcanzo el minimo de origenes de la metodologia."""
    got = n_origins(df)
    if got < required:
        raise S.SchemaError(
            f"el backtest corrio con {got} origenes y la metodologia exige {required}"
        )
