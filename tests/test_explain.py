"""Tests de la capa de atribucion.

El chequeo que importa es la **identidad de SHAP**: el valor base mas la suma de
todas las contribuciones tiene que dar exactamente la prediccion del modelo. Si eso
no cierra, la explicacion es de otra fila, de otro cuantil, o de otro modelo — y una
explicacion que no corresponde a la prediccion mostrada es peor que no explicar.

Usan `recovered_panel` de `conftest.py` y no un panel propio: el modelo tabular exige
el esquema completo, y armar uno aparte se desincronizaria del contrato.
"""

from __future__ import annotations

import pandas as pd
import pytest

from blindside import config as cfg
from blindside.data import schema as S
from blindside.explain import (
    NoExplicableError,
    atribucion_global,
    atribuir,
    modelo_explicable,
)
from blindside.models.baselines import NaiveForecaster
from blindside.models.gbdt import LightGBMForecaster, LightGBMQuantileForecaster

pytestmark = pytest.mark.slow


class Envoltorio:
    """Simulacro de una capa que envuelve al modelo, como hace el conformal."""

    name = "envoltorio"

    def __init__(self, base) -> None:
        self.base = base


@pytest.fixture(scope="module")
def origen(recovered_panel: pd.DataFrame) -> pd.Timestamp:
    """Un origen con dias por delante, para que el futuro caiga dentro del panel."""
    return pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))[-8]


@pytest.fixture(scope="module")
def historia(recovered_panel: pd.DataFrame, origen: pd.Timestamp) -> pd.DataFrame:
    return recovered_panel[recovered_panel[S.DATE] <= origen]


@pytest.fixture(scope="module")
def futuro(historia: pd.DataFrame, origen: pd.Timestamp) -> pd.DataFrame:
    """Indice de futuro sin columna de target, como exige el contrato del modelo."""
    sids = sorted(historia[S.SERIES_ID].unique())[:3]
    filas = [
        {S.SERIES_ID: sid, S.DATE: origen + pd.Timedelta(days=h), "h": h}
        for sid in sids
        for h in range(1, 4)
    ]
    return pd.DataFrame(filas)


@pytest.fixture(scope="module")
def modelo(historia: pd.DataFrame) -> LightGBMForecaster:
    return LightGBMForecaster(n_estimators=40, max_train_origins=6).fit(
        historia, target=S.DEMAND_LATENT
    )


@pytest.fixture(scope="module")
def cuantilico(historia: pd.DataFrame) -> LightGBMQuantileForecaster:
    return LightGBMQuantileForecaster(
        quantiles=(0.5, cfg.ECONOMICS.critical_fraction),
        n_estimators=40,
        max_train_origins=6,
    ).fit(historia, target=S.DEMAND_LATENT)


@pytest.fixture(scope="module")
def naive(historia: pd.DataFrame) -> NaiveForecaster:
    return NaiveForecaster().fit(historia, target=S.DEMAND_LATENT)


# --- La identidad, que es lo que hace verificable la explicacion ----------
def test_la_atribucion_reconstruye_la_prediccion(futuro, modelo) -> None:
    """valor_base + suma de TODAS las contribuciones = prediccion del modelo.

    Se prueba con top_k=1 a proposito: si el `resto` no estuviera bien calculado,
    la identidad fallaria justo ahi y no con un top_k grande donde el resto es chico.
    """
    fila = futuro.head(1)
    esperado = float(modelo.predict(fila).iloc[0])

    for top_k in (1, 3, 100):
        atr = atribuir(modelo, fila, top_k=top_k)
        assert atr.prediccion_reconstruida == pytest.approx(esperado, abs=1e-6), (
            f"la identidad de SHAP no cierra con top_k={top_k}"
        )


def test_el_recorte_devuelve_los_mas_influyentes(futuro, modelo) -> None:
    """top_k tiene que dar los de mayor valor absoluto, ordenados."""
    fila = futuro.head(1)
    todos = atribuir(modelo, fila, top_k=1000)
    pocos = atribuir(modelo, fila, top_k=3)

    magnitudes = [abs(a.contribucion) for a in pocos.aportes]
    assert magnitudes == sorted(magnitudes, reverse=True), "no vienen ordenados"

    mayores = sorted((abs(a.contribucion) for a in todos.aportes), reverse=True)[:3]
    assert magnitudes == pytest.approx(mayores)


def test_declara_cuantas_features_tenia(futuro, modelo) -> None:
    """Sin el total, un top_k de 5 sobre 73 features parece la explicacion completa."""
    atr = atribuir(modelo, futuro.head(1), top_k=5)
    assert atr.n_features > 5
    assert len(atr.aportes) == 5


