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

from blindside import config as cfg
from blindside.data import schema as S
from blindside.models.base import Forecaster, quantile_col

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

    @property
    def quantiles(self) -> tuple[float, ...]:
        """Los cuantiles del modelo envuelto, no los del config.

        Sin esta propiedad el consumidor cae al default de `cfg.FORECAST` y pierde
        los cuantiles que el modelo realmente entreno. Paso en la API: el artefacto
        tiene un booster en q* = 0,625 y `/reorder` interpolaba q* entre 0,5 y 0,9
        porque preguntaba `getattr(model, "quantiles", cfg.FORECAST.quantiles)` y
        `hasattr` daba False. La cantidad servida era distinta de la cantidad que
        el backtest media, sin que ninguna metrica lo notara.
        """
        return tuple(getattr(self.base, "quantiles", cfg.FORECAST.quantiles) or ())

    def reorder_quantity(self, future: pd.DataFrame, **kwargs: object) -> pd.Series:
        """Delega la orden en el modelo base, que sabe si tiene q* entrenado."""
        base_reorder = getattr(self.base, "reorder_quantity", None)
        if base_reorder is None:
            raise AttributeError(f"{self.name}: el modelo base no emite orden")
        return base_reorder(future, **kwargs)

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
        """Cuantiles del modelo envuelto si los tiene; si no, derivados del intervalo.

        **Por que hay dos caminos.** El conformal entrega *un* intervalo a *un*
        nivel, no una distribucion. Cuando envuelve un modelo puntual no queda otra
        que interpolar entre el limite inferior, la prediccion y el superior, y eso
        es lo que hacia siempre.

        Pero cuando el base es un modelo cuantilico, interpolar **descarta los
        boosters que se entrenaron con perdida cuantilica en cada nivel** y los
        reemplaza por la forma de la banda conformal. Eso no es una aproximacion
        mas gruesa, es otra distribucion: medido sobre 25 series con q* = 0,625, la
        banda daba q0,625 = 1,93 y el booster entrenado da 1,52, o sea una orden
        **21,5 % mas alta**. Y como la banda esta sobre-inflada — cubre 99,5 %
        cuando promete 90 % — el error va siempre en la misma direccion: pedir de
        mas. La interfaz mostraba esa cantidad como si fuera la salida del cuantil
        critico, que es lo que el README afirma.

        Asi que si el base sabe dar cuantiles, manda el base. El conformal sigue
        siendo el dueno del intervalo, que es para lo que tiene garantia de
        cobertura. La version completa de esto es CQR — conformalizar los cuantiles
        del base en vez de tratarlos como finales — y esta pendiente. Detalle en
        `docs/decisiones.md` D20.
        """
        if getattr(self.base, "supports_quantiles", False) and hasattr(
            self.base, "predict_quantile"
        ):
            return self.base.predict_quantile(future, quantiles)

        from blindside.models.base import quantile_col

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


