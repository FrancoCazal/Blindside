/**
 * Textos de la interfaz en inglés. Es el idioma por defecto y la **forma de
 * referencia**: `es.ts` tiene que cumplir el mismo tipo, así que una clave que
 * falta en un idioma no compila.
 *
 * Las funciones reciben cifras ya formateadas. Formatear acá crearía una
 * dependencia circular con `format.ts`, que lee el idioma activo.
 */

const MOTIVOS = {
  quebrado_ahora: {
    corto: "Stocked out now",
    significa: "In stockout over the last few days, without a break.",
    hacer:
      "Urgent today, not analytical: demand is being lost while you read this. Restock before reviewing anything else.",
  },
  riesgo_merma: {
    corto: "Waste risk",
    significa:
      "With the current policy, half or more of what gets ordered is not expected to sell over the horizon. In perishables that surplus is lost when it expires.",
    hacer:
      "Lower the order to the suggested quantity, which already prices in the cost of surplus. The avoidable column says how much of that loss goes away.",
  },
  no_confiable: {
    corto: "Unreliable model",
    significa:
      "The model loses to the seasonal naive on this series. The overall MASE does not apply here.",
    hacer:
      "Do not use the suggested quantity without reviewing it. The 21-day moving average is a better reference for these series until the cause is understood.",
  },
  alto_volumen: {
    corto: "High volume",
    significa:
      "In the top demand decile, so an error is costly in absolute terms even when the relative error is small.",
    hacer: "Review these first by impact, even when the model is accurate.",
  },
  senal_escasa: {
    corto: "Thin signal",
    significa:
      "A large share of recent demand is estimated rather than observed, because the series spent a long time out of stock.",
    hacer:
      "The forecast leans on the censoring correction more than on real sales. Treat the interval as wider than it says.",
  },
} as Record<string, { corto: string; significa: string; hacer: string }>;

