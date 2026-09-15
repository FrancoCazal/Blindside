"""Frente A2 · recuperacion de demanda censurada (seccion 8.0 del plan).

Va **antes** de las features, no despues. Un lag calculado sobre la venta
observada arrastra el sesgo de censura a todo lo que se derive de el, y
corregir despues no lo deshace (docs/decisiones.md D4).

El problema
-----------
Cuando hubo quiebre de stock la venta registrada es cero, pero la demanda no lo
era. Entrenar sobre la venta observada produce el **efecto spiral-down**: se
pide de menos, hay mas quiebres, se observa menos demanda, se pide de menos
todavia. El nombre y la mecanica son de Tobit Exponential Smoothing con
agregacion temporal (https://arxiv.org/html/2409.05412v1). El sesgo equivalente
en decisores humanos esta documentado en Tong, Feiler y Larrick (2018),
https://journals.sagepub.com/doi/10.1111/poms.12823.

Por que aca se puede *medir* y no solo afirmar
----------------------------------------------
FreshRetailNet-50K anota el quiebre **hora por hora**. Eso da dos cosas que un
dataset de ventas normal no da: un mecanismo de correccion que usa informacion
real en vez de un supuesto, y un subconjunto de dias limpios (sin ninguna hora
de quiebre) donde la venta observada **es** la demanda. Ese subconjunto es la
verdad de terreno contra la que se mide el sesgo.

Los dos recuperadores
---------------------
``HourlyProfileRecovery`` (por defecto)
    Estima el perfil de demanda intradiario con las horas sin quiebre y usa la
    masa de demanda perdida como factor de inflacion. Es el que aprovecha la
    anotacion horaria, que es lo distintivo del dataset.

``TobitEWMARecovery``
    Trata el dia censurado como una observacion censurada por la derecha y lo
    reemplaza por el nivel esperado que estima una media movil exponencial de
    los dias limpios. Es la referencia citable y sirve de contraste: si los dos
    metodos dan resultados parecidos, la conclusion no depende del metodo.

Los dos respetan la misma cota, que es la unica no negociable: **la demanda
latente nunca es menor que la venta observada**. La venta ocurrio.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from dfcore import config as cfg
from dfcore.data import schema as S

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

#: Columna intermedia: peso de la masa de demanda intradiaria observable,
#: ponderado por el perfil real y no por horas uniformes.
PROFILE_WEIGHT = "profile_weight"


# --------------------------------------------------------------------------
# Base
# --------------------------------------------------------------------------
class DemandRecovery(ABC):
    """Interfaz de un recuperador de demanda latente."""

    name: str = "recovery"

    @abstractmethod
    def recover(self, panel: pd.DataFrame) -> pd.DataFrame:
        """Agrega `demand_latent` e `inflation_factor` al panel."""

    @staticmethod
    def _finalize(panel: pd.DataFrame, latent: np.ndarray) -> pd.DataFrame:
        """Aplica la cota inferior y calcula el factor, una sola vez y para todos."""
        observed = panel[S.SALE_AMOUNT].to_numpy(dtype="float64")
        latent = np.asarray(latent, dtype="float64")

        # Cota dura: la venta observada ocurrio, es cota inferior de la demanda.
        latent = np.maximum(latent, observed)
        # Los dias sin ninguna hora de quiebre no se tocan: ahi la venta ES la
        # demanda, y es justamente el subconjunto que despues sirve de verdad
        # de terreno. Inventar correccion ahi destruiria la medicion.
        clean = ~panel[S.IS_CENSORED].to_numpy(dtype=bool)
        latent[clean] = observed[clean]

        out = panel.copy()
        out[S.DEMAND_LATENT] = latent.astype("float32")
        with np.errstate(divide="ignore", invalid="ignore"):
            factor = np.where(observed > 0, latent / observed, np.where(latent > 0, np.inf, 1.0))
        out[S.INFLATION] = np.where(np.isfinite(factor), factor, np.nan).astype("float32")
        return out


# --------------------------------------------------------------------------
# Recuperador por perfil horario
# --------------------------------------------------------------------------
@dataclass
class HourlyProfileRecovery(DemandRecovery):
    """Inflacion por masa de demanda perdida, estimada con el perfil intradiario.

    Mecanica, en cuatro pasos:

    1. Con las **horas sin quiebre** de todo el panel se estima un perfil
       ``w_h``, la fraccion de la demanda diaria que ocurre en la hora ``h``.
       El perfil se estima por producto cuando hay evidencia suficiente y se
       cae al perfil de la categoria y despues al global. Estimarlo solo con
       horas limpias es lo que evita que el propio quiebre deprima el perfil.
    2. Para cada dia se suma el peso de las horas **disponibles**:
       ``A = sum(w_h para h sin quiebre)``.
    3. La venta observada es la demanda del dia por ``A``, asi que la demanda
       latente es ``observada / A``.
    4. Se topea la inflacion en ``max_inflation`` y no se corrige cuando ``A``
       cae por debajo de ``min_available_weight``.

    Los dos limites del paso 4 no son cosmetica. Un dia con 15 de 16 franjas en
    quiebre y una sola venta chica implicaria, sin tope, una demanda latente
    dieciseis veces mayor apoyada en un unico dato. Preferir un sesgo residual
    conocido a una varianza inventada es la decision correcta, y se declara.
    """

    name: str = "hourly_profile"
    config: cfg.CensoringConfig = cfg.CENSORING
    #: Minimo de horas limpias para confiar en un perfil de nivel producto.
    min_hours_for_profile: int = 200
    #: Clave de agrupacion del perfil, de mas fina a mas gruesa.
    profile_levels: Sequence[str] = (S.PRODUCT_ID, S.THIRD_CATEGORY_ID)

    def recover(self, panel: pd.DataFrame) -> pd.DataFrame:
        missing = [c for c in S.HOURLY_COLS if c not in panel.columns]
        if missing:
            raise S.SchemaError(
                f"{self.name} necesita {missing}. Cargar el panel con "
                "loaders.load_hourly_panel()."
            )

        sales = _stack(panel[S.HOURS_SALE], "float64")
        status = _stack(panel[S.HOURS_STOCK_STATUS], "int8").astype(bool)
        open_idx = np.asarray(self.config.open_hours, dtype="int64")

        sales_open = sales[:, open_idx]
        oos_open = status[:, open_idx]

        profiles = self._estimate_profiles(panel, sales_open, oos_open)
        weights = profiles  # (n, n_open), ya alineado fila por fila

        available = np.where(oos_open, 0.0, weights).sum(axis=1)
        total = weights.sum(axis=1)
        # `available` y `total` estan en la misma escala; el cociente es la
        # fraccion de masa de demanda que el dia pudo llegar a mostrar.
        with np.errstate(divide="ignore", invalid="ignore"):
            share = np.where(total > 0, available / total, 1.0)
        share = np.clip(np.nan_to_num(share, nan=1.0), 0.0, 1.0)

        observed_open = sales_open.sum(axis=1)
        daily = panel[S.SALE_AMOUNT].to_numpy(dtype="float64")
        # `sale_amount` es el total del dia; las horas fuera de la ventana
        # comercial aportan poco pero no cero. Se corrige solo la parte que
        # ocurre dentro de la ventana y el resto se deja tal cual.
        outside = np.clip(daily - observed_open, 0.0, None)

        correctable = (share >= self.config.min_available_weight) & (share < 1.0)
        factor = np.ones_like(share)
        factor[correctable] = np.minimum(1.0 / share[correctable], self.config.max_inflation)

        latent = observed_open * factor + outside

        out = self._finalize(panel, latent)
        out[PROFILE_WEIGHT] = share.astype("float32")
        n_corrected = int((factor > 1.0).sum())
        n_capped = int((factor >= self.config.max_inflation - 1e-9).sum())
        starved = panel[S.IS_CENSORED].to_numpy(dtype=bool) & (
            share < self.config.min_available_weight
        )
        n_skipped = int(starved.sum())
        log.info(
            "%s: %d dias corregidos, %d topeados en x%.1f, %d censurados sin "
            "correccion por masa disponible < %.2f",
            self.name,
            n_corrected,
            n_capped,
            self.config.max_inflation,
            n_skipped,
            self.config.min_available_weight,
        )
        return out

    def _estimate_profiles(
        self, panel: pd.DataFrame, sales_open: np.ndarray, oos_open: np.ndarray
    ) -> np.ndarray:
        """Perfil intradiario por fila, estimado solo con horas sin quiebre.

        Devuelve una matriz (n_filas, n_horas_comerciales) donde cada fila es el
        perfil que le corresponde a esa observacion segun su producto o su
        categoria. La jerarquia de respaldo evita que un producto con pocas
        horas limpias reciba un perfil de ruido.
        """
        clean_mask = ~oos_open
        clean_sales = np.where(clean_mask, sales_open, 0.0)

        global_num = clean_sales.sum(axis=0)
        global_den = clean_mask.sum(axis=0)
        global_profile = _safe_profile(global_num, global_den)

        n_rows, n_hours = sales_open.shape
        out = np.tile(global_profile, (n_rows, 1))

        # De mas gruesa a mas fina, para que la mas fina sobreescriba cuando
        # tiene evidencia suficiente.
        for level in reversed(list(self.profile_levels)):
            if level not in panel.columns:
                continue
            keys = panel[level].to_numpy()
            for key in np.unique(keys):
                rows = keys == key
                den = clean_mask[rows].sum(axis=0)
                if den.sum() < self.min_hours_for_profile:
                    continue
                num = clean_sales[rows].sum(axis=0)
                prof = _safe_profile(num, den)
                if prof is None:
                    continue
                out[rows] = prof
        return out


def _safe_profile(num: np.ndarray, den: np.ndarray) -> np.ndarray | None:
    """Perfil normalizado a partir de sumas y conteos por hora."""
    with np.errstate(divide="ignore", invalid="ignore"):
        mean_per_hour = np.where(den > 0, num / np.maximum(den, 1), np.nan)
    if not np.isfinite(mean_per_hour).any():
        return None
    # Las horas sin ninguna observacion limpia heredan la media de las que si
    # la tienen; dejarlas en cero equivaldria a afirmar que no venden.
    fill = float(np.nanmean(mean_per_hour))
    mean_per_hour = np.where(np.isfinite(mean_per_hour), mean_per_hour, fill)
    total = mean_per_hour.sum()
    if total <= 0:
        # Serie sin ninguna venta limpia: perfil plano. Con demanda cero el
        # factor de inflacion es irrelevante de todos modos.
        return np.full_like(mean_per_hour, 1.0 / mean_per_hour.size)
    return mean_per_hour / total


# --------------------------------------------------------------------------
# Recuperador Tobit / EWMA
# --------------------------------------------------------------------------
@dataclass
class TobitEWMARecovery(DemandRecovery):
    """Censura por la derecha resuelta con el nivel esperado de los dias limpios.

    Para cada serie se estima el nivel con una media movil exponencial calculada
    **solo sobre dias sin quiebre**, y se propaga hacia adelante. En un dia
    censurado la demanda latente es el maximo entre la venta observada y ese
    nivel escalado por la fraccion de dia perdida.

    Es mas grueso que el recuperador por perfil porque no usa la posicion de las
    horas de quiebre, solo cuantas fueron. Existe como contraste: dos metodos
    independientes que coinciden hacen que la conclusion no dependa de la
    eleccion de metodo, y eso es una pregunta que el panel va a hacer.

    Detalle antifugas: la EWMA se calcula con ``shift(1)`` dentro de cada serie,
    asi que el nivel de un dia nunca incluye ese dia. Sin el shift, el propio
    valor censurado entraria en su propia correccion.
    """

    name: str = "tobit_ewma"
    config: cfg.CensoringConfig = cfg.CENSORING

    def recover(self, panel: pd.DataFrame) -> pd.DataFrame:
        df = panel.sort_values([S.SERIES_ID, S.DATE], kind="mergesort")
        observed = df[S.SALE_AMOUNT]
        censored = df[S.IS_CENSORED].to_numpy(dtype=bool)

        clean_only = observed.where(~censored)
        level = (
            clean_only.groupby(df[S.SERIES_ID], observed=True)
            .transform(lambda s: s.ffill().shift(1).ewm(span=self.config.ewma_span).mean())
            .to_numpy(dtype="float64")
        )
        # Series que arrancan censuradas no tienen historia limpia previa: se
        # cae a la media limpia de la propia serie y luego a la global.
        series_mean = (
            clean_only.groupby(df[S.SERIES_ID], observed=True).transform("mean").to_numpy("float64")
        )
        global_mean = float(np.nanmean(clean_only.to_numpy(dtype="float64")))
        level = np.where(np.isfinite(level), level, series_mean)
        level = np.where(np.isfinite(level), level, global_mean)

        # Fraccion del dia comercial efectivamente disponible.
        share = df[S.AVAILABLE_WEIGHT].to_numpy(dtype="float64")
        obs = observed.to_numpy(dtype="float64")

        latent = obs.copy()
        usable = censored & (share >= self.config.min_available_weight)
        # Esperanza de una demanda truncada por la derecha, aproximada: el nivel
        # completo del dia cuando el nivel supera lo que se alcanzo a vender.
        candidate = np.maximum(obs, level)
        capped = np.minimum(candidate, obs * self.config.max_inflation)
        # Si no se vendio nada, el tope multiplicativo no aplica y manda el nivel.
        capped = np.where(obs > 0, capped, candidate)
        latent[usable] = capped[usable]

        out = self._finalize(df, latent)
        log.info(
            "%s: %d dias censurados corregidos de %d",
            self.name,
            int(usable.sum()),
            int(censored.sum()),
        )
        return out.reset_index(drop=True)


def _stack(col: pd.Series, dtype: str) -> np.ndarray:
    arr = np.stack([np.asarray(v, dtype=dtype) for v in col])
    if arr.shape[1] != 24:
        raise S.SchemaError(f"se esperaban 24 horas por fila, llegaron {arr.shape[1]}")
    return arr


# --------------------------------------------------------------------------
# Medicion: sesgo de demanda re-censurada
# --------------------------------------------------------------------------
def recensored_bias(
    y_true_observed: np.ndarray | pd.Series,
    y_pred: np.ndarray | pd.Series,
    *,
    is_censored: np.ndarray | pd.Series,
) -> float:
    """Sesgo relativo medido **solo en dias limpios**, donde la verdad se conoce.

    Definicion operativa: en los dias sin ninguna hora de quiebre la venta
    observada es la demanda real. Ahi se mide

        bias = (mean(y_pred) - mean(y_obs)) / mean(y_obs)

    Un modelo entrenado sobre la venta cruda da un valor **negativo**: aprendio
    de una demanda deprimida por los quiebres y predice de menos incluso en los
    dias en los que no hubo ninguno. Un modelo entrenado sobre demanda latente
    recuperada deberia acercarse a cero.

    Es la forma que tienen los numeros publicados de CADRE sobre este mismo
    dataset, -8,1 % a -1,3 % (https://www.mdpi.com/2071-1050/18/15/7642), asi
    que el resultado propio es comparable con un tercero en vez de autoevaluado.

    Se mide en dias limpios a proposito: en los dias censurados no hay verdad de
    terreno, y compararse contra la venta observada ahi premiaria justamente al
    modelo sesgado.
    """
    obs = np.asarray(y_true_observed, dtype="float64")
    pred = np.asarray(y_pred, dtype="float64")
    clean = ~np.asarray(is_censored, dtype=bool)
    if clean.sum() == 0:
        return float("nan")
    denom = obs[clean].mean()
    if denom <= 0:
        return float("nan")
    return float((pred[clean].mean() - denom) / denom)


def censoring_report(panel: pd.DataFrame) -> pd.DataFrame:
    """Tabla comparativa observado vs latente. Va al EDA y al dashboard."""
    censored = panel[S.IS_CENSORED]
    rows = [
        {
            "grupo": "todos los dias",
            "n": len(panel),
            "demanda_observada": panel[S.SALE_AMOUNT].mean(),
            "demanda_latente": panel[S.DEMAND_LATENT].mean(),
        },
        {
            "grupo": "dias limpios",
            "n": int((~censored).sum()),
            "demanda_observada": panel.loc[~censored, S.SALE_AMOUNT].mean(),
            "demanda_latente": panel.loc[~censored, S.DEMAND_LATENT].mean(),
        },
        {
            "grupo": "dias censurados",
            "n": int(censored.sum()),
            "demanda_observada": panel.loc[censored, S.SALE_AMOUNT].mean(),
            "demanda_latente": panel.loc[censored, S.DEMAND_LATENT].mean(),
        },
    ]
    out = pd.DataFrame(rows)
    out["uplift_pct"] = 100 * (out["demanda_latente"] / out["demanda_observada"] - 1)
    return out


RECOVERIES: dict[str, type[DemandRecovery]] = {
    "hourly_profile": HourlyProfileRecovery,
    "tobit_ewma": TobitEWMARecovery,
}


def get_recovery(name: str) -> DemandRecovery:
    if name not in RECOVERIES:
        raise KeyError(f"recuperador '{name}' desconocido; hay {sorted(RECOVERIES)}")
    return RECOVERIES[name]()


__all__ = [
    "DemandRecovery",
    "HourlyProfileRecovery",
    "TobitEWMARecovery",
    "censoring_report",
    "get_recovery",
    "recensored_bias",
]
