"""Features de rezago, ventana movil e intermitencia.

Convencion que sostiene todo el diseno antifugas, y conviene leerla despacio
porque es la fuente habitual de errores silenciosos:

    **Las features de la fila `t` usan `y[t]` y valores anteriores. Nada mas.**

O sea que la fila `t` describe "lo que se sabe al cerrar el dia t", y por eso
puede usarse como **origen** de pronostico. `y_lag_0` es `y[t]`, que al cerrar el
dia t ya se conocio; `y_lag_1` es `y[t-1]`; la media movil de 7 cubre `y[t-6..t]`.

Con esa convencion, el ensamblado supervisado de `build.py` une la fila de
features del origen `T` con los objetivos de `T+1 .. T+H`, y ninguna feature
puede contener informacion posterior a `T` ni por accidente. Es la diferencia
entre "me acorde de no filtrar" y "no se puede filtrar".

El error clasico que esto evita: calcular `lag_1` respecto de la **fecha
objetivo**. Para un objetivo en `T+7`, ese `lag_1` seria `y[T+6]`, seis dias
dentro del futuro que se quiere pronosticar. La metrica sale espectacular y el
modelo no sirve para nada.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from blindside.data import schema as S

if TYPE_CHECKING:
    from collections.abc import Sequence

#: Rezagos por defecto. 1..7 cubre la semana; 14, 21 y 28 capturan la
#: estacionalidad semanal en multiplos, que es donde vive la senal en retail.
DEFAULT_LAGS: tuple[int, ...] = (0, 1, 2, 3, 6, 7, 13, 14, 20, 21, 27, 28)

#: Ventanas de estadisticos moviles.
DEFAULT_WINDOWS: tuple[int, ...] = (7, 14, 28)


def add_lag_features(
    df: pd.DataFrame,
    *,
    target: str = S.DEMAND_LATENT,
    lags: Sequence[int] = DEFAULT_LAGS,
    group: str = S.SERIES_ID,
    date_col: str = S.DATE,
    prefix: str | None = None,
) -> pd.DataFrame:
    """Rezagos por grupo, ordenados por fecha.

    `lag=0` es el valor del propio dia. Es legitimo como feature de origen y es
    la feature mas informativa que existe para un horizonte corto, asi que
    excluirla por prudencia mal entendida costaria exactitud sin ganar rigor.
    """
    _require(df, [group, date_col, target])
    out = df.sort_values([group, date_col], kind="mergesort").copy()
    prefix = prefix or _prefix_for(target)
    g = out.groupby(group, observed=True)[target]
    for lag in lags:
        out[f"{prefix}_lag_{lag}"] = g.shift(lag).astype("float32")
    return out


def add_rolling_features(
    df: pd.DataFrame,
    *,
    target: str = S.DEMAND_LATENT,
    windows: Sequence[int] = DEFAULT_WINDOWS,
    group: str = S.SERIES_ID,
    date_col: str = S.DATE,
    prefix: str | None = None,
) -> pd.DataFrame:
    """Media, desvio, minimo, maximo y mediana moviles, cerrando en `t`.

    La ventana **incluye** `t`, coherente con la convencion del modulo. No hace
    falta `shift(1)` porque el objetivo vive en `t+h` con `h >= 1`, nunca en `t`.
    """
    _require(df, [group, date_col, target])
    out = df.sort_values([group, date_col], kind="mergesort").copy()
    prefix = prefix or _prefix_for(target)
    g = out.groupby(group, observed=True)[target]
    for w in windows:
        roll = g.rolling(window=w, min_periods=max(2, w // 4))
        out[f"{prefix}_roll_mean_{w}"] = _flatten(roll.mean(), out.index)
        out[f"{prefix}_roll_std_{w}"] = _flatten(roll.std(), out.index)
        out[f"{prefix}_roll_max_{w}"] = _flatten(roll.max(), out.index)
        out[f"{prefix}_roll_min_{w}"] = _flatten(roll.min(), out.index)
        out[f"{prefix}_roll_median_{w}"] = _flatten(roll.median(), out.index)
    # Momentum: cuanto se movio el nivel corto respecto del largo. Un cociente y
    # no una diferencia, para que sea comparable entre series de escala distinta.
    if {f"{prefix}_roll_mean_7", f"{prefix}_roll_mean_28"} <= set(out.columns):
        short = out[f"{prefix}_roll_mean_7"]
        long = out[f"{prefix}_roll_mean_28"]
        out[f"{prefix}_momentum_7_28"] = (short / long.where(long > 0)).astype("float32")
    return out


def add_seasonal_features(
    df: pd.DataFrame,
    *,
    target: str = S.DEMAND_LATENT,
    season_length: int = 7,
    n_cycles: int = 4,
    group: str = S.SERIES_ID,
    date_col: str = S.DATE,
    prefix: str | None = None,
) -> pd.DataFrame:
    """Media del mismo dia de la semana en los ultimos `n_cycles` ciclos.

    Es la feature que le da al modelo, ya masticado, lo que el baseline
    estacional ingenuo hace a mano. Si el modelo no le gana al baseline teniendo
    esto adentro, el problema no es de features.
    """
    _require(df, [group, date_col, target])
    out = df.sort_values([group, date_col], kind="mergesort").copy()
    prefix = prefix or _prefix_for(target)
    g = out.groupby(group, observed=True)[target]

    same_dow = [g.shift(season_length * k) for k in range(1, n_cycles + 1)]
    stacked = pd.concat(same_dow, axis=1)
    out[f"{prefix}_dow_mean_{n_cycles}"] = stacked.mean(axis=1).astype("float32")
    out[f"{prefix}_dow_std_{n_cycles}"] = stacked.std(axis=1).astype("float32")
    return out


def add_intermittency_features(
    df: pd.DataFrame,
    *,
    target: str = S.DEMAND_LATENT,
    windows: Sequence[int] = (28,),
    group: str = S.SERIES_ID,
    date_col: str = S.DATE,
) -> pd.DataFrame:
    """Fraccion de ceros y dias desde la ultima venta.

    La cola de baja rotacion es la mayoria del catalogo en perecederos, y es
    donde MAPE explota y donde los modelos complejos suelen perder contra el
    ingenuo. Estas features le permiten al modelo global **saber** que esta
    mirando una serie intermitente y comportarse distinto ahi.
    """
    _require(df, [group, date_col, target])
    out = df.sort_values([group, date_col], kind="mergesort").copy()
    is_zero = (out[target] <= 0).astype("float32")
    gz = is_zero.groupby(out[group], observed=True)
    for w in windows:
        roll = gz.rolling(window=w, min_periods=max(2, w // 4)).mean()
        out[f"zero_share_{w}"] = _flatten(roll, out.index)

    # Dias desde la ultima venta positiva, sin bucles de Python: se propaga el
    # indice posicional del ultimo dia con venta y se resta.
    pos = pd.Series(np.arange(len(out)), index=out.index)
    last_sale = pos.where(out[target] > 0).groupby(out[group], observed=True).ffill()
    out["days_since_sale"] = (pos - last_sale).astype("float32")
    return out


def add_censoring_history(
    df: pd.DataFrame,
    *,
    windows: Sequence[int] = (7, 28),
    group: str = S.SERIES_ID,
    date_col: str = S.DATE,
) -> pd.DataFrame:
    """Historia de quiebres de la serie, como feature.

    Que una serie venga quebrando seguido es informacion real sobre su demanda:
    quiebra porque se pide de menos respecto de lo que se vende. Es la feature
    que le permite al modelo aprender el patron que la recuperacion de censura
    corrige en el target, y las dos cosas se refuerzan.
    """
    _require(df, [group, date_col, S.IS_CENSORED])
    out = df.sort_values([group, date_col], kind="mergesort").copy()
    censored = out[S.IS_CENSORED].astype("float32")
    gc = censored.groupby(out[group], observed=True)
    for w in windows:
        roll = gc.rolling(window=w, min_periods=max(2, w // 4)).mean()
        out[f"censored_share_{w}"] = _flatten(roll, out.index)
    if S.OOS_HOURS_OPEN in out.columns:
        go = out[S.OOS_HOURS_OPEN].astype("float32").groupby(out[group], observed=True)
        out["oos_hours_roll_7"] = _flatten(go.rolling(window=7, min_periods=2).mean(), out.index)
    return out


def add_exogenous_lags(
    df: pd.DataFrame,
    *,
    columns: Sequence[str],
    lags: Sequence[int] = (0, 1, 7),
    group: str = S.SERIES_ID,
    date_col: str = S.DATE,
) -> pd.DataFrame:
    """Rezagos de covariables exogenas (descuento, clima).

    El clima **no se conoce a futuro**, asi que solo entra rezagado y anclado en
    el origen. Usar la temperatura real del dia objetivo seria fuga: en
    produccion ese dato no existe todavia. El descuento si se conoce de antemano,
    pero se rezaga igual para que el efecto de arrastre quede disponible.
    """
    out = df.sort_values([group, date_col], kind="mergesort").copy()
    present = [c for c in columns if c in out.columns]
    for col in present:
        g = out.groupby(group, observed=True)[col]
        for lag in lags:
            out[f"{col}_lag_{lag}"] = g.shift(lag).astype("float32")
    return out


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def _prefix_for(target: str) -> str:
    """Prefijo corto y estable segun el target, para no arrastrar nombres largos."""
    return {S.DEMAND_LATENT: "latent", S.SALE_AMOUNT: "obs"}.get(target, target)


def _flatten(rolled: pd.Series, index: pd.Index) -> pd.Series:
    """Aplana el resultado de un `groupby.rolling`, que trae MultiIndex."""
    if isinstance(rolled.index, pd.MultiIndex):
        rolled = rolled.reset_index(level=0, drop=True)
    return rolled.reindex(index).astype("float32")


def _require(df: pd.DataFrame, cols: Sequence[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise S.SchemaError(f"faltan columnas {missing}")


def lag_feature_names(df: pd.DataFrame) -> list[str]:
    """Nombres de features generadas por este modulo presentes en `df`."""
    markers = (
        "_lag_",
        "_roll_",
        "_momentum_",
        "_dow_mean_",
        "_dow_std_",
        "zero_share_",
        "days_since_sale",
        "censored_share_",
        "oos_hours_roll_",
    )
    return [c for c in df.columns if any(m in c for m in markers)]
