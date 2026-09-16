"""CONTRATO 4 de 4 · request y response de la API.

Existe antes que el backend a proposito (seccion 13 del plan): con este archivo
el frontend arranca contra datos simulados y deja de estar en el camino critico.

Los nombres de campo son los mismos del esquema de datos y del contrato de
backtest. Un rename aca es un rename en tres lugares mas, asi que no se
renombra por gusto.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Health(BaseModel):
    """Respuesta de /health. Sirve para el healthcheck de Docker Compose."""

    status: str = "ok"
    version: str
    model_loaded: bool
    #: Etiqueta del artefacto servido. Sin esto no se sabe que modelo respondio.
    model_name: str | None = None
    trained_until: date | None = None
    #: Motivo por el que el artefacto existe pero no se pudo cargar. Distingue
    #: "no hay modelo" de "hay uno y esta roto", que se arreglan distinto: el
    #: primero pide entrenar, el segundo casi siempre es desfasaje entre el
    #: artefacto y el codigo (paquete renombrado, version de sklearn distinta).
    model_error: str | None = None

    model_config = ConfigDict(protected_namespaces=())


class SeriesRef(BaseModel):
    """Referencia a una serie tienda-producto."""

    series_id: str = Field(examples=["12_403"])
    store_id: int
    product_id: int
    city_id: int | None = None


# --- /forecast -----------------------------------------------------------
class ForecastRequest(BaseModel):
    series_ids: Annotated[list[str], Field(min_length=1, max_length=500)]
    horizon: Annotated[int, Field(ge=1, le=28)] = 7
    #: Nivel nominal del intervalo. La cobertura empirica se reporta aparte,
    #: porque prometer 90 % y cubrir 60 % es el error que este proyecto mide.
    coverage: Annotated[float, Field(gt=0.5, lt=1.0)] = 0.90
    #: Si es True, el pronostico es de demanda latente (censura corregida).
    #: Si es False, de venta observada. La diferencia entre ambos es el
    #: resultado que el proyecto defiende, asi que es un parametro explicito.
    recover_censoring: bool = True


class ForecastPoint(BaseModel):
    dt: date
    h: Annotated[int, Field(ge=1)]
    y_pred: Annotated[float, Field(ge=0)]
    pred_lo: Annotated[float, Field(ge=0)] | None = None
    pred_hi: Annotated[float, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def _interval_ordered(self) -> ForecastPoint:
        if self.pred_lo is not None and self.pred_hi is not None and self.pred_hi < self.pred_lo:
            raise ValueError("pred_hi no puede ser menor que pred_lo")
        return self


class SeriesForecast(BaseModel):
    series: SeriesRef
    points: list[ForecastPoint]


class ForecastResponse(BaseModel):
    model_name: str
    coverage_nominal: float
    #: Cobertura medida en el backtest para este modelo. Es la que importa.
    coverage_empirical: float | None = None
    forecasts: list[SeriesForecast]

    model_config = ConfigDict(protected_namespaces=())


# --- /reorder ------------------------------------------------------------
class ReorderRequest(BaseModel):
    series_ids: Annotated[list[str], Field(min_length=1, max_length=500)]
    horizon: Annotated[int, Field(ge=1, le=28)] = 7
    #: Costo de quedarse corto: margen perdido por unidad no vendida.
    cu: Annotated[float, Field(gt=0)] = 1.0
    #: Costo de quedarse largo. En perecederos es perdida total al vencimiento,
    #: no costo de capital, y por eso empuja q* hacia arriba.
    co: Annotated[float, Field(gt=0)] = 0.6


class ReorderLine(BaseModel):
    series: SeriesRef
    dt: date
    #: Cantidad sugerida = cuantil q* de la demanda latente. La salida del
    #: modelo **es** la orden, no un insumo para calcularla.
    qty: Annotated[float, Field(ge=0)]
    #: Cuantil critico usado, q* = Cu / (Cu + Co).
    critical_fraction: Annotated[float, Field(gt=0, lt=1)]
    expected_shortfall: Annotated[float, Field(ge=0)]
    expected_overage: Annotated[float, Field(ge=0)]
    #: Costo esperado relativo a la politica actual (promedio movil). Negativo
    #: significa ahorro. Adimensional: el dataset primario esta normalizado.
    cost_delta_pct: float


class ReorderResponse(BaseModel):
    critical_fraction: float
    lines: list[ReorderLine]
    #: Ahorro agregado en porcentaje de costo esperado, no en moneda.
    total_cost_delta_pct: float


# --- /anomalies ----------------------------------------------------------
class AnomalyKind(str, Enum):
    LOAD_ERROR = "load_error"
    STOCKOUT = "stockout"
    RESIDUAL_SPIKE = "residual_spike"
    LEVEL_SHIFT = "level_shift"


class Anomaly(BaseModel):
    series: SeriesRef
    dt: date
    kind: AnomalyKind
    score: float
    observed: float
    expected: float | None = None


class AnomalyResponse(BaseModel):
    detector: str
    threshold: float
    anomalies: list[Anomaly]


# --- /explain ------------------------------------------------------------
class ShapContribution(BaseModel):
    feature: str
    value: float | None = None
    contribution: float


class ExplainRequest(BaseModel):
    series_id: str
    dt: date
    top_k: Annotated[int, Field(ge=1, le=50)] = 12


class ExplainResponse(BaseModel):
    series: SeriesRef
    dt: date
    base_value: float
    prediction: float
    contributions: list[ShapContribution]


# --- /backtest -----------------------------------------------------------
class MetricRow(BaseModel):
    """Una metrica de un modelo, con dispersion entre origenes.

    `std` no es opcional por diseno: la metodologia del proyecto prohibe
    reportar un numero unico, porque un promedio bueno esconde un origen
    catastrofico.
    """

    model_name: str
    metric: str
    mean: float
    std: float
    worst_origin: float
    best_origin: float
    n_origins: Annotated[int, Field(ge=1)]

    model_config = ConfigDict(protected_namespaces=())


class BacktestResponse(BaseModel):
    target: str
    horizon: int
    season_length: int
    rows: list[MetricRow]
    #: Fila del baseline oficial del dataset, cuando esta disponible. Es la
    #: referencia externa que convierte el resultado en comparable.
    external_baseline: MetricRow | None = None


__all__ = [
    "Anomaly",
    "AnomalyKind",
    "AnomalyResponse",
    "BacktestResponse",
    "ExplainRequest",
    "ExplainResponse",
    "ForecastPoint",
    "ForecastRequest",
    "ForecastResponse",
    "Health",
    "MetricRow",
    "ReorderLine",
    "ReorderRequest",
    "ReorderResponse",
    "SeriesForecast",
    "SeriesRef",
    "ShapContribution",
]