class CQRForecaster(Forecaster):
    """Conformalized Quantile Regression. Envuelve un modelo **cuantilico**.

    Romano, Patterson y Candes, NeurIPS 2019 (https://arxiv.org/abs/1905.03222).

    Por que hace falta, medido
    ---------------------------
    El conformal de residuos absolutos de `ConformalForecaster` calcula **una**
    semiamplitud por paso de horizonte y se la pega a todas las series. Sobre este
    panel eso falla de una forma concreta: el p99 de la demanda diaria es doce
    veces la mediana, asi que el cuantil de residuos queda dominado por la cola y
    el intervalo sale enorme para la serie tipica. Medido: cubre **99,5 %** cuando
    promete 90 %, con un ancho de 9,5 veces el MAE. Un intervalo que cubre casi
    todo no dice nada — el caso degenerado seria `[0, infinito)`, que cubre el
    100 % y es inutil.

    Como lo arregla
    ---------------
    En vez de centrar un intervalo en la prediccion puntual, CQR **parte de los
    cuantiles que el modelo base ya estima** y les aplica una correccion escalar:

        E_i = max(q_lo(x_i) - y_i,  y_i - q_hi(x_i))      sobre calibracion
        Q   = cuantil (1 - alpha) de E, con correccion de muestra finita
        intervalo = [q_lo(x) - Q,  q_hi(x) + Q]

    Dos cosas lo hacen distinto y las dos importan:

    1. **El ancho es adaptativo por x sin pedirlo.** Los cuantiles del base ya son
       condicionales a las features, asi que una serie volatil recibe una banda
       ancha y una estable una angosta. La variante `adaptive` del conformal de
       residuos intenta lo mismo escalando por una dispersion *por serie*, que es
       una aproximacion mucho mas gruesa: no ve el dia, ni la promocion, ni el
       quiebre.

    2. **`Q` puede ser negativo.** Si los cuantiles del base ya cubren de mas, CQR
       **aprieta** el intervalo. El conformal de residuos solo puede ensanchar,
       porque su score es un valor absoluto. Esa es la razon de fondo por la que
       una sobre-cobertura de 99,5 % no se podia corregir antes: la mecanica no
       tenia forma de expresar "esto esta demasiado ancho".

    Lo que conserva del resto del modulo
    ------------------------------------
    La particion sigue siendo **temporal**, el score se agrupa por **paso de
    horizonte**, y el limite inferior se recorta en cero. Las tres razones son las
    mismas que estan arriba en el docstring del modulo.

    Lo que NO cambia
    ----------------
    La **cantidad a pedir no sale de aca**. Sale del booster entrenado en `q*`, que
    es lo que arregla D20. CQR corrige el intervalo que se dibuja y la cobertura
    que se reporta, que es una de las tres metricas de exito declaradas. Mezclar
    las dos cosas fue el defecto anterior y no se repite: `predict_quantile`
    delega en el base sin tocar.
    """

    supports_quantiles = True

    def __init__(
        self,
        base: Forecaster,
        *,
        alpha: float = 1 - cfg.FORECAST.coverage,
        calibration_days: int | None = None,
        horizon: int = cfg.FORECAST.horizon,
    ) -> None:
        super().__init__()
        if not 0 < alpha < 1:
            raise ValueError(f"alpha debe estar en (0, 1), llego {alpha}")
        if not getattr(base, "supports_quantiles", False):
            raise TypeError(
                f"CQR necesita un modelo base cuantilico, llego {type(base).__name__}. "
                "Para un modelo puntual esta ConformalForecaster."
            )
        self.base = base
        self.alpha = alpha
        self.horizon = horizon
        self.calibration_days = calibration_days or 2 * horizon
        self.name = f"cqr_{base.name}"
        #: Niveles que delimitan el intervalo nominal. Se redondean a proposito:
        #: `1 - 0.90` da 0,09999999999999998 en punto flotante, asi que `alpha/2`
        #: no es exactamente 0,05 y el base rechaza el nivel por no estar entre los
        #: que entreno. El nivel es una cantidad nominal que viene de la config, no
        #: un resultado de calculo, asi que canonizarlo es lo correcto.
        self.q_lo = round(alpha / 2, 10)
        self.q_hi = round(1 - alpha / 2, 10)
        #: Correccion conformal por paso de horizonte. **Puede ser negativa.**
        self.adjustment_: dict[int, float] = {}

    @property
    def quantiles(self) -> tuple[float, ...]:
        """Los del base, mas los dos niveles del intervalo si no estuvieran."""
        propios = tuple(getattr(self.base, "quantiles", ()) or ())
        return tuple(sorted(set(propios) | {self.q_lo, self.q_hi}))

    # -- Entrenamiento ----------------------------------------------------
    def _fit(self, history: pd.DataFrame, *, target: str) -> None:
        dates = pd.DatetimeIndex(sorted(history[S.DATE].unique()))
        if len(dates) <= self.calibration_days + self.horizon:
            raise ValueError(
                f"{self.name}: hacen falta mas de "
                f"{self.calibration_days + self.horizon} dias de train para "
                f"calibrar, llegaron {len(dates)}"
            )
        cut = dates[-self.calibration_days - 1]
        fit_part = history[history[S.DATE] <= cut]
        cal_part = history[history[S.DATE] > cut]

        scores = self._calibration_scores(fit_part, cal_part, cut, target=target)
        self.adjustment_ = _quantile_by_horizon(scores, alpha=self.alpha, column="score")
        log.info(
            "%s: calibrado con %d dias y %d scores; correcciones %s",
            self.name,
            self.calibration_days,
            len(scores),
            {h: round(v, 4) for h, v in self.adjustment_.items()},
        )
        negativas = sum(1 for v in self.adjustment_.values() if v < 0)
        if negativas:
            log.info(
                "%s: %d de %d correcciones son negativas, o sea que los cuantiles "
                "del base cubrian de mas y CQR aprieta el intervalo",
                self.name,
                negativas,
                len(self.adjustment_),
            )

        self.base.fit(history, target=target)

    def _calibration_scores(
        self, fit_part: pd.DataFrame, cal_part: pd.DataFrame, cut: pd.Timestamp, *, target: str
    ) -> pd.DataFrame:
        """Score de conformidad de CQR sobre el tramo de calibracion.

        `E_i = max(q_lo - y, y - q_hi)`. Es positivo cuando el punto quedo afuera
        del intervalo y **negativo cuando quedo adentro**, y esa es la mitad
        informativa: mide cuanto sobra de intervalo.
        """
        base = _clone(self.base)
        base.fit(fit_part, target=target)

        cols = [S.SERIES_ID, S.DATE, *S.HIERARCHY_COLS, *S.KNOWN_FUTURE_COLS]
        future = cal_part[[c for c in cols if c in cal_part.columns]].copy()
        future["h"] = (future[S.DATE] - cut).dt.days.astype("int16")
        future = future[future["h"] <= self.horizon].reset_index(drop=True)
        if future.empty:
            raise ValueError(f"{self.name}: el tramo de calibracion quedo vacio")

        preds = base.predict_quantile(future, (self.q_lo, self.q_hi))
        lo = preds[quantile_col(self.q_lo)].to_numpy(dtype="float64")
        hi = preds[quantile_col(self.q_hi)].to_numpy(dtype="float64")
        # Los boosters por cuantil pueden salir cruzados: se ordenan, que es la
        # correccion estandar y no cambia la cobertura marginal de cada nivel.
        lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)

        truth = cal_part.set_index([S.SERIES_ID, S.DATE])[target]
        keys = pd.MultiIndex.from_arrays([future[S.SERIES_ID], future[S.DATE]])
        actual = truth.reindex(keys).to_numpy(dtype="float64")

        return pd.DataFrame(
            {
                "h": future["h"].to_numpy(),
                S.SERIES_ID: future[S.SERIES_ID].to_numpy(),
                "score": np.maximum(lo - actual, actual - hi),
            }
        ).dropna(subset=["score"])

    # -- Prediccion -------------------------------------------------------
    def _predict(self, future: pd.DataFrame) -> np.ndarray:
        return self.base.predict(future).to_numpy()

    def _adjustment_for(self, future: pd.DataFrame) -> np.ndarray:
        if not self.adjustment_:
            raise RuntimeError(f"{self.name}: sin calibrar")
        # Un `h` fuera de lo calibrado usa el mayor disponible: extrapolar hacia
        # una correccion menor seria prometer precision que no se midio.
        fallback = max(self.adjustment_.values())
        return future["h"].map(self.adjustment_).fillna(fallback).to_numpy(dtype="float64")

    def predict_interval(self, future: pd.DataFrame) -> pd.DataFrame:
        """Cuantiles del base corridos por la correccion conformal."""
        preds = self.base.predict_quantile(future, (self.q_lo, self.q_hi))
        lo = preds[quantile_col(self.q_lo)].to_numpy(dtype="float64")
        hi = preds[quantile_col(self.q_hi)].to_numpy(dtype="float64")
        lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)

        adj = self._adjustment_for(future)
        lo = np.clip(lo - adj, 0.0, None)
        hi = hi + adj
        # Con una correccion negativa grande los limites podrian cruzarse. Se
        # colapsan al punto medio en vez de devolver un intervalo invertido.
        cruzado = hi < lo
        if cruzado.any():
            medio = (lo + hi) / 2.0
            lo = np.where(cruzado, medio, lo)
            hi = np.where(cruzado, medio, hi)

        point = self.predict(future).to_numpy()
        return pd.DataFrame(
            {"y_pred": point, "pred_lo": lo, "pred_hi": np.maximum(hi, lo)}, index=future.index
        )

    def predict_quantile(self, future: pd.DataFrame, quantiles: Sequence[float]) -> pd.DataFrame:
        """Delega en el base **sin tocar**. Ver la nota del docstring de la clase."""
        return self.base.predict_quantile(future, quantiles)

    def reorder_quantity(self, future: pd.DataFrame, **kwargs: object) -> pd.Series:
        """Delega la orden en el base, que es el que tiene el booster de q*."""
        base_reorder = getattr(self.base, "reorder_quantity", None)
        if base_reorder is None:
            raise AttributeError(f"{self.name}: el modelo base no emite orden")
        return base_reorder(future, **kwargs)


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


def _quantile_by_horizon(
    residuals: pd.DataFrame, *, alpha: float, column: str = "residual"
) -> dict[int, float]:
    """Cuantil conformal por paso de horizonte, con la correccion de muestra finita.

    El cuantil se toma en `ceil((n + 1)(1 - alpha)) / n` y no en `1 - alpha`. Es
    la correccion de muestra finita del split-conformal: sin ella la cobertura
    queda por debajo del nominal cuando `n` es chico, que es exactamente el caso
    aca — la calibracion son dos semanas.

    Sirve para las dos variantes. En el conformal de residuos la columna son
    residuos absolutos y el cuantil sale positivo; en CQR es un score con signo y
    **puede salir negativo**, que es como CQR aprieta un intervalo que cubre de
    mas. Por eso aca no se recorta en cero.
    """
    out: dict[int, float] = {}
    global_res = residuals[column].to_numpy(dtype="float64")
    for h, grp in residuals.groupby("h", observed=True):
        res = grp[column].to_numpy(dtype="float64")
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
    from blindside.evaluate import contracts as C
    from blindside.evaluate.metrics import empirical_coverage, mean_interval_width

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


__all__ = ["CQRForecaster", "ConformalForecaster", "coverage_by_group"]
