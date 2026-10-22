"""Pipeline de carga y actualizacion de datos.

    python -m blindside.data.update ingest --input data/incoming/lote.parquet
    python -m blindside.data.update ingest --input lote.parquet --train
    python -m blindside.data.update batch --split eval
    python -m blindside.data.update rollback
    python -m blindside.data.update status

Hasta aca el sistema era **batch**: `make data` armaba el panel una vez, `make
recover` lo corregia y la API lo cargaba al arrancar. No habia forma de sumar dias
nuevos sin rehacer todo, y la unica alternativa obvia — un endpoint que reciba un
CSV — seria abrir una ruta de escritura sin idempotencia, sin atomicidad y sin
autenticacion. Esto implementa el orden que fija `docs/auditoria_final.md`:

1. **Contrato de entrada.** El lote trae las mismas 19 columnas del dataset
   original, con las secuencias horarias. Se valida con el mismo `build_panel` que
   arma el panel la primera vez, asi que un lote no puede entrar por un camino mas
   laxo que el inicial: si las horas de quiebre derivadas no coinciden con
   `stock_hour6_22_cnt`, se rechaza igual.
2. **Upsert por (serie, dia), nunca append ciego.** Cada fila del lote cae en uno
   de tres casos: nueva, duplicado exacto (se ignora) o **conflicto** (misma clave,
   otros valores). El conflicto por defecto **rechaza el lote entero** y no escribe
   nada: corregir una venta ya registrada es una decision, no un efecto colateral
   de reingerir un archivo. Con `--on-conflict replace` se acepta explicitamente.
3. **Escritura atomica con respaldo.** Cada capa se escribe a un temporal y se
   mueve con `os.replace`; la version anterior queda como `*.prev.parquet`. La API
   recarga cuando cambia la fecha de modificacion, asi que nunca lee un archivo a
   medio escribir.
4. **Recuperacion de censura completa.** Se recorre todo el panel y no solo las
   filas nuevas, porque el recuperador estima perfiles intradiarios con toda la
   historia. Son ~4 s sobre las 3.066 series.
5. **Reentrenamiento opcional con promocion segura** (`--train`). Los dos
   artefactos se entrenan como *candidatos*, pasan una prueba de humo y recien ahi
   reemplazan al vigente, que queda como `*.prev.joblib` para `rollback`.

Lo que **no** hace, a proposito: no hay endpoint HTTP que dispare nada de esto. La
API no tiene autenticacion, y una ruta que cambia los datos o el modelo servido
sin autenticacion es un agujero, no una funcion. Se corre desde la terminal o
desde el contenedor del pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import pandas as pd

from blindside import config as cfg
from blindside.data import schema as S

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

Layer = Literal["processed", "sample"]
OnConflict = Literal["reject", "replace"]

#: Claves del upsert. Es la granularidad canonica del contrato de datos.
KEYS: tuple[str, str] = (S.SERIES_ID, S.DATE)

#: Columnas escalares que se comparan para distinguir duplicado de conflicto. Va
#: la jerarquia tambien: una serie que cambia de categoria entre lotes no es un
#: dato nuevo, es un error de origen que conviene ver.
COMPARE_SCALAR: tuple[str, ...] = (
    *S.HIERARCHY_COLS,
    S.SALE_AMOUNT,
    S.OOS_HOURS_OPEN,
    *S.KNOWN_FUTURE_COLS,
    *S.WEATHER_COLS,
)
COMPARE_HOURLY: tuple[str, ...] = S.HOURLY_COLS

#: Cuantas entradas del registro se conservan. El registro es evidencia de
#: operacion, no un historial completo: con un lote diario son mas de seis meses.
LOG_KEEP = 200

#: Series que entran a la prueba de humo del candidato.
SMOKE_SERIES = 25


class IngestRejectedError(ValueError):
    """El lote no se puede ingerir tal como vino. Nada se escribio."""

    def __init__(self, message: str, report: IngestReport) -> None:
        super().__init__(message)
        self.report = report


class SmokeTestError(RuntimeError):
    """El candidato no paso la prueba de humo. El artefacto vigente no se toco."""


# --------------------------------------------------------------------------
# Rutas por capa
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class LayerPaths:
    """Donde vive cada archivo de una capa. Se resuelve en cada llamada para que
    los tests puedan reapuntar `config` con monkeypatch."""

    panel: Path
    demand: Path
    log: Path

    @classmethod
    def of(cls, layer: Layer) -> LayerPaths:
        if layer == "sample":
            return cls(
                panel=cfg.DATA_SAMPLE / cfg.PANEL_FILE,
                demand=cfg.DATA_SAMPLE / cfg.DEMAND_FILE,
                log=cfg.DATA_SAMPLE / cfg.UPDATE_LOG_FILE,
            )
        return cls(
            panel=cfg.DATA_INTERIM / cfg.PANEL_FILE,
            demand=cfg.DATA_PROCESSED / cfg.DEMAND_FILE,
            log=cfg.DATA_PROCESSED / cfg.UPDATE_LOG_FILE,
        )


def previous_of(path: Path) -> Path:
    """`demand.parquet` -> `demand.prev.parquet`."""
    return path.with_name(f"{path.stem}.prev{path.suffix}")


# --------------------------------------------------------------------------
# Reporte
# --------------------------------------------------------------------------
@dataclass
class IngestReport:
    """Lo que hizo una ingesta con cada fila. Va al registro y a la terminal."""

    kind: str = "ingest"
    status: str = "pendiente"
    message: str = ""
    layer: str = "processed"
    input: str | None = None
    input_sha256: str | None = None
    on_conflict: str = "reject"
    dry_run: bool = False
    started_at: str = field(default_factory=lambda: _now())
    finished_at: str | None = None
    rows_in: int = 0
    rows_new: int = 0
    rows_duplicate: int = 0
    rows_conflict: int = 0
    rows_replaced: int = 0
    new_series: int = 0
    conflict_sample: list[str] = field(default_factory=list)
    series_with_gaps: int = 0
    batch_date_min: str | None = None
    batch_date_max: str | None = None
    panel_rows_before: int = 0
    panel_rows_after: int = 0
    panel_date_max_before: str | None = None
    panel_date_max_after: str | None = None
    recovered: bool = False
    trained: bool = False
    promoted: list[str] = field(default_factory=list)
    smoke: dict[str, Any] = field(default_factory=dict)
    seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# Lectura y validacion del lote
# --------------------------------------------------------------------------
def read_batch(path: Path) -> pd.DataFrame:
    """Lee un lote en el esquema crudo del dataset. Parquet o CSV.

    En CSV las dos secuencias horarias van como listas JSON (`"[0, 1, ...]"`),
    que es la unica forma de meter 24 valores en una celda sin inventar un
    separador propio.
    """
    if not path.exists():
        raise FileNotFoundError(f"no existe el lote {path}")
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        df = pd.read_parquet(path)
    elif suffix == ".csv":
        df = pd.read_csv(path)
        for col in S.HOURLY_COLS:
            if col in df.columns:
                df[col] = df[col].map(_parse_hourly)
    else:
        raise S.SchemaError(f"formato de lote no soportado: {suffix} (parquet o csv)")

    missing = [c for c in S.RAW_COLUMNS if c not in df.columns]
    if missing:
        raise S.SchemaError(
            f"el lote no trae las columnas del contrato de entrada: {missing}. Son las "
            "19 del dataset original, con las dos secuencias horarias"
        )
    return df[list(S.RAW_COLUMNS)].copy()


def _parse_hourly(value: Any) -> list[float]:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise S.SchemaError(f"secuencia horaria ilegible: {value[:40]!r}") from exc
    return value


def prepare_batch(raw: pd.DataFrame) -> pd.DataFrame:
    """Pasa el lote crudo al panel canonico, con las mismas validaciones del inicio."""
    from blindside.data.freshretail import build_panel

    if raw.empty:
        raise S.SchemaError("el lote esta vacio")
    panel = build_panel(raw, keep_hourly=True)
    panel["split"] = "update"
    return panel


# --------------------------------------------------------------------------
# Upsert
# --------------------------------------------------------------------------
@dataclass
class MergeResult:
    panel: pd.DataFrame
    rows_new: int
    rows_duplicate: int
    rows_conflict: int
    rows_replaced: int
    new_series: int
    conflict_keys: list[str]


def _same(a: pd.Series, b: pd.Series) -> np.ndarray:
    """Igualdad fila a fila tolerante a float32 y a NaN en los dos lados."""
    if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
        x = a.to_numpy(dtype="float64")
        y = b.to_numpy(dtype="float64")
        return np.isclose(x, y, rtol=1e-5, atol=1e-6, equal_nan=True)
    return (a.astype(str) == b.astype(str)).to_numpy()


def _same_hourly(a: pd.Series, b: pd.Series) -> np.ndarray:
    if a.empty:
        return np.zeros(0, dtype=bool)
    x = np.stack([np.asarray(v, dtype="float64") for v in a])
    y = np.stack([np.asarray(v, dtype="float64") for v in b])
    return np.isclose(x, y, rtol=1e-5, atol=1e-6).all(axis=1)


def merge_batch(
    current: pd.DataFrame, batch: pd.DataFrame, *, on_conflict: OnConflict = "reject"
) -> MergeResult:
    """Upsert del lote sobre el panel vigente. No escribe nada.

    Con `on_conflict="reject"` y algun conflicto, devuelve el resultado con el
    panel **sin cambios**: el llamador decide rechazar. Asi el conteo de
    conflictos se puede reportar completo en vez de cortar en el primero.
    """
    keys = list(KEYS)
    scalar = [c for c in COMPARE_SCALAR if c in batch.columns and c in current.columns]
    hourly = [c for c in COMPARE_HOURLY if c in batch.columns and c in current.columns]

    cur = current[[*keys, *scalar, *hourly]]
    joined = batch.merge(cur, on=keys, how="left", suffixes=("", "__cur"), indicator=True)
    existe = (joined["_merge"] == "both").to_numpy()

    iguales = np.ones(len(joined), dtype=bool)
    if existe.any():
        sub = joined.loc[existe]
        ok = np.ones(len(sub), dtype=bool)
        for c in scalar:
            ok &= _same(sub[c], sub[f"{c}__cur"])
        for c in hourly:
            ok &= _same_hourly(sub[c], sub[f"{c}__cur"])
        iguales[np.flatnonzero(existe)] = ok

    nueva = ~existe
    duplicada = existe & iguales
    conflicto = existe & ~iguales

    conflict_keys = (
        joined.loc[conflicto, S.SERIES_ID].astype(str)
        + "@"
        + pd.to_datetime(joined.loc[conflicto, S.DATE]).dt.date.astype(str)
    ).tolist()

    known = set(current[S.SERIES_ID].astype(str).unique())
    new_series = len(set(batch.loc[nueva, S.SERIES_ID].astype(str)) - known)

    if conflicto.any() and on_conflict == "reject":
        return MergeResult(
            panel=current,
            rows_new=int(nueva.sum()),
            rows_duplicate=int(duplicada.sum()),
            rows_conflict=int(conflicto.sum()),
            rows_replaced=0,
            new_series=new_series,
            conflict_keys=conflict_keys,
        )

    entran = batch.loc[nueva | conflicto]
    if conflicto.any():
        reemplazar = pd.MultiIndex.from_frame(batch.loc[conflicto, keys])
        quedan = ~pd.MultiIndex.from_frame(current[keys]).isin(reemplazar)
        base = current.loc[quedan]
    else:
        base = current

    if entran.empty:
        merged = current
    else:
        cols = list(current.columns)
        faltan = [c for c in cols if c not in entran.columns]
        if faltan:
            raise S.SchemaError(f"el lote preparado no tiene {faltan}, que el panel vigente si")
        merged = pd.concat([base, entran[cols]], ignore_index=True)
        merged = S.cast_panel(merged)
        merged = S.validate_panel(merged, allow_gaps=True)

    return MergeResult(
        panel=merged,
        rows_new=int(nueva.sum()),
        rows_duplicate=int(duplicada.sum()),
        rows_conflict=int(conflicto.sum()),
        rows_replaced=int(conflicto.sum()),
        new_series=new_series,
        conflict_keys=conflict_keys,
    )


# --------------------------------------------------------------------------
# Escritura atomica
# --------------------------------------------------------------------------
def atomic_write_parquet(df: pd.DataFrame, path: Path, *, keep_previous: bool = True) -> Path:
    """Escribe `df` sin dejar nunca un archivo a medio escribir en `path`.

    La version anterior se copia a `*.prev.parquet` **antes** del reemplazo, y el
    reemplazo es un `os.replace` en el mismo directorio, que es atomico en los dos
    sistemas operativos donde corre el proyecto.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if keep_previous and path.exists():
        prev = previous_of(path)
        tmp_prev = prev.with_name(f".{prev.name}.tmp")
        shutil.copy2(path, tmp_prev)
        os.replace(tmp_prev, prev)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        df.to_parquet(tmp, index=False, compression="zstd")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def _atomic_write_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------
