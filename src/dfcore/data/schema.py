"""CONTRATO 1 de 4 · esquema de datos.

Este modulo es la fuente de verdad de como se llaman las columnas, que tipo
tienen y cual es la granularidad. Todo lo demas (features, modelos, backtest,
API, dashboard) consume estos nombres y no strings literales.

Granularidad canonica: **una fila por (serie, dia)**. La serie es el par
tienda-producto. Las secuencias horarias del dataset original sobreviven solo
hasta la recuperacion de censura (seccion 8.0 del plan) y despues se descartan,
porque cargarlas en cada paso posterior no aporta y multiplica la memoria por 24.

Referencia del esquema original:
https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Iterable

# --- Claves --------------------------------------------------------------
#: Identificador sintetico de serie, "<store_id>_<product_id>". Existe porque
#: casi todas las operaciones agrupan por serie y una sola clave es mas rapida
#: y menos propensa a error que una tupla.
SERIES_ID: Final = "series_id"
DATE: Final = "dt"

STORE_ID: Final = "store_id"
PRODUCT_ID: Final = "product_id"

#: Clave natural de la serie. `SERIES_ID` se deriva de estas dos columnas.
SERIES_KEYS: Final[tuple[str, ...]] = (STORE_ID, PRODUCT_ID)

# --- Jerarquias (seccion 8.3: reconciliacion MinT) -----------------------
CITY_ID: Final = "city_id"
MANAGEMENT_GROUP_ID: Final = "management_group_id"
FIRST_CATEGORY_ID: Final = "first_category_id"
SECOND_CATEGORY_ID: Final = "second_category_id"
THIRD_CATEGORY_ID: Final = "third_category_id"

#: Jerarquia geografica, de mas agregado a mas desagregado.
HIERARCHY_GEO: Final[tuple[str, ...]] = (CITY_ID, STORE_ID)

#: Jerarquia de catalogo, de mas agregado a mas desagregado.
HIERARCHY_CATALOG: Final[tuple[str, ...]] = (
    MANAGEMENT_GROUP_ID,
    FIRST_CATEGORY_ID,
    SECOND_CATEGORY_ID,
    THIRD_CATEGORY_ID,
    PRODUCT_ID,
)

#: Todas las columnas de jerarquia sin repetir.
HIERARCHY_COLS: Final[tuple[str, ...]] = (
    CITY_ID,
    STORE_ID,
    MANAGEMENT_GROUP_ID,
    FIRST_CATEGORY_ID,
    SECOND_CATEGORY_ID,
    THIRD_CATEGORY_ID,
    PRODUCT_ID,
)

# --- Target y censura ----------------------------------------------------
#: Demanda **observada** (censurada por los quiebres). Es lo que el ERP ve.
SALE_AMOUNT: Final = "sale_amount"

#: Demanda **latente** recuperada. La produce dfcore.decision.censoring y es
#: el target real de entrenamiento. No existe en el dataset original.
DEMAND_LATENT: Final = "demand_latent"

#: Horas de quiebre dentro de la ventana comercial 6:00-22:00 (del dataset).
OOS_HOURS_OPEN: Final = "stock_hour6_22_cnt"

#: Horas de quiebre en el dia completo, derivadas de `hours_stock_status`.
OOS_HOURS_DAY: Final = "oos_hours_day"

#: Peso de la masa de demanda intradiaria efectivamente observable ese dia.
#: 1.0 = ninguna hora perdida; 0.0 = el dia entero en quiebre.
AVAILABLE_WEIGHT: Final = "available_weight"

#: Bandera de dia censurado. Es la que permite *medir* la correccion en vez de
#: solo afirmarla, y la que define el subconjunto limpio de evaluacion.
IS_CENSORED: Final = "is_censored"

#: Factor aplicado por el recuperador: demand_latent / sale_amount.
INFLATION: Final = "inflation_factor"

# --- Secuencias horarias (solo capa interim) -----------------------------
HOURS_SALE: Final = "hours_sale"
HOURS_STOCK_STATUS: Final = "hours_stock_status"
HOURLY_COLS: Final[tuple[str, ...]] = (HOURS_SALE, HOURS_STOCK_STATUS)

# --- Covariables conocidas de antemano ----------------------------------
#: Se conocen para el futuro (calendario y plan comercial), asi que se pueden
#: usar como regresores del horizonte sin cometer fuga.
DISCOUNT: Final = "discount"
HOLIDAY_FLAG: Final = "holiday_flag"
ACTIVITY_FLAG: Final = "activity_flag"

KNOWN_FUTURE_COLS: Final[tuple[str, ...]] = (DISCOUNT, HOLIDAY_FLAG, ACTIVITY_FLAG)

# --- Covariables de clima -----------------------------------------------
#: OJO: el clima **no** se conoce con certeza a futuro. Se trata como
#: observado hasta t y se propaga por persistencia en el horizonte, o se
#: excluye. Usarlo con su valor real futuro es fuga de informacion.
PRECIPITATION: Final = "precpt"
AVG_TEMPERATURE: Final = "avg_temperature"
AVG_HUMIDITY: Final = "avg_humidity"
AVG_WIND_LEVEL: Final = "avg_wind_level"

WEATHER_COLS: Final[tuple[str, ...]] = (
    PRECIPITATION,
    AVG_TEMPERATURE,
    AVG_HUMIDITY,
    AVG_WIND_LEVEL,
)

# --- Columnas del dataset original --------------------------------------
#: Exactamente los 19 campos del parquet de HuggingFace, en su orden.
RAW_COLUMNS: Final[tuple[str, ...]] = (
    CITY_ID,
    STORE_ID,
    MANAGEMENT_GROUP_ID,
    FIRST_CATEGORY_ID,
    SECOND_CATEGORY_ID,
    THIRD_CATEGORY_ID,
    PRODUCT_ID,
    DATE,
    SALE_AMOUNT,
    HOURS_SALE,
    OOS_HOURS_OPEN,
    HOURS_STOCK_STATUS,
    DISCOUNT,
    HOLIDAY_FLAG,
    ACTIVITY_FLAG,
    PRECIPITATION,
    AVG_TEMPERATURE,
    AVG_HUMIDITY,
    AVG_WIND_LEVEL,
)

# --- Tipos ---------------------------------------------------------------
#: Tipos del panel diario canonico. `is_censored` es bool y no int para que un
#: filtro accidental por verdad/falsedad no pase silencioso.
PANEL_DTYPES: Final[dict[str, str]] = {
    SERIES_ID: "string",
    DATE: "datetime64[ns]",
    CITY_ID: "int32",
    STORE_ID: "int32",
    MANAGEMENT_GROUP_ID: "int32",
    FIRST_CATEGORY_ID: "int32",
    SECOND_CATEGORY_ID: "int32",
    THIRD_CATEGORY_ID: "int32",
    PRODUCT_ID: "int32",
    SALE_AMOUNT: "float32",
    OOS_HOURS_OPEN: "int16",
    OOS_HOURS_DAY: "int16",
    AVAILABLE_WEIGHT: "float32",
    IS_CENSORED: "bool",
    DISCOUNT: "float32",
    HOLIDAY_FLAG: "int8",
    ACTIVITY_FLAG: "int8",
    PRECIPITATION: "float32",
    AVG_TEMPERATURE: "float32",
    AVG_HUMIDITY: "float32",
    AVG_WIND_LEVEL: "float32",
}

#: Columnas obligatorias del panel diario que sale de la capa de datos.
PANEL_REQUIRED: Final[tuple[str, ...]] = tuple(PANEL_DTYPES)

#: Columnas obligatorias del panel ya corregido por censura.
DEMAND_REQUIRED: Final[tuple[str, ...]] = (*PANEL_REQUIRED, DEMAND_LATENT, INFLATION)


class SchemaError(ValueError):
    """El DataFrame no cumple el contrato. Es un error, no una advertencia."""


def make_series_id(df: pd.DataFrame) -> pd.Series:
    """Deriva `series_id` a partir de la clave natural tienda-producto."""
    missing = [c for c in SERIES_KEYS if c not in df.columns]
    if missing:
        raise SchemaError(f"faltan columnas para derivar {SERIES_ID}: {missing}")
    return (
        df[STORE_ID].astype("int64").astype(str) + "_" + df[PRODUCT_ID].astype("int64").astype(str)
    ).astype("string")


def cast_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica `PANEL_DTYPES` a las columnas presentes, sin inventar columnas."""
    out = df.copy()
    for col, dtype in PANEL_DTYPES.items():
        if col in out.columns:
            out[col] = out[col].astype(dtype)
    return out


