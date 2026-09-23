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
from typing import Annotated, Final, Literal

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
    #: Banda de rotacion (baja, media, alta), con los mismos cortes con los que el
    #: backtest desagrega sus metricas. Es la columna "Clase" de la tabla, y esta
    #: porque el modelo complejo no le gana al ingenuo en baja rotacion: quien
    #: mira la lista tiene que poder ver de que clase es cada fila.
    rotation_band: str | None = None
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


# --- Plan comercial del horizonte ---------------------------------------
class CommercialPlan(BaseModel):
    """Covariables que se conocen de antemano, para los dias del horizonte.

    **Por que existe este objeto.** El modelo usa tres covariables del dia
    objetivo que no son fuga porque se conocen antes: descuento, feriado y
    actividad comercial. En el backtest salen del panel, que ya tiene esos dias.
    En produccion el horizonte esta **despues** del ultimo dia del panel, asi que
    no hay de donde leerlas: o las aporta quien consulta, que es el que conoce su
    plan comercial, o hay que asumir un valor.

    Sin este campo la API las dejaba en NaN. Eso no era un detalle: medido sobre un
    fold real, servir las tres en NaN da **MASE 1,639 contra 0,879** con las
    covariables reales — 86 % peor, y peor que el naive estacional — y una orden
    52,5 % mas alta de lo que corresponde. El backtest estaba perfecto porque el
    arnes si las poblaba; el desajuste vivia solo en inferencia, y LightGBM trata
    el NaN como una rama mas, asi que la API contestaba 200 con un numero plausible.

    El default no es neutro sino medido: la mediana de los ultimos dias del panel.
    Las cinco variantes evaluadas y por que gano esa estan en `docs/decisiones.md`
    D19. Y se **declara en la respuesta**, porque una suposicion que no se ve es
    peor que un error.
    """

    #: Multiplicador de precio: 1,0 es precio de lista y 0,31 el descuento mas
    #: agresivo del panel. No es un porcentaje de descuento, es el factor.
    discount: Annotated[float, Field(gt=0.0, le=1.0)] = 1.0
    #: Feriado. Verificado que en el panel es atributo puro de la fecha: las 97
    #: fechas tienen un solo valor para todas las series.
    holiday_flag: Annotated[int, Field(ge=0, le=1)] = 0
    #: Campania o actividad comercial de la serie.
    activity_flag: Annotated[int, Field(ge=0, le=1)] = 0


#: Plan neutro: precio de lista, sin feriado y sin campania. **No es el default**,
#: es el ultimo recurso cuando no hay panel del que sacar la mediana. Medido sobre
#: un fold real, asumir precio de lista subestima la orden un 13,2 % contra las
#: covariables reales, porque el 45,9 % de las filas del panel tiene descuento y el
#: descuento sube la demanda. El default es `panel_median`. Ver D19.
PLAN_NEUTRO: Final = CommercialPlan()

#: Dias de panel con los que se calcula la mediana del plan por defecto. Coincide
#: con la ventana de la politica de reposicion a proposito: las dos responden a
#: "que viene pasando ultimamente".
PLAN_WINDOW_DAYS: Final = 21


class PlanEcho(BaseModel):
    """El plan con el que se contesto, y de donde salio.

    Va en la respuesta y no solo en el request porque el default se resuelve del
    lado del servidor: una respuesta que no dice que descuento asumio no se puede
    auditar, y el descuento es la covariable que mas pesa de las tres.

    `source` distingue tres casos:

    - `request`: lo aporto quien consulta. Es el unico que no es una suposicion.
    - `panel_median`: la mediana de los ultimos dias del panel, o sea "la cadencia
      comercial reciente sigue". Es el default y esta elegido por medicion, no por
      gusto: ver `docs/decisiones.md` D19.
    - `default`: precio de lista sin campania. Se usa cuando no hay panel del que
      sacar la mediana, y queda declarado porque subestima la orden un 13 %.
    """

    plan: CommercialPlan
    source: Literal["request", "panel_median", "default"]
    #: Dias de panel con los que se calculo la mediana, cuando aplica.
    window_days: int | None = None


# --- /forecast -----------------------------------------------------------
class ForecastRequest(BaseModel):
    series_ids: Annotated[list[str], Field(min_length=1, max_length=500)]
    horizon: Annotated[int, Field(ge=1, le=28)] = 7
    #: Plan comercial del horizonte. Si no viene, se resuelve con la mediana del
    #: panel y la respuesta declara cual se uso.
    plan: CommercialPlan | None = None
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
    #: Plan comercial con el que se calculo, y si lo aporto quien consulta o lo
    #: asumio el servidor.
    plan: PlanEcho
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
    #: Plan comercial del horizonte. Si no viene, se resuelve con la mediana del panel.
    plan: CommercialPlan | None = None
    #: Ventana de la politica contra la que se compara: promedio movil de N dias,
    #: que es como repone hoy la operacion. Es el denominador de `cost_delta_pct`.
    policy_window: Annotated[int, Field(ge=1, le=90)] = 21


