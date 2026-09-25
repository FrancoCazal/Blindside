"""Tests de render del dashboard.

`AppTest` corre el script con el runtime real de Streamlit, asi que atrapa lo que un
import no atrapa: un `column_config` mal armado, una columna que no existe, o una
dependencia que esta en local y **no en la imagen de servicio**.

Ese ultimo caso no es hipotetico. La primera version de la portada usaba
`Styler.background_gradient`, que exige **matplotlib** — y matplotlib queda fuera del
target `serve` a proposito, porque pesa y no hace falta para responder `/forecast`. En
local andaba y en Docker habria tumbado la pagina, o sea justo durante el demo.

Corren sobre `data/sample/`, que va commiteado, asi que no necesitan el dataset.
"""

from __future__ import annotations

from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(str(APP), default_timeout=300).run()
    if at.exception:
        pytest.fail(f"la app lanzo al arrancar: {[str(e.value) for e in at.exception]}")
    return at


def test_la_portada_es_el_triage(app) -> None:
    """La primera pantalla responde 'que miro primero', no 'que hay en el panel'.

    El orden del menu es la decision de producto: un dashboard que abre en estadisticas
    descriptivas obliga a buscar donde esta el problema.
    """
    menu = app.sidebar.radio[0]
    assert menu.options[0] == "Qué mirar primero"
    assert menu.value == "Qué mirar primero"


def test_la_portada_renderiza_sin_excepciones(app) -> None:
    assert not app.exception


def test_la_portada_declara_cuanto_aisla(app) -> None:
    """Si el triage marcara casi todo, no priorizaria nada. El KPI lo hace visible."""
    etiquetas = {m.label for m in app.metric}
    assert "Series en cartera" in etiquetas
    assert "Piden atención" in etiquetas

    piden = next(m for m in app.metric if m.label == "Piden atención")
    total = next(m for m in app.metric if m.label == "Series en cartera")
    n_piden = int(str(piden.value).replace(",", ""))
    n_total = int(str(total.value).replace(",", ""))
    assert 0 < n_piden < n_total, "el triage tiene que aislar un subconjunto propio"
    assert n_piden / n_total < 0.6, f"marca {n_piden / n_total:.0%}: no prioriza nada"


def test_hay_un_expander_por_motivo_con_su_remedio(app) -> None:
    """Una alarma sin accion es ruido, asi que cada motivo explica que hacer."""
    from blindside.evaluate import triage as T

    assert len(app.expander) == len(T.GRUPOS)


def test_se_puede_filtrar_por_motivo(app) -> None:
    """Cada motivo pide una accion distinta, asi que se revisan por separado."""
    from blindside.evaluate import triage as T

    opciones = app.selectbox[0].options
    assert opciones[0].startswith("Todas")
    for g in T.GRUPOS:
        assert g.etiqueta in opciones


def test_la_tabla_de_motivos_no_usa_matplotlib(app) -> None:
    """Regresion del bug que solo aparecia en Docker.

    No se puede assertear la ausencia de matplotlib desde aca, pero si que la pagina
    renderizo sus dos tablas: con `background_gradient` y sin matplotlib, la segunda
    no llegaria a existir.
    """
    assert len(app.dataframe) >= 2


@pytest.mark.parametrize(
    "pantalla",
    [
        "Vista general",
        "Serie individual",
        "Ablación de censura",
        "Comparativa de modelos",
        "Reposición",
        "Validación y antifugas",
        "Reporte completo",
    ],
)
def test_todas_las_pantallas_renderizan(pantalla: str) -> None:
    """Agregar la portada no puede haber roto las que ya estaban."""
    at = AppTest.from_file(str(APP), default_timeout=300).run()
    at.sidebar.radio[0].set_value(pantalla).run()
    assert not at.exception, f"'{pantalla}' lanzo: {[str(e.value) for e in at.exception]}"
