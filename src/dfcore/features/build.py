"""Ensamblado supervisado anclado en el origen.

Este modulo es donde el diseno antifugas se vuelve estructura en vez de buena
intencion. La idea es una sola y vale la pena decirla completa.

Un pronostico se hace **en un origen** `T` y apunta a `T+1 .. T+H`. Las features
se calculan una sola vez por `(serie, T)` con datos de hasta `T` inclusive, y
despues se replican para los `H` objetivos, agregando `h` como feature. La
estrategia es **directa** (un modelo que recibe `h`), no recursiva, asi que no
hay realimentacion de predicciones dentro del horizonte.

Consecuencia practica: la matriz de entrenamiento no tiene ninguna columna que
pueda contener informacion posterior al origen, porque todas vienen de la fila
del origen. La alternativa habitual — calcular lags respecto de la fecha
objetivo — mete `y[T+h-1]` como feature de un objetivo en `T+h`, o sea seis dias
del futuro que se quiere predecir cuando `h=7`. La metrica sale brillante y el
modelo no sirve.

Lo unico que se toma de la fecha **objetivo** son cosas que se conocen de
antemano sin mirar el futuro: el calendario y las covariables planificadas
(descuento, feriado, actividad promocional). El clima queda excluido a proposito,
porque a 7 dias no se conoce; entra solo rezagado y anclado en el origen.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from dfcore import config as cfg
from dfcore.data import schema as S
from dfcore.features import calendar as cal
from dfcore.features import lags as lg

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

#: Columna del paso de horizonte en la matriz supervisada.
H = "h"
#: Fecha del origen de cada fila.
ORIGIN_DATE = "origin_date"
#: Target de la fila supervisada.
Y = "y"
#: Venta observada del dia objetivo. Viaja como columna auxiliar para el
#: contrato de backtest; **no** es feature y `feature_columns()` la excluye.
Y_OBSERVED = "y_observed"

#: Columnas que nunca son features, por identidad o por ser el propio objetivo.
NON_FEATURES: tuple[str, ...] = (
    S.SERIES_ID,
    S.DATE,
    ORIGIN_DATE,
    Y,
    Y_OBSERVED,
    S.SALE_AMOUNT,
    S.DEMAND_LATENT,
    S.INFLATION,
    S.AVAILABLE_WEIGHT,
    S.OOS_HOURS_DAY,
    S.OOS_HOURS_OPEN,
    S.IS_CENSORED,
    "split",
    "profile_weight",
)

#: Categoricas de jerarquia. LightGBM las consume como categoricas nativas.
CATEGORICAL_FEATURES: tuple[str, ...] = S.HIERARCHY_COLS


def add_origin_features(
    panel: pd.DataFrame,
    *,
    target: str = S.DEMAND_LATENT,
    lags_: Sequence[int] = lg.DEFAULT_LAGS,
    windows: Sequence[int] = lg.DEFAULT_WINDOWS,
    season_length: int = 7,
) -> pd.DataFrame:
    """Calcula, para cada fila del panel, todo lo que se sabe al cerrar ese dia.

    El resultado es el "estado de origen": cualquier fila puede usarse como
    origen de pronostico y sus features son validas por construccion.
    """
    df = S.validate_panel(panel, required=(*S.PANEL_REQUIRED, target), allow_gaps=True)
    df = lg.add_lag_features(df, target=target, lags=lags_)
    df = lg.add_rolling_features(df, target=target, windows=windows)
    df = lg.add_seasonal_features(df, target=target, season_length=season_length)
    df = lg.add_intermittency_features(df, target=target)
    df = lg.add_censoring_history(df)
    df = lg.add_exogenous_lags(df, columns=(*S.WEATHER_COLS, S.DISCOUNT), lags=(0, 1, 7))
    return df


def make_origins(
    panel: pd.DataFrame,
    *,
    horizon: int,
    min_train_days: int,
    last_origin: pd.Timestamp | None = None,
) -> pd.DatetimeIndex:
    """Fechas utilizables como origen: con historia suficiente y futuro suficiente."""
    dates = pd.DatetimeIndex(sorted(panel[S.DATE].unique()))
    if len(dates) < min_train_days + horizon:
        raise ValueError(
            f"el panel tiene {len(dates)} dias y hacen falta al menos "
            f"{min_train_days + horizon} para un origen con horizonte {horizon}"
        )
    first = dates[min_train_days - 1]
    # `-horizon - 1` y no `-horizon`: el ultimo origen tiene que dejar `horizon`
    # dias **por delante**, asi que su objetivo mas lejano cae justo en el ultimo
    # dia del panel. Con `-horizon` el objetivo del ultimo origen se saldria del
    # panel por un dia y ese fold quedaria incompleto en silencio.
    latest = dates[-horizon - 1]
    if last_origin is not None:
        latest = min(latest, pd.Timestamp(last_origin))
    return dates[(dates >= first) & (dates <= latest)]


def build_supervised(
    panel_with_features: pd.DataFrame,
    origins: Sequence[pd.Timestamp] | pd.DatetimeIndex,
    *,
    horizon: int,
    target: str = S.DEMAND_LATENT,
    include_target: bool = True,
) -> pd.DataFrame:
    """Une el estado de cada origen con sus `horizon` objetivos.

    Devuelve una fila por `(serie, origen, h)`. Con `include_target=False` no
    exige que el objetivo exista, que es el caso de la inferencia real: se
    pronostica hacia adelante y ahi todavia no hay verdad.
    """
    df = panel_with_features
    origins = pd.DatetimeIndex(origins)

    state = df[df[S.DATE].isin(origins)].copy()
    if state.empty:
        raise ValueError("ninguna fila del panel cae en los origenes pedidos")
    state = state.rename(columns={S.DATE: ORIGIN_DATE})
    # Las covariables del dia del origen no se llevan al objetivo: para eso
    # estan sus versiones rezagadas. Dejarlas seria confundir "el descuento del
    # origen" con "el descuento del dia que se pronostica".
    #
    # Las columnas de censura del origen tambien se van, y por un motivo menos
    # obvio: al unir con la verdad, pandas desambigua el choque de nombres con
    # el sufijo `_target`, y aparece un `is_censored_target` que **si** es del
    # dia objetivo. Como no figura en `NON_FEATURES`, entraria a la matriz como
    # feature y le contaria al modelo si el dia que tiene que pronosticar tuvo
    # quiebre. Es fuga, y de la peor clase: predecir demanda sabiendo el quiebre
    # futuro. La informacion de censura del origen ya viaja, agregada y sin
    # ambiguedad, en las features `censored_share_*`.
    drop_from_state = (
        *S.KNOWN_FUTURE_COLS,
        *S.WEATHER_COLS,
        S.SALE_AMOUNT,
        target,
        S.INFLATION,
        S.IS_CENSORED,
        S.OOS_HOURS_OPEN,
        S.OOS_HOURS_DAY,
        S.AVAILABLE_WEIGHT,
    )
    state = state.drop(columns=[c for c in dict.fromkeys(drop_from_state) if c in state.columns])

    steps = pd.DataFrame({H: np.arange(1, horizon + 1, dtype="int16")})
    grid = state.merge(steps, how="cross")
    grid[S.DATE] = grid[ORIGIN_DATE] + pd.to_timedelta(grid[H], unit="D")

    # Del dia objetivo se toma solo lo conocido de antemano, mas la verdad y la
    # venta observada, que son etiquetas y no features.
    truth_cols = [S.SERIES_ID, S.DATE, *S.KNOWN_FUTURE_COLS]
    if include_target:
        truth_cols += [S.SALE_AMOUNT, S.IS_CENSORED]
    truth = df[[c for c in dict.fromkeys(truth_cols) if c in df.columns]].copy()
    if include_target:
        # El target se copia a `Y` **antes** del rename. Cuando el target es la
        # propia venta observada (rama de ablacion de censura), `target` y
        # `SALE_AMOUNT` son la misma columna y un rename doble la colapsaria en
        # una sola, dejando la matriz sin objetivo.
        truth[Y] = df.loc[truth.index, target]
        truth = truth.rename(columns={S.SALE_AMOUNT: Y_OBSERVED})

    how = "inner" if include_target else "left"
    out = grid.merge(truth, on=[S.SERIES_ID, S.DATE], how=how, suffixes=("", "_target"))

    if include_target:
        out = out[out[Y].notna()].reset_index(drop=True)

    out = cal.add_calendar_features(out)
    log.info(
        "matriz supervisada: %d filas, %d series, %d origenes, horizonte %d",
        len(out),
        out[S.SERIES_ID].nunique(),
        out[ORIGIN_DATE].nunique(),
        horizon,
    )
    return out


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Columnas que el modelo puede consumir. Todo lo demas es etiqueta o clave.

    Dos filtros. El primero es la lista negra explicita de `NON_FEATURES`. El
    segundo es estructural: **nada que termine en `_target`** entra a la matriz.

    Ese sufijo lo pone pandas cuando el estado del origen y la verdad del dia
    objetivo tienen una columna con el mismo nombre, asi que una columna
    `algo_target` es, por definicion, del dia objetivo. Descartarlas por patron
    en vez de enumerarlas una por una hace que agregar una columna nueva al panel
    no pueda abrir una fuga por olvido.
    """
    banned = set(NON_FEATURES)
    cols = [c for c in df.columns if c not in banned and not c.endswith("_target") and c != Y]
    return [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]


def build_features_layer(
    demand_panel: pd.DataFrame,
    *,
    target: str = S.DEMAND_LATENT,
    forecast: cfg.ForecastConfig = cfg.FORECAST,
) -> pd.DataFrame:
    """Capa `data/processed/features.parquet`: estado de origen para todo el panel.

    Persiste el **estado por fila**, no la matriz supervisada. El motivo es que la
    matriz depende del horizonte y del conjunto de origenes, y el arnes de
    backtesting los cambia en cada fold; regenerarla es barato, recalcular los
    lags no.
    """
    return add_origin_features(
        demand_panel,
        target=target,
        season_length=forecast.season_length,
    )


__all__ = [
    "CATEGORICAL_FEATURES",
    "H",
    "NON_FEATURES",
    "ORIGIN_DATE",
    "Y",
    "Y_OBSERVED",
    "add_origin_features",
    "build_features_layer",
    "build_supervised",
    "feature_columns",
    "make_origins",
]
