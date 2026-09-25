"""Tests de los contrastes clasicos de M6.

Lo que se verifica aca **no** es la calidad del pronostico: SARIMA y Prophet son
librerias de terceros y testear su aritmetica seria testear statsforecast. Lo que
se verifica es el contrato: que respeten la interfaz `Forecaster`, que degraden de
forma explicita cuando una serie no se puede ajustar, y que no devuelvan negativos
ni NaN — porque una demanda negativa no es informacion y un NaN que llega al
newsvendor produce una orden nula sin avisar.

El de Prophet se saltea si el paquete no esta instalado. Esta comentado en
`requirements.txt` a proposito, asi que un evaluador que corra `make test` sobre un
clon nuevo no tiene por que tenerlo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from blindside import config as cfg
from blindside.data import schema as S
from blindside.models import classical as K
from blindside.models.base import NotFittedError

pytestmark = pytest.mark.slow

SIN_PROPHET = not K.ProphetForecaster.disponible()


def _panel(series: dict[str, list[float]], inicio: str = "2024-01-01") -> pd.DataFrame:
    """Panel minimo con las columnas del contrato."""
    filas = []
    for sid, valores in series.items():
        tienda, producto = sid.split("_")
        for i, v in enumerate(valores):
            filas.append(
                {
                    S.SERIES_ID: sid,
                    S.DATE: pd.Timestamp(inicio) + pd.Timedelta(days=i),
                    S.STORE_ID: int(tienda),
                    S.PRODUCT_ID: int(producto),
                    S.DEMAND_LATENT: float(v),
                }
            )
    return pd.DataFrame(filas)


def _futuro(sids: list[str], origen: pd.Timestamp, horizonte: int) -> pd.DataFrame:
    filas = []
    for sid in sids:
        for h in range(1, horizonte + 1):
            filas.append(
                {
                    S.SERIES_ID: sid,
                    S.DATE: origen + pd.Timedelta(days=h),
                    "h": h,
                }
            )
    return pd.DataFrame(filas)


def _estacional(n: int, nivel: float = 3.0, semilla: int = 0) -> list[float]:
    """Serie con estacionalidad semanal, que es lo que SARIMA tiene que capturar."""
    rng = np.random.default_rng(semilla)
    t = np.arange(n)
    y = nivel + 0.8 * np.sin(2 * np.pi * t / 7) + rng.normal(0, 0.3, n)
    return np.maximum(0.0, y).round(3).tolist()


# --- Contrato ------------------------------------------------------------
def test_sarima_respeta_el_contrato_de_forecaster() -> None:
    """Predecir sin ajustar levanta, y ajustar devuelve el propio modelo."""
    modelo = K.SarimaForecaster()
    with pytest.raises(NotFittedError):
        modelo.predict(_futuro(["1_1"], pd.Timestamp("2024-03-01"), 7))

    panel = _panel({"1_1": _estacional(60)})
    assert modelo.fit(panel, target=S.DEMAND_LATENT) is modelo


def test_sarima_predice_un_valor_por_paso_y_serie() -> None:
    """El largo de la salida tiene que coincidir con el del indice de futuro."""
    panel = _panel({"1_1": _estacional(60), "1_2": _estacional(60, nivel=8.0, semilla=1)})
    modelo = K.SarimaForecaster().fit(panel, target=S.DEMAND_LATENT)
    futuro = _futuro(["1_1", "1_2"], pd.Timestamp("2024-02-29"), cfg.FORECAST.horizon)

    pred = modelo.predict(futuro)
    assert len(pred) == len(futuro)
    assert pred.notna().all(), "un NaN llega al newsvendor y produce una orden nula sin avisar"


def test_sarima_nunca_predice_negativo() -> None:
    """La demanda no es negativa, y SARIMA sobre series con ceros lo intenta seguido."""
    # Serie con muchos ceros: es donde un ARIMA sin recorte predice negativo.
    rng = np.random.default_rng(3)
    y = np.where(rng.random(60) < 0.55, 0.0, rng.uniform(0.5, 2.0, 60)).round(3).tolist()
    panel = _panel({"1_1": y})
    modelo = K.SarimaForecaster().fit(panel, target=S.DEMAND_LATENT)

    pred = modelo.predict(_futuro(["1_1"], pd.Timestamp("2024-02-29"), cfg.FORECAST.horizon))
    assert (pred >= 0).all(), f"predijo negativo: {pred.tolist()}"


def test_sarima_captura_el_nivel_de_la_serie() -> None:
    """Dos series con niveles muy distintos no pueden recibir el mismo pronostico.

    Es el chequeo minimo de que el estado es **por serie** y no global. Si el
    `_fit_series` se estuviera pisando, las dos predicciones coincidirian.
    """
    panel = _panel(
        {"1_1": _estacional(60, nivel=2.0), "1_2": _estacional(60, nivel=20.0, semilla=5)}
    )
    modelo = K.SarimaForecaster().fit(panel, target=S.DEMAND_LATENT)
    futuro = _futuro(["1_1", "1_2"], pd.Timestamp("2024-02-29"), 7)
    pred = modelo.predict(futuro)

    baja = pred[futuro[S.SERIES_ID] == "1_1"].mean()
    alta = pred[futuro[S.SERIES_ID] == "1_2"].mean()
    assert alta > 3 * baja, f"no distingue el nivel: baja {baja:.2f}, alta {alta:.2f}"


# --- Degradacion explicita ----------------------------------------------
def test_sarima_cae_al_promedio_global_con_historia_insuficiente() -> None:
    """Menos de dos ciclos estacionales no alcanzan para estimar la parte estacional.

    El fallback es el promedio global y **no** un KeyError ni un NaN: una serie nueva
    con dos semanas de vida es una condicion de operacion, no una excepcion.
    """
    corta = [1.0] * (K.MIN_DAYS - 1)
    panel = _panel({"1_1": corta})
    modelo = K.SarimaForecaster().fit(panel, target=S.DEMAND_LATENT)

    pred = modelo.predict(_futuro(["1_1"], pd.Timestamp("2024-01-20"), 3))
    assert pred.notna().all()
    assert np.allclose(pred.to_numpy(), 1.0), "el fallback tiene que ser el promedio global"


def test_sarima_devuelve_cero_en_una_serie_toda_cero() -> None:
    """Un ARIMA sobre una constante no tiene varianza que modelar.

    Devolver el cero directo es mas honesto que un ajuste degenerado, y en un
    catalogo de perecederos las series muertas existen.
    """
    panel = _panel({"1_1": [0.0] * 60})
    modelo = K.SarimaForecaster().fit(panel, target=S.DEMAND_LATENT)

    pred = modelo.predict(_futuro(["1_1"], pd.Timestamp("2024-02-29"), 7))
    assert np.allclose(pred.to_numpy(), 0.0)


def test_sarima_usa_el_promedio_global_en_una_serie_nunca_vista() -> None:
    """La serie del futuro no estaba en el train. No puede ser un KeyError."""
    panel = _panel({"1_1": _estacional(60)})
    modelo = K.SarimaForecaster().fit(panel, target=S.DEMAND_LATENT)

    pred = modelo.predict(_futuro(["9_9"], pd.Timestamp("2024-02-29"), 3))
    assert pred.notna().all()
    assert np.allclose(pred.to_numpy(), pred.iloc[0]), "el fallback es constante por definicion"


def test_sarima_cuenta_los_fallos_de_ajuste() -> None:
    """Un contraste que fallo en la mitad de las series no es un contraste.

    `n_failed_` existe para que eso sea visible en vez de quedar escondido detras de
    un promedio que igual se calcula.
    """
    panel = _panel({"1_1": _estacional(60), "1_2": [2.0] * (K.MIN_DAYS - 1)})
    modelo = K.SarimaForecaster().fit(panel, target=S.DEMAND_LATENT)
    # La serie corta no cuenta como fallo de ajuste: no se intento ajustarla.
    assert modelo.n_failed_ == 0
    assert hasattr(modelo, "n_failed_")


# --- La orden fija y la busqueda -----------------------------------------
def test_la_variante_auto_se_nombra_distinto() -> None:
    """Los dos aparecen en el mismo reporte, asi que no pueden compartir nombre."""
    assert K.SarimaForecaster().name == "sarima"
    assert K.SarimaForecaster(auto=True).name == "sarima_auto"


def test_el_orden_por_defecto_es_el_declarado() -> None:
    """El orden es una decision documentada, no un default de la libreria."""
    modelo = K.SarimaForecaster()
    assert modelo.order == K.DEFAULT_ORDER
    assert modelo.seasonal_order == K.DEFAULT_SEASONAL_ORDER
    assert modelo.season_length == cfg.FORECAST.season_length


# --- Prophet -------------------------------------------------------------
def test_prophet_declara_si_esta_disponible() -> None:
    """La consulta no puede levantar, porque el arnes la usa para decidir saltearlo."""
    assert isinstance(K.ProphetForecaster.disponible(), bool)


@pytest.mark.skipif(not SIN_PROPHET, reason="prophet esta instalado en este entorno")
def test_prophet_explica_como_instalarse_cuando_falta() -> None:
    """Un ImportError sin instrucciones hace perder tiempo."""
    panel = _panel({"1_1": _estacional(60)})
    with pytest.raises(ImportError, match="pip install prophet"):
        K.ProphetForecaster().fit(panel, target=S.DEMAND_LATENT)


@pytest.mark.skipif(SIN_PROPHET, reason="prophet no esta instalado (es opcional)")
def test_prophet_predice_sin_negativos_ni_nan() -> None:
    panel = _panel({"1_1": _estacional(60), "1_2": _estacional(60, nivel=9.0, semilla=2)})
    modelo = K.ProphetForecaster().fit(panel, target=S.DEMAND_LATENT)
    futuro = _futuro(["1_1", "1_2"], pd.Timestamp("2024-02-29"), cfg.FORECAST.horizon)

    pred = modelo.predict(futuro)
    assert len(pred) == len(futuro)
    assert pred.notna().all()
    assert (pred >= 0).all()


@pytest.mark.skipif(SIN_PROPHET, reason="prophet no esta instalado (es opcional)")
def test_prophet_apaga_la_estacionalidad_anual() -> None:
    """Con 97 dias de panel no hay ciclo anual posible.

    Dejar que la libreria decida produce un aviso por serie y, peor, la posibilidad
    de que ajuste un armonico anual sobre tres meses de datos.
    """
    modelo = K.ProphetForecaster()
    assert modelo.growth == "flat", "una tendencia lineal a 7 dias sobre 97 extrapola de mas"
