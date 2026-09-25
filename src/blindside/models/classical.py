"""SARIMA y Prophet: los contrastes clasicos que declara M6.

Por que estan aca y para que sirven
-----------------------------------
El proyecto defiende un modelo **global** — un solo LightGBM que ve las 3066
series a la vez y aprende de sus features compartidas. La objecion obvia a eso es
que el pronostico de series temporales tiene una tradicion de modelos **por
serie**, y que un global puede estar ganando solo porque se comparo contra
baselines simples. SARIMA y Prophet son la respuesta a esa objecion: son
per-serie, tienen decadas de uso, y si el global no les gana hay poco que
discutir.

No son baselines en el sentido de `baselines.py`. Ahi los cinco son
deterministas y sin hiperparametros, asi que su metrica es un hecho. Estos dos
**estiman parametros**, asi que su resultado depende de como se los configure y
eso hay que declararlo.

La decision de orden fija, y por que no es una trampa
----------------------------------------------------
`AutoARIMA` busca el orden por serie con una busqueda paso a paso. Medido sobre
este panel cuesta **2,3 segundos por serie**, o sea unas dos horas para 400 series
por 8 origenes. Un SARIMA de orden **fija y declarada** cuesta 85 ms — 27 veces
menos — y eso es lo que hace la comparacion posible dentro del presupuesto.

Podria parecer que fijar el orden lo perjudica a proposito. Por eso el modelo
acepta `auto=True`, y el notebook `03` mide las dos variantes sobre una porcion
chica para verificar que la orden fija no le esta regalando nada al global. El
orden por defecto — `(1,0,1)(1,0,0)[7]` — sale de lo que el panel muestra: una
serie diaria con estacionalidad semanal clara (ver notebook `01`) y sin tendencia
marcada en 97 dias, asi que `d=0` con un AR y un MA estacionales es el modelo
razonable de partida.

Sobre Prophet
-------------
`prophet` esta **comentado en requirements.txt** a proposito: su instalacion
arrastra un backend de Stan y el plan lo declara «aislado del camino critico». El
import es perezoso y el error, explicito. Con 97 dias de panel Prophet queda
reducido a tendencia lineal a tramos mas estacionalidad semanal: no hay ciclo
anual posible y los feriados ya viajan como covariable en el modelo global. Es un
contraste legitimo, pero conviene saber que en esta ventana no esta en su terreno.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from blindside import config as cfg
from blindside.models.base import SeriesLevelForecaster

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

#: Orden por defecto de SARIMA. Declarado y no buscado; ver el docstring del modulo.
DEFAULT_ORDER: tuple[int, int, int] = (1, 0, 1)
DEFAULT_SEASONAL_ORDER: tuple[int, int, int] = (1, 0, 0)

#: Dias minimos de historia para intentar ajustar. Por debajo de dos ciclos
#: estacionales completos el ajuste estacional no tiene con que estimarse y la
#: libreria puede devolver NaN en silencio.
MIN_DAYS = 21


class SarimaForecaster(SeriesLevelForecaster):
    """SARIMA por serie, con orden declarada. Contraste clasico de M6.

    Args:
        order: `(p, d, q)` no estacional.
        seasonal_order: `(P, D, Q)` estacional; el periodo lo da `season_length`.
        season_length: 7, la estacionalidad semanal del panel.
        auto: si es True usa `AutoARIMA` y busca el orden por serie. Cuesta ~27
            veces mas; existe para verificar que la orden fija no perjudica.
    """

    name = "sarima"

    def __init__(
        self,
        *,
        order: Sequence[int] = DEFAULT_ORDER,
        seasonal_order: Sequence[int] = DEFAULT_SEASONAL_ORDER,
        season_length: int = cfg.FORECAST.season_length,
        auto: bool = False,
    ) -> None:
        super().__init__()
        self.order = tuple(order)
        self.seasonal_order = tuple(seasonal_order)
        self.season_length = season_length
        self.auto = auto
        self.name = "sarima_auto" if auto else "sarima"
        #: Series en las que el ajuste fallo y se cayo al naive estacional. Se
        #: cuenta y se reporta: un modelo que falla en la mitad de las series y
        #: promedia bien no es un contraste, es un promedio de otra cosa.
        self.n_failed_: int = 0

    def _nuevo_modelo(self) -> Any:
        from statsforecast.models import ARIMA, AutoARIMA

        if self.auto:
            return AutoARIMA(season_length=self.season_length)
        return ARIMA(
            order=self.order,
            season_length=self.season_length,
            seasonal_order=self.seasonal_order,
        )

    def _fit_series(self, y: np.ndarray) -> np.ndarray | None:
        """Devuelve el pronostico ya calculado, no un objeto ajustado.

        `statsforecast` expone `forecast(y, h)` como una sola operacion que ajusta
        y predice, y guardar el objeto ajustado por serie costaria memoria sin
        ganar nada: el horizonte es fijo y conocido. Asi que el "estado" de esta
        serie **es** su pronostico a `horizon` pasos.
        """
        if y.size < MIN_DAYS:
            return None
        # Las series de baja rotacion pueden ser todo ceros. SARIMA sobre una
        # constante no tiene varianza que modelar y la libreria avisa o falla;
        # devolver el cero directo es mas honesto que un ajuste degenerado.
        if not np.any(y > 0):
            return np.zeros(cfg.FORECAST.horizon, dtype="float64")
        try:
            salida = self._nuevo_modelo().forecast(y=y, h=cfg.FORECAST.horizon)
            pred = np.asarray(salida["mean"], dtype="float64")
        except Exception as exc:  # noqa: BLE001 - la libreria levanta de todo
            log.debug("%s: ajuste fallido (%s); se cae al naive estacional", self.name, exc)
            self.n_failed_ += 1
            return None
        if not np.all(np.isfinite(pred)):
            self.n_failed_ += 1
            return None
        # La demanda no es negativa. SARIMA sobre una serie con ceros predice
        # negativo con facilidad, y un negativo no es informacion.
        return np.clip(pred, 0.0, None)

    def _predict_series(self, state: np.ndarray | None, steps: np.ndarray) -> np.ndarray:
        if state is None:
            # Fallback explicito y no un KeyError: el promedio global de la clase
            # base. `SeriesLevelForecaster` ya lo usa para series no vistas.
            return np.full(steps.shape[0], self._global_fallback, dtype="float64")
        # `steps` es 1-indexado. Un `h` mayor al horizonte entrenado recicla el
        # ultimo valor en vez de extrapolar, que es lo mismo que hacen los
        # baselines estacionales.
        idx = np.clip(steps - 1, 0, state.shape[0] - 1)
        return state[idx]

    def _fit(self, history: pd.DataFrame, *, target: str) -> None:
        self.n_failed_ = 0
        super()._fit(history, target=target)
        total = len(self._state)
        if self.n_failed_:
            log.warning(
                "%s: %d de %d series no ajustaron y usan el promedio global (%.1f %%)",
                self.name,
                self.n_failed_,
                total,
                100 * self.n_failed_ / max(total, 1),
            )


class ProphetForecaster(SeriesLevelForecaster):
    """Prophet por serie. Import perezoso: el paquete es opcional.

    Con 97 dias de panel queda reducido a tendencia lineal a tramos mas
    estacionalidad semanal, asi que la estacionalidad anual se apaga
    explicitamente en vez de dejar que la libreria decida y avise.
    """

    name = "prophet"

    def __init__(
        self,
        *,
        season_length: int = cfg.FORECAST.season_length,
        growth: str = "flat",
    ) -> None:
        super().__init__()
        self.season_length = season_length
        #: `flat` y no `linear` a proposito: con 97 dias una tendencia lineal
        #: ajustada por serie extrapola con mucha confianza a 7 dias y es la
        #: forma tipica en que Prophet falla en series cortas.
        self.growth = growth
        self.n_failed_: int = 0
        #: Fecha de referencia para reconstruir el eje temporal. Prophet necesita
        #: fechas reales y no indices, asi que se guarda el ultimo dia del train.
        self._last_date: pd.Timestamp | None = None

    @staticmethod
    def disponible() -> bool:
        """Si el paquete esta instalado. La interfaz y el arnes lo consultan."""
        from importlib.util import find_spec

        return find_spec("prophet") is not None

    def _fit(self, history: pd.DataFrame, *, target: str) -> None:
        if not self.disponible():
            raise ImportError(
                "prophet no esta instalado. Esta comentado en requirements.txt "
                "porque su instalacion arrastra un backend de Stan y el plan lo "
                "declara aislado del camino critico. Para correr este contraste: "
                "pip install prophet==1.1.6"
            )
        from blindside.data import schema as S

        self._last_date = pd.Timestamp(history[S.DATE].max())
        self.n_failed_ = 0
        super()._fit(history, target=target)
        if self.n_failed_:
            log.warning(
                "%s: %d de %d series no ajustaron", self.name, self.n_failed_, len(self._state)
            )

    def _fit_series(self, y: np.ndarray) -> np.ndarray | None:
        if y.size < MIN_DAYS or not np.any(y > 0):
            return np.zeros(cfg.FORECAST.horizon, dtype="float64") if y.size else None
        import logging as _logging

        from prophet import Prophet

        # Prophet escribe en stdout por cada serie. Con cientos de series eso
        # inunda el log y esconde lo que importa.
        _logging.getLogger("cmdstanpy").setLevel(_logging.ERROR)
        _logging.getLogger("prophet").setLevel(_logging.ERROR)

        assert self._last_date is not None
        fechas = pd.date_range(end=self._last_date, periods=y.size, freq="D")
        df = pd.DataFrame({"ds": fechas, "y": y})
        try:
            modelo = Prophet(
                growth=self.growth,
                yearly_seasonality=False,
                weekly_seasonality=True,
                daily_seasonality=False,
                uncertainty_samples=0,  # no se usa el intervalo de Prophet
            )
            modelo.fit(df)
            futuro = modelo.make_future_dataframe(periods=cfg.FORECAST.horizon, freq="D")
            pred = modelo.predict(futuro.tail(cfg.FORECAST.horizon))["yhat"].to_numpy()
        except Exception as exc:  # noqa: BLE001
            log.debug("%s: ajuste fallido (%s)", self.name, exc)
            self.n_failed_ += 1
            return None
        if not np.all(np.isfinite(pred)):
            self.n_failed_ += 1
            return None
        return np.clip(np.asarray(pred, dtype="float64"), 0.0, None)

    def _predict_series(self, state: np.ndarray | None, steps: np.ndarray) -> np.ndarray:
        if state is None:
            return np.full(steps.shape[0], self._global_fallback, dtype="float64")
        idx = np.clip(steps - 1, 0, state.shape[0] - 1)
        return state[idx]


__all__ = [
    "DEFAULT_ORDER",
    "DEFAULT_SEASONAL_ORDER",
    "ProphetForecaster",
    "SarimaForecaster",
]