def validate_panel(
    df: pd.DataFrame,
    *,
    required: Iterable[str] = PANEL_REQUIRED,
    allow_gaps: bool = False,
) -> pd.DataFrame:
    """Verifica el contrato y devuelve el DataFrame ordenado canonicamente.

    Comprueba, en orden de gravedad:

    1. Que esten todas las columnas obligatorias.
    2. Que no haya filas duplicadas por (serie, fecha) — una serie con dos
       filas para el mismo dia rompe cualquier lag.
    3. Que el target observado no tenga nulos ni negativos.
    4. Que las banderas de censura sean consistentes entre si.
    5. Opcionalmente, que el calendario de cada serie sea continuo, porque un
       hueco silencioso vuelve un lag de 7 dias un lag de otra cosa.

    Devuelve el DataFrame ordenado por (serie, fecha) con el indice reseteado.
    Todo lo que consume el panel asume ese orden.
    """
    required = tuple(required)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SchemaError(f"columnas obligatorias ausentes: {missing}")

    if df.empty:
        raise SchemaError("el panel esta vacio")

    dup = df.duplicated(subset=[SERIES_ID, DATE]).sum()
    if dup:
        raise SchemaError(f"{dup} filas duplicadas por ({SERIES_ID}, {DATE})")

    if not pd.api.types.is_datetime64_any_dtype(df[DATE]):
        raise SchemaError(f"{DATE} debe ser datetime64, es {df[DATE].dtype}")

    if df[SALE_AMOUNT].isna().any():
        raise SchemaError(f"{SALE_AMOUNT} tiene nulos")
    if (df[SALE_AMOUNT] < 0).any():
        raise SchemaError(f"{SALE_AMOUNT} tiene valores negativos")

    if IS_CENSORED in df.columns and OOS_HOURS_OPEN in df.columns:
        inconsistent = int((df[IS_CENSORED] != (df[OOS_HOURS_OPEN] > 0)).sum())
        if inconsistent:
            raise SchemaError(
                f"{inconsistent} filas donde {IS_CENSORED} no coincide con "
                f"{OOS_HOURS_OPEN} > 0"
            )

    if AVAILABLE_WEIGHT in df.columns:
        w = df[AVAILABLE_WEIGHT]
        if w.isna().any() or ((w < 0) | (w > 1 + 1e-6)).any():
            raise SchemaError(f"{AVAILABLE_WEIGHT} debe estar en [0, 1] y sin nulos")

    if DEMAND_LATENT in df.columns:
        latent = df[DEMAND_LATENT]
        if latent.isna().any():
            raise SchemaError(f"{DEMAND_LATENT} tiene nulos")
        # La demanda latente nunca puede ser menor que la venta observada:
        # la venta ocurrio, es una cota inferior de la demanda.
        below = int((latent < df[SALE_AMOUNT] - 1e-6).sum())
        if below:
            raise SchemaError(
                f"{below} filas con {DEMAND_LATENT} < {SALE_AMOUNT}; la venta "
                "observada es cota inferior de la demanda"
            )

    out = df.sort_values([SERIES_ID, DATE], kind="mergesort").reset_index(drop=True)

    if not allow_gaps:
        gaps = _series_with_gaps(out)
        if gaps:
            raise SchemaError(
                f"{len(gaps)} series con huecos de calendario, p.ej. {gaps[:3]}. "
                "Reindexar antes de construir lags o pasar allow_gaps=True."
            )
    return out


