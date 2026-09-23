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
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Basis(str, Enum):
    """Base de calculo. Es el vocabulario del toggle de la interfaz (`?basis=`).

    No reemplaza a `recover_censoring` en los requests: ese nombre ya esta en el
    contrato y renombrarlo seria un rename en tres lugares mas. El booleano
    entra, la base sale — asi la respuesta dice con que artefacto se contesto.
    """

    OBSERVED = "observed"
    RECOVERED = "recovered"

    @classmethod
    def from_flag(cls, *, recover_censoring: bool) -> Basis:
        return cls.RECOVERED if recover_censoring else cls.OBSERVED


class ModelStatus(BaseModel):
    """Estado de un artefacto. Hay uno por base de calculo.

    `n_series_seen` contra `n_series_in_panel` existe porque el desajuste
    train/serve que ninguna metrica detecta es servir un artefacto entrenado
    sobre `data/sample/` contra el panel completo. Paso en este proyecto.
    """

    basis: Basis
    artifact: str
    loaded: bool
    model_name: str | None = None
    #: Columna con la que se entreno: sale_amount o demand_latent.
    target: str | None = None
    trained_until: date | None = None
    n_series_seen: int | None = None
    n_series_in_panel: int | None = None
    error: str | None = None

    model_config = ConfigDict(protected_namespaces=())


class PanelInfo(BaseModel):
    """Que datos se estan sirviendo. Dispara el estado de muestra de la interfaz.

    Los conteos van **siempre contra su referencia**: "60 de 3066 series" dice
    algo, "60 series" no. La referencia sale del manifiesto del submuestreo, asi
    que es `None` si no esta — y en ese caso la interfaz no puede afirmar que
    esta viendo el panel completo.
    """

    source: Literal["processed", "sample"]
    is_sample: bool
    n_series: int
    n_stores: int
    n_products: int
    n_days: int
    date_min: date
    date_max: date
    reference_n_series: int | None = None
    reference_n_stores: int | None = None
    reference_n_products: int | None = None


class CoveragePoint(BaseModel):
    """Cobertura empirica de un paso del horizonte contra la nominal.

    La degradacion **no** es monotona y eso es correcto: con estacionalidad
    semanal el objetivo de h7 cae el mismo dia de la semana que el origen.
    """

    h: Annotated[int, Field(ge=1)]
    coverage_nominal: float
    coverage_empirical: float
    n: Annotated[int, Field(ge=1)]


class Health(BaseModel):
    """Respuesta de /health. Sirve para el healthcheck de Docker Compose."""

    status: str = "ok"
    version: str
    #: Se refiere al artefacto de la base por defecto (la recuperada), que es lo
    #: que el healthcheck del contenedor tiene que vigilar. El detalle por base
    #: esta en `models`.
    model_loaded: bool
    #: Etiqueta del artefacto servido. Sin esto no se sabe que modelo respondio.
    model_name: str | None = None
    trained_until: date | None = None
    #: Motivo por el que el artefacto existe pero no se pudo cargar. Distingue
    #: "no hay modelo" de "hay uno y esta roto", que se arreglan distinto: el
    #: primero pide entrenar, el segundo casi siempre es desfasaje entre el
    #: artefacto y el codigo (paquete renombrado, version de sklearn distinta).
    model_error: str | None = None

    #: Un estado por base de calculo. Si la base `observed` no esta cargada, el
    #: toggle de la interfaz no puede cambiar la cantidad sugerida, y eso tiene
    #: que ser visible antes de la demo y no durante.
    models: list[ModelStatus] = []
    panel: PanelInfo | None = None
    coverage_nominal: float | None = None
    coverage_by_horizon: list[CoveragePoint] = []
    #: Por que `coverage_by_horizon` viene vacio, cuando viene vacio. Un bloque
    #: sin datos con el motivo a la vista es honesto; un numero inventado no.
    coverage_note: str | None = None

    model_config = ConfigDict(protected_namespaces=())


class SeriesRef(BaseModel):
    """Referencia a una serie tienda-producto."""

    series_id: str = Field(examples=["12_403"])
    store_id: int
    product_id: int
    city_id: int | None = None


# --- /series -------------------------------------------------------------
class SeriesItem(SeriesRef):
    """Serie con su jerarquia de catalogo, para el selector.

    FreshRetailNet-50K **no trae nombres de producto**: la jerarquia son ids
    numericos. Asi que la "descripcion" que muestra y busca el selector es la
    jerarquia formateada, no un nombre comercial que el dataset no tiene.
    Inventar nombres seria mas lindo y seria falso.
    """

    management_group_id: int | None = None
    first_category_id: int | None = None
    second_category_id: int | None = None
    third_category_id: int | None = None
    #: Texto contra el que corre la busqueda, junto con el codigo de la serie.
    label: str


