"""Tests del triage de cartera.

Lo que se verifica son las dos propiedades de las que depende que la portada sirva:

1. **Que los umbrales aislen poco.** Una alerta que marca un tercio del catalogo no es
   una alerta — ya paso con `censored_days_last_28 >= 14`, cuya mediana del panel era
   12 de 28. Hay un test que falla si un grupo marca mas de la mitad.
2. **Que cada grupo mida lo que dice.** Se construyen series con un defecto conocido y
   se exige que caigan en el grupo correcto y **no** en los otros, porque un grupo que
   se activa por el motivo equivocado manda a la persona a revisar la cosa que no era.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from blindside import config as cfg
from blindside.data import schema as S
from blindside.evaluate import triage as T


def _panel(series: dict[str, dict], dias: int = 40) -> pd.DataFrame:
    """Panel minimo. Cada serie declara `latente`, `observada` y `censurado`."""
    filas = []
    for sid, spec in series.items():
        tienda, producto = sid.split("_")
        for i in range(dias):
            filas.append(
                {
                    S.SERIES_ID: sid,
                    S.DATE: pd.Timestamp("2024-01-01") + pd.Timedelta(days=i),
                    S.STORE_ID: int(tienda),
                    S.PRODUCT_ID: int(producto),
                    S.DEMAND_LATENT: float(spec["latente"][i]),
                    S.SALE_AMOUNT: float(spec["observada"][i]),
                    S.IS_CENSORED: bool(spec["censurado"][i]),
                }
            )
    return pd.DataFrame(filas)


def _plana(nivel: float, dias: int = 40) -> dict:
    y = np.full(dias, nivel)
    return {"latente": y, "observada": y.copy(), "censurado": np.zeros(dias, dtype=bool)}


def _backtest(mase_objetivo: dict[str, float], panel: pd.DataFrame) -> pd.DataFrame:
    """Resultado de backtest sintetico que produce el MASE pedido por serie.

    El denominador de MASE de una serie plana es 0, asi que las series de estos tests
    llevan una oscilacion para que el denominador exista.
    """
    filas = []
    sl = cfg.FORECAST.season_length
    for sid, objetivo in mase_objetivo.items():
        y = panel[panel[S.SERIES_ID] == sid].sort_values(S.DATE)[S.DEMAND_LATENT].to_numpy()
        denom = float(np.abs(y[sl:] - y[:-sl]).mean())
        error = objetivo * denom
        for h in range(1, 8):
            filas.append(
                {
                    S.SERIES_ID: sid,
                    "model": "cqr_lgbm_quantile",
                    "y_true": 10.0,
                    "y_pred": 10.0 - error,
                    "h": h,
                    "origin": pd.Timestamp("2024-02-01"),
                }
            )
    return pd.DataFrame(filas)


def _oscilante(nivel: float, dias: int = 40, amp: float = 0.5) -> dict:
    """Serie con estacionalidad semanal **mas ruido**.

    El ruido no es decorativo: una serie perfectamente periodica en 7 dias tiene error
    del naive estacional **exactamente cero**, asi que el denominador de MASE se anula y
    la metrica queda indefinida. Es un caso degenerado real que conviene recordar.
    """
    rng = np.random.default_rng(int(nivel * 1000) + dias)
    t = np.arange(dias)
    y = nivel + amp * np.sin(2 * np.pi * t / 7) + rng.normal(0, 0.1 * nivel, dias)
    return {
        "latente": np.maximum(0.01, y),
        "observada": np.maximum(0.01, y).copy(),
        "censurado": np.zeros(dias, dtype=bool),
    }


# --- Las señales miden lo que dicen --------------------------------------
def test_la_fraccion_estimada_pondera_por_masa_y_no_por_dias() -> None:
    """Diez dias con una hora caida no es lo mismo que dos dias enteros caidos.

    Contando **dias con quiebre** los dos casos dan lo mismo, y es la razon de que la
    señal sea una fraccion de demanda y no un conteo.
    """
    dias = 40
    # A: muchos dias con una correccion chica.
    lat_a = np.full(dias, 10.0)
    obs_a = np.full(dias, 10.0)
    cen_a = np.zeros(dias, dtype=bool)
    obs_a[:10] = 9.0
    cen_a[:10] = True

    # B: pocos dias con una correccion enorme.
    lat_b = np.full(dias, 10.0)
    obs_b = np.full(dias, 10.0)
    cen_b = np.zeros(dias, dtype=bool)
    obs_b[:2] = 0.0
    cen_b[:2] = True

    panel = _panel(
        {
            "1_1": {"latente": lat_a, "observada": obs_a, "censurado": cen_a},
            "1_2": {"latente": lat_b, "observada": obs_b, "censurado": cen_b},
        },
        dias=dias,
    )
    s = T.series_signals(panel, ventana_dias=dias)

    assert s.loc["1_1", "tasa_quiebre"] > s.loc["1_2", "tasa_quiebre"], "A tiene mas dias"
    assert s.loc["1_2", "frac_estimada"] > s.loc["1_1", "frac_estimada"], (
        "pero B tiene mas masa estimada, que es lo que importa para confiar o no"
    )


def test_la_racha_vigente_es_la_que_termina_hoy() -> None:
    """Distinto de la racha maxima historica, y en este panel la diferencia es 95 vs 6.

    Una racha que termino hace un mes no es un problema operativo de hoy.
    """
    dias = 40
    cen = np.zeros(dias, dtype=bool)
    cen[5:20] = True  # racha historica de 15, terminada hace mucho
    y = np.full(dias, 5.0)
    panel = _panel({"1_1": {"latente": y, "observada": y.copy(), "censurado": cen}}, dias=dias)

    assert T.series_signals(panel, ventana_dias=dias).loc["1_1", "racha_vigente"] == 0

    cen2 = np.zeros(dias, dtype=bool)
    cen2[-4:] = True  # racha vigente de 4
    panel2 = _panel({"1_1": {"latente": y, "observada": y.copy(), "censurado": cen2}}, dias=dias)
    assert T.series_signals(panel2, ventana_dias=dias).loc["1_1", "racha_vigente"] == 4


def test_el_error_va_normalizado_y_no_en_mae() -> None:
    """El MAE por serie correlaciona 0,86 con el nivel: rankear por MAE es rankear
    por volumen. El MASE por serie se despega de la escala.

    Dos series con el MISMO error relativo y volumenes 10x tienen que dar el mismo
    MASE. Si la señal estuviera en MAE, la grande saldria diez veces peor.
    """
    panel = _panel({"1_1": _oscilante(2.0), "1_2": _oscilante(20.0, amp=5.0)})
    bt = _backtest({"1_1": 1.2, "1_2": 1.2}, panel)
    s = T.series_signals(panel, bt, ventana_dias=40)

    assert s.loc["1_1", "mase_serie"] == pytest.approx(s.loc["1_2", "mase_serie"], rel=0.05)
    assert s.loc["1_2", "demanda_media"] > 5 * s.loc["1_1", "demanda_media"]


def test_sin_backtest_no_inventa_el_error() -> None:
    """Sin resultado de backtest no hay como saber si el modelo es confiable.

    Poner un valor por defecto seria peor: la portada mostraria un grupo vacio como si
    fuera informacion de que no hay series problematicas.
    """
    panel = _panel({"1_1": _oscilante(3.0)})
    s = T.series_signals(panel)
    assert "mase_serie" not in s.columns

    m = T.triage(s)
    assert "no_confiable" not in m.columns
    assert "Modelo no confiable" not in m[T.MOTIVO_COL].iloc[0]


# --- Los grupos se activan por el motivo correcto ------------------------
def test_cada_grupo_se_activa_por_su_propio_motivo() -> None:
    """Un grupo que se enciende por el motivo equivocado manda a revisar otra cosa."""
    dias = 40
    sana = _oscilante(2.0, dias)

    mala_modelo = _oscilante(2.0, dias)

    escasa = _oscilante(2.0, dias)
    escasa["observada"] = escasa["latente"] * 0.4  # 60 % estimada
    escasa["censurado"] = np.ones(dias, dtype=bool)

    quebrada = _oscilante(2.0, dias)
    cen = np.zeros(dias, dtype=bool)
    cen[-6:] = True
    quebrada["censurado"] = cen

    panel = _panel(
        {"1_1": sana, "1_2": mala_modelo, "1_3": escasa, "1_4": quebrada}, dias=dias
    )
    bt = _backtest({"1_1": 0.5, "1_2": 1.5, "1_3": 0.5, "1_4": 0.5}, panel)
    m = T.triage(T.series_signals(panel, bt, ventana_dias=dias))

    assert not m.loc["1_1", "no_confiable"] and not m.loc["1_1", "senal_escasa"]
    assert m.loc["1_2", "no_confiable"], "MASE 1,5 tiene que marcar"
    assert not m.loc["1_2", "senal_escasa"], "y no puede marcar señal escasa"
    assert m.loc["1_3", "senal_escasa"], "60 % estimada tiene que marcar"
    assert not m.loc["1_3", "no_confiable"]
    assert m.loc["1_4", "quebrado_ahora"], "6 dias de racha vigente tienen que marcar"


def test_el_corte_de_no_confiable_es_perder_contra_el_naive() -> None:
    """MASE > 1 no es un umbral arbitrario: es el punto donde el modelo no se justifica."""
    assert T.UMBRALES.mase_no_confiable == 1.0

    panel = _panel({"1_1": _oscilante(3.0), "1_2": _oscilante(3.0)})
    bt = _backtest({"1_1": 0.99, "1_2": 1.01}, panel)
    m = T.triage(T.series_signals(panel, bt, ventana_dias=40))

    assert not m.loc["1_1", "no_confiable"]
    assert m.loc["1_2", "no_confiable"]


def test_una_serie_puede_no_tener_ningun_motivo() -> None:
    """Que la mayoria no tenga motivo es el resultado buscado, no un bug.

    Si todas las series entraran a algun grupo, la portada no priorizaria nada.
    """
    panel = _panel({"1_1": _oscilante(2.0), "1_2": _oscilante(2.1)})
    bt = _backtest({"1_1": 0.5, "1_2": 0.5}, panel)
    m = T.triage(T.series_signals(panel, bt, ventana_dias=40))

    assert (m["n_motivos"] == 0).any()
    assert (m[T.MOTIVO_COL] == "").any()


def test_los_motivos_se_acumulan_y_se_nombran() -> None:
    """La portada ordena por cantidad de motivos, asi que tienen que sumar bien."""
    dias = 40
    mala = _oscilante(9.0, dias, amp=2.0)
    mala["observada"] = mala["latente"] * 0.4
    mala["censurado"] = np.ones(dias, dtype=bool)

    panel = _panel({"1_1": mala, "1_2": _oscilante(1.0, dias)}, dias=dias)
    bt = _backtest({"1_1": 1.6, "1_2": 0.5}, panel)
    m = T.triage(T.series_signals(panel, bt, ventana_dias=dias))

    fila = m.loc["1_1"]
    assert fila["n_motivos"] >= 3
    for etiqueta in ("Modelo no confiable", "Señal escasa", "Alto volumen"):
        assert etiqueta in fila[T.MOTIVO_COL]


# --- Los umbrales tienen que aislar poco ---------------------------------
@pytest.mark.slow
def test_ningun_grupo_marca_medio_catalogo(recovered_panel: pd.DataFrame) -> None:
    """El test que impide repetir el error de la alerta que marcaba el 35,6 %.

    Los umbrales estan calibrados sobre el panel real; esto corre sobre el sintetico,
    asi que el limite es holgado a proposito: lo que se atrapa es un umbral que dejo
    de aislar, no una desviacion de unos puntos.
    """
    s = T.series_signals(recovered_panel)
    m = T.triage(s)
    for g in T.GRUPOS:
        if g.clave in m.columns:
            share = m[g.clave].mean()
            assert share < 0.5, f"'{g.etiqueta}' marca {share:.1%}, no aisla nada"


def test_el_resumen_reporta_series_y_volumen() -> None:
    """404 series y 22 % del volumen son dos cosas distintas, y las dos hacen falta."""
    panel = _panel({"1_1": _oscilante(20.0, amp=5.0), "1_2": _oscilante(1.0)})
    bt = _backtest({"1_1": 1.5, "1_2": 0.5}, panel)
    resumen = T.resumen_por_grupo(T.triage(T.series_signals(panel, bt, ventana_dias=40)))

    assert {"grupo", "series", "share_series", "share_volumen", "solo_este_motivo"} <= set(
        resumen.columns
    )
    no_conf = resumen[resumen["clave"] == "no_confiable"].iloc[0]
    assert no_conf["series"] == 1
    # La serie mala es la de volumen 20 contra una de 1: pesa mucho mas que 1 de 2.
    assert no_conf["share_volumen"] > no_conf["share_series"]


def test_los_umbrales_estan_declarados_y_son_inmutables() -> None:
    """Si se pudieran cambiar en caliente, la portada cambiaria de significado."""
    with pytest.raises((AttributeError, TypeError)):
        T.UMBRALES.mase_no_confiable = 2.0  # type: ignore[misc]


def test_cada_grupo_explica_que_hacer() -> None:
    """Un grupo sin remedio es una alarma sin accion, que es ruido."""
    for g in T.GRUPOS:
        assert g.etiqueta and g.que_significa and g.que_hacer
        assert len(g.que_hacer) > 25, f"'{g.clave}' no dice que hacer"
