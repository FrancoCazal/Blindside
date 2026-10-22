"""Pipeline de actualizacion: upsert idempotente, conflictos y promocion segura.

Lo que estos tests fijan es lo que separa una actualizacion continua de "un
endpoint que recibe un CSV":

* Reingerir el mismo lote **no cambia nada**.
* Un lote que contradice datos ya cargados se **rechaza entero** y no escribe.
* Ninguna capa queda a medio escribir: la anterior siempre queda como `.prev`.
* Un artefacto nuevo no reemplaza al vigente sin pasar la prueba de humo, y el
  reemplazo se puede deshacer.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from blindside import config as cfg
from blindside.data import schema as S
from blindside.data import update as U
from blindside.models.base import TARGET_BY_BASIS
from blindside.models.baselines import SeasonalNaiveForecaster

DIAS_INICIALES = 90


def _raw(hourly_panel: pd.DataFrame) -> pd.DataFrame:
    """El panel sintetico en el esquema crudo de entrada: las 19 columnas."""
    return hourly_panel[list(S.RAW_COLUMNS)].copy()


@pytest.fixture()
def capas(synthetic_hourly_panel: pd.DataFrame, tmp_path, monkeypatch):
    """Panel vigente con los primeros 90 dias y el lote con los 7 siguientes."""
    for nombre, attr in (
        ("interim", "DATA_INTERIM"),
        ("processed", "DATA_PROCESSED"),
        ("sample", "DATA_SAMPLE"),
        ("artifacts", "ARTIFACTS"),
        ("incoming", "DATA_INCOMING"),
    ):
        d = tmp_path / nombre
        d.mkdir()
        monkeypatch.setattr(cfg, attr, d)

    raw = _raw(synthetic_hourly_panel)
    corte = raw[S.DATE].min() + pd.Timedelta(days=DIAS_INICIALES - 1)
    inicial = U.prepare_batch(raw[raw[S.DATE] <= corte])
    inicial["split"] = "train"
    paths = U.LayerPaths.of("processed")
    inicial.to_parquet(paths.panel, index=False)
    U.recover_demand(inicial).to_parquet(paths.demand, index=False)

    lote = tmp_path / "incoming" / "lote.parquet"
    raw[raw[S.DATE] > corte].to_parquet(lote, index=False)
    return {"paths": paths, "lote": lote, "raw": raw, "corte": corte}


# --- Upsert ----------------------------------------------------------------
def test_un_lote_nuevo_suma_filas_y_deja_respaldo(capas) -> None:
    paths = capas["paths"]
    antes = pd.read_parquet(paths.panel)

    report = U.ingest(capas["lote"])

    assert report.status == "ok"
    assert report.rows_new == 24 * 7
    assert report.rows_duplicate == report.rows_conflict == 0
    despues = pd.read_parquet(paths.panel)
    assert len(despues) == len(antes) + 24 * 7
    assert despues[S.DATE].max() > antes[S.DATE].max()

    # La demanda se recalculo sobre el panel nuevo y cumple su contrato.
    demanda = pd.read_parquet(paths.demand)
    assert len(demanda) == len(despues)
    S.validate_panel(demanda, required=S.DEMAND_REQUIRED, allow_gaps=True)

    # La version anterior quedo, para poder volver atras a mano.
    assert U.previous_of(paths.panel).exists()
    assert len(pd.read_parquet(U.previous_of(paths.panel))) == len(antes)
    assert U.previous_of(paths.demand).exists()


def test_reingerir_el_mismo_lote_no_cambia_nada(capas) -> None:
    """Idempotencia. Es lo que vuelve seguro reintentar despues de una falla."""
    paths = capas["paths"]
    U.ingest(capas["lote"])
    mtime = paths.panel.stat().st_mtime_ns
    filas = len(pd.read_parquet(paths.panel))

    report = U.ingest(capas["lote"])

    assert report.status == "sin_cambios"
    assert report.rows_new == 0
    assert report.rows_duplicate == 24 * 7
    assert paths.panel.stat().st_mtime_ns == mtime, "no tiene que reescribir la capa"
    assert len(pd.read_parquet(paths.panel)) == filas


def test_un_conflicto_rechaza_el_lote_entero_y_no_escribe(capas, tmp_path) -> None:
    """Corregir una venta ya registrada es una decision, no un efecto colateral."""
    paths = capas["paths"]
    raw = capas["raw"]
    ya_cargado = raw[raw[S.DATE] <= capas["corte"]].tail(30).copy()
    ya_cargado[S.SALE_AMOUNT] = ya_cargado[S.SALE_AMOUNT] + 5.0
    nuevo = raw[raw[S.DATE] > capas["corte"]]
    lote = tmp_path / "conflicto.parquet"
    pd.concat([ya_cargado, nuevo]).to_parquet(lote, index=False)

    mtime = paths.panel.stat().st_mtime_ns
    with pytest.raises(U.IngestRejectedError) as exc:
        U.ingest(lote)

    assert exc.value.report.rows_conflict == 30
    assert exc.value.report.status == "rechazado"
    assert exc.value.report.conflict_sample, "tiene que decir cuales filas chocan"
    assert paths.panel.stat().st_mtime_ns == mtime, "un lote rechazado no escribe nada"
    # Y el rechazo queda registrado: es lo que alguien va a querer rastrear.
    assert U.read_log(paths.log)[-1]["status"] == "rechazado"


def test_con_replace_el_conflicto_se_acepta_explicitamente(capas, tmp_path) -> None:
    paths = capas["paths"]
    raw = capas["raw"]
    fila = raw[raw[S.DATE] <= capas["corte"]].head(1).copy()
    fila[S.SALE_AMOUNT] = 123.0
    lote = tmp_path / "correccion.parquet"
    fila.to_parquet(lote, index=False)

    report = U.ingest(lote, on_conflict="replace")

    assert report.rows_replaced == 1
    panel = pd.read_parquet(paths.panel)
    sid = S.make_series_id(fila).iloc[0]
    corregida = panel[(panel[S.SERIES_ID] == sid) & (panel[S.DATE] == fila[S.DATE].iloc[0])]
    assert len(corregida) == 1, "reemplazar no puede duplicar la clave"
    assert corregida[S.SALE_AMOUNT].iloc[0] == pytest.approx(123.0)


def test_la_corrida_en_seco_cuenta_sin_escribir(capas) -> None:
    paths = capas["paths"]
    mtime = paths.panel.stat().st_mtime_ns
    report = U.ingest(capas["lote"], dry_run=True)
    assert report.status == "simulado"
    assert report.rows_new == 24 * 7
    assert paths.panel.stat().st_mtime_ns == mtime
    assert not paths.log.exists()


# --- Contrato de entrada ---------------------------------------------------
def test_un_lote_sin_las_columnas_del_contrato_se_rechaza(capas, tmp_path) -> None:
    lote = tmp_path / "incompleto.parquet"
    capas["raw"].drop(columns=[S.HOURS_STOCK_STATUS]).to_parquet(lote, index=False)
    with pytest.raises(S.SchemaError, match="columnas del contrato"):
        U.ingest(lote)


def test_un_lote_con_quiebres_inconsistentes_se_rechaza(capas, tmp_path) -> None:
    """Las mismas validaciones que la carga inicial: no hay un camino mas laxo."""
    raw = capas["raw"][capas["raw"][S.DATE] > capas["corte"]].copy()
    raw[S.OOS_HOURS_OPEN] = raw[S.OOS_HOURS_OPEN] + 1
    lote = tmp_path / "inconsistente.parquet"
    raw.to_parquet(lote, index=False)
    with pytest.raises(S.SchemaError, match="no coinciden"):
        U.ingest(lote)


def test_el_lote_csv_lleva_las_secuencias_como_json(capas, tmp_path) -> None:
    raw = capas["raw"][capas["raw"][S.DATE] > capas["corte"]].copy()
    csv = raw.copy()
    for col in S.HOURLY_COLS:
        csv[col] = csv[col].map(lambda v: json.dumps(np.asarray(v).tolist()))
    path = tmp_path / "lote.csv"
    csv.to_csv(path, index=False)

    report = U.ingest(path)
    assert report.status == "ok"
    assert report.rows_new == len(raw)


# --- Artefactos --------------------------------------------------------------
def _candidatos(panel: pd.DataFrame) -> None:
    for basis, target in TARGET_BY_BASIS.items():
        SeasonalNaiveForecaster().fit(panel, target=target).save(cfg.candidate_path(basis))


def test_la_prueba_de_humo_acepta_un_artefacto_sano(capas) -> None:
    demanda = pd.read_parquet(capas["paths"].demand)
    _candidatos(demanda)
    out = U.smoke_test(cfg.candidate_path("recovered"), demanda, basis="recovered")
    assert out["n_rows"] > 0
    assert out["trained_until"] == str(demanda[S.DATE].max().date())


def test_la_prueba_de_humo_rechaza_un_artefacto_de_la_otra_base(capas) -> None:
    """Un artefacto cruzado hace que el toggle de censura conteste lo mismo."""
    demanda = pd.read_parquet(capas["paths"].demand)
    _candidatos(demanda)
    with pytest.raises(U.SmokeTestError, match="exige"):
        U.smoke_test(cfg.candidate_path("observed"), demanda, basis="recovered")


def test_promover_conserva_el_anterior_y_rollback_lo_restaura(capas) -> None:
    demanda = pd.read_parquet(capas["paths"].demand)
    viejo = demanda[demanda[S.DATE] < demanda[S.DATE].max() - pd.Timedelta(days=10)]
    for basis, target in TARGET_BY_BASIS.items():
        SeasonalNaiveForecaster().fit(viejo, target=target).save(cfg.model_path(basis))
    _candidatos(demanda)

    assert U.promote() == ["recovered", "observed"]
    from blindside.models.base import Forecaster

    vigente = Forecaster.load(cfg.model_path("recovered"))
    anterior = Forecaster.load(cfg.previous_path("recovered"))
    assert vigente.last_train_date > anterior.last_train_date
    assert not cfg.candidate_path("recovered").exists(), "el candidato se mueve, no se copia"

    U.rollback()
    restaurado = Forecaster.load(cfg.model_path("recovered"))
    assert restaurado.last_train_date == anterior.last_train_date
    # Rollback es un intercambio: el promovido queda como anterior y se puede deshacer.
    assert Forecaster.load(cfg.previous_path("recovered")).last_train_date == (
        vigente.last_train_date
    )


def test_promover_sin_candidato_falla_sin_tocar_nada(capas) -> None:
    demanda = pd.read_parquet(capas["paths"].demand)
    for basis, target in TARGET_BY_BASIS.items():
        SeasonalNaiveForecaster().fit(demanda, target=target).save(cfg.model_path(basis))
    mtime = cfg.model_path("recovered").stat().st_mtime_ns
    with pytest.raises(FileNotFoundError, match="candidato"):
        U.promote()
    assert cfg.model_path("recovered").stat().st_mtime_ns == mtime


def test_guardar_un_modelo_no_deja_temporales(capas) -> None:
    demanda = pd.read_parquet(capas["paths"].demand)
    path = cfg.model_path("recovered")
    SeasonalNaiveForecaster().fit(demanda, target=S.DEMAND_LATENT).save(path)
    assert path.exists()
    assert not list(path.parent.glob(".*.tmp"))


def test_el_registro_conserva_lo_que_hizo_cada_ingesta(capas) -> None:
    U.ingest(capas["lote"])
    U.ingest(capas["lote"])
    entradas = U.read_log(capas["paths"].log)
    assert [e["status"] for e in entradas] == ["ok", "sin_cambios"]
    assert entradas[0]["input_sha256"] == entradas[1]["input_sha256"]
