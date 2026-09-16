"""Prediccion conformal por particion · seccion 8.1 del plan.

Intervalos con cobertura garantizada sin supuestos distribucionales. El
procedimiento es corto y por eso mismo conviene entender que hace y que no.

1. Se parte el train en **ajuste** y **calibracion**.
2. Se entrena el modelo base solo con el tramo de ajuste.
3. Se miden los residuos absolutos sobre calibracion, que el modelo no vio.
4. El cuantil `1 - alpha` de esos residuos es la semiamplitud del intervalo.
5. Se reentrena el modelo base con todo el train y se le pega esa semiamplitud.

Lo que garantiza: cobertura marginal `>= 1 - alpha` sobre el conjunto evaluado,
sin suponer normalidad ni homocedasticidad. Lo que **no** garantiza: cobertura
condicional por serie. Un intervalo puede cubrir el 90 % global y solo el 60 % en
las series volatiles. De ahi la variante adaptativa.

Tres decisiones de diseno que se apartan del conformal de manual, y las tres
importan en series temporales:

**La particion es temporal, no aleatoria.** El conformal estandar parte al azar
porque supone intercambiabilidad. En una serie temporal partir al azar pondria
dias futuros en calibracion y dias pasados en evaluacion, o sea la misma fuga que
todo el proyecto evita. Se calibra con el tramo **final** del train.

**Los residuos se agrupan por paso de horizonte.** Predecir a 7 dias es mas
dificil que a 1, asi que un cuantil unico produce intervalos demasiado anchos en
`h=1` y demasiado angostos en `h=7` — cubre el 90 % en promedio y falla
sistematicamente donde mas importa. Se calcula un cuantil por `h`.

**El intervalo se recorta en cero.** La demanda no es negativa. Un limite
inferior negativo no es informacion, es ruido que ademas ensancha el intervalo
medio sin aportar cobertura.

La libreria de Nixtla trae conformal listo (docs/decisiones.md D7). Se implementa
aca de todos modos porque el arnes necesita la particion temporal y el
agrupamiento por horizonte, que son justamente las dos cosas que la version
generica no hace. El tiempo ahorrado va a **verificar la cobertura**, que es lo
que se defiende.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from dfcore import config as cfg
from dfcore.data import schema as S
from dfcore.models.base import Forecaster

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

#: Semiamplitud minima. Un cuantil de residuos exactamente cero produciria un
#: intervalo degenerado en series planas, que reportaria 0 % de cobertura.
MIN_HALF_WIDTH = 1e-6


class ConformalForecaster(Forecaster):
    """Envuelve un modelo puntual y le agrega intervalos calibrados.

    Args:
        base: modelo a envolver. Se usa su clase para reinstanciarlo, asi que
            tiene que poder reentrenarse.
        alpha: 1 - nivel nominal. `alpha=0.1` da un intervalo del 90 %.
        calibration_days: dias finales del train reservados para calibrar. Por
            defecto el doble del horizonte, para que haya al menos dos ventanas
            completas de cada paso de horizonte en calibracion.
        adaptive: normaliza el residuo por una estimacion de dispersion de la
            serie, asi las series volatiles reciben intervalos mas anchos que las
            estables. Es barato y se nota en el grafico de cobertura.
    """

    supports_quantiles = True

    def __init__(
        self,
        base: Forecaster,
        *,
        alpha: float = 1 - cfg.FORECAST.coverage,
        calibration_days: int | None = None,
        horizon: int = cfg.FORECAST.horizon,
        adaptive: bool = False,
        dispersion_window: int = 28,
    ) -> None:
        super().__init__()
        if not 0 < alpha < 1:
            raise ValueError(f"alpha debe estar en (0, 1), llego {alpha}")
        self.base = base
        self.alpha = alpha
        self.horizon = horizon
        self.calibration_days = calibration_days or 2 * horizon
        self.adaptive = adaptive
        self.dispersion_window = dispersion_window
        self.name = f"conformal_{base.name}" + ("_adaptive" if adaptive else "")
        #: Semiamplitud por paso de horizonte.
        self.half_width_: dict[int, float] = {}
        #: Escala de dispersion por serie, solo en el modo adaptativo.
        self.dispersion_: pd.Series | None = None
        self._global_dispersion: float = 1.0

    # -- Entrenamiento ----------------------------------------------------
    def _fit(self, history: pd.DataFrame, *, target: str) -> None:
        dates = pd.DatetimeIndex(sorted(history[S.DATE].unique()))
        if len(dates) <= self.calibration_days + self.horizon:
            raise ValueError(
                f"{self.name}: hacen falta mas de "
                f"{self.calibration_days + self.horizon} dias de train para "
                f"calibrar, llegaron {len(dates)}"
            )
        # Particion TEMPORAL. El origen de calibracion es el ultimo dia del tramo
        # de ajuste; lo que viene despues son los objetivos de calibracion.
        cut = dates[-self.calibration_days - 1]
        fit_part = history[history[S.DATE] <= cut]
        cal_part = history[history[S.DATE] > cut]

        if self.adaptive:
            self.dispersion_ = _dispersion_by_series(
                fit_part, target=target, window=self.dispersion_window
            )
            self._global_dispersion = float(np.nanmedian(self.dispersion_.to_numpy()))

        residuals = self._calibration_residuals(fit_part, cal_part, cut, target=target)
        self.half_width_ = _quantile_by_horizon(residuals, alpha=self.alpha)
        log.info(
            "%s: calibrado con %d dias y %d residuos; semiamplitudes %s",
            self.name,
            self.calibration_days,
            len(residuals),
            {h: round(w, 4) for h, w in self.half_width_.items()},
        )

        # Reentrenar con TODO el train: la calibracion ya esta hecha y el modelo
        # final tiene que aprovechar los dias reservados. Es lo que hace el
        # split-conformal estandar y lo que mantiene la garantia aproximada.
        self.base.fit(history, target=target)

    def _calibration_residuals(
        self, fit_part: pd.DataFrame, cal_part: pd.DataFrame, cut: pd.Timestamp, *, target: str
    ) -> pd.DataFrame:
        """Residuos absolutos del tramo de calibracion, con su paso de horizonte."""
        base = _clone(self.base)
        base.fit(fit_part, target=target)

        future = cal_part[[S.SERIES_ID, S.DATE, *S.HIERARCHY_COLS]].copy()
        future = future[[c for c in future.columns if c in cal_part.columns]]
        future["h"] = (future[S.DATE] - cut).dt.days.astype("int16")
        future = future[future["h"] <= self.horizon].reset_index(drop=True)
        if future.empty:
            raise ValueError(f"{self.name}: el tramo de calibracion quedo vacio")

        preds = base.predict(future)
        truth = cal_part.set_index([S.SERIES_ID, S.DATE])[target]
        keys = pd.MultiIndex.from_arrays([future[S.SERIES_ID], future[S.DATE]])
        actual = truth.reindex(keys).to_numpy(dtype="float64")

        out = pd.DataFrame(
            {
                "h": future["h"].to_numpy(),
                S.SERIES_ID: future[S.SERIES_ID].to_numpy(),
                "residual": np.abs(actual - preds.to_numpy()),
            }
        ).dropna(subset=["residual"])

        if self.adaptive and self.dispersion_ is not None:
            scale = (
                out[S.SERIES_ID]
                .map(self.dispersion_)
                .fillna(self._global_dispersion)
                .to_numpy(dtype="float64")
            )
            # Residuo normalizado: el cuantil se calcula en unidades de
            # dispersion y despues se re-escala por serie al predecir.
            out["residual"] = out["residual"] / np.maximum(scale, 1e-6)
        return out

    # -- Prediccion -------------------------------------------------------
    def _predict(self, future: pd.DataFrame) -> np.ndarray:
        return self.base.predict(future).to_numpy()

    def predict_interval(self, future: pd.DataFrame) -> pd.DataFrame:
        """Prediccion puntual con sus limites. Es la salida que consume la API."""
        point = self.predict(future)
        half = self._half_width_for(future)
        lo = np.clip(point.to_numpy() - half, 0.0, None)
        hi = point.to_numpy() + half
        return pd.DataFrame(
            {"y_pred": point.to_numpy(), "pred_lo": lo, "pred_hi": hi}, index=future.index
        )

    def predict_quantile(self, future: pd.DataFrame, quantiles: Sequence[float]) -> pd.DataFrame:
        """Cuantiles derivados del intervalo conformal.

        Interpola linealmente entre el limite inferior, la prediccion puntual y el
        limite superior. Es una aproximacion honesta y hay que decir que lo es: el
        conformal entrega **un** intervalo a un nivel, no una distribucion
        completa. Para cuantiles de verdad esta `LightGBMQuantileForecaster`, que
        entrena una perdida cuantilica por cuantil.
        """
        from dfcore.models.base import quantile_col

        interval = self.predict_interval(future)
        lo = interval["pred_lo"].to_numpy()
        mid = interval["y_pred"].to_numpy()
        hi = interval["pred_hi"].to_numpy()

        nominal_lo = self.alpha / 2
        nominal_hi = 1 - self.alpha / 2
        anchors = np.array([nominal_lo, 0.5, nominal_hi])
        out = {}
        for q in sorted(quantiles):
            values = np.stack([lo, mid, hi], axis=1)
            out[quantile_col(q)] = np.clip(
                np.array([np.interp(q, anchors, row) for row in values]), 0.0, None
            )
        return pd.DataFrame(out, index=future.index)

    def _half_width_for(self, future: pd.DataFrame) -> np.ndarray:
        if not self.half_width_:
            raise RuntimeError(f"{self.name}: sin calibrar")
        # Un `h` fuera de lo calibrado usa el mayor disponible: extrapolar hacia
        # un intervalo mas angosto seria prometer precision que no se midio.
        fallback = max(self.half_width_.values())
        half = future["h"].map(self.half_width_).fillna(fallback).to_numpy(dtype="float64")
        if self.adaptive and self.dispersion_ is not None:
            scale = (
                future[S.SERIES_ID]
                .map(self.dispersion_)
                .fillna(self._global_dispersion)
                .to_numpy(dtype="float64")
            )
            half = half * np.maximum(scale, 1e-6)
        return np.maximum(half, MIN_HALF_WIDTH)


def _clone(model: Forecaster) -> Forecaster:
    """Copia sin entrenar del modelo, para calibrar sin contaminar el original."""
    import copy

    fresh = copy.deepcopy(model)
    Forecaster.__init__(fresh)
    fresh.name = model.name
    return fresh


def _dispersion_by_series(history: pd.DataFrame, *, target: str, window: int) -> pd.Series:
    """Desvio de las diferencias de primer orden, por serie.

    Se usa la diferencia y no el nivel a proposito: mide cuanto **se mueve** la
    serie, que es lo que hace difícil pronosticarla. Una serie con nivel 100 y
    plana es facil; una con nivel 2 y saltos de 2 no lo es.
    """
    df = history.sort_values([S.SERIES_ID, S.DATE], kind="mergesort")
    tail = df.groupby(S.SERIES_ID, observed=True).tail(window)
    diffs = tail.groupby(S.SERIES_ID, observed=True)[target].diff().abs()
    scale = diffs.groupby(tail[S.SERIES_ID], observed=True).mean()
    overall = float(np.nanmean(scale.to_numpy()))
    return scale.fillna(overall).clip(lower=1e-6).rename("dispersion")


def _quantile_by_horizon(residuals: pd.DataFrame, *, alpha: float) -> dict[int, float]:
    """Cuantil conformal por paso de horizonte, con la correccion de muestra finita.

    El cuantil se toma en `ceil((n + 1)(1 - alpha)) / n` y no en `1 - alpha`. Es
    la correccion de muestra finita del split-conformal: sin ella la cobertura
    queda por debajo del nominal cuando `n` es chico, que es exactamente el caso
    aca — la calibracion son dos semanas.
    """
    out: dict[int, float] = {}
    global_res = residuals["residual"].to_numpy(dtype="float64")
    for h, grp in residuals.groupby("h", observed=True):
        res = grp["residual"].to_numpy(dtype="float64")
        if res.size < 20:
            # Muy pocos residuos para ese paso: se usa el conjunto completo, que
            # es mas conservador que inventar un cuantil con cinco puntos.
            res = global_res
        n = res.size
        level = min(np.ceil((n + 1) * (1 - alpha)) / n, 1.0)
        out[int(h)] = float(np.quantile(res, level))
    return out


def coverage_by_group(result: pd.DataFrame, *, group: str, nominal: float) -> pd.DataFrame:
    """Cobertura empirica desagregada. Es donde se ve la limitacion del conformal.

    El conformal garantiza cobertura **marginal**, no condicional. Desagregar por
    horizonte o por banda de rotacion muestra si el 90 % global esconde un 60 % en
    algun subgrupo. Es la tabla que conviene mostrar antes de que la pregunte el
    panel.
    """
    from dfcore.evaluate import contracts as C
    from dfcore.evaluate.metrics import empirical_coverage, mean_interval_width

    rows = []
    for (model, key), g in result.groupby([C.MODEL, group], observed=True):
        if C.PRED_LO not in g.columns or g[C.PRED_LO].isna().all():
            continue
        rows.append(
            {
                "model": model,
                group: key,
                "coverage_empirical": empirical_coverage(g[C.Y_TRUE], g[C.PRED_LO], g[C.PRED_HI]),
                "coverage_nominal": nominal,
                "interval_width": mean_interval_width(g[C.PRED_LO], g[C.PRED_HI]),
                "n": int(len(g)),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out["gap"] = out["coverage_empirical"] - out["coverage_nominal"]
    return out


__all__ = ["ConformalForecaster", "coverage_by_group"]