def read_log(path: Path) -> list[dict[str, Any]]:
    """Entradas del registro, de la mas vieja a la mas nueva. Vacio si no hay."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("registro %s ilegible (%s); se trata como vacio", path, exc)
        return []
    return data if isinstance(data, list) else []


def append_log(path: Path, entry: dict[str, Any]) -> None:
    entries = [*read_log(path), entry][-LOG_KEEP:]
    _atomic_write_json(entries, path)


# --------------------------------------------------------------------------
# Recuperacion
# --------------------------------------------------------------------------
def recover_demand(panel_hourly: pd.DataFrame, *, method: str = "hourly_profile") -> pd.DataFrame:
    """La misma recuperacion que `make recover`, sobre el panel completo."""
    from blindside.decision.censoring import get_recovery

    out = get_recovery(method).recover(panel_hourly)
    out = out.drop(columns=[c for c in S.HOURLY_COLS if c in out.columns])
    return S.validate_panel(out, required=S.DEMAND_REQUIRED, allow_gaps=True)


# --------------------------------------------------------------------------
# Artefactos: candidato, prueba de humo, promocion, rollback
# --------------------------------------------------------------------------
def _bases(basis: str) -> list[cfg.Basis]:
    return ["recovered", "observed"] if basis == "both" else [basis]  # type: ignore[list-item]


def smoke_future(panel: pd.DataFrame, series_ids: Sequence[str], horizon: int) -> pd.DataFrame:
    """Indice de futuro minimo para la prueba de humo.

    Las covariables conocidas van con la mediana de los ultimos 21 dias, igual que
    el plan por defecto de la API. Con NaN el modelo contestaria igual — LightGBM
    trata el NaN como una rama — y la prueba pasaria sin probar lo que se sirve.
    """
    origin = pd.Timestamp(panel[S.DATE].max())
    dates = [origin + pd.Timedelta(days=h) for h in range(1, horizon + 1)]
    grid = pd.MultiIndex.from_product(
        [list(series_ids), dates], names=[S.SERIES_ID, S.DATE]
    ).to_frame(index=False)
    grid["h"] = (grid[S.DATE] - origin).dt.days.astype("int16")
    grid[S.SERIES_ID] = grid[S.SERIES_ID].astype("string")

    recent = panel[panel[S.DATE] > origin - pd.Timedelta(days=21)]
    grid[S.DISCOUNT] = np.float32(np.clip(recent[S.DISCOUNT].median(), 1e-6, 1.0))
    grid[S.HOLIDAY_FLAG] = np.int8(round(float(recent[S.HOLIDAY_FLAG].median())))
    grid[S.ACTIVITY_FLAG] = np.int8(round(float(recent[S.ACTIVITY_FLAG].median())))
    return grid.merge(S.series_index(panel), on=S.SERIES_ID, how="left")


def smoke_test(path: Path, panel: pd.DataFrame, *, basis: cfg.Basis) -> dict[str, Any]:
    """Carga el candidato y le pide un pronostico. Falla con el motivo si algo no va.

    No mide calidad — eso es el backtest. Mide que el artefacto **sirva**: que se
    deserialice, que este entrenado sobre la base correcta, que conteste para las
    series del panel y que lo que conteste sean numeros finitos y no negativos.
    """
    from blindside.models.base import TARGET_BY_BASIS, Forecaster, fitted_target

    model = Forecaster.load(path)
    trained_on = fitted_target(model)
    if trained_on is not None and trained_on != TARGET_BY_BASIS[basis]:
        raise SmokeTestError(
            f"{path.name}: entrenado sobre '{trained_on}', la base '{basis}' exige "
            f"'{TARGET_BY_BASIS[basis]}'"
        )

    ids = sorted(panel[S.SERIES_ID].astype(str).unique())[:SMOKE_SERIES]
    future = smoke_future(panel, ids, cfg.FORECAST.horizon)
    point = np.asarray(model.predict(future), dtype="float64")
    if point.shape[0] != len(future):
        raise SmokeTestError(f"{path.name}: {point.shape[0]} predicciones para {len(future)} filas")
    if not np.isfinite(point).all():
        raise SmokeTestError(f"{path.name}: predicciones no finitas")
    if (point < -1e-9).any():
        raise SmokeTestError(f"{path.name}: predicciones negativas")

    out: dict[str, Any] = {
        "basis": basis,
        "model": model.name,
        "n_rows": int(len(future)),
        "mean_pred": float(point.mean()),
        "trained_until": str(model.last_train_date.date()) if model.last_train_date else None,
    }
    if getattr(model, "supports_quantiles", False):
        qs = tuple(getattr(model, "quantiles", None) or cfg.FORECAST.quantiles)
        q = model.predict_quantile(future, qs).to_numpy(dtype="float64")
        if not np.isfinite(q).all():
            raise SmokeTestError(f"{path.name}: cuantiles no finitos")
        out["quantiles"] = list(qs)
    return out


def train_candidates(
    demand: pd.DataFrame, *, basis: str = "both", model: str = "lgbm_quantile"
) -> dict[str, Path]:
    """Entrena los candidatos sin tocar el artefacto vigente."""
    from blindside.models.__main__ import train_basis

    q_star = cfg.ECONOMICS.critical_fraction
    quantiles = tuple(sorted({*cfg.FORECAST.quantiles, q_star}))
    out: dict[str, Path] = {}
    for b in _bases(basis):
        _, path = train_basis(
            demand,
            basis=b,
            model_name=model,
            quantiles=quantiles,
            conformal=True,
            out=cfg.candidate_path(b),
        )
        out[b] = path
    return out


def promote(basis: str = "both") -> list[str]:
    """Reemplaza el vigente por el candidato, conservando el anterior.

    El orden importa: primero se copia el vigente a `*.prev`, despues se mueve el
    candidato con `os.replace`. Al reves habria un instante sin artefacto vigente,
    y la API recarga justamente cuando ve cambiar el archivo.
    """
    promoted = []
    for b in _bases(basis):
        cand = cfg.candidate_path(b)
        if not cand.exists():
            raise FileNotFoundError(f"no hay candidato para la base '{b}' en {cand}")
    for b in _bases(basis):
        cand, cur, prev = cfg.candidate_path(b), cfg.model_path(b), cfg.previous_path(b)
        if cur.exists():
            tmp = prev.with_name(f".{prev.name}.tmp")
            shutil.copy2(cur, tmp)
            os.replace(tmp, prev)
        os.replace(cand, cur)
        promoted.append(b)
        log.info("promovido %s -> %s (anterior en %s)", cand.name, cur.name, prev.name)
    return promoted


def rollback(basis: str = "both") -> list[str]:
    """Vuelve a la version anterior. Es un intercambio, asi que se puede deshacer."""
    swapped = []
    for b in _bases(basis):
        if not cfg.previous_path(b).exists():
            raise FileNotFoundError(
                f"no hay version anterior para la base '{b}' ({cfg.previous_path(b).name})"
            )
    for b in _bases(basis):
        cur, prev = cfg.model_path(b), cfg.previous_path(b)
        tmp = cur.with_name(f".{cur.name}.swap")
        if cur.exists():
            shutil.copy2(cur, tmp)
        os.replace(prev, cur)
        if tmp.exists():
            os.replace(tmp, prev)
        swapped.append(b)
        log.info("rollback de la base '%s': %s restaurado", b, cur.name)
    return swapped


# --------------------------------------------------------------------------
# Orquestacion
# --------------------------------------------------------------------------
def ingest(
    input_path: Path,
    *,
    layer: Layer = "processed",
    on_conflict: OnConflict = "reject",
    train: bool = False,
    dry_run: bool = False,
) -> IngestReport:
    """Ingiere un lote de punta a punta. Devuelve el reporte; tambien lo registra.

    Levanta `IngestRejectedError` si hay conflictos y `on_conflict="reject"`; en
    ese caso no se escribio ninguna capa, pero el rechazo **si** queda en el
    registro, porque un lote rechazado es justamente lo que alguien va a querer
    rastrear despues.
    """
    t0 = time.perf_counter()
    paths = LayerPaths.of(layer)
    report = IngestReport(
        layer=layer,
        input=str(input_path),
        on_conflict=on_conflict,
        dry_run=dry_run,
    )

    def cerrar(status: str, message: str) -> IngestReport:
        report.status = status
        report.message = message
        report.finished_at = _now()
        report.seconds = round(time.perf_counter() - t0, 2)
        if not dry_run:
            append_log(paths.log, report.to_dict())
        return report

    if not paths.panel.exists():
        raise FileNotFoundError(
            f"no hay panel vigente en {paths.panel}. La primera carga se hace con "
            "`make data`; este comando suma lotes sobre un panel que ya existe"
        )

    report.input_sha256 = _sha256(input_path) if input_path.exists() else None
    raw = read_batch(input_path)
    batch = prepare_batch(raw)
    report.rows_in = int(len(batch))
    report.batch_date_min = str(batch[S.DATE].min().date())
    report.batch_date_max = str(batch[S.DATE].max().date())

    from blindside.data import loaders

    current = loaders.load_hourly_panel(path=paths.panel)
    report.panel_rows_before = int(len(current))
    report.panel_date_max_before = str(current[S.DATE].max().date())

    merged = merge_batch(current, batch, on_conflict=on_conflict)
    report.rows_new = merged.rows_new
    report.rows_duplicate = merged.rows_duplicate
    report.rows_conflict = merged.rows_conflict
    report.rows_replaced = merged.rows_replaced
    report.new_series = merged.new_series
    report.conflict_sample = merged.conflict_keys[:10]

    if merged.rows_conflict and on_conflict == "reject":
        cerrar(
            "rechazado",
            f"{merged.rows_conflict} filas del lote contradicen datos ya cargados "
            f"(p. ej. {', '.join(merged.conflict_keys[:3])}). No se escribio nada. "
            "Si la correccion es intencional, repetir con --on-conflict replace",
        )
        raise IngestRejectedError(report.message, report)

    report.panel_rows_after = int(len(merged.panel))
    report.panel_date_max_after = str(merged.panel[S.DATE].max().date())
    report.series_with_gaps = len(S._series_with_gaps(merged.panel))

    if merged.rows_new == 0 and merged.rows_replaced == 0:
        return cerrar(
            "sin_cambios",
            f"las {merged.rows_duplicate} filas del lote ya estaban cargadas con los "
            "mismos valores. Reingerir el mismo archivo no cambia nada",
        )

    if dry_run:
        return cerrar("simulado", "corrida en seco: no se escribio ninguna capa")

    demand = recover_demand(merged.panel)
    atomic_write_parquet(merged.panel, paths.panel)
    atomic_write_parquet(demand, paths.demand)
    report.recovered = True

    if train:
        candidates = train_candidates(demand)
        for b, path in candidates.items():
            report.smoke[b] = smoke_test(path, demand, basis=b)
        report.promoted = promote("both")
        report.trained = True

    partes = [f"{merged.rows_new} filas nuevas"]
    if merged.rows_replaced:
        partes.append(f"{merged.rows_replaced} reemplazadas")
    if merged.rows_duplicate:
        partes.append(f"{merged.rows_duplicate} duplicadas ignoradas")
    if merged.new_series:
        partes.append(f"{merged.new_series} series nuevas que el modelo no conoce hasta reentrenar")
    if not train:
        partes.append("el modelo sigue entrenado hasta su fecha anterior: correr con --train")
    return cerrar("ok", "; ".join(partes))


def export_batch(
    *,
    split: str = "eval",
    out: Path | None = None,
    days: int | None = None,
    layer: Layer = "processed",
) -> Path:
    """Arma un lote en el esquema crudo a partir de un split del dataset original.

    Sirve para ejercitar el pipeline con datos reales: toma las series del panel
    vigente y las filas de ese split en `data/raw/`. Como el panel ya trae los dos
    splits, ingerir este lote **no** agrega filas: prueba que reingerir lo mismo es
    idempotente. Con `--days` se recorta a los ultimos N dias del split.
    """
    from blindside.data.freshretail import ensure_raw, read_subset

    paths = LayerPaths.of(layer)
    panel = pd.read_parquet(paths.panel, columns=[S.CITY_ID, S.STORE_ID, S.PRODUCT_ID])
    chosen = panel.drop_duplicates(ignore_index=True)
    raw_path = ensure_raw(splits=(split,))[split]
    raw = read_subset(raw_path, chosen)
    raw[S.DATE] = pd.to_datetime(raw[S.DATE])
    if days is not None:
        corte = raw[S.DATE].max() - pd.Timedelta(days=days - 1)
        raw = raw[raw[S.DATE] >= corte]

    out = out or cfg.DATA_INCOMING / f"lote_{split}_{raw[S.DATE].max().date()}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(out, index=False, compression="zstd")
    log.info("lote escrito en %s (%d filas, %d series)", out, len(raw), len(chosen))
    return out


def status(layer: Layer = "processed") -> dict[str, Any]:
    """Estado de la capa servida y de los artefactos, para la terminal."""
    paths = LayerPaths.of(layer)
    entries = read_log(paths.log)

    def info(p: Path) -> dict[str, Any] | None:
        if not p.exists():
            return None
        st = p.stat()
        return {
            "file": p.name,
            "bytes": st.st_size,
            "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(
                timespec="seconds"
            ),
        }

    return {
        "layer": layer,
        "panel": info(paths.panel),
        "demand": info(paths.demand),
        "last_update": entries[-1] if entries else None,
        "artifacts": {
            b: {
                "current": info(cfg.model_path(b)),
                "previous": info(cfg.previous_path(b)),
                "candidate": info(cfg.candidate_path(b)),
            }
            for b in cfg.MODEL_FILES
        },
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="blindside.data.update",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    ing = sub.add_parser("ingest", help="suma un lote al panel, recupera y opcionalmente reentrena")
    ing.add_argument("--input", type=Path, required=True, help="lote .parquet o .csv")
    ing.add_argument("--layer", choices=["processed", "sample"], default="processed")
    ing.add_argument("--on-conflict", choices=["reject", "replace"], default="reject")
    ing.add_argument("--train", action="store_true", help="reentrenar y promover si pasa")
    ing.add_argument("--dry-run", action="store_true", help="validar y contar sin escribir")

    bat = sub.add_parser("batch", help="arma un lote desde un split del dataset original")
    bat.add_argument("--split", choices=["train", "eval"], default="eval")
    bat.add_argument("--days", type=int, default=None)
    bat.add_argument("--out", type=Path, default=None)
    bat.add_argument("--layer", choices=["processed", "sample"], default="processed")

    for name, ayuda in (
        ("promote", "promueve los candidatos ya entrenados"),
        ("rollback", "vuelve a la version anterior de los artefactos"),
    ):
        sp = sub.add_parser(name, help=ayuda)
        sp.add_argument("--basis", choices=["both", "recovered", "observed"], default="both")

    st = sub.add_parser("status", help="estado de la capa servida y de los artefactos")
    st.add_argument("--layer", choices=["processed", "sample"], default="processed")
    return p.parse_args(argv)


def _print_report(report: IngestReport) -> None:
    r = report
    print("\n=== Ingesta de lote ===", file=sys.stderr)
    print(f"estado:     {r.status}", file=sys.stderr)
    print(
        f"lote:       {r.input} ({r.rows_in} filas, {r.batch_date_min} -> {r.batch_date_max})",
        file=sys.stderr,
    )
    print(f"nuevas:     {r.rows_new}", file=sys.stderr)
    print(f"duplicadas: {r.rows_duplicate}", file=sys.stderr)
    print(f"conflictos: {r.rows_conflict} (reemplazadas {r.rows_replaced})", file=sys.stderr)
    if r.panel_rows_after:
        print(
            f"panel:      {r.panel_rows_before} -> {r.panel_rows_after} filas, hasta "
            f"{r.panel_date_max_after}",
            file=sys.stderr,
        )
    if r.trained:
        print(f"modelo:     reentrenado y promovido ({', '.join(r.promoted)})", file=sys.stderr)
    print(f"\n{r.message}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s · %(message)s")
    args = _parse_args(argv)

    if args.command == "ingest":
        try:
            report = ingest(
                args.input,
                layer=args.layer,
                on_conflict=args.on_conflict,
                train=args.train,
                dry_run=args.dry_run,
            )
        except IngestRejectedError as exc:
            _print_report(exc.report)
            return 2
        _print_report(report)
        return 0

    if args.command == "batch":
        path = export_batch(split=args.split, out=args.out, days=args.days, layer=args.layer)
        print(
            f"lote listo: {path}\n"
            f"ingerir con: python -m blindside.data.update ingest --input {path}",
            file=sys.stderr,
        )
        return 0

    if args.command in ("promote", "rollback"):
        fn = promote if args.command == "promote" else rollback
        done = fn(args.basis)
        entry = {
            "kind": args.command,
            "status": "ok",
            "bases": done,
            "finished_at": _now(),
            "started_at": _now(),
            "message": f"{args.command}: {', '.join(done)}",
        }
        append_log(LayerPaths.of("processed").log, entry)
        print(f"{args.command}: {', '.join(done)}", file=sys.stderr)
        return 0

    print(json.dumps(status(args.layer), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
