"""Endpoints operativos: alertas, resumen del dataset, pipeline y recarga.

Reusan el fixture de `test_api.py`: panel sintetico en disco y artefactos en un
directorio temporal.
"""

from __future__ import annotations

import os
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from blindside import config as cfg
from blindside.data import schema as S
from blindside.evaluate import triage as T
from tests.test_api import _save_both_bases, _save_quantile_bases


# --- Merma, como logica pura -----------------------------------------------
def test_merma_se_mide_sobre_la_demanda_esperada() -> None:
    lineas = pd.DataFrame(
        {
            S.SERIES_ID: ["a", "a", "b", "b"],
            "expected_demand": [1.0, 1.0, 2.0, 2.0],
            "overage_model": [0.1, 0.1, 0.2, 0.2],
            "overage_policy": [0.6, 0.6, 0.1, 0.1],
        }
    )
    m = T.merma_signals(lineas)
    # a: la politica deja sin vender 1,2 de 2 esperadas.
    assert m.loc["a", "merma_politica"] == pytest.approx(0.6)
    assert m.loc["a", "merma_evitable"] == pytest.approx(0.5)
    # b: la politica deja menos que el modelo; no hay merma evitable.
    assert m.loc["b", "merma_evitable"] == 0.0


def test_riesgo_de_merma_exige_que_la_orden_sugerida_la_reduzca() -> None:
    """Sobrante alto con cualquier orden razonable no se arregla bajando la cantidad."""
    señales = pd.DataFrame(
        {
            "merma_politica": [0.8, 0.8, 0.2],
            "merma_evitable": [0.4, 0.0, 0.0],
        },
        index=pd.Index(["evitable", "inevitable", "normal"], name=S.SERIES_ID),
    )
    m = T.triage(señales, grupos=[T.GRUPO_MERMA])
    assert m["riesgo_merma"].tolist() == [True, False, False]


def test_los_grupos_urgentes_van_primero() -> None:
    urgentes = [g.urgente for g in T.TODOS_LOS_GRUPOS]
    assert urgentes == sorted(urgentes, reverse=True)
    assert {g.clave for g in T.TODOS_LOS_GRUPOS} >= {"quebrado_ahora", "riesgo_merma"}


# --- /alerts -----------------------------------------------------------------
def test_alertas_sin_modelo_con_cuantiles_dicen_que_falta(panel_on_disk, recovered_panel) -> None:
    from api import main

    _save_both_bases(panel_on_disk, recovered_panel)  # naive: sin cuantiles
    with TestClient(main.app) as client:
        body = client.get("/alerts").json()

    claves = {g["key"] for g in body["groups"]}
    assert "riesgo_merma" not in claves
    faltan = {u["key"]: u["reason"] for u in body["unavailable"]}
    assert "riesgo_merma" in faltan and "make train" in faltan["riesgo_merma"]
    # Sin backtest guardado tampoco hay error por serie, y lo dice.
    assert "no_confiable" in faltan


def test_alertas_con_cuantiles_incluyen_merma(panel_on_disk, recovered_panel) -> None:
    from api import main

    _save_quantile_bases(panel_on_disk, recovered_panel)
    with TestClient(main.app) as client:
        body = client.get("/alerts?limit=1000").json()
        assert client.get("/alerts?group=no_existe").status_code == 404

    grupos = {g["key"]: g for g in body["groups"]}
    assert "riesgo_merma" in grupos
    assert grupos["riesgo_merma"]["urgent"] is True
    assert grupos["riesgo_merma"]["threshold"]
    # Cada item flaggeado dice por que, y trae las cifras de su motivo.
    assert body["total"] == len(body["items"]) == body["n_flagged"]
    for item in body["items"]:
        assert item["reasons"], "una serie en la lista sin motivo es ruido"
        assert item["waste_policy"] is not None
        assert item["label"]


def test_filtrar_por_grupo_devuelve_solo_ese_motivo(panel_on_disk, recovered_panel) -> None:
    from api import main

    _save_quantile_bases(panel_on_disk, recovered_panel)
    with TestClient(main.app) as client:
        body = client.get("/alerts?group=alto_volumen").json()
    assert body["items"]
    assert all("alto_volumen" in i["reasons"] for i in body["items"])