def test_el_cuantilico_explica_el_cuantil_critico_por_defecto(futuro, cuantilico) -> None:
    """La cifra que se muestra es la orden, que sale de q*, no de la mediana.

    Explicar la mediana seria explicar un numero distinto del que el usuario ve.
    """
    fila = futuro.head(1)
    atr = atribuir(cuantilico, fila)

    q_critico = cfg.ECONOMICS.critical_fraction
    esperado = float(cuantilico.predict_quantile(fila, [q_critico]).iloc[0, 0])
    assert atr.prediccion_reconstruida == pytest.approx(esperado, abs=1e-6)


def test_pedir_otro_cuantil_explica_ese_cuantil(futuro, cuantilico) -> None:
    """Cada booster es un modelo distinto, asi que su descomposicion difiere."""
    fila = futuro.head(1)
    mediana = atribuir(cuantilico, fila, quantile=0.5)

    esperado = float(cuantilico.predict_quantile(fila, [0.5]).iloc[0, 0])
    assert mediana.prediccion_reconstruida == pytest.approx(esperado, abs=1e-6)


# --- Desenvolver envoltorios ---------------------------------------------
def test_encuentra_el_modelo_debajo_del_envoltorio(modelo) -> None:
    """El artefacto servido es un conformal envolviendo un LightGBM."""
    assert modelo_explicable(Envoltorio(Envoltorio(modelo))) is modelo


def test_atribuye_a_traves_del_envoltorio(futuro, modelo) -> None:
    fila = futuro.head(1)
    directa = atribuir(modelo, fila, top_k=5)
    envuelta = atribuir(Envoltorio(modelo), fila, top_k=5)

    assert [a.feature for a in directa.aportes] == [a.feature for a in envuelta.aportes]
    assert directa.valor_base == pytest.approx(envuelta.valor_base)


def test_un_modelo_sin_features_dice_por_que(futuro, naive) -> None:
    """El mensaje util es 'cargaste un naive', no un AttributeError."""
    with pytest.raises(NoExplicableError, match="no produce contribuciones"):
        atribuir(naive, futuro.head(1))


def test_el_error_nombra_la_cadena_revisada(futuro, naive) -> None:
    """Si hay envoltorios, hay que poder ver donde se busco."""
    with pytest.raises(NoExplicableError, match="envoltorio -> naive"):
        atribuir(Envoltorio(naive), futuro.head(1))


def test_pedir_cuantil_a_un_modelo_puntual_no_se_ignora(futuro, modelo) -> None:
    """Silenciarlo daria la explicacion de otra cifra que la pedida."""
    with pytest.raises(NoExplicableError, match="no tiene boosters por"):
        atribuir(modelo, futuro.head(1), quantile=0.9)


# --- Contrato de entrada -------------------------------------------------
def test_atribuir_exige_una_sola_fila(futuro, modelo) -> None:
    """Aceptar varias invitaria a promediarlas sin decirlo."""
    with pytest.raises(ValueError, match="una prediccion"):
        atribuir(modelo, futuro)


def test_top_k_tiene_que_ser_positivo(futuro, modelo) -> None:
    with pytest.raises(ValueError, match="top_k"):
        atribuir(modelo, futuro.head(1), top_k=0)


# --- Atribucion global ---------------------------------------------------
def test_la_global_separa_magnitud_de_direccion(futuro, modelo) -> None:
    """aporte_medio es |SHAP| promedio; aporte_neto lleva signo.

    Las dos juntas distinguen la feature que DISCRIMINA (magnitud alta, neto cerca
    de cero: sube unas series y baja otras) de la que corre el nivel de todo el
    panel para el mismo lado.
    """
    tabla = atribucion_global(modelo, futuro)

    assert list(tabla.columns) == ["aporte_medio", "aporte_neto"]
    assert tabla.index.name == "feature"
    assert (tabla["aporte_medio"] >= 0).all(), "una media de valores absolutos no es negativa"
    assert tabla["aporte_medio"].is_monotonic_decreasing, "no viene ordenada"
    # El neto nunca puede superar en magnitud a la media de absolutos.
    assert (tabla["aporte_neto"].abs() <= tabla["aporte_medio"] + 1e-9).all()


def test_la_global_respeta_el_recorte(futuro, modelo) -> None:
    assert len(atribucion_global(modelo, futuro, top_k=4)) == 4


def test_la_global_no_promedia_un_futuro_vacio(futuro, modelo) -> None:
    with pytest.raises(ValueError, match="al menos una fila"):
        atribucion_global(modelo, futuro.head(0))