def _series_with_gaps(df: pd.DataFrame) -> list[str]:
    """Series cuyo calendario diario no es contiguo."""
    g = df.groupby(SERIES_ID, observed=True)[DATE]
    span = (g.max() - g.min()).dt.days + 1
    counts = g.size()
    bad = span != counts
    return bad[bad].index.astype(str).tolist()


def reindex_daily(df: pd.DataFrame, *, fill_value: float = 0.0) -> pd.DataFrame:
    """Rellena huecos de calendario por serie con dias completos.

    Un dia ausente en el panel no significa "demanda desconocida": en retail
    significa que no hubo venta. Se rellena con `fill_value` en el target y con
    el ultimo valor conocido en las covariables de contexto, que es lo que hace
    un dia faltante realista y no un agujero que rompa los lags.
    """
    frames = []
    static = [c for c in HIERARCHY_COLS if c in df.columns]
    for sid, grp in df.groupby(SERIES_ID, observed=True, sort=True):
        full = pd.date_range(grp[DATE].min(), grp[DATE].max(), freq="D")
        g = grp.set_index(DATE).reindex(full)
        g.index.name = DATE
        g[SERIES_ID] = sid
        for col in static:
            g[col] = grp[col].iloc[0]
        for col in (SALE_AMOUNT, DEMAND_LATENT):
            if col in g.columns:
                g[col] = g[col].fillna(fill_value)
        for col in (OOS_HOURS_OPEN, OOS_HOURS_DAY):
            if col in g.columns:
                g[col] = g[col].fillna(0)
        if AVAILABLE_WEIGHT in g.columns:
            g[AVAILABLE_WEIGHT] = g[AVAILABLE_WEIGHT].fillna(1.0)
        if IS_CENSORED in g.columns:
            g[IS_CENSORED] = g[IS_CENSORED].fillna(False).astype(bool)
        ctx = [c for c in (*KNOWN_FUTURE_COLS, *WEATHER_COLS) if c in g.columns]
        if ctx:
            g[ctx] = g[ctx].ffill().bfill()
        frames.append(g.reset_index())
    out = pd.concat(frames, ignore_index=True)
    return cast_panel(out)


