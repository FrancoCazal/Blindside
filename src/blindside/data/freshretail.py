"""Frente A · carga y submuestreo de FreshRetailNet-50K.

Contrato de este modulo, y es un contrato duro: **nunca materializa el dataset
completo en memoria**. Cualquier funcion que lo haga es un bug, no una
optimizacion pendiente (docs/decisiones.md D2).

El porque, con numeros: el parquet de train pesa 106 MB comprimido, pero
``hours_sale`` y ``hours_stock_status`` son secuencias de 24 elementos sobre
4,5 M de filas. Expandido son ~216 M de valores solo en esas dos columnas, del
orden de 1,7 GB en float64. Un ``load_dataset(...).to_pandas()`` no entra en una
maquina de trabajo normal.

La estrategia es de dos pasadas:

1. Se leen **solo tres columnas** de identificacion para armar el inventario de
   series. Eso son ~100 MB de enteros, manejable.
2. Se elige el subconjunto con semilla fija y se relee el parquet con el filtro
   empujado a pyarrow, trayendo todas las columnas **solo de las filas elegidas**.

El submuestreo es por **tienda completa**, no por serie suelta: se eligen tiendas
al azar y se conservan todos sus productos. Cuesta un poco de precision en el
tamano final del subconjunto y a cambio deja intactas las dos jerarquias del
dataset, que es lo que necesita la reconciliacion MinT de la seccion 8.3. Una
muestra de series sueltas dejaria tiendas con tres productos y agregados que no
representan nada.

Fuente: https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K (CC BY 4.0)
Paper: https://arxiv.org/abs/2505.16319
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.dataset as pads
import pyarrow.parquet as pq

from blindside import config as cfg
from blindside.data import schema as S

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

#: Nombres de los dos archivos del repo de HuggingFace.
REMOTE_FILES: dict[str, str] = {
    "train": "data/train.parquet",
    "eval": "data/eval.parquet",
}

#: Columnas minimas para armar el inventario de series.
ID_COLUMNS: tuple[str, ...] = (S.CITY_ID, S.STORE_ID, S.PRODUCT_ID)

#: Metadatos del submuestreo. Se escriben junto al panel para que el subconjunto
#: sea auditable sin releer el parquet original.
MANIFEST_FILE = "subsample_manifest.json"


# --------------------------------------------------------------------------
# Descarga
# --------------------------------------------------------------------------
def ensure_raw(
    *, raw_dir: Path | None = None, splits: Sequence[str] = ("train", "eval")
) -> dict[str, Path]:
    """Descarga los parquet a `data/raw/` si no estan. Devuelve las rutas.

    Usa la cache de `huggingface_hub`, asi que repetir la llamada no re-descarga.
    Los archivos quedan fuera de git (ver .gitignore).
    """
    raw_dir = raw_dir or cfg.DATA_RAW
    raw_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for split in splits:
        remote = REMOTE_FILES[split]
        local = raw_dir / Path(remote).name
        if local.exists():
            log.info("%s ya esta en %s", split, local)
            out[split] = local
            continue
        from huggingface_hub import hf_hub_download

        log.info("descargando %s de %s", remote, cfg.HF_DATASET)
        got = hf_hub_download(
            repo_id=cfg.HF_DATASET,
            filename=remote,
            repo_type="dataset",
            local_dir=str(raw_dir),
        )
        got_path = Path(got)
        if got_path != local:
            got_path.replace(local)
        out[split] = local
    return out


# --------------------------------------------------------------------------
# Pasada 1 · inventario de series
# --------------------------------------------------------------------------
def series_inventory(path: Path) -> pd.DataFrame:
    """Triples unicos (ciudad, tienda, producto) leyendo solo tres columnas.

    Es la unica lectura que toca todas las filas del parquet, y por eso lee el
    minimo posible de columnas.
    """
    table = pq.read_table(path, columns=list(ID_COLUMNS))
    inv = table.to_pandas().drop_duplicates(ignore_index=True)
    del table
    return inv.astype({c: "int32" for c in ID_COLUMNS})


def choose_series(
    inventory: pd.DataFrame,
    *,
    n_series: int,
    cities: Sequence[int] | None,
    seed: int,
) -> pd.DataFrame:
    """Elige el subconjunto de series con semilla fija, por tienda completa.

    Devuelve el inventario filtrado. El tamano final puede pasarse de
    `n_series` por lo que aporte la ultima tienda: se prefiere eso a partir el
    catalogo de una tienda a la mitad, porque una tienda con la mitad de sus
    productos vuelve mentira el agregado de esa tienda.
    """
    inv = inventory
    if cities is not None:
        inv = inv[inv[S.CITY_ID].isin(list(cities))]
        if inv.empty:
            raise ValueError(f"ninguna serie en las ciudades {tuple(cities)}")

    sizes = inv.groupby(S.STORE_ID, observed=True).size().sort_index()
    rng = np.random.default_rng(seed)
    order = rng.permutation(sizes.index.to_numpy())
    cumulative = sizes.reindex(order).cumsum()
    keep_mask = cumulative.shift(fill_value=0) < n_series
    keep_stores = cumulative.index[keep_mask].to_numpy()

    chosen = inv[inv[S.STORE_ID].isin(keep_stores)].sort_values(
        [S.CITY_ID, S.STORE_ID, S.PRODUCT_ID], ignore_index=True
    )
    log.info(
        "elegidas %d series de %d tiendas (objetivo %d) con semilla %d",
        len(chosen),
        len(keep_stores),
        n_series,
        seed,
    )
    return chosen


# --------------------------------------------------------------------------
# Pasada 2 · lectura filtrada
# --------------------------------------------------------------------------
def read_subset(path: Path, chosen: pd.DataFrame) -> pd.DataFrame:
    """Lee todas las columnas solo de las tiendas elegidas.

    El filtro se empuja a pyarrow (`filter=`), asi que los row groups que no
    contienen esas tiendas no se decodifican. Despues se ajusta al par exacto
    tienda-producto en pandas, que ya opera sobre un subconjunto chico.
    """
    stores = pd.unique(chosen[S.STORE_ID]).tolist()
    dataset = pads.dataset(path, format="parquet")
    table = dataset.to_table(
        columns=list(S.RAW_COLUMNS),
        filter=pc.field(S.STORE_ID).isin(stores),
    )
    df = table.to_pandas()
    del table

    wanted = set(map(tuple, chosen[[S.STORE_ID, S.PRODUCT_ID]].to_numpy().tolist()))
    pairs = list(zip(df[S.STORE_ID], df[S.PRODUCT_ID], strict=True))
    mask = np.fromiter((p in wanted for p in pairs), dtype=bool, count=len(df))
    return df.loc[mask].reset_index(drop=True)


# --------------------------------------------------------------------------
# Construccion del panel diario
# --------------------------------------------------------------------------
def _stack_hourly(col: pd.Series, dtype: str) -> np.ndarray:
    """Convierte una columna de secuencias de 24 elementos en (n, 24)."""
    arr = np.stack([np.asarray(v, dtype=dtype) for v in col])
    if arr.ndim != 2 or arr.shape[1] != 24:
        raise S.SchemaError(f"se esperaban secuencias de 24 horas, llegaron {arr.shape}")
    return arr


def build_panel(raw: pd.DataFrame, *, keep_hourly: bool = True) -> pd.DataFrame:
    """Pasa del crudo al panel diario canonico del contrato de datos.

    Deriva tres cosas de las secuencias horarias:

    * ``oos_hours_day`` — horas de quiebre en el dia completo.
    * ``available_weight`` — fraccion de franjas comerciales **sin** quiebre. Es
      la version uniforme, que supone que todas las horas venden lo mismo. El
      recuperador de censura la reemplaza por una version ponderada con el
      perfil intradiario real; esta sirve como referencia y como sanity check.
    * ``is_censored`` — hubo al menos una hora de quiebre en la ventana comercial.

    Con ``keep_hourly=False`` descarta las secuencias, que es lo que se hace una
    vez recuperada la demanda latente.
    """
    df = raw.copy()
    df[S.DATE] = pd.to_datetime(df[S.DATE])
    df[S.SERIES_ID] = S.make_series_id(df)

    status = _stack_hourly(df[S.HOURS_STOCK_STATUS], "int8")
    open_idx = np.asarray(cfg.CENSORING.open_hours, dtype="int64")
    n_open = open_idx.size

    df[S.OOS_HOURS_DAY] = status.sum(axis=1).astype("int16")
    oos_open = status[:, open_idx].sum(axis=1).astype("int16")

    # Chequeo de consistencia contra la columna del propio dataset. Si esto
    # falla, la ventana comercial asumida en config esta corrida y todo el
    # factor de inflacion de la censura sale mal.
    declared = df[S.OOS_HOURS_OPEN].to_numpy(dtype="int16")
    mismatch = int((oos_open != declared).sum())
    if mismatch:
        raise S.SchemaError(
            f"{mismatch}/{len(df)} filas donde las horas de quiebre derivadas de "
            f"{S.HOURS_STOCK_STATUS} en la ventana {cfg.CENSORING.open_hours[0]}.."
            f"{cfg.CENSORING.open_hours[-1]} no coinciden con {S.OOS_HOURS_OPEN}. "
            "Revisar CensoringConfig.open_hours."
        )

    df[S.AVAILABLE_WEIGHT] = ((n_open - oos_open) / n_open).astype("float32")
    df[S.IS_CENSORED] = (oos_open > 0).to_numpy() if hasattr(oos_open, "to_numpy") else oos_open > 0

    cols = [c for c in S.PANEL_REQUIRED]
    if keep_hourly:
        cols += list(S.HOURLY_COLS)
    out = S.cast_panel(df[cols])
    return S.validate_panel(out, allow_gaps=True)


# --------------------------------------------------------------------------
# Orquestacion
# --------------------------------------------------------------------------
def build_subsample(
    *,
    out_dir: Path,
    n_series: int,
    cities: Sequence[int] | None,
    seed: int,
    raw_dir: Path | None = None,
    splits: Sequence[str] = ("train", "eval"),
) -> Path:
    """Descarga, submuestrea y persiste el panel. Devuelve la ruta del parquet.

    Los dos splits oficiales se concatenan: ``train`` son 90 dias y ``eval`` los
    7 siguientes. Juntos dan 97 dias por serie, que es lo que hace posible correr
    8 origenes de backtest con horizonte 7 y ademas medirse contra la ventana de
    evaluacion oficial del benchmark.
    """
    paths = ensure_raw(raw_dir=raw_dir, splits=splits)

    inventory = series_inventory(paths["train"])
    chosen = choose_series(inventory, n_series=n_series, cities=cities, seed=seed)

    frames = []
    for split in splits:
        raw = read_subset(paths[split], chosen)
        panel = build_panel(raw)
        panel["split"] = split
        frames.append(panel)
        log.info("split %s: %d filas, %d series", split, len(panel), panel[S.SERIES_ID].nunique())
        del raw

    panel = pd.concat(frames, ignore_index=True)
    panel = S.validate_panel(panel, allow_gaps=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / cfg.PANEL_FILE
    panel.to_parquet(target, index=False, compression="zstd")

    manifest = {
        "source": cfg.HF_DATASET,
        "license": "CC BY 4.0",
        "seed": seed,
        "n_series_requested": n_series,
        "n_series_actual": int(panel[S.SERIES_ID].nunique()),
        "n_stores": int(panel[S.STORE_ID].nunique()),
        "cities": list(cities) if cities is not None else "all",
        "splits": list(splits),
        "date_min": str(panel[S.DATE].min().date()),
        "date_max": str(panel[S.DATE].max().date()),
        "n_rows": int(len(panel)),
        "censoring_window": list(cfg.CENSORING.open_hours),
        "censoring_config": asdict(cfg.CENSORING),
        "censoring_summary": S.describe_censoring(panel),
    }
    (out_dir / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("panel escrito en %s (%d filas)", target, len(panel))
    return target


def make_sample(*, interim_dir: Path, out_dir: Path, n_series: int, seed: int) -> Path:
    """Recorta el panel de `data/interim/` a la muestra chica commiteada.

    `data/sample/` existe para que el repo se pueda clonar y correr sin
    descargar 115 MB. Se eligen series **con censura observada**, porque una
    muestra de series sin quiebres no permitiria probar la pieza central del
    proyecto.
    """
    src = interim_dir / cfg.PANEL_FILE
    if not src.exists():
        raise FileNotFoundError(f"no existe {src}; correr primero `make data`")
    panel = pd.read_parquet(src)

    per_series = panel.groupby(S.SERIES_ID, observed=True)[S.IS_CENSORED].mean()
    eligible = per_series[(per_series > 0.05) & (per_series < 0.8)].index.to_numpy()
    if eligible.size < n_series:
        eligible = per_series.index.to_numpy()
    rng = np.random.default_rng(seed)
    keep = rng.choice(eligible, size=min(n_series, eligible.size), replace=False)

    sample = panel[panel[S.SERIES_ID].isin(keep)].reset_index(drop=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / cfg.PANEL_FILE
    sample.to_parquet(target, index=False, compression="zstd")

    manifest = {
        "derived_from": str(src.relative_to(cfg.ROOT)),
        "source": cfg.HF_DATASET,
        "license": "CC BY 4.0 - atribucion a Dingdong-Inc",
        "seed": seed,
        "n_series": int(sample[S.SERIES_ID].nunique()),
        "n_rows": int(len(sample)),
        "selection": "series con entre 5 % y 80 % de dias censurados",
        "censoring_summary": S.describe_censoring(sample),
    }
    (out_dir / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("muestra escrita en %s (%d series)", target, sample[S.SERIES_ID].nunique())
    return target


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--out", type=Path, default=cfg.DATA_INTERIM, help="directorio de salida")
    p.add_argument("--seed", type=int, default=cfg.SUBSAMPLE.seed)
    p.add_argument("--n-series", type=int, default=cfg.SUBSAMPLE.n_series)
    p.add_argument(
        "--cities",
        type=int,
        nargs="*",
        default=list(cfg.SUBSAMPLE.cities) if cfg.SUBSAMPLE.cities else None,
        help="ids de ciudad a conservar; vacio = todas",
    )
    p.add_argument(
        "--make-sample",
        action="store_true",
        help="en vez de descargar, recorta data/interim/ a la muestra commiteada",
    )
    p.add_argument("--interim", type=Path, default=cfg.DATA_INTERIM)
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s · %(message)s")
    args = _parse_args(argv)
    if args.make_sample:
        make_sample(
            interim_dir=args.interim,
            out_dir=args.out,
            n_series=cfg.SUBSAMPLE.sample_n_series,
            seed=args.seed,
        )
    else:
        cities = tuple(args.cities) if args.cities else None
        build_subsample(
            out_dir=args.out,
            n_series=args.n_series,
            cities=cities,
            seed=args.seed,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
