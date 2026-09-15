"""Acceso a las capas de datos, con degradacion explicita a `data/sample/`.

Regla del repo: si el subconjunto grande de `data/interim/` no esta, se usa la
muestra commiteada de `data/sample/` y **se avisa por log**. Nunca en silencio:
un resultado calculado sobre 60 series y presentado como si fueran 3000 es
exactamente el tipo de error que arruina una defensa.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import pandas as pd

from dfcore import config as cfg
from dfcore.data import schema as S

log = logging.getLogger(__name__)

Layer = Literal["panel", "demand", "features"]

_LAYER_FILE: dict[str, str] = {
    "panel": cfg.PANEL_FILE,
    "demand": cfg.DEMAND_FILE,
    "features": cfg.FEATURES_FILE,
}


class DataNotAvailableError(FileNotFoundError):
    """No hay datos en ninguna capa. El mensaje dice que comando correr."""


def resolve_path(layer: Layer, *, prefer_sample: bool = False) -> Path:
    """Ubica el archivo de una capa. Orden: interim/processed y luego sample."""
    filename = _LAYER_FILE[layer]
    primary = cfg.DATA_INTERIM if layer == "panel" else cfg.DATA_PROCESSED
    candidates = [cfg.DATA_SAMPLE / filename, primary / filename]
    if not prefer_sample:
        candidates.reverse()

    for path in candidates:
        if path.exists():
            if path.parent == cfg.DATA_SAMPLE:
                log.warning(
                    "usando la MUESTRA commiteada %s. Es chica y sirve para que el "
                    "repo corra sin descargar nada, no para reportar resultados. "
                    "Correr `make data` para el subconjunto completo.",
                    path,
                )
            return path

    hint = "make data" if layer == "panel" else "make features"
    raise DataNotAvailableError(
        f"no hay datos de la capa '{layer}'. Buscado en "
        f"{[str(c) for c in candidates]}. Correr `{hint}`."
    )


def load_panel(
    *, path: Path | None = None, prefer_sample: bool = False, drop_hourly: bool = True
) -> pd.DataFrame:
    """Panel diario crudo (demanda observada + anotacion de censura).

    Por defecto descarta las secuencias horarias: solo las necesita el
    recuperador de censura, y arrastrarlas multiplica la memoria por 24.
    """
    path = path or resolve_path("panel", prefer_sample=prefer_sample)
    df = pd.read_parquet(path)
    if drop_hourly:
        df = df.drop(columns=[c for c in S.HOURLY_COLS if c in df.columns])
    return S.validate_panel(df, allow_gaps=True)


def load_hourly_panel(*, path: Path | None = None, prefer_sample: bool = False) -> pd.DataFrame:
    """Panel con las secuencias horarias intactas. Solo para censoring."""
    path = path or resolve_path("panel", prefer_sample=prefer_sample)
    df = pd.read_parquet(path)
    missing = [c for c in S.HOURLY_COLS if c not in df.columns]
    if missing:
        raise S.SchemaError(
            f"{path} no trae {missing}; se genero con keep_hourly=False y no sirve "
            "para recuperar la censura"
        )
    return S.validate_panel(df, allow_gaps=True)


def load_demand(*, path: Path | None = None, prefer_sample: bool = False) -> pd.DataFrame:
    """Panel con la demanda latente ya recuperada. Es el insumo de las features."""
    path = path or resolve_path("demand", prefer_sample=prefer_sample)
    df = pd.read_parquet(path)
    return S.validate_panel(df, required=S.DEMAND_REQUIRED, allow_gaps=True)


def load_features(*, path: Path | None = None, prefer_sample: bool = False) -> pd.DataFrame:
    """Matriz de features. No se valida con el contrato del panel porque agrega
    decenas de columnas derivadas; la validacion propia vive en features.build."""
    path = path or resolve_path("features", prefer_sample=prefer_sample)
    return pd.read_parquet(path)


def save_layer(df: pd.DataFrame, layer: Layer, *, out_dir: Path | None = None) -> Path:
    """Persiste una capa en su directorio canonico."""
    out_dir = out_dir or (cfg.DATA_INTERIM if layer == "panel" else cfg.DATA_PROCESSED)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / _LAYER_FILE[layer]
    df.to_parquet(target, index=False, compression="zstd")
    log.info("capa '%s' escrita en %s (%d filas)", layer, target, len(df))
    return target


__all__ = [
    "DataNotAvailableError",
    "load_demand",
    "load_features",
    "load_hourly_panel",
    "load_panel",
    "resolve_path",
    "save_layer",
]