# --- /dataset/summary --------------------------------------------------------
def test_resumen_del_dataset_cierra_contra_el_panel(panel_on_disk, recovered_panel) -> None:
    from api import main

    with TestClient(main.app) as client:
        body = client.get("/dataset/summary").json()

    assert body["totals"]["n_series"] == recovered_panel[S.SERIES_ID].nunique()
    assert len(body["daily"]) == recovered_panel[S.DATE].nunique()
    total = sum(d["observed"] for d in body["daily"])
    assert total == pytest.approx(float(recovered_panel[S.SALE_AMOUNT].sum()), rel=1e-4)
    assert len(body["weekday"]) == 7
    assert sum(b["n_series"] for b in body["stockout_hist"]) == body["totals"]["n_series"]
    assert sum(s["n_series"] for s in body["stores"]) == body["totals"]["n_series"]
    # La recuperada nunca queda por debajo de la observada.
    assert all(d["recovered"] >= d["observed"] - 1e-6 for d in body["daily"])
    # Sin capa horaria en disco el perfil no se inventa: viene vacio y con motivo.
    assert body["hourly"] == [] and body["hourly_note"]


# --- /pipeline y frescura -----------------------------------------------------
def test_pipeline_es_de_solo_lectura_y_dice_que_correr(panel_on_disk, recovered_panel) -> None:
    from api import main

    _save_both_bases(panel_on_disk, recovered_panel)
    with TestClient(main.app) as client:
        body = client.get("/pipeline").json()
        # Ningun verbo de escritura sobre el pipeline.
        assert client.post("/pipeline").status_code == 405

    assert body["freshness"]["status"] == "al_dia"
    assert body["freshness"]["days_behind"] == 0
    assert any("make update" in s["command"] for s in body["steps"])
    assert {a["basis"] for a in body["artifacts"]} == {"observed", "recovered"}
    assert body["updates"] == []


def test_la_frescura_detecta_un_modelo_que_no_vio_los_ultimos_dias(
    panel_on_disk, recovered_panel
) -> None:
    from api import main

    from blindside.models.base import TARGET_BY_BASIS
    from blindside.models.baselines import SeasonalNaiveForecaster

    corte = recovered_panel[S.DATE].max() - pd.Timedelta(days=4)
    viejo = recovered_panel[recovered_panel[S.DATE] <= corte]
    for basis, target in TARGET_BY_BASIS.items():
        SeasonalNaiveForecaster().fit(viejo, target=target).save(
            panel_on_disk / cfg.MODEL_FILES[basis]
        )
    with TestClient(main.app) as client:
        fresca = client.get("/health").json()["freshness"]
    assert fresca["status"] == "desfasado"
    assert fresca["days_behind"] == 4


