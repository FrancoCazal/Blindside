"""Tests de M4: clustering de perfiles y deteccion de anomalias.

Lo que se verifica no es la calidad del agrupamiento -- eso se mide y se reporta, no
se asegura con un assert -- sino las dos propiedades de las que depende que sirvan:

1. **Que no haya fuga.** Un cluster o un detector ajustado con datos posteriores al
   origen es una fuga aunque no toque la columna de target. `assign` y `score` no
   pueden reajustar, y se comprueba dandoles mas datos y exigiendo el mismo resultado.
2. **Que la forma sea forma.** Las features se normalizan por el nivel de la serie, asi
   que dos series con el mismo perfil y volumenes distintos tienen que caer en el mismo
   grupo. Si eso falla, el clustering esta agrupando por rotacion y ya existe una
   banda de rotacion que hace eso.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from blindside.data import schema as S
from blindside.unsupervised import (
    ANOMALY_COL,
    CLUSTER_COL,
    SCORE_COL,
    DemandProfileClusters,
    WindowAnomalyDetector,
    dbscan_profiles,
    perfil_por_cluster,
    residual_anomalies,
    shape_features,
)
from blindside.unsupervised.clustering import MIN_DAYS

pytestmark = pytest.mark.slow


def _serie(
    n: int = 70,
    *,
    nivel: float = 3.0,
    amplitud: float = 0.4,
    ceros: float = 0.0,
    semilla: int = 0,
) -> np.ndarray:
    """Serie con estacionalidad semanal, nivel e intermitencia controlados."""
    rng = np.random.default_rng(semilla)
    t = np.arange(n)
    y = nivel * (1.0 + amplitud * np.sin(2 * np.pi * t / 7)) + rng.normal(0, 0.05 * nivel, n)
    if ceros > 0:
        y[rng.random(n) < ceros] = 0.0
    return np.maximum(0.0, y)


def _panel(series: dict[str, np.ndarray]) -> pd.DataFrame:
    filas = []
    for sid, y in series.items():
        tienda, producto = sid.split("_")
        for i, v in enumerate(y):
            filas.append(
                {
                    S.SERIES_ID: sid,
                    S.DATE: pd.Timestamp("2024-01-01") + pd.Timedelta(days=i),
                    S.STORE_ID: int(tienda),
                    S.PRODUCT_ID: int(producto),
                    S.DEMAND_LATENT: float(v),
                    S.IS_CENSORED: bool(v <= 0),
                }
            )
    return pd.DataFrame(filas)


@pytest.fixture(scope="module")
def panel_formas() -> pd.DataFrame:
    """Tres formas distintas, dos niveles cada una. Seis series.

    Cada par comparte la semilla a proposito: asi lo **unico** que cambia entre los
    dos es el nivel. Con semillas distintas, los ceros caen en otros dias y la racha
    media difiere de verdad, que es otra forma y no el mismo perfil escalado.
    """
    return _panel(
        {
            # Estacional fuerte, sin ceros. Niveles 2 y 20.
            "1_1": _serie(nivel=2.0, amplitud=0.5, semilla=1),
            "1_2": _serie(nivel=20.0, amplitud=0.5, semilla=1),
            # Plana. Niveles 3 y 30.
            "2_1": _serie(nivel=3.0, amplitud=0.02, semilla=3),
            "2_2": _serie(nivel=30.0, amplitud=0.02, semilla=3),
            # Intermitente. Niveles 2 y 20.
            "3_1": _serie(nivel=2.0, amplitud=0.1, ceros=0.5, semilla=5),
            "3_2": _serie(nivel=20.0, amplitud=0.1, ceros=0.5, semilla=5),
        }
    )


# --- Las features describen forma, no nivel ------------------------------
def test_la_forma_no_depende_del_nivel(panel_formas) -> None:
    """Dos series con el mismo perfil y volumenes 10x tienen features parecidas.

    Es la propiedad que justifica normalizar. Si fallara, el clustering agruparia por
    rotacion, que es lo que ya hace `rotation_band`.
    """
    tabla = shape_features(panel_formas)
    for baja, alta in (("1_1", "1_2"), ("2_1", "2_2"), ("3_1", "3_2")):
        d = np.abs(tabla.loc[baja] - tabla.loc[alta]).max()
        assert d < 0.35, f"{baja} y {alta} deberian tener la misma forma, difieren {d:.3f}"


def test_las_formas_distintas_se_distinguen(panel_formas) -> None:
    """La estacional y la plana no pueden tener la misma amplitud semanal."""
    tabla = shape_features(panel_formas)
    assert tabla.loc["1_1", "amplitud_semanal"] > tabla.loc["2_1", "amplitud_semanal"] * 3
    assert tabla.loc["3_1", "tasa_ceros"] > 0.3
    assert tabla.loc["1_1", "tasa_ceros"] < 0.05


def test_las_series_muy_cortas_quedan_afuera() -> None:
    """Un perfil semanal sobre dos observaciones por dia es ruido, no forma."""
    panel = _panel({"1_1": _serie(70), "1_2": _serie(MIN_DAYS - 1)})
    tabla = shape_features(panel)
    assert "1_1" in tabla.index
    assert "1_2" not in tabla.index


def test_una_serie_toda_cero_no_rompe_ni_da_infinito() -> None:
    """Dividir por la media es dividir por cero. Es un caso real del catalogo.

    Lo que tiene que dar 0 es lo **normalizado por el nivel**, que es lo indefinido.
    `tasa_ceros` vale 1 y `racha_ceros_media` vale el largo de la serie, y eso es
    correcto: describen la serie sin dividir por nada.
    """
    panel = _panel({"1_1": _serie(70), "1_2": np.zeros(70)})
    tabla = shape_features(panel)

    assert np.isfinite(tabla.to_numpy()).all(), "hay infinitos o NaN en las features"
    normalizadas = ["cv", "amplitud_semanal", "pico_relativo", "autocorr_7"]
    assert (tabla.loc["1_2", normalizadas] == 0.0).all(), "el nivel indefinido tiene que dar 0"
    assert tabla.loc["1_2", "tasa_ceros"] == 1.0
    assert tabla.loc["1_2", "racha_ceros_media"] == 70.0


def test_la_racha_de_ceros_distingue_disperso_de_bloque() -> None:
    """Veinte ceros sueltos y veinte seguidos dan la misma tasa y no son lo mismo."""
    n = 60
    disperso = np.ones(n) * 2.0
    disperso[::3] = 0.0  # 20 ceros repartidos
    bloque = np.ones(n) * 2.0
    bloque[20:40] = 0.0  # 20 ceros juntos

    tabla = shape_features(_panel({"1_1": disperso, "1_2": bloque}))
    assert tabla.loc["1_1", "tasa_ceros"] == pytest.approx(tabla.loc["1_2", "tasa_ceros"], abs=0.02)
    assert tabla.loc["1_2", "racha_ceros_media"] > 5 * tabla.loc["1_1", "racha_ceros_media"]


# --- La fuga, que es la razon del diseno ---------------------------------
def test_assign_no_reajusta(panel_formas) -> None:
    """Es el test antifuga del modulo.

    Si `assign` reajustara, el cluster de una serie cambiaria segun con que otras
    series venga, y la feature del dia de test dependeria del contenido del test.
    """
    mitad = panel_formas[panel_formas[S.DATE] <= pd.Timestamp("2024-02-25")]
    modelo = DemandProfileClusters(k=3).fit(mitad)

    centroides_antes = modelo.centroides_.copy()
    a = modelo.assign(mitad)
    b = modelo.assign(panel_formas)  # mas dias: no puede mover nada

    pd.testing.assert_frame_equal(centroides_antes, modelo.centroides_)
    # Los grupos de las series que ya estaban pueden cambiar si su forma cambio con
    # los dias nuevos, pero los centroides no. Eso es lo que no se puede mover.
    assert set(a.index) <= set(b.index)


def test_assign_antes_de_fit_levanta(panel_formas) -> None:
    with pytest.raises(RuntimeError, match="fit antes de assign"):
        DemandProfileClusters().assign(panel_formas)


def test_fit_sin_historia_suficiente_dice_por_que() -> None:
    panel = _panel({"1_1": _serie(10), "1_2": _serie(12)})
    with pytest.raises(ValueError, match="dias de historia"):
        DemandProfileClusters().fit(panel)


# --- Contrato de la feature ----------------------------------------------
def test_la_feature_es_numerica_para_que_el_modelo_la_vea(panel_formas) -> None:
    """Regresion de un bug medido: como `category`, el selector la descartaba.

    `features.build.feature_columns` filtra a dtypes numericos, asi que una columna
    categorica de pandas no entra a la matriz y el modelo entrena sin ella dando
    exactamente el mismo MASE. Se detecto porque las dos ramas daban 0,6098 de MAE.
    """
    from blindside.features.build import feature_columns

    modelo = DemandProfileClusters(k=3).fit(panel_formas)
    con = modelo.add_feature(panel_formas, modelo.assign(panel_formas))

    assert pd.api.types.is_numeric_dtype(con[CLUSTER_COL])
    assert CLUSTER_COL in feature_columns(con), "el selector de features la descarta"


def test_una_serie_nueva_recibe_el_grupo_modal(panel_formas) -> None:
    """Arranque en frio: sin forma estimable, el fallback y no un nulo."""
    modelo = DemandProfileClusters(k=3).fit(panel_formas)
    con_nueva = pd.concat([panel_formas, _panel({"9_9": _serie(5)})], ignore_index=True)

    etq = modelo.assign(con_nueva)
    assert etq.loc["9_9"] == modelo.fallback_
    assert etq.notna().all()


def test_el_fallback_es_el_grupo_mas_poblado(panel_formas) -> None:
    modelo = DemandProfileClusters(k=3).fit(panel_formas)
    assert modelo.fallback_ == int(modelo.etiquetas_.value_counts().idxmax())


def test_k_no_puede_pasar_la_cantidad_de_series(panel_formas) -> None:
    """Pedir 50 grupos con 6 series tiene que degradar, no explotar."""
    modelo = DemandProfileClusters(k=50).fit(panel_formas)
    assert modelo.etiquetas_.nunique() <= 6


def test_perfil_por_cluster_describe_los_grupos(panel_formas) -> None:
    """Un cluster sin descripcion es un numero."""
    modelo = DemandProfileClusters(k=3).fit(panel_formas)
    perfil = perfil_por_cluster(panel_formas, modelo.assign(panel_formas))

    assert "n_series" in perfil.columns
    assert perfil["n_series"].sum() == 6
    assert perfil["demanda_media"].is_monotonic_decreasing


# --- DBSCAN --------------------------------------------------------------
def test_dbscan_puede_dejar_series_sin_grupo(panel_formas) -> None:
    """Es su diferencia con K-Means y la razon de tenerlo: sabe decir 'ninguno'."""
    etq = dbscan_profiles(panel_formas, eps=0.3, min_samples=3)
    assert (etq == -1).any(), "con eps chico todo deberia caer en ruido"
    assert etq.index.is_unique


# --- Isolation Forest ----------------------------------------------------
def test_el_detector_marca_el_pico_inyectado() -> None:
    """Chequeo minimo de utilidad: una ventana con un pico de 10x tiene que salir."""
    y = _serie(80, nivel=3.0, amplitud=0.1, semilla=7)
    y[50] = 30.0  # carga erronea, no quiebre
    panel = _panel({"1_1": y, "1_2": _serie(80, nivel=3.0, amplitud=0.1, semilla=8)})

    det = WindowAnomalyDetector(window=14, contamination=0.05).fit(panel)
    marcas = det.score(panel)
    sospechosas = marcas[marcas[ANOMALY_COL]]

    # El pico del dia 50 entra en las ventanas que terminan entre el 50 y el 63.
    dentro = sospechosas[sospechosas[S.SERIES_ID] == "1_1"][S.DATE]
    ventana_pico = pd.date_range("2024-02-20", "2024-03-04")  # dias 50..63
    assert any(d in ventana_pico for d in dentro), "no marco la ventana con el pico"


def test_score_no_reajusta_el_umbral() -> None:
    """Si el umbral se recalculara, el resultado dependeria del lote que se pase.

    Marcar "el 1 % mas raro del lote" hace que una ventana pase de anomala a normal
    solo por venir acompanada de otras, lo que es inaceptable para un filtro.
    """
    panel = _panel({"1_1": _serie(80, semilla=9), "1_2": _serie(80, nivel=9.0, semilla=10)})
    det = WindowAnomalyDetector(window=14).fit(panel)
    umbral = det.umbral_

    solo_una = panel[panel[S.SERIES_ID] == "1_1"]
    a = det.score(solo_una)
    b = det.score(panel)
    assert det.umbral_ == umbral, "el umbral se movio al puntuar"

    # La misma ventana tiene que recibir el mismo puntaje en los dos lotes.
    junto = a.merge(b, on=[S.SERIES_ID, S.DATE], suffixes=("_sola", "_junta"))
    assert not junto.empty
    assert junto[f"{SCORE_COL}_sola"].to_numpy() == pytest.approx(
        junto[f"{SCORE_COL}_junta"].to_numpy()
    )


def test_score_antes_de_fit_levanta() -> None:
    panel = _panel({"1_1": _serie(40)})
    with pytest.raises(RuntimeError, match="fit antes de score"):
        WindowAnomalyDetector().score(panel)


def test_el_detector_ignora_el_nivel_de_la_serie() -> None:
    """Sin normalizar, marcaria toda la alta rotacion, que es escala y no rareza."""
    panel = _panel(
        {f"1_{i}": _serie(80, nivel=2.0, amplitud=0.3, semilla=i) for i in range(1, 6)}
        | {"2_1": _serie(80, nivel=200.0, amplitud=0.3, semilla=20)}
    )
    det = WindowAnomalyDetector(window=14, contamination=0.05).fit(panel)
    marcas = det.score(panel)

    tasa_alta = marcas[marcas[S.SERIES_ID] == "2_1"][ANOMALY_COL].mean()
    assert tasa_alta < 0.5, f"marco el {tasa_alta:.0%} de la serie de nivel alto por su escala"


def test_series_mas_cortas_que_la_ventana_no_rompen() -> None:
    panel = _panel({"1_1": _serie(40), "1_2": _serie(5)})
    det = WindowAnomalyDetector(window=14).fit(panel)
    marcas = det.score(panel)
    assert set(marcas[S.SERIES_ID].unique()) == {"1_1"}


def test_el_contraste_con_censura_reporta_lo_nuevo() -> None:
    """La medicion que dice si aporta: lo marcado que NO estaba anotado."""
    panel = _panel({f"1_{i}": _serie(80, ceros=0.2, semilla=i) for i in range(1, 6)})
    det = WindowAnomalyDetector(window=14, contamination=0.05).fit(panel)
    tabla = det.contraste_con_censura(panel)

    assert {"marcadas", "ya_eran_quiebre", "hallazgos_nuevos"} <= set(tabla.columns)
    assert 0.0 <= tabla["ya_eran_quiebre"].iloc[0] <= 1.0
    assert tabla["hallazgos_nuevos"].iloc[0] <= tabla["marcadas"].iloc[0]


# --- Anomalias sobre el residuo ------------------------------------------
def test_las_anomalias_del_residuo_encuentran_lo_inesperado() -> None:
    """Detectar sobre la serie encuentra lo raro; sobre el residuo, lo no previsto."""
    n = 60
    res = pd.DataFrame(
        {
            S.SERIES_ID: ["1_1"] * n,
            "y_true": [3.0] * n,
            "y_pred": [3.0] * n,
        }
    )
    res.loc[30, "y_true"] = 30.0  # el modelo no lo vio venir

    out = residual_anomalies(res, z=3.0)
    assert bool(out.loc[30, ANOMALY_COL]), "no marco la sorpresa"
    assert int(out[ANOMALY_COL].sum()) == 1


def test_un_residuo_constante_no_tiene_sorpresas() -> None:
    """Desvio cero: no hay nada inesperado, y no puede salir NaN como anomalia."""
    res = pd.DataFrame({S.SERIES_ID: ["1_1"] * 20, "y_true": [3.0] * 20, "y_pred": [2.5] * 20})
    out = residual_anomalies(res)
    assert not out[ANOMALY_COL].any()
    assert out[ANOMALY_COL].notna().all()


def test_el_residuo_se_estandariza_por_serie() -> None:
    """Tres unidades de error son normales en alta rotacion y enormes en baja."""
    n = 40
    res = pd.DataFrame(
        {
            S.SERIES_ID: ["alta"] * n + ["baja"] * n,
            "y_true": list(np.linspace(90, 110, n)) + [3.0] * n,
            "y_pred": [100.0] * n + [3.0] * n,
        }
    )
    res.loc[n + 5, "y_true"] = 6.0  # +3 sobre una serie de nivel 3

    out = residual_anomalies(res, z=3.0)
    assert bool(out.loc[n + 5, ANOMALY_COL]), "el error chico en la serie chica es grande"
    assert not out[out[S.SERIES_ID] == "alta"][ANOMALY_COL].any()


def test_el_residuo_exige_las_columnas_del_contrato() -> None:
    with pytest.raises(ValueError, match="faltan columnas"):
        residual_anomalies(pd.DataFrame({S.SERIES_ID: ["1_1"], "y_true": [1.0]}))
