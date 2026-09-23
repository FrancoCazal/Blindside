"""La API degrada en vez de caerse.

El caso que fija este archivo paso de verdad. `joblib` graba la **ruta del modulo**
dentro del pickle, asi que al renombrar el paquete de `dfcore` a `blindside` todo
artefacto anterior murio con `ModuleNotFoundError: No module named 'dfcore'`. La
API no lo manejaba: explotaba en el arranque y el contenedor entraba en bucle de
reinicio.

La misma falla aparece con cualquier desfasaje entre artefacto y codigo — una clase
renombrada, un modulo movido, una version de scikit-learn distinta de la que
serializo. Es una condicion **esperable en operacion**, no una excepcion
excepcional, y por eso tiene que degradar a `model_loaded: false` con el motivo a
la vista en vez de tumbar el servicio.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from blindside import config as cfg
from blindside.data import schema as S


@pytest.fixture()
def panel_on_disk(recovered_panel: pd.DataFrame, tmp_path, monkeypatch):
    """Escribe el panel en un directorio temporal y apunta la config ahi."""
    processed = tmp_path / "processed"
    processed.mkdir(parents=True)
    recovered_panel.to_parquet(processed / cfg.DEMAND_FILE, index=False)

    monkeypatch.setattr(cfg, "DATA_PROCESSED", processed)
    monkeypatch.setattr(cfg, "DATA_SAMPLE", tmp_path / "sample_vacio")
    # Sin manifiesto no hay referencia de panel completo, y eso tiene que ser el
    # default del test: si apuntara al data/interim/ real, el resultado dependeria
    # de si la maquina descargo el dataset.
    monkeypatch.setattr(cfg, "DATA_INTERIM", tmp_path / "interim_vacio")
    # Idem con los reportes: si apuntara al reports/ real, la cobertura por
    # horizonte dependeria de si en esta maquina se corrio `make models`.
    monkeypatch.setattr(cfg, "REPORTS", tmp_path / "reports_vacio")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    monkeypatch.setattr(cfg, "ARTIFACTS", artifacts)
    return artifacts


def _save_both_bases(artifacts, panel: pd.DataFrame) -> None:
    """Serializa un artefacto por base, como hace `make train`."""
    from blindside.models.base import TARGET_BY_BASIS
    from blindside.models.baselines import SeasonalNaiveForecaster

    for basis, target in TARGET_BY_BASIS.items():
        model = SeasonalNaiveForecaster().fit(panel, target=target)
        model.save(artifacts / cfg.MODEL_FILES[basis])


def test_health_without_artifact(panel_on_disk) -> None:
    """Sin artefacto la API arranca igual y lo dice. Es el estado de un clon nuevo."""
    from api import main

    with TestClient(main.app) as client:
        body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["model_loaded"] is False
    assert body["model_error"] is None  # no hay artefacto, no hay error de carga

    # Y lo dice **por base**: las dos faltan, con el nombre de archivo que falta.
    bases = {m["basis"]: m for m in body["models"]}
    assert set(bases) == {"observed", "recovered"}
    assert not any(m["loaded"] for m in bases.values())
    assert bases["observed"]["artifact"] == cfg.MODEL_FILES["observed"]


def test_unloadable_artifact_does_not_crash_the_api(panel_on_disk) -> None:
    """Un artefacto ilegible degrada el servicio, no lo mata.

    Se simula con un archivo que no es un pickle valido. El efecto es el mismo que
    el del rename: `Forecaster.load` levanta y la API tiene que sobrevivir.
    """
    from api import main

    (panel_on_disk / "model.joblib").write_bytes(b"esto no es un pickle")

    with TestClient(main.app) as client:
        body = client.get("/health").json()

        assert body["status"] == "ok", "la API tiene que arrancar igual"
        assert body["model_loaded"] is False
        assert body["model_error"], "tiene que decir por que fallo, no solo que fallo"

        # Y los endpoints que dependen del modelo responden 503 con el motivo,
        # distinguible del caso "no hay artefacto".
        resp = client.post("/forecast", json={"series_ids": ["1_1"], "horizon": 3})
        assert resp.status_code == 503
        assert "reentrenar" in resp.json()["detail"].lower()


def test_series_endpoint_works_without_a_model(panel_on_disk) -> None:
    """Los endpoints de solo datos no dependen del artefacto.

    Importa porque el dashboard lee los parquet directamente: si la API se queda
    sin modelo, la superficie de datos tiene que seguir en pie.
    """
    from api import main

    with TestClient(main.app) as client:
        resp = client.get("/series?limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 5
        # El total va aparte de la pagina: el selector muestra "5 de 24".
        assert body["total"] > 5
        assert {"series_id", "store_id", "product_id", "label"} <= set(body["items"][0])

        censoring = client.get("/censoring")
        assert censoring.status_code == 200
        assert censoring.json()["summary"]["n_series"] > 0


def test_forecast_rejects_unknown_series(panel_on_disk) -> None:
    from api import main

    with TestClient(main.app) as client:
        resp = client.post("/forecast", json={"series_ids": ["no_existe"], "horizon": 3})
    # 503 si no hay modelo, 404 si lo hay y la serie no existe. Cualquiera de los
    # dos es correcto; lo que no puede es 200 ni 500.
    assert resp.status_code in (404, 503)


def test_health_reports_the_training_cutoff(panel_on_disk, recovered_panel) -> None:
    """`trained_until` existe para detectar un artefacto viejo de un vistazo."""
    from blindside.models.baselines import SeasonalNaiveForecaster

    model = SeasonalNaiveForecaster().fit(recovered_panel, target=S.DEMAND_LATENT)
    model.save(panel_on_disk / "model.joblib")

    from api import main

    with TestClient(main.app) as client:
        body = client.get("/health").json()

    assert body["model_loaded"] is True
    assert body["model_name"] == "seasonal_naive"
    assert body["trained_until"] == str(recovered_panel[S.DATE].max().date())
    assert body["model_error"] is None


# --- El toggle de censura -------------------------------------------------
# Son dos artefactos y no uno. Con un solo modelo el control cambia la serie que
# se dibuja pero devuelve la misma cantidad sugerida en las dos posiciones, y
# entonces la afirmacion central del proyecto — corregir la censura cambia lo que
# hay que pedir — se queda sin evidencia en la unica pantalla que la muestra.


def test_forecast_honours_the_basis(panel_on_disk, recovered_panel) -> None:
    """Cada base contesta con su propio artefacto, y las dos no dan lo mismo."""
    _save_both_bases(panel_on_disk, recovered_panel)
    series = sorted(recovered_panel[S.SERIES_ID].astype(str).unique())[:5]

    from api import main

    with TestClient(main.app) as client:
        recovered = client.post(
            "/forecast",
            json={"series_ids": series, "horizon": 7, "recover_censoring": True},
        )
        observed = client.post(
            "/forecast",
            json={"series_ids": series, "horizon": 7, "recover_censoring": False},
        )

    assert recovered.status_code == 200
    assert observed.status_code == 200
    assert recovered.json()["basis"] == "recovered"
    assert observed.json()["basis"] == "observed"

    def total(body) -> float:
        return sum(p["y_pred"] for f in body["forecasts"] for p in f["points"])

    total_recovered = total(recovered.json())
    total_observed = total(observed.json())
    # La recuperada no puede pronosticar menos que la observada: la demanda latente
    # es la venta mas lo que no se pudo vender. Y tiene que ser estrictamente mayor,
    # o el toggle no esta cambiando de artefacto.
    assert total_recovered > total_observed


def test_reorder_honours_the_basis(panel_on_disk, recovered_panel) -> None:
    """La cantidad a pedir depende de la base. Es el punto del control."""
    _save_both_bases(panel_on_disk, recovered_panel)
    series = sorted(recovered_panel[S.SERIES_ID].astype(str).unique())[:3]

    from api import main

    with TestClient(main.app) as client:
        resp = client.post(
            "/reorder",
            json={"series_ids": series, "horizon": 7, "recover_censoring": False},
        )

    # SeasonalNaive no emite cuantiles, asi que la orden no se puede derivar: 501
    # con el motivo. Lo que se verifica aca es que el 501 nombre el modelo de la
    # base pedida y no el de la otra.
    assert resp.status_code == 501
    assert "observed" in resp.json()["detail"]


def test_artifact_trained_on_the_wrong_basis_is_rejected(panel_on_disk, recovered_panel) -> None:
    """Un artefacto cruzado no se sirve: haria que el toggle mienta sin fallar.

    Si el modelo de demanda latente se sirviera como base observada, las dos
    posiciones del control devolverian el mismo numero. La interfaz mostraria una
    diferencia de cero y el efecto que el proyecto mide parecerian ser ruido.
    """
    from blindside.models.baselines import SeasonalNaiveForecaster

    model = SeasonalNaiveForecaster().fit(recovered_panel, target=S.DEMAND_LATENT)
    model.save(panel_on_disk / cfg.MODEL_FILES["observed"])  # la base equivocada

    from api import main

    with TestClient(main.app) as client:
        body = client.get("/health").json()
        resp = client.post(
            "/forecast",
            json={"series_ids": ["0_0"], "horizon": 3, "recover_censoring": False},
        )

    observed = next(m for m in body["models"] if m["basis"] == "observed")
    assert observed["loaded"] is False
    assert S.DEMAND_LATENT in observed["error"] and S.SALE_AMOUNT in observed["error"]

    assert resp.status_code == 503
    assert "observed" in resp.json()["detail"]


# --- Selector -------------------------------------------------------------
def test_series_search_and_pagination(panel_on_disk, recovered_panel) -> None:
    """La busqueda cubre el codigo y la jerarquia, y la pagina informa el total.

    Un desplegable con 3066 series no es usable, asi que el selector busca. Y sin
    `total` no se puede distinguir "no hay resultados" de "hay mas, pagina".
    """
    from api import main

    with TestClient(main.app) as client:
        todas = client.get("/series?limit=1000").json()
        por_codigo = client.get("/series?q=1_3").json()
        por_jerarquia = client.get("/series?q=tienda 2").json()
        por_tienda = client.get("/series?store_id=1&limit=1000").json()
        pagina = client.get("/series?limit=3&offset=3").json()

    assert todas["total"] == recovered_panel[S.SERIES_ID].nunique()
    assert [i["series_id"] for i in por_codigo["items"]] == ["1_3"]

    # La busqueda por jerarquia trae **todas** las series de esa tienda. No trae
    # solo esas: con un catalogo sin nombres, la etiqueta es una lista de ids y un
    # numero suelto tambien aparece en el producto o la categoria. La precision la
    # da el filtro `store_id`, la busqueda esta para descubrir.
    de_la_tienda = {
        sid for sid in recovered_panel[S.SERIES_ID].astype(str).unique() if sid.startswith("2_")
    }
    assert de_la_tienda <= {i["series_id"] for i in por_jerarquia["items"]}
    assert all(i["store_id"] == 1 for i in por_tienda["items"])
    assert por_tienda["total"] == len(por_tienda["items"])

    # La paginacion es estable: ordenada por series_id y sin solapamiento.
    assert pagina["offset"] == 3
    assert [i["series_id"] for i in pagina["items"]] == [
        i["series_id"] for i in todas["items"][3:6]
    ]

    # La etiqueta es la jerarquia, no un nombre inventado: el dataset no trae
    # nombres de producto.
    assert "producto" in todas["items"][0]["label"]


# --- Historia observada contra latente -----------------------------------
def test_series_history_returns_both_curves(panel_on_disk, recovered_panel) -> None:
    """Las dos series salen juntas y alineadas, con los tramos de quiebre.

    Es el endpoint de la pantalla principal. La comprobacion que importa es la
    ultima: el uplift en los dias **sin** quiebre tiene que ser exactamente cero,
    porque esos dias son la verdad de terreno con la que se mide el sesgo y
    corregirlos destruiria la medicion.
    """
    from api import main

    sid = sorted(recovered_panel[S.SERIES_ID].astype(str).unique())[0]
    with TestClient(main.app) as client:
        body = client.get(f"/series/{sid}/history").json()
        recorte = client.get(f"/series/{sid}/history?days=30").json()
        faltante = client.get("/series/no_existe/history")

    esperado = recovered_panel[recovered_panel[S.SERIES_ID].astype(str) == sid]
    assert len(body["points"]) == len(esperado)
    assert body["open_hours"] == len(cfg.CENSORING.open_hours)
    assert len(recorte["points"]) == 30
    assert faltante.status_code == 404

    for p in body["points"]:
        assert p["recovered"] >= p["observed"] - 1e-9
        if not p["is_censored"]:
            assert p["recovered"] == pytest.approx(p["observed"])

    # Los tramos cubren exactamente los dias marcados como censurados.
    assert sum(r["n_days"] for r in body["runs"]) == body["summary"]["n_censored_days"]
    assert body["summary"]["max_run_days"] == max(r["n_days"] for r in body["runs"])
    assert body["summary"]["uplift_pct"] > 0
    assert body["summary"]["uplift_pct_clean_days"] == pytest.approx(0.0, abs=1e-9)


def test_series_history_batch_serves_the_table(panel_on_disk, recovered_panel) -> None:
    """La tabla de reposicion necesita historia por fila: una llamada, no N.

    El sparkline de quiebre y la comparacion contra la politica de media movil se
    calculan sobre la historia, asi que sin el lote la pantalla haria una consulta
    por fila visible contra un panel que ya esta en memoria.
    """
    from api import main

    ids = sorted(recovered_panel[S.SERIES_ID].astype(str).unique())[:4]
    with TestClient(main.app) as client:
        resp = client.post("/series/history", json={"series_ids": ids, "days": 14})
        faltante = client.post("/series/history", json={"series_ids": ["no_existe"]})

    assert resp.status_code == 200
    body = resp.json()["series"]
    assert [s["series"]["series_id"] for s in body] == ids
    assert all(len(s["points"]) == 14 for s in body)
    assert faltante.status_code == 404


# --- Pantallas de evidencia ----------------------------------------------
def test_series_serves_the_rotation_band(panel_on_disk, recovered_panel) -> None:
    """La columna "Clase" de la tabla sale de la misma banda que el backtest.

    Que el modelo complejo no le gane al ingenuo en baja rotacion es un resultado
    esperado, pero solo se puede leer en la lista si cada fila declara su clase.
    """
    from api import main

    with TestClient(main.app) as client:
        items = client.get("/series?limit=25").json()["items"]

    bandas = {i["rotation_band"] for i in items}
    assert bandas <= {"baja", "media", "alta"}
    assert len(bandas) > 1, "con 24 series sinteticas tienen que aparecer varias clases"


def test_products_map_is_a_measured_projection(panel_on_disk, recovered_panel) -> None:
    """El mapa es PCA sobre features de comportamiento, no un scatter dibujado.

    La varianza explicada viaja en la respuesta porque un scatter sin ella invita a
    leer distancias que la proyeccion no conserva.
    """
    from api import main

    with TestClient(main.app) as client:
        body = client.get("/products/map").json()

    assert body["method"] == "pca"
    assert len(body["points"]) == recovered_panel[S.PRODUCT_ID].nunique()
    assert len(body["explained_variance"]) == 2
    assert all(0 <= v <= 1 for v in body["explained_variance"])
    assert sum(body["explained_variance"]) <= 1.0 + 1e-9
    punto = body["points"][0]
    assert punto["rotation_band"] in {"baja", "media", "alta"}
    assert punto["n_series"] >= 1


def test_backtest_breakdown_exposes_every_origin(
    panel_on_disk, recovered_panel, tmp_path, monkeypatch
) -> None:
    """Las ocho lineas por origen ya estaban en el parquet; esto las expone.

    El agregado solo no alcanza: un promedio bueno esconde un origen catastrofico, y
    es el origen malo el que despues pasa en produccion.
    """
    from blindside import config as cfg_mod
    from blindside.evaluate.backtest import run_backtest
    from blindside.models.baselines import SeasonalNaiveForecaster

    reports = tmp_path / "reports_breakdown"
    reports.mkdir()
    forecast = cfg_mod.ForecastConfig(n_origins=3)
    result = run_backtest(recovered_panel, [SeasonalNaiveForecaster()], forecast=forecast)
    result.to_parquet(reports / "backtest_models.parquet", index=False)
    monkeypatch.setattr(cfg, "REPORTS", reports)

    from api import main

    with TestClient(main.app) as client:
        body = client.get("/backtest/breakdown").json()

    assert body["n_origins"] == 3
    assert {r["origin"] for r in body["origins"]} == {0, 1, 2}
    assert {r["h"] for r in body["horizons"]} == set(range(1, 8))
    assert {r["band"] for r in body["bands"]} <= {"baja", "media", "alta"}
    assert all(r["metric"] in {"mase", "wape", "mae", "coverage"} for r in body["origins"])


def test_explain_returns_real_contributions_or_says_why_not(panel_on_disk, recovered_panel) -> None:
    """Las contribuciones las calcula LightGBM, no el paquete `shap`.

    Con un baseline cargado el endpoint no puede explicar nada, y eso tiene que ser
    un 501 que nombre el motivo en vez de una respuesta vacia o inventada.
    """
    from blindside.models.baselines import SeasonalNaiveForecaster

    model = SeasonalNaiveForecaster().fit(recovered_panel, target=S.DEMAND_LATENT)
    model.save(panel_on_disk / cfg.MODEL_FILES["recovered"])

    from api import main

    with TestClient(main.app) as client:
        dt = str((recovered_panel[S.DATE].max() + pd.Timedelta(days=1)).date())
        resp = client.post("/explain", json={"series_id": "0_0", "dt": dt, "top_k": 5})
        fuera = client.post("/explain", json={"series_id": "0_0", "dt": "2020-01-01"})

    assert resp.status_code == 501
    assert "contribuciones" in resp.json()["detail"]
    # Una fecha fuera del horizonte tampoco puede devolver 200: el 404 lista las
    # fechas que si se pueden explicar.
    assert fuera.status_code in (404, 501)


# --- Estado global que la interfaz deriva de /health ----------------------
def test_health_reports_panel_counts_and_missing_coverage(panel_on_disk, recovered_panel) -> None:
    """Conteos del panel servido y el motivo por el que falta la cobertura.

    Un bloque de cobertura vacio **con el motivo** es honesto; un numero sintetico
    en su lugar seria contradictorio con lo que el proyecto mide, que es justamente
    la brecha entre cobertura prometida y cobertura real.
    """
    from api import main

    with TestClient(main.app) as client:
        body = client.get("/health").json()

    panel = body["panel"]
    assert panel["source"] == "processed"
    assert panel["is_sample"] is False
    assert panel["n_series"] == recovered_panel[S.SERIES_ID].nunique()
    assert panel["n_stores"] == recovered_panel[S.STORE_ID].nunique()
    assert panel["n_products"] == recovered_panel[S.PRODUCT_ID].nunique()
    # Sin manifiesto no hay referencia, y entonces la interfaz no puede afirmar
    # que esta viendo el panel completo.
    assert panel["reference_n_series"] is None

    assert body["coverage_nominal"] == cfg.FORECAST.coverage
    assert body["coverage_by_horizon"] == []
    assert "make models" in body["coverage_note"]


def test_health_flags_the_committed_sample(recovered_panel, tmp_path, monkeypatch) -> None:
    """Servir la muestra tiene que ser visible, con el conteo contra su referencia.

    Presentar 60 series como si fueran 3066 es el error que arruina una defensa, y
    la interfaz solo puede marcarlo si la API se lo dice.
    """
    sample = tmp_path / "sample"
    sample.mkdir()
    recovered_panel.to_parquet(sample / cfg.DEMAND_FILE, index=False)
    interim = tmp_path / "interim"
    interim.mkdir()
    (interim / cfg.MANIFEST_FILE).write_text(
        json.dumps({"n_series_actual": 3066, "n_stores": 38, "n_products": 309}),
        encoding="utf-8",
    )

    monkeypatch.setattr(cfg, "DATA_PROCESSED", tmp_path / "processed_vacio")
    monkeypatch.setattr(cfg, "DATA_SAMPLE", sample)
    monkeypatch.setattr(cfg, "DATA_INTERIM", interim)
    monkeypatch.setattr(cfg, "ARTIFACTS", tmp_path / "artifacts_vacio")
    monkeypatch.setattr(cfg, "REPORTS", tmp_path / "reports_vacio")

    from api import main

    with TestClient(main.app) as client:
        panel = client.get("/health").json()["panel"]

    assert panel["source"] == "sample"
    assert panel["is_sample"] is True
    assert panel["reference_n_series"] == 3066
    assert panel["n_series"] < panel["reference_n_series"]


def test_health_computes_empirical_coverage_by_horizon(
    panel_on_disk, tmp_path, monkeypatch
) -> None:
    """La cobertura por horizonte sale del backtest guardado, no del request.

    Se mide sobre un resultado con intervalos: 9 de cada 10 objetivos dentro de la
    banda dan 0,9 empirico contra 0,9 nominal.
    """
    from blindside.evaluate import contracts as C

    reports = tmp_path / "reports"
    reports.mkdir()
    rows = []
    for h in (1, 2, 3):
        for i in range(10):
            dentro = i < 9
            rows.append(
                {
                    C.MODEL: "conformal_lgbm",
                    C.HORIZON_STEP: h,
                    C.Y_TRUE: 1.0 if dentro else 9.0,
                    C.PRED_LO: 0.5,
                    C.PRED_HI: 1.5,
                }
            )
    pd.DataFrame(rows).to_parquet(reports / "backtest_models.parquet", index=False)
    monkeypatch.setattr(cfg, "REPORTS", reports)

    from api import main

    with TestClient(main.app) as client:
        body = client.get("/health").json()

    assert body["coverage_note"] is None
    assert [c["h"] for c in body["coverage_by_horizon"]] == [1, 2, 3]
    for point in body["coverage_by_horizon"]:
        assert point["coverage_empirical"] == pytest.approx(0.9)
        assert point["coverage_nominal"] == cfg.FORECAST.coverage
        assert point["n"] == 10


# --- CORS -----------------------------------------------------------------
# Sin esto el dev server del frontend no puede llamar a la API: es otro puerto y
# el navegador bloquea la respuesta. Con autenticacion ausente, el allowlist es
# lo que evita que cualquier pagina abierta lea los pronosticos del usuario.


def test_cors_allows_the_dev_server_and_nothing_else(panel_on_disk) -> None:
    from api import main

    permitido = "http://localhost:5173"
    with TestClient(main.app) as client:
        preflight = client.options(
            "/health",
            headers={
                "Origin": permitido,
                "Access-Control-Request-Method": "GET",
            },
        )
        ajeno = client.get("/health", headers={"Origin": "http://cualquiera.example"})

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == permitido
    # El origen ajeno recibe la respuesta sin el header, que es lo que hace que el
    # navegador la descarte. No es un 403: CORS se aplica del lado del cliente.
    assert "access-control-allow-origin" not in ajeno.headers


def test_cors_origins_can_be_overridden_by_env(monkeypatch) -> None:
    """El allowlist se configura sin editar el codigo, para el despliegue."""
    from api import main

    monkeypatch.delenv("BLINDSIDE_CORS_ORIGINS", raising=False)
    assert main.cors_origins() == list(main.DEFAULT_CORS_ORIGINS)

    monkeypatch.setenv("BLINDSIDE_CORS_ORIGINS", "https://blindside.example, http://otro:3000")
    assert main.cors_origins() == ["https://blindside.example", "http://otro:3000"]
