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
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    monkeypatch.setattr(cfg, "ARTIFACTS", artifacts)
    return artifacts


def test_health_without_artifact(panel_on_disk) -> None:
    """Sin artefacto la API arranca igual y lo dice. Es el estado de un clon nuevo."""
    from api import main

    with TestClient(main.app) as client:
        body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["model_loaded"] is False
    assert body["model_error"] is None  # no hay artefacto, no hay error de carga


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
        assert len(body) == 5
        assert {"series_id", "store_id", "product_id"} <= set(body[0])

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
