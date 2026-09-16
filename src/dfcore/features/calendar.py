"""Features de calendario.

Todas se derivan de la fecha objetivo y de nada mas, asi que son las unicas
features que se conocen con certeza para todo el horizonte. Eso las vuelve
seguras por construccion: no hay forma de cometer fuga con el dia de la semana.

La estacionalidad semanal se codifica **ciclicamente** (seno y coseno) ademas de
como entero. El entero le sirve al arbol, que parte donde quiere; las
componentes ciclicas le sirven al modelo lineal y a la red, que sin ellas
tratarian el domingo (6) y el lunes (0) como extremos opuestos cuando en
realidad son vecinos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dfcore.data import schema as S

#: Epoca fija para la tendencia lineal. **No** se usa el minimo del frame.
#:
#: Anclar en `df[date].min()` parece inofensivo y es un bug silencioso: el frame
#: de entrenamiento abarca decenas de dias y el de inferencia solo el horizonte,
#: asi que la misma fecha recibe un valor distinto segun quien la calcule. La
#: feature termina significando dos cosas diferentes a cada lado del `fit`.
#:
#: Un arbol lo tolera — el valor cae en el bin mas bajo y la particion sigue
#: teniendo sentido — pero un modelo lineal extrapola sobre la escala equivocada y
#: explota. Medido: con el ancla movil, Ridge daba MASE 3,75 con desvio 5,26 entre
#: origenes y sesgo de +5,98 en el peor; con la epoca fija vuelve al rango
#: razonable. LightGBM apenas se movia, que es lo que hace al bug dificil de ver.
TREND_EPOCH: pd.Timestamp = pd.Timestamp("2020-01-01")

#: Nombres de las features de calendario que produce `add_calendar_features`.
CALENDAR_FEATURES: tuple[str, ...] = (
    "dow",
    "dow_sin",
    "dow_cos",
    "day_of_month",
    "dom_sin",
    "dom_cos",
    "week_of_year",
    "month",
    "is_weekend",
    "is_month_start",
    "is_month_end",
    "days_since_start",
)


def add_calendar_features(df: pd.DataFrame, *, date_col: str = S.DATE) -> pd.DataFrame:
    """Agrega las features de calendario. No toca ninguna otra columna."""
    if date_col not in df.columns:
        raise S.SchemaError(f"falta la columna de fecha '{date_col}'")
    out = df.copy()
    dt = pd.to_datetime(out[date_col])

    dow = dt.dt.dayofweek
    out["dow"] = dow.astype("int8")
    out["dow_sin"] = np.sin(2 * np.pi * dow / 7).astype("float32")
    out["dow_cos"] = np.cos(2 * np.pi * dow / 7).astype("float32")

    dom = dt.dt.day
    out["day_of_month"] = dom.astype("int8")
    # El ciclo mensual se normaliza a 31 y no a la longitud real del mes: la
    # diferencia es despreciable frente al ruido y evita un salto artificial
    # entre febrero y marzo.
    out["dom_sin"] = np.sin(2 * np.pi * dom / 31).astype("float32")
    out["dom_cos"] = np.cos(2 * np.pi * dom / 31).astype("float32")

    out["week_of_year"] = dt.dt.isocalendar().week.to_numpy().astype("int8")
    out["month"] = dt.dt.month.astype("int8")
    out["is_weekend"] = (dow >= 5).astype("int8")
    out["is_month_start"] = dt.dt.is_month_start.astype("int8")
    out["is_month_end"] = dt.dt.is_month_end.astype("int8")

    # Tendencia lineal comun a todas las series, anclada en una epoca **fija**.
    # Ver el comentario de TREND_EPOCH: anclar en el minimo del frame hace que la
    # feature valga distinto en entrenamiento y en inferencia.
    out["days_since_start"] = (dt - TREND_EPOCH).dt.days.astype("int32")
    return out


def paraguayan_holidays(years: list[int] | tuple[int, ...]) -> pd.DatetimeIndex:
    """Feriados nacionales paraguayos de fecha fija, mas los moviles calculables.

    Existe para el **caso secundario** (generador calibrado a Focal Point, frente
    K del plan). El dataset primario es chino y ya trae su propia bandera
    ``holiday_flag``, asi que no se le aplica este calendario: mezclar feriados
    paraguayos con datos de Shanghai seria ruido disfrazado de feature.

    Los feriados de fecha movil que dependen de Pascua se derivan del algoritmo
    de Butcher; los "puentes" que el Ejecutivo decreta ano a ano no son
    predecibles y no se incluyen.
    """
    fixed = [(1, 1), (3, 1), (5, 1), (5, 14), (5, 15), (6, 12), (8, 15), (9, 29), (12, 8), (12, 25)]
    dates: list[pd.Timestamp] = []
    for year in years:
        dates.extend(pd.Timestamp(year=year, month=m, day=d) for m, d in fixed)
        easter = _easter(year)
        # Jueves y Viernes Santo.
        dates.append(easter - pd.Timedelta(days=3))
        dates.append(easter - pd.Timedelta(days=2))
    return pd.DatetimeIndex(sorted(dates))


def _easter(year: int) -> pd.Timestamp:
    """Domingo de Pascua por el algoritmo de Butcher (calendario gregoriano)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lam = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lam) // 451
    month, day = divmod(h + lam - 7 * m + 114, 31)
    return pd.Timestamp(year=year, month=month, day=day + 1)


def add_holiday_proximity(
    df: pd.DataFrame,
    holidays: pd.DatetimeIndex,
    *,
    date_col: str = S.DATE,
    max_days: int = 7,
) -> pd.DataFrame:
    """Dias al feriado mas cercano, con signo.

    Negativo antes del feriado, positivo despues, cero el mismo dia. Importa mas
    que la bandera binaria: en perecederos el pico de compra es el dia **previo**
    al feriado, no el feriado, y una bandera de un dia no captura eso.
    """
    out = df.copy()
    if len(holidays) == 0:
        out["days_to_holiday"] = np.int16(max_days)
        out["is_holiday"] = np.int8(0)
        return out

    dates = pd.to_datetime(out[date_col]).to_numpy(dtype="datetime64[D]")
    hol = holidays.to_numpy(dtype="datetime64[D]")
    # Distancia con signo al feriado mas cercano, vectorizado.
    diffs = (dates[:, None] - hol[None, :]).astype("int32")
    nearest = np.abs(diffs).argmin(axis=1)
    signed = diffs[np.arange(diffs.shape[0]), nearest]
    out["days_to_holiday"] = np.clip(signed, -max_days, max_days).astype("int16")
    out["is_holiday"] = (signed == 0).astype("int8")
    return out