class ReorderLine(BaseModel):
    series: SeriesRef
    dt: date
    #: Cantidad sugerida = cuantil q* de la demanda latente. La salida del
    #: modelo **es** la orden, no un insumo para calcularla.
    qty: Annotated[float, Field(ge=0)]
    #: Cuantil critico usado, q* = Cu / (Cu + Co).
    critical_fraction: Annotated[float, Field(gt=0, lt=1)]
    #: Cantidad que repondria la politica actual: promedio movil de
    #: `policy_window` dias de la base activa. Va en la respuesta porque es el
    #: numero contra el que se lee todo lo demas.
    policy_qty: Annotated[float, Field(ge=0)]
    #: Demanda esperada bajo la distribucion predictiva del modelo. No es el
    #: pronostico puntual del cuantil critico: es la media de la distribucion.
    expected_demand: Annotated[float, Field(ge=0)]
    #: E[(D - q)+] bajo la distribucion del modelo. **Cota inferior**: la grilla
    #: de cuantiles termina en 0,95 y la cola se trata como plana, asi que la
    #: demanda extrema no esta descrita. `tail_mass` dice cuanta masa quedo afuera.
    expected_shortfall: Annotated[float, Field(ge=0)]
    #: E[(q - D)+] bajo la misma distribucion. En perecederos es merma esperada.
    expected_overage: Annotated[float, Field(ge=0)]
    #: Costo esperado relativo a la politica actual, las dos ordenes evaluadas
    #: bajo la **misma** distribucion predictiva. Negativo significa ahorro.
    #: Adimensional: el dataset primario esta normalizado.
    cost_delta_pct: float


class ReorderResponse(BaseModel):
    critical_fraction: float
    #: Base con la que se calculo la orden. Las dos bases dan cantidades
    #: distintas y el numero no dice de cual salio, asi que va en la respuesta.
    basis: Basis
    model_name: str
    #: Plan comercial asumido o recibido. Ver `CommercialPlan`.
    plan: PlanEcho
    #: Ventana de la politica de referencia, en dias.
    policy_window: int
    #: Masa de probabilidad por encima del ultimo cuantil de la grilla, que no
    #: esta descrita. Es el motivo por el que el faltante esperado es una cota
    #: inferior, y va en la respuesta para que la interfaz lo pueda decir.
    tail_mass: float
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
    #: Misma semantica que en el resto: se explica el artefacto de esa base.
    recover_censoring: bool = True
    #: Plan comercial del dia explicado. Importa mas aca que en el resto: el
    #: descuento es el contribuyente mas grande de la explicacion, asi que
    #: explicar con un supuesto sin declararlo es explicar otra cosa.
    plan: CommercialPlan | None = None


class ExplainResponse(BaseModel):
    series: SeriesRef
    dt: date
    basis: Basis
    model_name: str
    #: Cuantil explicado. Es el critico y no la mediana: el numero que la interfaz
    #: muestra es la cantidad a pedir, asi que explicar la mediana seria explicar
    #: otra cifra.
    quantile: float | None = None
    base_value: float
    prediction: float
    #: Plan comercial con el que se armo la matriz de features explicada.
    plan: PlanEcho
    contributions: list[ShapContribution]

    model_config = ConfigDict(protected_namespaces=())


# --- /products/map -------------------------------------------------------
class ProductPoint(BaseModel):
    product_id: int
    x: float
    y: float
    rotation_band: str
    demanda_media: float
    tasa_quiebre: float
    n_series: int


class ProductMap(BaseModel):
    """Proyeccion 2D del catalogo, con la varianza que realmente captura.

    La varianza explicada va en la respuesta porque un scatter sin ella invita a
    leer distancias que la proyeccion no conserva.
    """

    method: str
    features: list[str]
    explained_variance: list[float]
    points: list[ProductPoint]


# --- /backtest/breakdown -------------------------------------------------
class OriginMetric(BaseModel):
    model_name: str
    origin: int
    origin_date: date
    metric: str
    value: float

    model_config = ConfigDict(protected_namespaces=())


class HorizonMetric(BaseModel):
    model_name: str
    h: int
    metric: str
    value: float

    model_config = ConfigDict(protected_namespaces=())


class BandMetric(BaseModel):
    model_name: str
    band: str
    metric: str
    value: float
    n: int

    model_config = ConfigDict(protected_namespaces=())


class BacktestBreakdown(BaseModel):
    """Desagregado del backtest: por origen, por horizonte y por banda.

    Es lo que convierte "MASE 0,83" en un argumento: el promedio bueno puede
    esconder un origen catastrofico, y el origen catastrofico es el que pasa en
    produccion.
    """

    target: str
    horizon: int
    n_origins: int
    origins: list[OriginMetric]
    horizons: list[HorizonMetric]
    bands: list[BandMetric]


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
    "PLAN_NEUTRO",
    "PLAN_WINDOW_DAYS",
    "Anomaly",
    "AnomalyKind",
    "AnomalyResponse",
    "BacktestBreakdown",
    "BacktestResponse",
    "BandMetric",
    "Basis",
    "CommercialPlan",
    "CoveragePoint",
    "ExplainRequest",
    "ExplainResponse",
    "ForecastPoint",
    "ForecastRequest",
    "ForecastResponse",
    "Health",
    "HistoryPoint",
    "HistorySummary",
    "HorizonMetric",
    "MetricRow",
    "ModelStatus",
    "OriginMetric",
    "PanelInfo",
    "PlanEcho",
    "ProductMap",
    "ProductPoint",
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