class SeriesPage(BaseModel):
    """Pagina de resultados del selector.

    Trae `total` porque el diseno muestra el conteo de resultados sobre el total
    y porque 3066 series no entran en un desplegable.
    """

    total: int
    limit: int
    offset: int
    query: str | None = None
    items: list[SeriesItem]


# --- /series/{series_id}/history -----------------------------------------
class StockoutRun(BaseModel):
    """Racha de dias consecutivos con quiebre. Es el sombreado del grafico.

    Se entregan los tramos ya agrupados y no solo la bandera por dia porque el
    grafico necesita el tramo como unidad: una racha de un dia se dibuja con
    ancho minimo, y la mediana del panel real es de 2 dias.
    """

    start: date
    end: date
    n_days: Annotated[int, Field(ge=1)]


class HistoryPoint(BaseModel):
    dt: date
    #: Venta registrada. Es lo que ve el ERP.
    observed: Annotated[float, Field(ge=0)]
    #: Demanda latente recuperada. En dias sin quiebre es identica a `observed`.
    recovered: Annotated[float, Field(ge=0)]
    is_censored: bool
    #: Horas de quiebre en la ventana comercial. La franja del grafico escala de
    #: 0 a `open_hours`, no de 0 a 24.
    oos_hours_open: float
    available_weight: float | None = None
    inflation_factor: float | None = None


class HistorySummary(BaseModel):
    n_days: int
    n_censored_days: int
    #: Dias con quiebre de los ultimos 28. Es la columna de la fila expandida.
    censored_days_last_28: int
    share_censored_days: float
    max_run_days: int
    mean_oos_hours_when_censored: float | None = None
    #: Uplift de la recuperacion sobre toda la serie.
    uplift_pct: float
    #: Uplift **en los dias sin quiebre**, que tiene que ser exactamente 0. Es
    #: la verdad de terreno con la que se mide el sesgo: si no da cero, la
    #: correccion esta tocando dias que no debia y la medicion queda destruida.
    uplift_pct_clean_days: float


class SeriesHistory(BaseModel):
    series: SeriesRef
    #: Franjas comerciales del dia (16 en este dataset). Escala de la franja de
    #: horas de quiebre.
    open_hours: int
    points: list[HistoryPoint]
    runs: list[StockoutRun]
    summary: HistorySummary


class SeriesHistoryRequest(BaseModel):
    """Historia de varias series. Es lo que pide la tabla de reposicion por fila."""

    series_ids: Annotated[list[str], Field(min_length=1, max_length=500)]
    days: Annotated[int, Field(ge=7, le=400)] | None = None


class SeriesHistoryBatch(BaseModel):
    series: list[SeriesHistory]


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
    #: Base con la que se contesto. Se devuelve siempre, tambien cuando coincide
    #: con el default: una respuesta que no dice sobre que base se calculo es
    #: indistinguible de la otra, y el toggle deja de ser verificable.
    basis: Basis
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
    #: Misma semantica que en `ForecastRequest`, y esta aca porque la orden es
    #: justamente lo que tiene que cambiar al corregir la censura. Sin este
    #: campo el toggle de la interfaz movia el grafico y no la decision, que es
    #: la mitad del argumento del proyecto.
    recover_censoring: bool = True


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
    #: Base con la que se calculo la orden. Las dos bases dan cantidades
    #: distintas y el numero no dice de cual salio, asi que va en la respuesta.
    basis: Basis
    model_name: str
    lines: list[ReorderLine]
    #: Ahorro agregado en porcentaje de costo esperado, no en moneda.
    total_cost_delta_pct: float

    model_config = ConfigDict(protected_namespaces=())


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
    "Basis",
    "CoveragePoint",
    "ExplainRequest",
    "ExplainResponse",
    "ForecastPoint",
    "ForecastRequest",
    "ForecastResponse",
    "Health",
    "HistoryPoint",
    "HistorySummary",
    "MetricRow",
    "ModelStatus",
    "PanelInfo",
    "ReorderLine",
    "ReorderRequest",
    "ReorderResponse",
    "SeriesForecast",
    "SeriesHistory",
    "SeriesHistoryBatch",
    "SeriesHistoryRequest",
    "SeriesItem",
    "SeriesPage",
    "SeriesRef",
    "ShapContribution",
    "StockoutRun",
]
