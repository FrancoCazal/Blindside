"""Backtesting de origen movil.

Split **estrictamente temporal**, nunca aleatorio. Un `KFold` sobre series
temporales entrena con el futuro y evalua el pasado, y produce metricas que no
significan nada.

Anatomia de un fold, que es donde vive el detalle importante:

    ... train hasta T ...  |  gap  |  test T+1 .. T+H
                           ^
                        origen T

El **gap** entre el fin del train y el comienzo del test es igual al horizonte, y
en este diseno sale gratis: el test empieza en `T+1` y termina en `T+H`, asi que
el ultimo dia de test esta a `H` dias del ultimo dia de train. Eso es exactamente
la situacion de produccion — se decide con lo que hay hoy y las consecuencias
llegan hasta `H` dias despues.

Ventana **expansiva** y no deslizante: cada fold sucesivo entrena con mas
historia. Con 97 dias por serie, tirar historia vieja no tiene sentido.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from dfcore import config as cfg
from dfcore.data import schema as S

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


@dataclass(frozen=True)
class Fold:
    """Un origen de backtest.

    Atributos:
        index: numero de fold, desde 0.
        origin: ultima fecha visible para entrenar. El modelo conoce `y[origin]`.
        train_end: alias de `origin`, por legibilidad en los asserts.
        test_start / test_end: `origin+1` y `origin+horizon`.
        horizon: pasos adelante.
    """

    index: int
    origin: pd.Timestamp
    horizon: int

    @property
    def train_end(self) -> pd.Timestamp:
        return self.origin

    @property
    def test_start(self) -> pd.Timestamp:
        return self.origin + pd.Timedelta(days=1)

    @property
    def test_end(self) -> pd.Timestamp:
        return self.origin + pd.Timedelta(days=self.horizon)

    @property
    def gap_days(self) -> int:
        """Distancia entre el ultimo dia de train y el ultimo de test."""
        return self.horizon

    def train_mask(self, dates: pd.Series) -> np.ndarray:
        return (dates <= self.origin).to_numpy()

    def test_mask(self, dates: pd.Series) -> np.ndarray:
        return ((dates >= self.test_start) & (dates <= self.test_end)).to_numpy()

    def __repr__(self) -> str:
        return (
            f"Fold({self.index}: train<={self.origin.date()}, "
            f"test {self.test_start.date()}..{self.test_end.date()})"
        )


class RollingOriginSplitter:
    """Genera los origenes de backtest y valida que sean suficientes.

    El numero de origenes que caben es una funcion de la historia disponible:

        n_max = (n_dias - min_train_days - horizon) // step + 1

    Si el panel no alcanza para `n_origins`, falla con el numero que si entra en
    vez de correr con menos en silencio. Reportar 3 origenes donde la
    metodologia declara 8 es el tipo de discrepancia que un panel encuentra.
    """

    def __init__(
        self,
        *,
        horizon: int = cfg.FORECAST.horizon,
        n_origins: int = cfg.FORECAST.n_origins,
        step: int = cfg.FORECAST.step,
        min_train_days: int = cfg.FORECAST.min_train_days,
    ) -> None:
        if horizon < 1:
            raise ValueError("horizon debe ser >= 1")
        if step < 1:
            raise ValueError("step debe ser >= 1")
        self.horizon = horizon
        self.n_origins = n_origins
        self.step = step
        self.min_train_days = min_train_days

    # -- API --------------------------------------------------------------
    def max_origins(self, n_days: int) -> int:
        usable = n_days - self.min_train_days - self.horizon
        if usable < 0:
            return 0
        return usable // self.step + 1

    def origins(self, dates: Sequence[pd.Timestamp] | pd.DatetimeIndex) -> list[pd.Timestamp]:
        """Origenes elegidos: los ultimos `n_origins`, separados por `step` dias.

        Se toman los **mas recientes** posibles. Un origen viejo entrena con poca
        historia y evalua un regimen que quizas ya no existe; los recientes son
        los que se parecen a la situacion en la que el modelo va a operar.
        """
        uniq = pd.DatetimeIndex(sorted(pd.unique(pd.DatetimeIndex(dates))))
        n_days = len(uniq)
        available = self.max_origins(n_days)
        if available < self.n_origins:
            raise ValueError(
                f"el panel tiene {n_days} dias distintos y solo admite {available} "
                f"origenes con horizonte {self.horizon}, paso {self.step} y "
                f"min_train_days {self.min_train_days}; la metodologia pide "
                f"{self.n_origins}. Bajar n_origins, bajar min_train_days o "
                f"acortar el horizonte, y declararlo."
            )
        # El ultimo origen deja exactamente `horizon` dias de test por delante.
        last_pos = n_days - self.horizon - 1
        positions = [last_pos - self.step * k for k in range(self.n_origins)][::-1]
        return [uniq[p] for p in positions]

    def split(self, panel: pd.DataFrame, *, date_col: str = S.DATE) -> Iterator[Fold]:
        """Itera los folds en orden cronologico."""
        for i, origin in enumerate(self.origins(panel[date_col])):
            yield Fold(index=i, origin=pd.Timestamp(origin), horizon=self.horizon)

    def folds(self, panel: pd.DataFrame, *, date_col: str = S.DATE) -> list[Fold]:
        return list(self.split(panel, date_col=date_col))


def naive_seasonal_scale(
    history: pd.DataFrame,
    *,
    target: str,
    season_length: int = cfg.FORECAST.season_length,
    floor: float = 1e-3,
) -> pd.Series:
    """Denominador de MASE por serie, calculado **solo con el train del fold**.

    Es el error absoluto medio en muestra del naive estacional:

        scale = mean(|y[t] - y[t-m]|)  para t en el train

    Que se calcule con el train y no con la serie completa no es un detalle: si
    el denominador viera el test, MASE quedaria contaminado de una forma que no
    se nota en el numero final. El contrato de backtest transporta este valor
    justamente para que no se recalcule despues con datos que no correspondan.

    Series planas dan escala cero y volverian MASE infinito. Se aplica un piso y
    se prefiere eso a descartar la serie: descartarla sesgaria la metrica hacia
    las series faciles.
    """
    df = history.sort_values([S.SERIES_ID, S.DATE], kind="mergesort")
    g = df.groupby(S.SERIES_ID, observed=True)[target]
    diff = (df[target] - g.shift(season_length)).abs()
    scale = diff.groupby(df[S.SERIES_ID], observed=True).mean()
    global_scale = float(np.nanmax([diff.mean(), floor]))
    return scale.fillna(global_scale).clip(lower=floor).rename("naive_scale")


def rotation_bands(
    history: pd.DataFrame,
    *,
    target: str,
    quantiles: tuple[float, float] = (0.5, 0.85),
) -> pd.Series:
    """Clasifica cada serie en baja, media o alta rotacion.

    Se calcula con el **train del primer origen**, nunca con la serie completa:
    la banda se usa para desagregar el reporte de metricas, y definirla con datos
    de test seria elegir los grupos sabiendo el resultado.

    Existe porque la metodologia exige reportar por banda de rotacion. Que el
    modelo complejo no le gane al ingenuo en baja rotacion es un resultado
    esperado y publicado, no un fracaso, pero solo se puede afirmar si la
    desagregacion existe.
    """
    mean_demand = history.groupby(S.SERIES_ID, observed=True)[target].mean()
    lo, hi = mean_demand.quantile(list(quantiles))
    bands = pd.Series("media", index=mean_demand.index, dtype="object")
    bands[mean_demand <= lo] = "baja"
    bands[mean_demand > hi] = "alta"
    return bands.rename("rotation_band")


__all__ = [
    "Fold",
    "RollingOriginSplitter",
    "naive_seasonal_scale",
    "rotation_bands",
]