def series_index(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla de atributos estaticos por serie, una fila por `series_id`.

    Es lo que consumen la reconciliacion jerarquica, el clustering y el
    dashboard, para no arrastrar las columnas de jerarquia en cada operacion.
    """
    cols = [c for c in HIERARCHY_COLS if c in df.columns]
    return (
        df.groupby(SERIES_ID, observed=True)[cols]
        .first()
        .reset_index()
        .pipe(lambda d: d.astype({c: "int32" for c in cols}))
    )


def describe_censoring(df: pd.DataFrame) -> dict[str, float]:
    """Resumen de censura del panel. Va al EDA y al README."""
    n = len(df)
    censored = df[IS_CENSORED] if IS_CENSORED in df.columns else df[OOS_HOURS_OPEN] > 0
    zero_sales = df[SALE_AMOUNT] <= 0
    return {
        "n_rows": float(n),
        "n_series": float(df[SERIES_ID].nunique()),
        "n_days": float(df[DATE].nunique()),
        "share_censored_days": float(censored.mean()),
        "share_zero_sale_days": float(zero_sales.mean()),
        "share_censored_and_zero": float((censored & zero_sales).mean()),
        "mean_oos_hours_when_censored": float(
            df.loc[censored, OOS_HOURS_OPEN].mean() if censored.any() else np.nan
        ),
    }
