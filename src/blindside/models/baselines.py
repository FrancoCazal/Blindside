"""Baselines. El piso contra el que se mide todo lo demas.

Son cuatro y cada uno responde una objecion distinta:

`NaiveForecaster`
    El ultimo valor. El piso absoluto. Si un modelo no le gana a esto, no hay
    nada que discutir.
`SeasonalNaiveForecaster`
    El mismo dia de la semana anterior. **Es el denominador de MASE** y es lo que
    de hecho hace la operacion cuando decide "el martes vendemos como el martes
    pasado". Ganarle a este es el objetivo del proyecto.
`MovingAverageForecaster`
    Promedio de las ultimas k semanas. Es la politica real de la mayoria de las
    pymes, la que el ROI compara contra el modelo.
`CrostonForecaster`
    Para las series intermitentes de la cola. El naive estacional falla ahi de
    una forma particular — predice cero cada vez que el dia de referencia fue
    cero — y sin Croston la comparacion en baja rotacion seria injusta a favor
    del modelo complejo.

Todos son deterministas y no tienen hiperparametros que tunear, asi que su
metrica es un hecho y no un resultado de busqueda. Eso es justo lo que se
necesita de un baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from blindside import config as cfg
from blindside.models.base import Forecaster, SeriesLevelForecaster


class NaiveForecaster(SeriesLevelForecaster):
    """Ultimo valor observado, repetido en todo el horizonte."""

    name = "naive"

    def _fit_series(self, y: np.ndarray) -> float:
        return float(y[-1]) if y.size else 0.0

    def _predict_series(self, state: float, steps: np.ndarray) -> np.ndarray:
        return np.full(steps.shape[0], state, dtype="float64")


class SeasonalNaiveForecaster(SeriesLevelForecaster):
    """Mismo dia de la semana anterior. Es el denominador de MASE.

    Para `h > m` se recicla el ultimo ciclo completo, que es la definicion
    estandar: el paso `h` toma el valor de `t - m + ((h - 1) mod m) + 1`.
    """

    name = "seasonal_naive"

    def __init__(self, season_length: int = cfg.FORECAST.season_length) -> None:
        super().__init__()
        self.season_length = season_length

    def _fit_series(self, y: np.ndarray) -> np.ndarray:
        m = self.season_length
        if y.size == 0:
            return np.zeros(m)
        if y.size < m:
            # Serie mas corta que un ciclo: se completa con su propia media.
            pad = np.full(m - y.size, float(y.mean()))
            return np.concatenate([pad, y])
        return y[-m:].astype("float64")

    def _predict_series(self, state: np.ndarray, steps: np.ndarray) -> np.ndarray:
        m = self.season_length
        idx = (steps - 1) % m
        return state[idx]


@dataclass
class _MAState:
    level: float


class MovingAverageForecaster(SeriesLevelForecaster):
    """Media movil de las ultimas `window` observaciones.

    Con `window = 21` son tres semanas, que es lo que hace a mano un responsable
    de compras. Es la **politica actual** del ROI (seccion 11 del plan), asi que
    su metrica no es solo un baseline: es el punto de partida economico.
    """

    name = "moving_average"

    def __init__(self, window: int = 21) -> None:
        super().__init__()
        self.window = window

    def _fit_series(self, y: np.ndarray) -> _MAState:
        if y.size == 0:
            return _MAState(0.0)
        return _MAState(float(y[-self.window :].mean()))

    def _predict_series(self, state: _MAState, steps: np.ndarray) -> np.ndarray:
        return np.full(steps.shape[0], state.level, dtype="float64")


class SeasonalMovingAverageForecaster(SeriesLevelForecaster):
    """Media del mismo dia de la semana en las ultimas `n_cycles` semanas.

    Combina lo de los dos anteriores y suele ser el baseline mas duro de vencer.
    Se incluye porque un modelo que le gana al naive estacional pero no a esto no
    aporta gran cosa, y omitirlo seria elegir un rival facil.
    """

    name = "seasonal_moving_average"

    def __init__(self, season_length: int = cfg.FORECAST.season_length, n_cycles: int = 4) -> None:
        super().__init__()
        self.season_length = season_length
        self.n_cycles = n_cycles

    def _fit_series(self, y: np.ndarray) -> np.ndarray:
        m, k = self.season_length, self.n_cycles
        if y.size == 0:
            return np.zeros(m)
        needed = m * k
        tail = y[-needed:] if y.size >= needed else y
        # Se alinea el final de la serie con el final del ciclo para que la
        # posicion 0 del estado sea el dia siguiente al ultimo observado.
        out = np.empty(m, dtype="float64")
        for offset in range(m):
            # Paso h = offset + 1 corresponde a los valores en t - m + offset + 1,
            # t - 2m + offset + 1, ...
            picks = [
                tail[-(m * c) + offset] for c in range(1, k + 1) if (m * c) - offset <= tail.size
            ]
            out[offset] = float(np.mean(picks)) if picks else float(tail.mean())
        return out

    def _predict_series(self, state: np.ndarray, steps: np.ndarray) -> np.ndarray:
        return state[(steps - 1) % self.season_length]


@dataclass
class _CrostonState:
    """Nivel de demanda y intervalo entre demandas."""

    demand_level: float
    interval: float

    @property
    def rate(self) -> float:
        return self.demand_level / self.interval if self.interval > 0 else 0.0


class CrostonForecaster(SeriesLevelForecaster):
    """Croston con la correccion de sesgo de Syntetos-Boylan (SBA).

    Croston clasico suaviza por separado el **tamano** de las demandas no nulas y
    el **intervalo** entre ellas, y estima la tasa como el cociente. El estimador
    original tiene sesgo positivo conocido; SBA lo corrige multiplicando por
    `1 - alpha/2`, y por eso es la variante que se usa aca.

    Aplica a la cola de baja rotacion, que en perecederos es la mayoria del
    catalogo. El naive estacional ahi predice cero cada vez que el dia de
    referencia fue cero, lo que produce un MASE enganosamente bueno en series
    casi vacias; Croston da la comparacion honesta.
    """

    name = "croston_sba"

    def __init__(self, alpha: float = 0.1) -> None:
        super().__init__()
        if not 0 < alpha < 1:
            raise ValueError("alpha debe estar en (0, 1)")
        self.alpha = alpha

    def _fit_series(self, y: np.ndarray) -> _CrostonState:
        nz = np.flatnonzero(y > 0)
        if nz.size == 0:
            return _CrostonState(0.0, 1.0)
        sizes = y[nz]
        intervals = np.diff(np.concatenate([[-1], nz]))

        level = float(sizes[0])
        interval = float(intervals[0]) if intervals.size else 1.0
        for size, gap in zip(sizes[1:], intervals[1:], strict=True):
            level += self.alpha * (float(size) - level)
            interval += self.alpha * (float(gap) - interval)
        return _CrostonState(level, max(interval, 1.0))

    def _predict_series(self, state: _CrostonState, steps: np.ndarray) -> np.ndarray:
        rate = state.rate * (1 - self.alpha / 2)  # correccion SBA
        return np.full(steps.shape[0], rate, dtype="float64")


class ZeroForecaster(SeriesLevelForecaster):
    """Predice cero siempre. Existe para los tests, no para el reporte.

    Sirve como control: una metrica que no empeora al pasar a este modelo esta
    mal calculada.
    """

    name = "zero"

    def _fit_series(self, y: np.ndarray) -> Any:
        return None

    def _predict_series(self, state: Any, steps: np.ndarray) -> np.ndarray:
        return np.zeros(steps.shape[0], dtype="float64")


#: Los cuatro baselines de la metodologia, mas el estacional-movil como quinto.
#: `seasonal_naive` es el que se usa como referencia en `improvement_vs_baseline`.
BASELINE_REGISTRY: dict[str, type[Forecaster]] = {
    "naive": NaiveForecaster,
    "seasonal_naive": SeasonalNaiveForecaster,
    "moving_average": MovingAverageForecaster,
    "seasonal_moving_average": SeasonalMovingAverageForecaster,
    "croston_sba": CrostonForecaster,
}

#: Denominador de MASE y referencia del objetivo SMART.
REFERENCE_BASELINE = "seasonal_naive"


def make_baselines(*, season_length: int = cfg.FORECAST.season_length) -> list[Forecaster]:
    """Instancia los cinco baselines con la estacionalidad del proyecto."""
    return [
        NaiveForecaster(),
        SeasonalNaiveForecaster(season_length=season_length),
        MovingAverageForecaster(window=3 * season_length),
        SeasonalMovingAverageForecaster(season_length=season_length),
        CrostonForecaster(),
    ]


def current_policy_forecast(
    history: pd.DataFrame, future: pd.DataFrame, *, target: str, window: int = 21
) -> pd.Series:
    """Pronostico de la **politica actual** para el simulador de ROI.

    Se modela como reposicion segun promedio movil reciente, que es lo que hace
    la mayoria de las pymes. Es una funcion suelta y no un `Forecaster` porque el
    simulador de politica la necesita sin el ceremonial de entrenar y serializar.
    """
    model = MovingAverageForecaster(window=window)
    model.fit(history, target=target)
    return model.predict(future)


__all__ = [
    "BASELINE_REGISTRY",
    "REFERENCE_BASELINE",
    "CrostonForecaster",
    "MovingAverageForecaster",
    "NaiveForecaster",
    "SeasonalMovingAverageForecaster",
    "SeasonalNaiveForecaster",
    "ZeroForecaster",
    "current_policy_forecast",
    "make_baselines",
]
