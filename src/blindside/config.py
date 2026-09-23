"""Configuracion central: rutas, semillas y constantes del dominio.

Todo el codigo importa de aqui en vez de hardcodear rutas o numeros magicos.
Un solo lugar para cambiar la semilla es lo que vuelve reproducible el repo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

# --- Rutas ---------------------------------------------------------------
# La raiz se resuelve desde la ubicacion de este archivo (src/blindside/config.py),
# asi funciona igual desde notebooks, tests, la API y la app.
ROOT = Path(__file__).resolve().parents[2]

DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_SAMPLE = ROOT / "data" / "sample"
ARTIFACTS = ROOT / "artifacts"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

#: Nombres de archivo canonicos de cada capa. El resto del codigo no
#: construye nombres de archivo a mano.
PANEL_FILE = "panel.parquet"  # data/interim: submuestreo crudo + secuencias horarias
DEMAND_FILE = "demand.parquet"  # data/processed: demanda latente recuperada
FEATURES_FILE = "features.parquet"  # data/processed: matriz de features
MANIFEST_FILE = "subsample_manifest.json"  # data/interim: que se submuestreo y con que semilla

# --- Bases de calculo ----------------------------------------------------
#: Las dos bases sobre las que se puede pronosticar. `recovered` es demanda
#: latente (censura corregida) y `observed` es la venta que registra el ERP.
Basis = Literal["observed", "recovered"]

#: Base por defecto. Es la recuperada porque es la que el proyecto defiende; la
#: interfaz arranca en `observed` a proposito, para corregirlo en vivo.
DEFAULT_BASIS: Final[Basis] = "recovered"

#: Un artefacto por base. Son **dos** y no uno porque el toggle de censura de la
#: interfaz tiene que cambiar las cantidades sugeridas, no solo que serie se
#: dibuja: un unico modelo entrenado sobre demanda latente puede mostrar la
#: brecha historica, pero responde lo mismo en las dos posiciones del control, y
#: entonces la mitad del argumento — que corregir la censura cambia lo que se
#: pide — queda sin evidencia. Los dos se entrenan con la misma arquitectura y
#: los mismos hiperparametros para que la comparacion sea pareada (D10).
MODEL_FILES: Final[dict[Basis, str]] = {
    "recovered": "model.joblib",
    "observed": "model_observed.joblib",
}


def model_path(basis: Basis = DEFAULT_BASIS) -> Path:
    """Ruta del artefacto de una base. Unico lugar donde vive ese nombre."""
    try:
        filename = MODEL_FILES[basis]
    except KeyError:
        raise ValueError(
            f"base de calculo '{basis}' desconocida; son {sorted(MODEL_FILES)}"
        ) from None
    # ARTIFACTS se lee en cada llamada a proposito: los tests lo reapuntan a un
    # tmp_path con monkeypatch y una ruta capturada al importar los ignoraria.
    return ARTIFACTS / filename


# --- Semilla -------------------------------------------------------------
#: Semilla unica del proyecto. Se puede sobreescribir con BLINDSIDE_SEED para
#: comprobar que un resultado no depende de una semilla afortunada.
SEED = int(os.environ.get("BLINDSIDE_SEED", 42))


# --- Constantes del dominio ---------------------------------------------
@dataclass(frozen=True)
class ForecastConfig:
    """Parametros de pronostico y validacion.

    ``horizon`` es 7 dias y no 28 a proposito: FreshRetailNet-50K tiene 90 dias
    de historia por serie y su split ``eval`` oficial son exactamente 7 dias.
    Un horizonte de 28 dias dejaria como maximo 2 origenes de backtest, muy
    lejos de los 8 que exige la metodologia. Ver docs/decisiones.md D8.
    """

    horizon: int = 7
    #: Estacionalidad semanal. Es el denominador de MASE (naive estacional).
    season_length: int = 7
    #: Numero minimo de origenes de backtest exigido por la metodologia.
    n_origins: int = 8
    #: Dias entre origenes consecutivos.
    step: int = 3
    #: Historia minima antes del primer origen, en dias.
    min_train_days: int = 42
    #: Nivel nominal del intervalo conformal.
    coverage: float = 0.90
    #: Cuantiles que se entrenan para la capa de decision.
    quantiles: tuple[float, ...] = (0.05, 0.5, 0.9, 0.95)


@dataclass(frozen=True)
class CensoringConfig:
    """Parametros de la recuperacion de demanda censurada (seccion 8.0).

    ``open_hours`` refleja que ``stock_hour6_22_cnt`` del dataset cuenta las
    horas de quiebre entre las 6:00 y las 22:00; fuera de esa ventana la tienda
    no vende y un cero no es senal de quiebre.

    Son los indices 6..21 de ``hours_stock_status``, o sea **16 franjas**, no 17.
    Verificado contra las filas de ejemplo de la ficha del dataset: la fila con
    mascara ``[0]*11 + [1]*13`` trae ``stock_hour6_22_cnt = 11``, que es la
    cuenta de quiebres en 6..21 y no en 6..22. La diferencia de una hora
    desplazaria todo el factor de inflacion de la recuperacion de censura.
    """

    open_hours: tuple[int, ...] = tuple(range(6, 22))
    #: Tope del factor de inflacion. Sin tope, un dia con 16 de 17 horas en
    #: quiebre produce una demanda latente absurda a partir de una sola venta.
    max_inflation: float = 3.0
    #: Peso minimo de horas disponibles para intentar la correccion.
    min_available_weight: float = 0.15
    #: Ventana de la media movil que estima el nivel en el recuperador Tobit.
    ewma_span: int = 14


@dataclass(frozen=True)
class SubsampleConfig:
    """Submuestreo declarado del dataset primario (ver docs/decisiones.md D2).

    El dataset completo son 4,85 M filas con dos columnas de secuencias de 24
    elementos. Nunca se materializa entero: el filtro se aplica durante la
    lectura del parquet.
    """

    #: Series objetivo del subconjunto de trabajo.
    n_series: int = 3000
    #: Ciudades que se conservan. None = todas las del parquet leido.
    cities: tuple[int, ...] | None = (0, 1, 2)
    #: Series del subconjunto commiteado en data/sample/.
    sample_n_series: int = 60
    seed: int = SEED


@dataclass(frozen=True)
class EconomicsConfig:
    """Economia del newsvendor.

    ``cu`` es el costo de quedarse corto (margen perdido) y ``co`` el de quedarse
    largo. En perecederos ``co`` es perdida total al vencimiento, no costo de
    capital, y eso empuja el cuantil optimo hacia arriba.

    Las magnitudes son adimensionales a proposito: ``sale_amount`` viene
    multiplicado por un coeficiente no divulgado, asi que el ROI del caso
    primario se expresa en porcentaje y no en moneda. Ver docs/roi.md.
    """

    cu: float = 1.0
    co: float = 0.6

    @property
    def critical_fraction(self) -> float:
        """q* = Cu / (Cu + Co). El cuantil que hay que pronosticar."""
        return self.cu / (self.cu + self.co)


FORECAST = ForecastConfig()
CENSORING = CensoringConfig()
SUBSAMPLE = SubsampleConfig()
ECONOMICS = EconomicsConfig()


@dataclass(frozen=True)
class Paths:
    """Agrupa las rutas para inyectarlas en tests con un tmp_path."""

    raw: Path = DATA_RAW
    interim: Path = DATA_INTERIM
    processed: Path = DATA_PROCESSED
    sample: Path = DATA_SAMPLE
    artifacts: Path = ARTIFACTS
    reports: Path = REPORTS
    figures: Path = FIGURES

    def mkdirs(self) -> None:
        for p in (
            self.raw,
            self.interim,
            self.processed,
            self.sample,
            self.artifacts,
            self.reports,
            self.figures,
        ):
            p.mkdir(parents=True, exist_ok=True)


PATHS = Paths()

#: Identificador de la fuente primaria en HuggingFace.
HF_DATASET = "Dingdong-Inc/FreshRetailNet-50K"

__all__ = [
    "ARTIFACTS",
    "CENSORING",
    "DATA_INTERIM",
    "DATA_PROCESSED",
    "DATA_RAW",
    "DATA_SAMPLE",
    "DEFAULT_BASIS",
    "DEMAND_FILE",
    "ECONOMICS",
    "FEATURES_FILE",
    "FIGURES",
    "FORECAST",
    "HF_DATASET",
    "MANIFEST_FILE",
    "MODEL_FILES",
    "PANEL_FILE",
    "PATHS",
    "REPORTS",
    "ROOT",
    "SEED",
    "SUBSAMPLE",
    "Basis",
    "CensoringConfig",
    "EconomicsConfig",
    "ForecastConfig",
    "Paths",
    "SubsampleConfig",
    "model_path",
]