export const en = {
  locale: "en-US",
  /** Separador entre la cifra y el signo de porcentaje. */
  espacioPorcentaje: "",
  meses: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  fechaCorta: (dia: number, mes: string) => `${mes} ${dia}`,
  diasSemana: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
  de: "of",
  codigoTienda: "S",
  codigoProducto: "P",
  tituloDocumento: "Blindside · perishable replenishment",

  comun: {
    reintentar: "Retry",
    cargando: "loading…",
    verLosDatos: "Show the data",
    comoSeCalcula: "How it's calculated",
    comoSeVerifica: "How it's verified",
    sinDato: "no data",
    si: "yes",
    no: "no",
    noSePudoCargar: (que: string) => `${que}: could not be loaded.`,
    exportarCsv: "Export CSV",
    primeraPagina: "First page",
    paginaAnterior: "Previous page",
    paginaSiguiente: "Next page",
    paginacion: (desde: string, hasta: string, total: string, pagina: string, paginas: string) =>
      `${desde}–${hasta} of ${total} · page ${pagina} of ${paginas}`,
    rango: (desde: string, hasta: string, total: string) => `${desde}–${hasta} of ${total}`,
    ceroSeries: "0 series",
    dias: (n: string) => `${n} d`,
    ninguna: "none yet",
  },

  bases: { observed: "Observed sales", recovered: "Recovered demand" },
  bandas: { alta: "high", media: "medium", baja: "low" } as Record<string, string>,
  rotacionDe: (banda: string) => `${banda} turnover`,

  nav: {
    aria: "Screens",
    grupos: { operacion: "Operations", analisis: "Analysis", sistema: "System" },
    pantallas: {
      panel: "Dashboard",
      alerts: "Alerts",
      reorder: "Replenishment",
      series: "Series",
      models: "Models",
      data: "Data",
      pipeline: "Pipeline",
    },
    iniciales: {
      panel: "D",
      alerts: "A",
      reorder: "R",
      series: "S",
      models: "M",
      data: "Dt",
      pipeline: "Pi",
    },
    colapsar: "« Collapse",
    expandir: "»",
  },

  cromo: {
    buscar: "Search series by store or product",
    tecla: "Ctrl K",
    muestra: "Sample",
    desfase: (dias: string) => `Model ${dias} d behind the data`,
    desfaseTitulo: "There is data newer than the model. Retrain with make update TRAIN=1 or make train.",
    angostoTitulo: "This needs more width",
    angostoTexto:
      "This interface is designed for 1180 px of content and supported down to 1024. Below that the decision figures would drop under 19 px and the tables would lose the columns that hold the comparison.",
    muestraTitulo: "These are not the full panel's numbers",
    muestraTexto: (series: string, tiendas: string, productos: string) =>
      `The data comes from data/sample/: ${series} series, ${tiendas} stores, ${productos} products. Error metrics and the recovery uplift are computed on that sample and are not comparable with the full panel.`,
    muestraComando: "Load the panel:",
  },

  preferencias: {
    boton: "Settings",
    titulo: "Settings",
    idioma: "Language",
    tema: "Theme",
    temas: { sistema: "System", claro: "Light", oscuro: "Dark" },
    nota: "Saved in this browser. No account needed.",
    cerrar: "Close",
  },

  toggle: {
    aria: "Calculation basis",
    anuncioCantidad: (base: string, antes: string, despues: string) =>
      `${base}. The suggested quantity goes from ${antes} to ${despues}`,
  },

  ratio: {
    rotulo: "Cost of surplus / of shortfall",
    aria: "Cost ratio",
    lecturas: {
      "0.3": "Dry goods: surplus is tied-up capital",
      "0.6": "Perishable: surplus is a total loss when it expires",
      "1": "Both errors cost the same: the optimum is the median",
      "1.5": "Surplus hurts more than a stockout",
    } as Record<string, string>,
    personalizado: "Custom cost ratio",
  },

  filtros: { tienda: "Store", rotacion: "Turnover", todas: "all", limpiar: "Clear" },

  estados: {
    sinArtefactoTitulo: "The model has not been trained",
    sinArtefactoTexto:
      "The API is up and serving data, but there is no artifact that can produce an order quantity. The evidence screens — Data and Models — still work because they do not depend on the model.",
    base: "Calculation basis",
    artefacto: "Artifact",
    estado: "Status",
    cargado: "loaded",
    falta: "missing",
    sinArtefactoComando:
      "make train serializes both artifacts, one per calculation basis. Both are needed: with only one, the censoring toggle changes the chart and returns the same quantity in both positions.",
    volverAConsultar: "Check again",
    sinRespuesta: "No response from the API",
    conError: "The API responded with an error",
    sinRespuestaTexto: (base: string) =>
      `The dashboard finds nothing listening on ${base}. It is not that there is no data: there is no process. If the API is running, this also happens when the browser origin is not in the CORS allowlist.`,
    conErrorTexto: "The API is up and rejected the request. The detail below comes from the backend.",
    ultimoIntento: "Last attempt",
    proximoIntento: "Next retry",
    enSegundos: (s: string) => `in ${s} s`,
    endpoint: "Endpoint",
    motivo: "Reason",
    codigo: (c: string) => `Status ${c}`,
    reintentarAhora: "Retry now",
    oBien: "or",
    cargandoPanel: "Loading panel data",
    apiViejaTitulo: "The API is older than this interface",
    apiViejaTexto: (url: string) =>
      `${url} responds, but it is missing fields this interface needs, such as the store list or the per-basis status.`,
    apiViejaComando:
      "If you are running the API in Docker, the image has the code it was built with: docker compose up -d --build api. Locally, make api already picks up the changes.",
  },

  selector: {
    aria: "Search series",
    placeholder: "Store, product or series code",
    resultados: "Results",
    sinResultados: (q: string) => `No results for “${q}”.`,
    mover: "↑↓ move",
    abrir: "↵ open",
    cerrarTecla: "esc close",
    cerrar: "Close",
  },

  descripcionSerie: (partes: {
    tienda: string;
    producto: string;
    grupo?: string;
    categorias?: string;
    ciudad?: string;
  }) =>
    [
      `store ${partes.tienda}`,
      `product ${partes.producto}`,
      partes.grupo != null ? `group ${partes.grupo}` : null,
      partes.categorias ? `cat ${partes.categorias}` : null,
      partes.ciudad != null ? `city ${partes.ciudad}` : null,
    ]
      .filter(Boolean)
      .join(" · "),

  motivos: MOTIVOS,
  cifraMotivo: {
    racha: (d: string) => `${d} d in a row out of stock`,
    merma: (pct: string) => `${pct} unsold under the policy`,
    mermaSinMedir: "waste not measured",
    mase: (v: string) => `MASE ${v}`,
    maseSinMedir: "MASE not measured",
    estimada: (pct: string) => `${pct} of demand is estimated`,
    volumen: (v: string) => `mean demand ${v}`,
  },
  umbral: {
    no_confiable: (v: string) => `series MASE above ${v}: worse than the seasonal naive`,
    alto_volumen: () => "top decile of mean demand over the last 28 days",
    senal_escasa: (pct: string) => `more than ${pct} of 28-day demand is estimated`,
    quebrado_ahora: (d: string) => `${d} or more stockout days in a row up to today`,
    riesgo_merma: (pct: string, horizonte: string) =>
      `expected surplus under the current policy of ${pct} or more of expected demand over ${horizonte} days, and the suggested quantity reduces it`,
  } as Record<string, (a: string, b: string) => string>,
  noCalculado: {
    no_confiable: "there is no saved backtest: run make models to measure error per series",
    riesgo_merma:
      "there is no model with quantiles loaded, and the expected surplus comes from the predictive distribution. Train with make train",
  } as Record<string, string>,

  ingesta: {
    estados: {
      ok: "applied",
      sin_cambios: "no changes",
      rechazado: "rejected",
      simulado: "dry run",
    } as Record<string, string>,
    tipo: { ingest: "ingestion", promote: "promotion", rollback: "rollback" } as Record<string, string>,
    resumen: (r: { nuevas: string; duplicadas: string; conflictos: string; estado: string }) => {
      if (r.estado === "rechazado") return `${r.conflictos} rows contradict data already loaded. Nothing was written.`;
      if (r.estado === "sin_cambios") return `All ${r.duplicadas} rows were already loaded with the same values.`;
      if (r.estado === "simulado") return `Dry run: ${r.nuevas} new rows would be added. Nothing was written.`;
      return `${r.nuevas} new rows · ${r.duplicadas} duplicates ignored.`;
    },
  },

  frescura: {
    al_dia: "up to date: the model saw all the data",
    desfasado: (d: string) => `behind: it is missing ${d} days of data`,
    sin_modelo: "no model loaded",
    sin_datos: "no data loaded",
  },

  modelos: {
    nombres: {
      cqr_lgbm_quantile: "Global LightGBM · CQR",
      conformal_lgbm_quantile_adaptive: "Global LightGBM · residual conformal",
      lgbm_global: "Global LightGBM · point",
      lgbm_quantile: "Global LightGBM · quantile",
      xgb_global: "Global XGBoost",
      ridge: "Ridge",
      lasso: "Lasso",
      croston_sba: "Croston SBA",
      moving_average: "21-day moving average",
      seasonal_moving_average: "Seasonal moving average",
      seasonal_naive: "Seasonal naive",
      naive: "Naive",
      sarima: "SARIMA",
      prophet: "Prophet",
    } as Record<string, string>,
    notas: {
      cqr_lgbm_quantile: "the served model",
      ridge: "regularized linear regression",
      lasso: "regularized linear regression",
      croston_sba: "for intermittent demand",
      moving_average: "the current policy",
      seasonal_naive: "MASE reference",
    } as Record<string, string>,
    prefijoLgbm: "Global LightGBM · ",
    menosError: (pct: string) => `${pct} less error`,
    masError: (pct: string) => `${pct} more error`,
    bandaGana: (banda: string) => `In ${banda} turnover the model beats the seasonal naive.`,
    bandaEmpata: (banda: string) => `In ${banda} turnover the model ties with the seasonal naive.`,
    bandaPierde: (banda: string) => `In ${banda} turnover the seasonal naive beats the model.`,
  },

  senal: {
    detalleEstimada: (pct: string) => `${pct} of demand in the last 28 days is estimated`,
    detalleRacha: (n: number) => `${n} ${n === 1 ? "day" : "days"} of stockout up to today`,
    detalleSinVenta: (n: number) => `${n} without a recorded sale`,
    escasa: "barely observed",
    parcial: "partial",
    observada: "observed",
    enQuiebre: (d: number) => `out of stock ${d} d`,
  },

  features: {
    exactas: {
      discount: "Discount factor",
      holiday_flag: "Holiday",
      activity_flag: "Promotion",
      product_id: "Product",
      store_id: "Store",
      city_id: "City",
      management_group_id: "Management group",
      first_category_id: "Main category",
      second_category_id: "Subcategory",
      third_category_id: "Detailed category",
      horizon_step: "Horizon day",
      h: "Horizon day",
      dow: "Day of week",
      dow_sin: "Day of week · sine cycle",
      dow_cos: "Day of week · cosine cycle",
      day_of_month: "Day of month",
      dom_sin: "Day of month · sine cycle",
      dom_cos: "Day of month · cosine cycle",
      week_of_year: "Week of year",
      month: "Month",
      is_weekend: "Weekend",
      is_month_start: "Start of month",
      is_month_end: "End of month",
      days_since_start: "Series age",
      days_since_sale: "Days since last sale",
      zero_share_28: "Days without sales · 28 days",
      censored_share_7: "Stockout days · 7 days",
      censored_share_28: "Stockout days · 28 days",
      oos_hours_roll_7: "Stockout hours · 7 days",
      latent_momentum_7_28: "Trend · 7 vs 28 days",
      latent_dow_mean_4: "Same-weekday mean · 4 weeks",
      latent_dow_std_4: "Same-weekday variability · 4 weeks",
    } as Record<string, string>,
    clima: {
      precpt: "Rain",
      avg_temperature: "Temperature",
      avg_humidity: "Humidity",
      avg_wind_level: "Wind",
      discount: "Discount",
    } as Record<string, string>,
    elDiaDelOrigen: "on the origin day",
    haceDias: (n: string) => `${n} days ago`,
    operaciones: {
      mean: "Mean demand",
      median: "Median demand",
      std: "Demand variability",
      min: "Minimum demand",
      max: "Maximum demand",
    } as Record<string, string>,
    ventana: (op: string, dias: string) => `${op} · ${dias} days`,
    demandaDelOrigen: "Demand on the origin day",
    demandaHace: (n: string) => `Demand ${n} days ago`,
  },

  graficoSerie: {
    aria: (serie: string, base: string, dias: string, quiebre: string, racha: string) =>
      `Series ${serie}: ${base} over ${dias} days, ${quiebre} with stockouts, longest run ${racha} days.`,
    franjaAria: (franjas: string) => `Stockout hours per day, from 0 to ${franjas} trading slots`,
    franja: "STOCKOUT HOURS PER DAY",
    pronostico: "Forecast",
    banda: "90% conformal band",
    diaConQuiebre: "Day with stockout",
    serieLimpia: "Clean series",
  },

  panel: {
    titulo: "Dashboard",
    contexto: (series: string, tiendas: string, productos: string, desde: string, hasta: string) =>
      `${series} series · ${tiendas} stores · ${productos} products · ${desde} → ${hasta}`,
    sinPanel: "no panel loaded",
    desfase: (d: string) => ` · the model has not seen the last ${d} days of data`,
    kpiAtencion: "Series needing attention",
    kpiAtencionPie: (pct: string, total: string) => `${pct} of ${total}; the rest need nothing special`,
    kpiError: "Model error · MASE",
    kpiErrorPie: (desvio: string, mejora: string | null) =>
      `± ${desvio} across origins${mejora ? ` · ${mejora} than the seasonal naive` : ""}`,
    sinBacktest: "no backtest: make models",
    kpiCobertura: "Actual interval coverage",
    kpiCoberturaPie: (nominal: string) => `promised ${nominal}; measured in the backtest`,
    sinMedir: "not measured",
    kpiEscondida: "Demand hidden by stockouts",
    kpiEscondidaPie: (pct: string) => `${pct} of series-days had a stockout`,
    calculando: "calculating…",
    paraHoy: "For today",
    paraHoyNota: (fecha: string) => `What is losing sales or stock while you read this. Data as of ${fecha}.`,
    noCalculado: (motivo: string) => `Could not be calculated: ${motivo}.`,
    paraRevisar: "To review",
    paraRevisarNota:
      "Analytical reasons: not urgent, but they change how much to trust the suggested quantity for those series.",
    demanda: "Panel demand",
    demandaNota: "Sum of all series, day by day. The gap between the two lines is the demand that stockouts hid.",
    modelos: "Models",
    verModelos: "See models",
    datosYModelo: "Data and model",
    verPipeline: "See pipeline",
    ningunaHoy: "No series today.",
    queHacer: "What to do.",
    verLas: (n: string) => `See all ${n} →`,
    motivo: "Reason",
    series: "Series",
    delCatalogo: "Of catalog",
    delVolumen: "Of volume",
    queHacerColumna: "What to do",
    abrir: "Open",
    ver: "See →",
    verSeriesDe: (m: string) => `See the series for ${m}`,
    sinMotivos: "No analytical reasons available.",
    seriesEnQuiebre: "Series out of stock that day",
    franjaEscala: "Series out of stock that day (0–100% scale)",
    demandaAria:
      "Total daily demand: observed sales against recovered demand, with the share of series out of stock below",
    columnasDemanda: ["Day", "Observed", "Recovered", "Out of stock"],
    rankingAria: "Less error than the seasonal naive, by model",
    rankingNota: (objetivo: string) =>
      `Less error than the seasonal naive; the project target is ${objetivo}. CQR and the residual conformal share one row because they share the forecast.`,
    sinBacktestTexto: "No saved backtest. Run make models.",
    sinFrescura: "The API does not report freshness.",
    datosHasta: "Data through",
    modeloHasta: "Model trained through",
    estado: "Status",
    ultimaIngesta: "Last ingestion",
  },

  alertas: {
    titulo: "Alerts",
    contexto: (n: string, total: string, fecha: string) =>
      `${n} of ${total} series need attention for at least one reason · data as of ${fecha}`,
    enFiltro: (n: string) => `${n} series with alerts in this filter`,
    filtrarAria: "Filter by reason",
    todas: "All",
    noCalculado: (motivo: string, razon: string) => `${motivo} was not calculated: ${razon}.`,
    caption: (motivo: string | null) =>
      `Series with alerts${motivo ? ` for ${motivo}` : ""}, those with more reasons first, then by volume`,
    columnas: {
      serie: "Series",
      clase: "Class",
      motivos: "Reasons",
      demanda: "Mean demand",
      estimada: "Estimated",
      estimadaTitulo: "Share of 28-day demand that is estimated",
      racha: "Run",
      rachaTitulo: "Stockout days in a row up to today",
      mase: "MASE",
      maseTitulo: "Series MASE in the backtest",
      sinVender: "Unsold under policy",
      sinVenderTitulo:
        "Expected 7-day surplus under the current policy, as a share of expected demand. Above 100% the policy orders more than twice what sells.",
      seEvita: "Avoided",
      seEvitaTitulo: "How much of that surplus goes away by ordering the suggested quantity",
    },
    vacio: "No series with this reason in the chosen filter.",
    queSignifica: "What it means",
    queHacer: "What to do",
    umbral: "Threshold",
    peso: (cat: string, vol: string, solo: string) =>
      `${cat} of catalog · ${vol} of volume · ${solo} only for this reason`,
    todasTexto: (limpio: string) =>
      `A series enters the list by reason, not by score. The reasons measure different things — the model failing, the series selling a lot, its recent demand being estimated, being out of stock, the policy over-ordering it — and each has its own remedy. That ${limpio} of the catalog has none is the intended outcome: an alert that flags everything prioritizes nothing.`,
    verTodos: "See all reasons",
  },

  reposicion: {
    titulo: "Replenishment",
    contexto: (fecha: string, series: string, orden: string) =>
      `Order for ${fecha} · ${series} series · sorted by ${orden}`,
    orden: {
      impacto: "expected saving",
      sugerido: "suggested quantity",
      politica: "current policy",
      delta: "change vs. policy",
      serie: "series",
    } as Record<string, string>,
    ordenarPor: (c: string) => `Sort by ${c}`,
    avisoObservada:
      "Basis: observed sales, which is what the ERP sees. It underestimates demand on stockout days, so these quantities reproduce next week's stockout.",
    kpiAhorro: "Expected saving",
    kpiAhorroPie: "less expected cost than the current policy",
    kpiOrden: "Order vs. policy",
    kpiOrdenPie: (n: string) => `${n} series change by more than 20%`,
    kpiSobrante: "Expected surplus",
    kpiSobrantePie: "vs. policy: this is waste at expiry",
    kpiFaltante: "Expected shortfall",
    kpiFaltantePie: "vs. policy: this is lost sales",
    anuncio: (base: string, delta: string) => `${base}. The total order is ${delta} vs. the policy`,
    vacio: "No series match the chosen store and turnover class.",
    caption: (fecha: string, orden: string) => `Quantity to order per series for ${fecha}, sorted by ${orden}`,
    columnas: {
      serie: "Series",
      clase: "Class",
      motivos: "Reasons",
      politica: "Policy",
      sugerido: "Suggested",
      delta: "Δ",
      ahorro: "Saving",
      quiebre: (d: string) => `Stockout ${d} d`,
      quiebreTitulo: (d: string) => `Stockout hours over the last ${d} days`,
    },
    diasConQuiebre: (n: string, d: string) => `${n} of ${d} days with stockout`,
    comoCuantil: (q: string, fecha: string, co: string, cu: string) =>
      `The suggested quantity is the critical quantile q* ${q} of demand on ${fecha}: with a surplus that costs ${co} and a shortfall that costs ${cu}, it is the quantity that minimizes expected cost. The prediction at that quantile is the order.`,
    comoPolitica: (ventana: string, modelo: string, cola: string) =>
      `The current policy is the ${ventana}-day moving average on the same basis. Saving, surplus and shortfall compare both quantities under the same predictive distribution of the model (${modelo}): they are expectations, not measured outcomes. The shortfall is a lower bound: the ${cola} of mass above the 0.95 quantile is not described.`,
    comoAhorro:
      "The Saving column is each series' share of the total saving of the filtered catalog. Magnitudes are dimensionless: sale_amount is multiplied by an undisclosed coefficient.",
  },

  serie: {
    rotacion: (b: string) => `${b} turnover`,
    dias: (n: string) => `${n} days`,
    enAlerta: "Alerting",
    cantidad: "Suggested quantity",
    politica: "Current policy",
    cambio: "Change vs. policy",
    ahorro: "Expected saving",
    faltante: "Expected shortfall",
    sobrante: "Expected surplus",
    proximos: "Next 7 days",
    columnas: ["Day", "Forecast", "90% interval", "Policy", "Suggested"],
    proximosNota: (q: string) =>
      `The forecast is the median; the suggested quantity is the q* ${q} quantile, which is why it sits above it when surplus costs less than shortfall.`,
    porQue: "Why this number",
    sinExplicacion: "The loaded model does not produce per-feature contributions.",
    cascadaAria: "Contribution of each variable to the suggested quantity",
    variableTecnica: (f: string) => `Technical variable: ${f}`,
    valorBase: "Base value",
    estasVariables: (n: string) => `These ${n} variables`,
    resto: "The rest",
    censura: "Censoring in this series",
    recuperada: "Recovered demand",
    diasQuiebre: "Stockout days",
    deTotal: (a: string, b: string) => `${a} of ${b}`,
    horasQuiebre: "Stockout hours per day",
    rachaMaxima: "Longest run",
    estimada28: "Estimated demand · 28 d",
    comoCantidad: (q: string, ventana: string) =>
      `The suggested quantity is the prediction at the critical quantile q* ${q}: with the chosen cost ratio it is the quantity that minimizes expected cost. The current policy is the ${ventana}-day moving average on the same basis, and both are evaluated under the same predictive distribution of the model.`,
    comoShap: (modelo: string, cuantil: string, base: string, puntual: string) =>
      `The contributions are TreeSHAP values from ${modelo} on the ${cuantil} quantile. They are additive: the base value (${base}) plus every contribution gives the explained figure. “The rest” is the sum of those that do not make the list. The point forecast for the same day is ${puntual}.`,
    critico: "critical",
    comoLimpios: (dif: string) =>
      `On days without stockouts recovered demand is identical to observed sales (in this series the difference is ${dif}), by design: those days are the ground truth used to measure the bias. Magnitudes are dimensionless: the dataset multiplies sales by an undisclosed coefficient.`,
  },

  modelosPantalla: {
    titulo: "Models",
    contexto: (origenes: string, horizonte: string) =>
      `${origenes} backtest origins · ${horizonte}-day horizon · error on recovered demand`,
    sinBacktest: "No saved backtest. It is generated with make models (about 45 minutes).",
    kpiError: "Served model error · MASE",
    kpiErrorPie: (desvio: string, nombre: string) => `± ${desvio} across origins · ${nombre}`,
    kpiPeor: "Worst origin",
    kpiPeorPie: (mejor: string) => `the month that goes wrong; best origin ${mejor}`,
    kpiNaive: "Vs. the seasonal naive",
    kpiNaivePie: (objetivo: string, cumplido: boolean) =>
      `less error · target ${objetivo}, ${cumplido ? "met" : "not met"}`,
    kpiCobertura: "Interval coverage",
    kpiCoberturaPie: (nominal: string, puntos: string | null, debajo: boolean) =>
      `promised ${nominal}${puntos ? `; ${puntos} points ${debajo ? "below" : "above"}` : ""}`,
    tabla: "Error by model",
    tablaNota: "Lower is better. Sorted by mean MASE.",
    columnas: {
      modelo: "Model",
      mase: "MASE",
      desvio: "Std. dev.",
      peor: "Worst origin",
      wape: "WAPE",
      naive: "Vs. naive",
      objetivo: (o: string) => `Target ${o}`,
    },
    variantes: (n: string) => `${n} variants with the same forecast`,
    referencia: "reference",
    notaNaive:
      "The seasonal naive scores above 1 and that is normal: the MASE denominator is its in-sample error and the numerator is out-of-sample. The 21-day moving average, which is the current policy, already beats the seasonal naive, so the model's improvement is not measured against a rival chosen to lose.",
    intervalo: "The interval",
    prometido: (n: string) => `promised ${n}`,
    sinIntervalo: "The last backtest has no models with intervals.",
    metodo: "Method",
    cobertura: "Coverage",
    ancho: "Mean width",
    servido: "served",
    conclusionIntervalo: (cqr: string, veces: string, residuos: string) =>
      `CQR covers ${cqr} with an interval ${veces} times narrower; the residual conformal covers ${residuos} because it is wide for every series. CQR is served: an interval that covers almost everything says nothing.`,
    coberturaH: "Coverage by horizon day",
    coberturaAria: (nominal: string) => `Empirical coverage by horizon day against ${nominal} promised`,
    dia: (h: string) => `day ${h}`,
    coberturaNota:
      "The dashed line is what was promised. The conformal guarantee is marginal, not per day: the days that fall below are the ones a conditional conformal would correct.",
    sinMedicion: "Not measured.",
    desglose: "Backtest breakdown",
    origen: "Error origin by origin",
    origenNota: "If a line breaks upward at some origin, that is the month that goes wrong.",
    origenAria:
      "MASE by backtest origin for the served model, the 21-day moving average and the seasonal naive",
    origenColumna: "Origin",
    origenDatos: "Show the values; the other models are in the table above",
    sinOrigen: "No data by origin.",
    horizonte: "By horizon day",
    banda: "By turnover class",
    sinDesglose: "No breakdown.",
    conclusionHorizonte: (d1: string, v1: string, dn: string, vn: string, dp: string, vp: string) =>
      `The served model's error goes from ${v1} on day ${d1} to ${vn} on day ${dn}, with the worst day at ${dp} (${vp}). It does not grow in a straight line because seasonality is weekly: day 7 falls on the same weekday as the origin.`,
    notaBandas: "Classes are defined with the first origin's training data, never with the full series.",
    comoBacktest: (origenes: string, horizonte: string) =>
      `Rolling-origin backtesting: ${origenes} origins, each trains on history up to its date and predicts the next ${horizonte} days. MASE divides the mean absolute error by the seasonal naive's in-sample error at each origin, so it is scale-free and comparable across series.`,
    comoAgrupado:
      "Models with exactly the same point metrics share one row: the conformal wrappers change the interval, not the forecast. The technical keys of each row are in the name tooltip.",
  },

  datos: {
    titulo: "Data",
    capaMuestra: "committed sample",
    capaTrabajo: "working subset",
    kpiSeries: "Series",
    kpiSeriesPie: (d: string) => `${d} days each`,
    kpiFilas: "Rows",
    kpiFilasPie: "one per series and day",
    kpiQuiebre: "Series-days with stockout",
    kpiQuiebrePie: (h: string) => `${h} hours of 16 when there is a stockout`,
    kpiRecuperada: "Recovered demand",
    kpiRecuperadaPie: "over observed sales, in total",
    enElTiempo: "Over time",
    enElTiempoNota:
      "On days without stockouts both lines are identical by design: they are the ground truth used to measure the bias.",
    escondida: "How much demand stockouts hide",
    escondidaNota: "The difference sits entirely on stockout days.",
    errorRecuperacion: "Could not load the recovery.",
    gruposCensura: {
      "todos los dias": "All days",
      "dias limpios": "Days without stockout",
      "dias censurados": "Days with stockout",
    } as Record<string, string>,
    columnasCensura: ["Days", "Series-days", "Mean observed sales", "Mean recovered demand", "Difference"],
    semana: "By day of week",
    semanaAria: "Mean demand per series by day of week, observed against recovered",
    columnasSemana: ["Day", "Observed", "Recovered", "With stockout"],
    porHora: "By hour of day",
    sinHoras: (nota: string) => `No hourly profile: ${nota}.`,
    horas: "Stockouts by hour",
    horasNota: "Dimmed: hours outside the 6–22 trading window.",
    horasSerieQuiebre: "Series-days out of stock at that hour",
    horasSerieVenta: "Share of the day's sales",
    horasAria: "Share of series-days out of stock at each hour of the day",
    horasTexto: (a: string, ha: string, c: string, hc: string, hp: string) =>
      `Stockouts build up through the day: ${a} of series-days at ${ha}:00 and ${c} at ${hc}:00. Sales peak at ${hp}:00, so an afternoon stockout hides less demand than a morning one, and the recovery weights it by that profile.`,
    columnasHoras: ["Hour", "Out of stock", "Of the day's sales", "Trading window"],
    porTienda: "By store",
    porCategoria: "By main category",
    prefijoTienda: "Store",
    prefijoCategoria: "Category",
    topDe: (n: string, total: string) => `the ${n} with most stockouts out of ${total}`,
    seriesN: (n: string) => `${n} series`,
    grupoAria: (titulo: string) => `${titulo}: share of series-days with stockout`,
    grupoDetalle: (uplift: string, vol: string) => `recovery uplift ${uplift} · ${vol} of volume`,
    notaTiendas: "Share of series-days with stockout. The stores on top are the ones hiding the most demand.",
    notaCategorias: "The dataset has no category names, only ids. Making them up would be more readable and false.",
    columnasGrupo: (prefijo: string) => [prefijo, "Series", "With stockout", "Uplift", "Of volume"],
    verFilas: (n: number) => (n === 1 ? "Show the row" : `Show all ${n} rows`),
    porRotacion: "By turnover",
    columnasRotacion: ["Class", "Series", "Of catalog", "Of volume", "With stockout"],
    rotacionNota: (cat: string, vol: string) =>
      `Low turnover is ${cat} of the catalog and weighs ${vol} of volume. The model's error in each class is under Models.`,
    histograma: "How much each series stocks out",
    histogramaAria: "Number of series by share of days with stockout",
    histogramaNota: (limpias: string, total: string) =>
      `Series by the share of their days with a stockout. ${limpias} of ${total} stock out on fewer than 10% of their days: censoring is not a rare case to discard, it is the panel's normal state.`,
    columnasHistograma: ["Days with stockout", "Series"],
    catalogo: "Catalog by behavior",
    verificaVentana: "The trading window.",
    verificaVentanaTexto: (franjas: string) =>
      `The dataset marks stockouts hour by hour and assumes the store sells from 6:00 to 22:00, that is ${franjas} slots.`,
    verificaCuenta: (dias: string, horas: string, franjas: string, resultado: string) =>
      `${dias} of days with stockout × ${horas} average hours ÷ ${franjas} = ${resultado} of trading hours out of stock, against the ≈20% declared by the dataset card.`,
    verificaCierre:
      "That the numbers add up is the check that the window is correct. The code also fails if the hours derived from the hourly mask do not match the dataset column.",
    verificaLimpios: "Days without stockout are left untouched.",
    verificaLimpiosTexto:
      "Recovered demand equals observed sales on those days by design: they are the ground truth used to measure the bias of the recovery.",
  },

  mapa: {
    error: "Could not load the product map.",
    aria: (n: string) => `Projection of ${n} products by demand behavior`,
    punto: (p: string, b: string) => `Product ${p} · ${b} turnover`,
    leyendaBanda: (b: string, n: string) => `${b} turnover · ${n}`,
    tamano: "size: mean demand",
    texto: (n: string, f: string, v: string) =>
      `${n} products projected with PCA on ${f} behavior variables. The two components capture ${v} of the variance: a point far from the center is a product whose combination of level, variability and stockouts is unlike the rest.`,
    producto: (p: string) => `Product ${p}`,
    rotacion: "Turnover",
    demanda: "Mean demand",
    quiebre: "Days with stockout",
    tiendas: "Stores selling it",
    verSerie: "See a series for this product →",
    elegir: "Pick a point to see the product.",
  },

  pipeline: {
    titulo: "Pipeline",
    contexto: "Read-only: the API has no authentication, so this screen does not trigger anything.",
    estado: "Status",
    capa: "Served layer",
    capaMuestra: "committed sample",
    capaTrabajo: "working subset",
    datosHasta: "Data through",
    modeloHasta: "Model trained through",
    frescura: "Freshness",
    recarga: "Automatic reload",
    cadaSegundos: (s: string) => `every ${s} s`,
    apagada: "off",
    ultimaCarga: "Last loaded",
    notaEstado:
      "The API watches the files' timestamps and reloads on its own. Ingestion writes with atomic replacement, so a half-written layer is never read.",
    archivos: "Files and artifacts",
    columnas: ["What", "Current", "Previous", "Candidate"],
    panelHorario: "Hourly panel",
    demanda: "Recovered demand",
    modelo: (base: string) => `Model · ${base}`,
    falta: "missing",
    cargado: "loaded",
    hasta: (f: string) => `through ${f}`,
    notaArtefactos:
      "A candidate replaces the current one only if it passes the smoke test. The previous one is kept for make rollback.",
    ingestas: "Recent ingestions",
    sinIngestas: "No batch has been ingested yet. The panel is the initial load.",
    columnasIngestas: ["When", "What", "Status", "New", "Duplicates", "Conflicts", "Detail"],
    comandos: "How to run it",
    pasos: {
      carga: {
        nombre: "Initial load",
        que: "Downloads FreshRetailNet-50K, subsamples by store and recovers censored demand.",
      },
      lote: {
        nombre: "Build a batch",
        que: "Exports a batch in the raw schema from the eval split, to test ingestion.",
      },
      ingesta: {
        nombre: "Ingest a batch",
        que: "Validates, upserts by (series, day), rejects conflicts, recovers censoring and writes the layers atomically. The API reloads on its own.",
      },
      reentreno: {
        nombre: "Ingest and retrain",
        que: "Also trains candidates, runs a smoke test on them and only then promotes them. The previous one is kept as .prev.",
      },
      rollback: {
        nombre: "Roll back",
        que: "Swaps the current artifact with the previous one. It can be undone.",
      },
    } as Record<string, { nombre: string; que: string }>,
  },
};

export type Textos = typeof en;
