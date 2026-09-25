"""Tests de la busqueda de hiperparametros.

Lo que se verifica no es que la busqueda encuentre buenos parametros -- eso depende
del panel y se reporta, no se asegura -- sino las decisiones que hacen que su
resultado sea creible:

1. **Que el espacio no incluya lo que es una decision documentada.** `objective` esta
   fijado en L1 por D10; si estuviera en el espacio, la busqueda podria revertirlo por
   unas milesimas de MASE y cambiar el significado de la salida.
2. **Que la mejora se compare contra los parametros actuales** y no contra el peor
   trial, porque contra el peor trial cualquier busqueda "mejora" por construccion.
3. **Que una mejora menor que la dispersion entre origenes no se adopte**, y que el
   criterio este en el codigo en vez de decidirse despues de ver el numero.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from blindside.models.gbdt import DEFAULT_LGBM_PARAMS
from blindside.models.tuning import (
    Busqueda,
    Resultado,
    disponible,
    espacio_lgbm,
)


class TrialFalso:
    """Simulacro del trial de Optuna: devuelve el punto medio de cada rango.

    Permite testear el espacio de busqueda sin instalar Optuna ni correr un estudio.
    """

    def __init__(self) -> None:
        self.number = 0
        self.pedidos: dict[str, tuple] = {}

    def suggest_float(self, nombre: str, lo: float, hi: float, *, log: bool = False) -> float:
        self.pedidos[nombre] = (lo, hi, log)
        return (lo + hi) / 2

    def suggest_int(self, nombre: str, lo: int, hi: int, *, log: bool = False) -> int:
        self.pedidos[nombre] = (lo, hi, log)
        return (lo + hi) // 2


def _resultado(
    *, mejor_mase: float, base_mase: float, base_desvio: float = 0.02
) -> Resultado:
    return Resultado(
        mejores_params=dict(DEFAULT_LGBM_PARAMS),
        mejor_objetivo=mejor_mase,
        mejor_mase=mejor_mase,
        mejor_desvio=0.02,
        base_objetivo=base_mase,
        base_mase=base_mase,
        base_desvio=base_desvio,
        busqueda=Busqueda(),
        historia=pd.DataFrame([{"trial": -1, "objetivo": base_mase}]),
    )


# --- El espacio de busqueda ----------------------------------------------
def test_el_espacio_no_toca_la_funcion_de_perdida() -> None:
    """`objective` es una decision documentada (D10), no un hiperparametro.

    Con L1 el modelo estima la mediana, que es lo que se quiere con una cola derecha
    larga. Si la busqueda pudiera cambiarlo a L2 por unas milesimas, la salida pasaria
    a ser una media y la interpretacion de todo el proyecto cambiaria en silencio.
    """
    trial = TrialFalso()
    params = espacio_lgbm(trial)

    assert "objective" not in params
    assert "metric" not in params
    assert "objective" not in trial.pedidos


def test_el_espacio_cubre_los_parametros_que_importan() -> None:
    trial = TrialFalso()
    params = espacio_lgbm(trial)

    esperados = {
        "learning_rate",
        "num_leaves",
        "min_child_samples",
        "feature_fraction",
        "bagging_fraction",
        "lambda_l2",
    }
    assert set(params) == esperados


def test_los_rangos_contienen_los_valores_actuales() -> None:
    """Si el default quedara fuera del rango, la busqueda no podria confirmarlo.

    El espacio esta centrado en lo que ya funciona a proposito: la pregunta es si se
    puede mejorar, y un espacio que excluye el punto de partida no puede responderla.
    """
    trial = TrialFalso()
    espacio_lgbm(trial)

    for nombre, (lo, hi, _) in trial.pedidos.items():
        actual = DEFAULT_LGBM_PARAMS[nombre]
        assert lo <= actual <= hi, f"{nombre}={actual} esta fuera del rango [{lo}, {hi}]"


def test_las_escalas_multiplicativas_son_logaritmicas() -> None:
    """Un learning rate se explora en escala log; una fraccion, lineal.

    Muestrear el learning rate uniformemente entre 0,02 y 0,15 pondria casi toda la
    masa en la mitad alta, que es la zona menos interesante.
    """
    trial = TrialFalso()
    espacio_lgbm(trial)

    assert trial.pedidos["learning_rate"][2] is True
    assert trial.pedidos["lambda_l2"][2] is True
    assert trial.pedidos["feature_fraction"][2] is False


# --- El criterio de adopcion ---------------------------------------------
def test_una_mejora_menor_que_la_dispersion_no_se_adopta() -> None:
    """Es lo que evita adoptar ruido.

    0,3 % de mejora cuando el desvio entre origenes es de 2 % no es una mejora: es
    una realizacion afortunada del azar sobre los origenes que se eligieron.
    """
    res = _resultado(base_mase=0.8200, mejor_mase=0.8175, base_desvio=0.02)
    assert res.mejora_pct > 0, "hubo mejora nominal"
    assert not res.vale_la_pena, "pero no supera la dispersion, asi que no se adopta"


def test_una_mejora_mayor_que_la_dispersion_si_se_adopta() -> None:
    res = _resultado(base_mase=0.8800, mejor_mase=0.8200, base_desvio=0.02)
    assert res.vale_la_pena


def test_no_encontrar_nada_no_cuenta_como_mejora() -> None:
    """El caso degenerado: el mejor trial es el default. Tiene que decirlo."""
    res = _resultado(base_mase=0.8200, mejor_mase=0.8200)
    assert res.mejora_pct == 0.0
    assert not res.vale_la_pena


def test_un_resultado_peor_da_mejora_negativa() -> None:
    res = _resultado(base_mase=0.8200, mejor_mase=0.8500)
    assert res.mejora_pct < 0
    assert not res.vale_la_pena


# --- Persistencia --------------------------------------------------------
def test_el_json_guarda_lo_necesario_para_auditar(tmp_path) -> None:
    """Sin el alcance de la busqueda, los parametros no se pueden interpretar."""
    res = _resultado(base_mase=0.8800, mejor_mase=0.8200)
    ruta = res.a_json(tmp_path / "tuning.json")

    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["vale_la_pena"] is True
    assert datos["busqueda"]["n_series"] == Busqueda().n_series
    assert datos["busqueda"]["n_origins"] == Busqueda().n_origins
    assert "mejores_params" in datos


def test_el_reporte_deriva_la_lectura_de_los_numeros(tmp_path) -> None:
    """La conclusion no puede ser un texto fijo que contradiga su propia tabla.

    Es el mismo arreglo que se le hizo al generador de la ablacion, donde una frase
    fija decia que el resultado "reproduce el valor publicado" mientras la tabla de
    arriba mostraba un factor de 2,2.
    """
    from blindside.models.tuning import escribir_reporte

    chica = escribir_reporte(
        _resultado(base_mase=0.8200, mejor_mase=0.8175), tmp_path / "chica.md"
    )
    grande = escribir_reporte(
        _resultado(base_mase=0.8800, mejor_mase=0.8200), tmp_path / "grande.md"
    )

    assert "no se adopta" in chica.read_text(encoding="utf-8")
    assert "Vale adoptarla" in grande.read_text(encoding="utf-8")


def test_el_reporte_declara_que_el_alcance_es_reducido(tmp_path) -> None:
    """400 series y 4 origenes no son los 3066 y 8 de la corrida oficial."""
    from blindside.models.tuning import escribir_reporte

    texto = escribir_reporte(
        _resultado(base_mase=0.8800, mejor_mase=0.8200), tmp_path / "r.md"
    ).read_text(encoding="utf-8")

    assert "3066" in texto, "tiene que decir contra que se compara el alcance"
    assert "origenes moviles" in texto


# --- Disponibilidad ------------------------------------------------------
def test_disponible_no_levanta() -> None:
    """El llamador la usa para decidir, asi que no puede tirar una excepcion."""
    assert isinstance(disponible(), bool)


@pytest.mark.skipif(disponible(), reason="optuna esta instalado en este entorno")
def test_sin_optuna_el_error_dice_como_instalarlo() -> None:
    from blindside.models.tuning import buscar_lgbm

    with pytest.raises(ImportError, match="pip install optuna"):
        buscar_lgbm(pd.DataFrame())