def test_la_api_recarga_sola_cuando_cambia_el_panel(
    panel_on_disk, recovered_panel, monkeypatch
) -> None:
    """La mitad de lectura de la actualizacion continua: nadie reinicia la API."""
    from api import main

    monkeypatch.setattr(main, "RELOAD_INTERVAL_S", 1e-6)
    demand = cfg.DATA_PROCESSED / cfg.DEMAND_FILE
    corte = recovered_panel[S.DATE].max() - pd.Timedelta(days=3)
    recovered_panel[recovered_panel[S.DATE] <= corte].to_parquet(demand, index=False)

    with TestClient(main.app) as client:
        antes = client.get("/health").json()["panel"]["date_max"]
        recovered_panel.to_parquet(demand, index=False)
        # Fecha de modificacion distinta aunque el sistema de archivos sea grueso.
        st = demand.stat()
        os.utime(demand, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        time.sleep(0.01)
        despues = client.get("/health").json()["panel"]["date_max"]

    assert antes == str(corte.date())
    assert despues == str(recovered_panel[S.DATE].max().date())


# --- Rediseño: /reorder/catalog, store_ids, filtros de alertas, /explain ------
def test_el_catalogo_ordena_todo_el_panel_y_no_solo_una_pagina(
    panel_on_disk, recovered_panel
) -> None:
    """E7: la primera fila tiene que ser la de mayor ahorro de **todo** el catalogo."""
    from api import main

    _save_quantile_bases(panel_on_disk, recovered_panel)
    with TestClient(main.app) as client:
        todo = client.get("/reorder/catalog?limit=500").json()
        pagina = client.get("/reorder/catalog?limit=5").json()
        segunda = client.get("/reorder/catalog?limit=5&offset=5").json()

    ahorros = [i["saving"] for i in todo["items"]]
    assert ahorros == sorted(ahorros, reverse=True)
    assert pagina["items"][0]["series"]["series_id"] == todo["items"][0]["series"]["series_id"]
    assert pagina["total"] == recovered_panel[S.SERIES_ID].nunique()
    # Las paginas no se pisan.
    ids_1 = {i["series"]["series_id"] for i in pagina["items"]}
    ids_2 = {i["series"]["series_id"] for i in segunda["items"]}
    assert not ids_1 & ids_2
    # Las participaciones en el ahorro suman 1 sobre el catalogo filtrado.
    assert sum(i["saving_share"] for i in todo["items"]) == pytest.approx(1.0, abs=1e-6)


def test_el_catalogo_coincide_con_reorder_para_la_misma_serie(
    panel_on_disk, recovered_panel
) -> None:
    """Las dos rutas usan el mismo calculo; una cantidad distinta seria un bug."""
    from api import main

    _save_quantile_bases(panel_on_disk, recovered_panel)
    with TestClient(main.app) as client:
        item = client.get("/reorder/catalog?limit=1").json()["items"][0]
        sid = item["series"]["series_id"]
        linea = client.post("/reorder", json={"series_ids": [sid], "co": 0.6}).json()["lines"][0]

    assert item["qty"] == pytest.approx(linea["qty"])
    assert item["policy_qty"] == pytest.approx(linea["policy_qty"])


def test_el_catalogo_filtra_por_tienda_y_clase_y_cambia_con_la_base(
    panel_on_disk, recovered_panel
) -> None:
    from api import main

    _save_quantile_bases(panel_on_disk, recovered_panel)
    with TestClient(main.app) as client:
        tienda = client.get("/reorder/catalog?store_id=1&limit=500").json()
        observada = client.get("/reorder/catalog?recover_censoring=false&limit=1").json()
        recuperada = client.get("/reorder/catalog?limit=1").json()
        por_serie = client.get("/reorder/catalog?sort=serie&dir=asc&limit=500").json()

    assert tienda["total"] == 8
    assert all(i["series"]["store_id"] == 1 for i in tienda["items"])
    assert tienda["totals"]["n_series"] == 8
    assert observada["basis"] == "observed" and recuperada["basis"] == "recovered"
    assert observada["totals"]["qty"] != pytest.approx(recuperada["totals"]["qty"])
    ids = [i["series"]["series_id"] for i in por_serie["items"]]
    assert ids == sorted(ids)


def test_health_declara_los_ids_reales_de_tienda(panel_on_disk, recovered_panel) -> None:
    """E1: el filtro armaba `range(n_stores)` y los ids reales no son contiguos."""
    from api import main

    with TestClient(main.app) as client:
        panel = client.get("/health").json()["panel"]
    assert panel["store_ids"] == sorted(int(s) for s in recovered_panel[S.STORE_ID].unique())


def test_alertas_filtran_por_clase_y_por_serie(panel_on_disk, recovered_panel) -> None:
    """E6: la clase de rotacion no se aplicaba a las alertas."""
    from api import main

    _save_quantile_bases(panel_on_disk, recovered_panel)
    with TestClient(main.app) as client:
        todas = client.get("/alerts?limit=1000").json()
        altas = client.get("/alerts?rotation_band=alta&limit=1000").json()
        sid = todas["items"][0]["series"]["series_id"]
        una = client.get(f"/alerts?series_id={sid}").json()

    assert altas["items"], "el panel sintetico tiene series de alta rotacion en alerta"
    assert all(i["rotation_band"] == "alta" for i in altas["items"])
    assert altas["total"] < todas["total"]
    assert [i["series"]["series_id"] for i in una["items"]] == [sid]


def test_explain_explica_la_misma_cifra_que_la_cantidad_sugerida(
    panel_on_disk, recovered_panel
) -> None:
    """E2: se explicaba la mediana y la pantalla mostraba otra cantidad.

    Con el modelo cuantilico la cifra explicada es la salida del cuantil critico,
    o sea la orden. La identidad base + aportes + resto tiene que cerrar exacta.
    """
    from api import main

    from blindside.models.gbdt import LightGBMQuantileForecaster

    # Un LightGBM chico de verdad: el doble de juguete no tiene boosters que explicar.
    for basis, target in (("recovered", S.DEMAND_LATENT), ("observed", S.SALE_AMOUNT)):
        modelo = LightGBMQuantileForecaster(
            quantiles=(0.05, 0.5, 0.625, 0.9, 0.95), n_estimators=20
        ).fit(recovered_panel, target=target)
        modelo.save(panel_on_disk / cfg.MODEL_FILES[basis])

    with TestClient(main.app) as client:
        sid = "0_0"
        linea = client.post("/reorder", json={"series_ids": [sid], "co": 0.6}).json()["lines"][0]
        ex = client.post("/explain", json={"series_id": sid, "dt": linea["dt"], "top_k": 5}).json()

    cierre = ex["base_value"] + sum(c["contribution"] for c in ex["contributions"]) + ex["rest"]
    assert ex["prediction"] == pytest.approx(cierre, abs=1e-6)
    assert ex["prediction"] == pytest.approx(linea["qty"], rel=1e-6)
    assert ex["point_forecast"] is not None
