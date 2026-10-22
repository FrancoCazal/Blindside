/**
 * Textos de la interfaz en español. Cumple el tipo `Textos` de `en.ts`: si falta
 * una clave o cambia la forma de una función, no compila.
 */

import type { Textos } from "./en";

export const es: Textos = {
  locale: "es-PY",
  espacioPorcentaje: " ",
  meses: ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
  fechaCorta: (dia, mes) => `${dia} ${mes}`,
  diasSemana: ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"],
  de: "de",
  codigoTienda: "T",
  codigoProducto: "P",
  tituloDocumento: "Blindside · reposición de perecederos",

  comun: {
    reintentar: "Reintentar",
    cargando: "cargando…",
    verLosDatos: "Ver los datos",
    comoSeCalcula: "Cómo se calcula",
    comoSeVerifica: "Cómo se verifica",
    sinDato: "sin dato",
    si: "sí",
    no: "no",
    noSePudoCargar: (que) => `${que}: no se pudo cargar.`,
    exportarCsv: "Exportar CSV",
    primeraPagina: "Primera página",
    paginaAnterior: "Página anterior",
    paginaSiguiente: "Página siguiente",
    paginacion: (desde, hasta, total, pagina, paginas) =>
      `${desde}–${hasta} de ${total} · página ${pagina} de ${paginas}`,
    rango: (desde, hasta, total) => `${desde}–${hasta} de ${total}`,
    ceroSeries: "0 series",
    dias: (n) => `${n} d`,
    ninguna: "ninguna todavía",
  },

  bases: { observed: "Venta observada", recovered: "Demanda recuperada" },
  bandas: { alta: "alta", media: "media", baja: "baja" },
  rotacionDe: (banda) => `rotación ${banda}`,

  nav: {
    aria: "Pantallas",
    grupos: { operacion: "Operación", analisis: "Análisis", sistema: "Sistema" },
    pantallas: {
      panel: "Panel",
      alerts: "Alertas",
      reorder: "Reposición",
      series: "Serie",
      models: "Modelos",
      data: "Datos",
      pipeline: "Pipeline",
    },
    iniciales: {
      panel: "P",
      alerts: "A",
      reorder: "R",
      series: "S",
      models: "M",
      data: "D",
      pipeline: "Pi",
    },
    colapsar: "« Colapsar",
    expandir: "»",
  },

  cromo: {
    buscar: "Buscar serie por tienda o producto",
    tecla: "Ctrl K",
    muestra: "Muestra",
    desfase: (dias) => `Modelo ${dias} d detrás de los datos`,
    desfaseTitulo: "Hay datos más nuevos que el modelo. Reentrenar con make update TRAIN=1 o make train.",
    angostoTitulo: "Hace falta más ancho",
    angostoTexto:
      "Esta interfaz está diseñada a 1180 px de contenido y soportada hasta 1024. Abajo de eso las cifras de decisión bajarían de 19 px y las tablas perderían columnas que sostienen la comparación.",
    muestraTitulo: "Estos números no son los del panel completo",
    muestraTexto: (series, tiendas, productos) =>
      `Los datos vienen de data/sample/: ${series} series, ${tiendas} tiendas, ${productos} productos. Las métricas de error y el uplift de recuperación se calculan sobre esa muestra y no son comparables con los del panel completo.`,
    muestraComando: "Cargar el panel:",
  },

  preferencias: {
    boton: "Preferencias",
    titulo: "Preferencias",
    idioma: "Idioma",
    tema: "Tema",
    temas: { sistema: "Sistema", claro: "Claro", oscuro: "Oscuro" },
    nota: "Se guardan en este navegador. No hace falta una cuenta.",
    cerrar: "Cerrar",
  },

  toggle: {
    aria: "Base de cálculo",
    anuncioCantidad: (base, antes, despues) =>
      `${base}. La cantidad sugerida pasa de ${antes} a ${despues}`,
  },

  ratio: {
    rotulo: "Costo del sobrante / del faltante",
    aria: "Ratio de costo",
    lecturas: {
      "0.3": "Producto seco: el sobrante es capital inmovilizado",
      "0.6": "Perecedero: el sobrante es pérdida total al vencimiento",
      "1": "Los dos errores cuestan igual: el óptimo es la mediana",
      "1.5": "El sobrante duele más que el quiebre",
    },
    personalizado: "Ratio de costo personalizado",
  },

  filtros: { tienda: "Tienda", rotacion: "Rotación", todas: "todas", limpiar: "Limpiar" },

  estados: {
    sinArtefactoTitulo: "Falta entrenar el modelo",
    sinArtefactoTexto:
      "La API está en pie y sirviendo datos, pero no hay artefacto que pueda emitir una cantidad a reponer. Las pantallas de evidencia — Datos y Modelos — funcionan igual, porque no dependen del modelo.",
    base: "Base de cálculo",
    artefacto: "Artefacto",
    estado: "Estado",
    cargado: "cargado",
    falta: "falta",
    sinArtefactoComando:
      "make train serializa los dos artefactos, uno por base de cálculo. Hacen falta los dos: con uno solo el toggle de censura cambia el gráfico y devuelve la misma cantidad en las dos posiciones.",
    volverAConsultar: "Volver a consultar",
    sinRespuesta: "No hay respuesta de la API",
    conError: "La API respondió con un error",
    sinRespuestaTexto: (base) =>
      `El dashboard no encuentra nada escuchando en ${base}. No es que no haya datos: es que no hay proceso. Si la API está corriendo, esto también pasa cuando el origen del navegador no está en el allowlist de CORS.`,
    conErrorTexto: "La API está en pie y rechazó la consulta. El detalle de abajo viene del backend.",
    ultimoIntento: "Último intento",
    proximoIntento: "Próximo reintento",
    enSegundos: (s) => `en ${s} s`,
    endpoint: "Endpoint",
    motivo: "Motivo",
    codigo: (c) => `Código ${c}`,
    reintentarAhora: "Reintentar ahora",
    oBien: "o bien",
    cargandoPanel: "Cargando datos del panel",
    apiViejaTitulo: "La API es anterior a esta interfaz",
    apiViejaTexto: (url) =>
      `${url} responde, pero le faltan campos que esta interfaz necesita, como la lista de tiendas o el estado por base de cálculo.`,
    apiViejaComando:
      "Si estás corriendo la API en Docker, la imagen tiene el código con el que se construyó: docker compose up -d --build api. En local, make api ya toma los cambios.",
  },

  selector: {
    aria: "Buscar serie",
    placeholder: "Tienda, producto o código de serie",
    resultados: "Resultados",
    sinResultados: (q) => `Sin resultados para «${q}».`,
    mover: "↑↓ mover",
    abrir: "↵ abrir",
    cerrarTecla: "esc cerrar",
    cerrar: "Cerrar",
  },

  descripcionSerie: (partes) =>
    [
      `tienda ${partes.tienda}`,
      `producto ${partes.producto}`,
      partes.grupo != null ? `grupo ${partes.grupo}` : null,
      partes.categorias ? `cat ${partes.categorias}` : null,
      partes.ciudad != null ? `ciudad ${partes.ciudad}` : null,
    ]
      .filter(Boolean)
      .join(" · "),

  motivos: {
    quebrado_ahora: {
      corto: "Quebrado ahora",
      significa: "Viene con quiebre en los últimos días, sin cortar.",
      hacer:
        "Es urgente hoy y no analítico: hay demanda que se está perdiendo mientras se lee esto. Reponer antes de revisar cualquier otra cosa.",
    },
    riesgo_merma: {
      corto: "Riesgo de merma",
      significa:
        "Con la política actual, la mitad o más de lo que se pide no se espera vender en el horizonte. En perecedero ese sobrante se pierde al vencer.",
      hacer:
        "Bajar a la cantidad sugerida, que ya descuenta el costo del sobrante. La columna de merma evitable dice cuánto de esa pérdida se va con el cambio.",
    },
    no_confiable: {
      corto: "Modelo no confiable",
      significa:
        "El modelo le pierde al naive estacional en esta serie. El MASE global no aplica acá.",
      hacer:
        "No usar la cantidad sugerida sin revisarla. La media móvil de 21 días es mejor referencia para estas series hasta entender por qué fallan.",
    },
    alto_volumen: {
      corto: "Alto volumen",
      significa:
        "Está en el decil de más demanda, así que un error cuesta en absoluto aunque el error relativo sea chico.",
      hacer: "Revisar primero por impacto, aunque el modelo acierte.",
    },
    senal_escasa: {
      corto: "Señal escasa",
      significa:
        "Buena parte de la demanda reciente es estimada y no observada, porque la serie estuvo mucho en quiebre.",
      hacer:
        "El pronóstico se apoya en la corrección de censura más que en venta real. Tratar el intervalo como más ancho de lo que dice.",
    },
  },
  cifraMotivo: {
    racha: (d) => `${d} d seguidos en quiebre`,
    merma: (pct) => `${pct} sin vender con la política`,
    mermaSinMedir: "merma sin medir",
    mase: (v) => `MASE ${v}`,
    maseSinMedir: "MASE sin medir",
    estimada: (pct) => `${pct} de la demanda es estimada`,
    volumen: (v) => `demanda media ${v}`,
  },
  umbral: {
    no_confiable: (v) => `MASE de la serie mayor a ${v}: peor que el naive estacional`,
    alto_volumen: () => "decil superior de demanda media de los últimos 28 días",
    senal_escasa: (pct) => `más del ${pct} de la demanda de 28 días es estimada`,
    quebrado_ahora: (d) => `${d} días o más de quiebre seguidos hasta hoy`,
    riesgo_merma: (pct, horizonte) =>
      `sobrante esperado de la política actual de ${pct} o más de la demanda esperada a ${horizonte} días, y la cantidad sugerida lo reduce`,
  },
  noCalculado: {
    no_confiable: "no hay backtest guardado: correr make models para medir el error por serie",
    riesgo_merma:
      "no hay un modelo con cuantiles cargado, y el sobrante esperado sale de la distribución predictiva. Entrenar con make train",
  },

  ingesta: {
    estados: {
      ok: "aplicado",
      sin_cambios: "sin cambios",
      rechazado: "rechazado",
      simulado: "en seco",
    },
    tipo: { ingest: "ingesta", promote: "promoción", rollback: "rollback" },
    resumen: (r) => {
      if (r.estado === "rechazado") return `${r.conflictos} filas contradicen datos ya cargados. No se escribió nada.`;
      if (r.estado === "sin_cambios") return `Las ${r.duplicadas} filas ya estaban cargadas con los mismos valores.`;
      if (r.estado === "simulado") return `Corrida en seco: se sumarían ${r.nuevas} filas nuevas. No se escribió nada.`;
      return `${r.nuevas} filas nuevas · ${r.duplicadas} duplicadas ignoradas.`;
    },
  },

  frescura: {
    al_dia: "al día: el modelo vio todos los datos",
    desfasado: (d) => `desfasado: le faltan ${d} días de datos`,
    sin_modelo: "sin modelo cargado",
    sin_datos: "sin datos cargados",
  },

  modelos: {
    nombres: {
      cqr_lgbm_quantile: "LightGBM global · CQR",
      conformal_lgbm_quantile_adaptive: "LightGBM global · conformal de residuos",
      lgbm_global: "LightGBM global · puntual",
      lgbm_quantile: "LightGBM global · cuantílico",
      xgb_global: "XGBoost global",
      ridge: "Ridge",
      lasso: "Lasso",
      croston_sba: "Croston SBA",
      moving_average: "Media móvil 21 días",
      seasonal_moving_average: "Media móvil estacional",
      seasonal_naive: "Naive estacional",
      naive: "Naive",
      sarima: "SARIMA",
      prophet: "Prophet",
    },
    notas: {
      cqr_lgbm_quantile: "el modelo servido",
      ridge: "regresión lineal regularizada",
      lasso: "regresión lineal regularizada",
      croston_sba: "para demanda intermitente",
      moving_average: "la política actual",
      seasonal_naive: "referencia del MASE",
    },
    prefijoLgbm: "LightGBM global · ",
    menosError: (pct) => `${pct} menos error`,
    masError: (pct) => `${pct} más error`,
    bandaGana: (banda) => `En rotación ${banda} el modelo le gana al naive estacional.`,
    bandaEmpata: (banda) => `En rotación ${banda} el modelo empata con el naive estacional.`,
    bandaPierde: (banda) => `En rotación ${banda} el naive estacional le gana al modelo.`,
  },

  senal: {
    detalleEstimada: (pct) => `${pct} de la demanda de los últimos 28 días es estimada`,
    detalleRacha: (n) => `${n} ${n === 1 ? "día" : "días"} de quiebre hasta hoy`,
    detalleSinVenta: (n) => `${n} sin venta registrada`,
    escasa: "casi sin observar",
    parcial: "parcial",
    observada: "observada",
    enQuiebre: (d) => `en quiebre ${d} d`,
  },

  features: {
    exactas: {
      discount: "Factor de descuento",
      holiday_flag: "Feriado",
      activity_flag: "Actividad comercial",
      product_id: "Producto",
      store_id: "Tienda",
      city_id: "Ciudad",
      management_group_id: "Grupo de gestión",
      first_category_id: "Categoría principal",
      second_category_id: "Subcategoría",
      third_category_id: "Categoría detallada",
      horizon_step: "Día del horizonte",
      h: "Día del horizonte",
      dow: "Día de la semana",
      dow_sin: "Día de semana · ciclo seno",
      dow_cos: "Día de semana · ciclo coseno",
      day_of_month: "Día del mes",
      dom_sin: "Día del mes · ciclo seno",
      dom_cos: "Día del mes · ciclo coseno",
      week_of_year: "Semana del año",
      month: "Mes",
      is_weekend: "Fin de semana",
      is_month_start: "Inicio de mes",
      is_month_end: "Fin de mes",
      days_since_start: "Antigüedad de la serie",
      days_since_sale: "Días desde la última venta",
      zero_share_28: "Días sin venta · 28 días",
      censored_share_7: "Días con quiebre · 7 días",
      censored_share_28: "Días con quiebre · 28 días",
      oos_hours_roll_7: "Horas de quiebre · 7 días",
      latent_momentum_7_28: "Tendencia · 7 contra 28 días",
      latent_dow_mean_4: "Media del mismo día · 4 semanas",
      latent_dow_std_4: "Variabilidad del mismo día · 4 semanas",
    },
    clima: {
      precpt: "Lluvia",
      avg_temperature: "Temperatura",
      avg_humidity: "Humedad",
      avg_wind_level: "Viento",
      discount: "Descuento",
    },
    elDiaDelOrigen: "el día del origen",
    haceDias: (n) => `hace ${n} días`,
    operaciones: {
      mean: "Media de demanda",
      median: "Mediana de demanda",
      std: "Variabilidad de demanda",
      min: "Mínimo de demanda",
      max: "Máximo de demanda",
    },
    ventana: (op, dias) => `${op} · ${dias} días`,
    demandaDelOrigen: "Demanda del día del origen",
    demandaHace: (n) => `Demanda hace ${n} días`,
  },

  graficoSerie: {
    aria: (serie, base, dias, quiebre, racha) =>
      `Serie ${serie}: ${base} de ${dias} días, ${quiebre} con quiebre de stock, racha máxima de ${racha} días.`,
    franjaAria: (franjas) => `Horas de quiebre por día, de 0 a ${franjas} franjas comerciales`,
    franja: "HORAS DE QUIEBRE POR DÍA",
    pronostico: "Pronóstico",
    banda: "Banda conformal 90 %",
    diaConQuiebre: "Día con quiebre",
    serieLimpia: "Serie limpia",
  },

  panel: {
    titulo: "Panel",
    contexto: (series, tiendas, productos, desde, hasta) =>
      `${series} series · ${tiendas} tiendas · ${productos} productos · ${desde} → ${hasta}`,
    sinPanel: "sin panel cargado",
    desfase: (d) => ` · el modelo no vio los últimos ${d} días de datos`,
    kpiAtencion: "Series que piden atención",
    kpiAtencionPie: (pct, total) => `${pct} de ${total}; el resto no necesita nada especial`,
    kpiError: "Error del modelo · MASE",
    kpiErrorPie: (desvio, mejora) =>
      `± ${desvio} entre orígenes${mejora ? ` · ${mejora} que el naive estacional` : ""}`,
    sinBacktest: "sin backtest: make models",
    kpiCobertura: "Cobertura real del intervalo",
    kpiCoberturaPie: (nominal) => `prometida ${nominal}; medida en el backtest`,
    sinMedir: "sin medir",
    kpiEscondida: "Demanda escondida por quiebres",
    kpiEscondidaPie: (pct) => `${pct} de los días-serie tuvo quiebre`,
    calculando: "calculando…",
    paraHoy: "Para hoy",
    paraHoyNota: (fecha) => `Lo que pierde venta o mercadería mientras se lee esto. Datos al ${fecha}.`,
    noCalculado: (motivo) => `No se pudo calcular: ${motivo}.`,
    paraRevisar: "Para revisar",
    paraRevisarNota:
      "Motivos analíticos: no son urgentes, pero cambian cuánto confiar en la cantidad sugerida de esas series.",
    demanda: "Demanda del panel",
    demandaNota:
      "Suma de todas las series, día por día. La brecha entre las dos líneas es la demanda que los quiebres escondieron.",
    modelos: "Modelos",
    verModelos: "Ver los modelos",
    datosYModelo: "Datos y modelo",
    verPipeline: "Ver el pipeline",
    ningunaHoy: "Ninguna serie hoy.",
    queHacer: "Qué hacer.",
    verLas: (n) => `Ver las ${n} →`,
    motivo: "Motivo",
    series: "Series",
    delCatalogo: "Del catálogo",
    delVolumen: "Del volumen",
    queHacerColumna: "Qué hacer",
    abrir: "Abrir",
    ver: "Ver →",
    verSeriesDe: (m) => `Ver las series de ${m}`,
    sinMotivos: "Sin motivos analíticos disponibles.",
    seriesEnQuiebre: "Series en quiebre ese día",
    franjaEscala: "Series en quiebre ese día (escala 0–100 %)",
    demandaAria:
      "Demanda total diaria: venta observada contra demanda recuperada, con la fracción de series en quiebre abajo",
    columnasDemanda: ["Día", "Observada", "Recuperada", "En quiebre"],
    rankingAria: "Menos error que el naive estacional, por modelo",
    rankingNota: (objetivo) =>
      `Menos error que el naive estacional; el objetivo del proyecto es ${objetivo}. CQR y el conformal de residuos van en una fila porque comparten el pronóstico.`,
    sinBacktestTexto: "Sin backtest guardado. Correr make models.",
    sinFrescura: "La API no informa frescura.",
    datosHasta: "Datos hasta",
    modeloHasta: "Modelo entrenado hasta",
    estado: "Estado",
    ultimaIngesta: "Última ingesta",
  },

  alertas: {
    titulo: "Alertas",
    contexto: (n, total, fecha) =>
      `${n} de ${total} series piden atención por al menos un motivo · datos al ${fecha}`,
    enFiltro: (n) => `${n} series con alerta en este filtro`,
    filtrarAria: "Filtrar por motivo",
    todas: "Todas",
    noCalculado: (motivo, razon) => `${motivo} no se calculó: ${razon}.`,
    caption: (motivo) =>
      `Series con alerta${motivo ? ` por ${motivo}` : ""}, primero las que tienen más motivos y después por volumen`,
    columnas: {
      serie: "Serie",
      clase: "Clase",
      motivos: "Motivos",
      demanda: "Demanda media",
      estimada: "Estimada",
      estimadaTitulo: "Fracción de la demanda de 28 días que es estimada",
      racha: "Racha",
      rachaTitulo: "Días de quiebre seguidos hasta hoy",
      mase: "MASE",
      maseTitulo: "MASE de la serie en el backtest",
      sinVender: "Sin vender con la política",
      sinVenderTitulo:
        "Sobrante esperado de la política actual a 7 días, como porcentaje de la demanda esperada. Arriba de 100 % la política pide más del doble de lo que se vende.",
      seEvita: "Se evita",
      seEvitaTitulo: "Cuánto de ese sobrante desaparece pidiendo la cantidad sugerida",
    },
    vacio: "Ninguna serie con este motivo en el filtro elegido.",
    queSignifica: "Qué significa",
    queHacer: "Qué hacer",
    umbral: "Umbral",
    peso: (cat, vol, solo) => `${cat} del catálogo · ${vol} del volumen · ${solo} solo por este motivo`,
    todasTexto: (limpio) =>
      `Una serie entra a la lista por motivo, no por puntaje. Los motivos miden cosas distintas — que el modelo falle, que la serie venda mucho, que su demanda reciente sea estimada, que esté quebrada, que la política la sobrepida — y cada uno tiene su remedio. Que ${limpio} del catálogo no tenga ninguno es el resultado buscado: una alerta que marca todo no prioriza nada.`,
    verTodos: "Ver todos los motivos",
  },

  reposicion: {
    titulo: "Reposición",
    contexto: (fecha, series, orden) => `Pedido para el ${fecha} · ${series} series · ordenadas por ${orden}`,
    orden: {
      impacto: "ahorro esperado",
      sugerido: "cantidad sugerida",
      politica: "política actual",
      delta: "cambio contra la política",
      serie: "serie",
    },
    ordenarPor: (c) => `Ordenar por ${c}`,
    avisoObservada:
      "Base: venta observada, que es lo que ve el ERP. Subestima la demanda de los días con quiebre, así que estas cantidades reproducen el quiebre de la semana que viene.",
    kpiAhorro: "Ahorro esperado",
    kpiAhorroPie: "menos costo esperado que la política actual",
    kpiOrden: "Orden contra la política",
    kpiOrdenPie: (n) => `${n} series cambian más del 20 %`,
    kpiSobrante: "Sobrante esperado",
    kpiSobrantePie: "contra la política: es la merma al vencer",
    kpiFaltante: "Faltante esperado",
    kpiFaltantePie: "contra la política: es la venta perdida",
    anuncio: (base, delta) => `${base}. La orden total queda ${delta} contra la política`,
    vacio: "Ninguna serie coincide con la tienda y la clase de rotación elegidas.",
    caption: (fecha, orden) => `Cantidad a pedir por serie para el ${fecha}, ordenada por ${orden}`,
    columnas: {
      serie: "Serie",
      clase: "Clase",
      motivos: "Motivos",
      politica: "Política",
      sugerido: "Sugerido",
      delta: "Δ",
      ahorro: "Ahorro",
      quiebre: (d) => `Quiebre ${d} d`,
      quiebreTitulo: (d) => `Horas de quiebre de los últimos ${d} días`,
    },
    diasConQuiebre: (n, d) => `${n} de ${d} días con quiebre`,
    comoCuantil: (q, fecha, co, cu) =>
      `La cantidad sugerida es el cuantil crítico q* ${q} de la demanda del ${fecha}: con un sobrante que cuesta ${co} y un faltante que cuesta ${cu}, es la cantidad que minimiza el costo esperado. La predicción en ese cuantil es la orden.`,
    comoPolitica: (ventana, modelo, cola) =>
      `La política actual es la media móvil de ${ventana} días de la misma base. El ahorro, el sobrante y el faltante comparan las dos cantidades bajo la misma distribución predictiva del modelo (${modelo}): son esperanzas, no resultados medidos. El faltante es una cota inferior: el ${cola} de masa por encima del cuantil 0,95 no está descrito.`,
    comoAhorro:
      "La columna Ahorro es la parte de cada serie en el ahorro total del catálogo filtrado. Las magnitudes son adimensionales: sale_amount viene multiplicado por un coeficiente no divulgado.",
  },

  serie: {
    rotacion: (b) => `rotación ${b}`,
    dias: (n) => `${n} días`,
    enAlerta: "En alerta",
    cantidad: "Cantidad sugerida",
    politica: "Política actual",
    cambio: "Cambio contra la política",
    ahorro: "Ahorro esperado",
    faltante: "Faltante esperado",
    sobrante: "Sobrante esperado",
    proximos: "Próximos 7 días",
    columnas: ["Día", "Pronóstico", "Intervalo 90 %", "Política", "Sugerido"],
    proximosNota: (q) =>
      `El pronóstico es la mediana; lo sugerido es el cuantil q* ${q}, y por eso queda por encima cuando el sobrante cuesta menos que el faltante.`,
    porQue: "Por qué este número",
    sinExplicacion: "El modelo cargado no produce contribuciones por feature.",
    cascadaAria: "Contribución de cada variable a la cantidad sugerida",
    variableTecnica: (f) => `Variable técnica: ${f}`,
    valorBase: "Valor base",
    estasVariables: (n) => `Estas ${n} variables`,
    resto: "El resto",
    censura: "Censura de esta serie",
    recuperada: "Demanda recuperada",
    diasQuiebre: "Días con quiebre",
    deTotal: (a, b) => `${a} de ${b}`,
    horasQuiebre: "Horas por día en quiebre",
    rachaMaxima: "Racha máxima",
    estimada28: "Demanda estimada · 28 d",
    comoCantidad: (q, ventana) =>
      `La cantidad sugerida es la predicción del cuantil crítico q* ${q}: con el ratio de costo elegido es la cantidad que minimiza el costo esperado. La política actual es la media móvil de ${ventana} días de la misma base, y las dos se evalúan bajo la misma distribución predictiva del modelo.`,
    comoShap: (modelo, cuantil, base, puntual) =>
      `Las contribuciones son TreeSHAP del modelo ${modelo} sobre el cuantil ${cuantil}. Son aditivas: el valor base (${base}) más todas las contribuciones da la cifra explicada. «El resto» es la suma de las que no entran en la lista. El pronóstico puntual del mismo día es ${puntual}.`,
    critico: "crítico",
    comoLimpios: (dif) =>
      `En los días sin quiebre la demanda recuperada es idéntica a la venta observada (en esta serie la diferencia es ${dif}), por diseño: esos días son la verdad con la que se mide el sesgo. Las magnitudes son adimensionales: el dataset multiplica la venta por un coeficiente no divulgado.`,
  },

  modelosPantalla: {
    titulo: "Modelos",
    contexto: (origenes, horizonte) =>
      `${origenes} orígenes de backtest · horizonte ${horizonte} días · error sobre la demanda recuperada`,
    sinBacktest: "No hay backtest guardado. Se genera con make models (unos 45 minutos).",
    kpiError: "Error del modelo servido · MASE",
    kpiErrorPie: (desvio, nombre) => `± ${desvio} entre orígenes · ${nombre}`,
    kpiPeor: "Peor origen",
    kpiPeorPie: (mejor) => `el mes que sale mal; mejor origen ${mejor}`,
    kpiNaive: "Contra el naive estacional",
    kpiNaivePie: (objetivo, cumplido) =>
      `menos error · objetivo ${objetivo}, ${cumplido ? "cumplido" : "no cumplido"}`,
    kpiCobertura: "Cobertura del intervalo",
    kpiCoberturaPie: (nominal, puntos, debajo) =>
      `prometida ${nominal}${puntos ? `; ${puntos} puntos ${debajo ? "por debajo" : "por encima"}` : ""}`,
    tabla: "Error de cada modelo",
    tablaNota: "Menor es mejor. Ordenados por MASE medio.",
    columnas: {
      modelo: "Modelo",
      mase: "MASE",
      desvio: "Desvío",
      peor: "Peor origen",
      wape: "WAPE",
      naive: "Contra el naive",
      objetivo: (o) => `Objetivo ${o}`,
    },
    variantes: (n) => `${n} variantes con el mismo pronóstico`,
    referencia: "referencia",
    notaNaive:
      "El naive estacional da más de 1 y es lo normal: el denominador del MASE es su error dentro de la muestra y el numerador es fuera de ella. La media móvil de 21 días, que es la política actual, ya le gana al naive estacional, así que la mejora del modelo no se mide contra un rival elegido para perder.",
    intervalo: "El intervalo",
    prometido: (n) => `prometido ${n}`,
    sinIntervalo: "El último backtest no trae modelos con intervalo.",
    metodo: "Método",
    cobertura: "Cobertura",
    ancho: "Ancho medio",
    servido: "servido",
    conclusionIntervalo: (cqr, veces, residuos) =>
      `CQR cubre ${cqr} con un intervalo ${veces} veces más angosto; el conformal de residuos cubre ${residuos} porque es ancho para todas las series. Se sirve CQR: un intervalo que cubre casi todo no informa.`,
    coberturaH: "Cobertura por día del horizonte",
    coberturaAria: (nominal) => `Cobertura empírica por día del horizonte contra ${nominal} prometido`,
    dia: (h) => `día ${h}`,
    coberturaNota:
      "La línea guionada es lo prometido. La garantía del conformal es marginal, no por día: los días que caen debajo son los que corregiría un conformal condicional.",
    sinMedicion: "Sin medición.",
    desglose: "Desglose del backtest",
    origen: "Error origen por origen",
    origenNota: "Si una línea se despega hacia arriba en algún origen, ahí está el mes que sale mal.",
    origenAria:
      "MASE por origen de backtest del modelo servido, la media móvil de 21 días y el naive estacional",
    origenColumna: "Origen",
    origenDatos: "Ver los valores y el resto de los modelos en la tabla de arriba",
    sinOrigen: "Sin datos por origen.",
    horizonte: "Por día del horizonte",
    banda: "Por clase de rotación",
    sinDesglose: "Sin desagregación.",
    conclusionHorizonte: (d1, v1, dn, vn, dp, vp) =>
      `El error del modelo servido va de ${v1} el día ${d1} a ${vn} el día ${dn}, con el peor día en ${dp} (${vp}). No crece en línea recta porque la estacionalidad es semanal: el día 7 cae el mismo día de la semana que el origen.`,
    notaBandas: "Las clases se definen con el train del primer origen, nunca con la serie completa.",
    comoBacktest: (origenes, horizonte) =>
      `Backtesting de origen móvil: ${origenes} orígenes, cada uno entrena con la historia hasta su fecha y predice los ${horizonte} días siguientes. El MASE divide el error absoluto medio por el del naive estacional dentro de la muestra de cada origen, así que es libre de escala y comparable entre series.`,
    comoAgrupado:
      "Los modelos con exactamente las mismas métricas puntuales van en una sola fila: los envoltorios conformales cambian el intervalo y no el pronóstico. Claves técnicas de cada fila en el tooltip del nombre.",
  },

  datos: {
    titulo: "Datos",
    capaMuestra: "muestra commiteada",
    capaTrabajo: "subconjunto de trabajo",
    kpiSeries: "Series",
    kpiSeriesPie: (d) => `${d} días cada una`,
    kpiFilas: "Filas",
    kpiFilasPie: "una por serie y día",
    kpiQuiebre: "Días-serie con quiebre",
    kpiQuiebrePie: (h) => `${h} horas de 16 cuando hay quiebre`,
    kpiRecuperada: "Demanda recuperada",
    kpiRecuperadaPie: "sobre la venta observada, en total",
    enElTiempo: "En el tiempo",
    enElTiempoNota:
      "En los días sin quiebre las dos líneas son idénticas por diseño: son la verdad con la que se mide el sesgo.",
    escondida: "Cuánta demanda esconden los quiebres",
    escondidaNota: "La diferencia se concentra entera en los días con quiebre.",
    errorRecuperacion: "No se pudo cargar la recuperación.",
    gruposCensura: {
      "todos los dias": "Todos los días",
      "dias limpios": "Días sin quiebre",
      "dias censurados": "Días con quiebre",
    },
    columnasCensura: ["Días", "Días-serie", "Venta observada media", "Demanda recuperada media", "Diferencia"],
    semana: "Por día de la semana",
    semanaAria: "Demanda media por serie y día de la semana, observada contra recuperada",
    columnasSemana: ["Día", "Observada", "Recuperada", "Con quiebre"],
    porHora: "Por hora del día",
    sinHoras: (nota) => `Sin perfil horario: ${nota}.`,
    horas: "Quiebres por hora",
    horasNota: "Apagadas, las horas fuera de la ventana comercial de 6 a 22.",
    horasSerieQuiebre: "Días-serie en quiebre a esa hora",
    horasSerieVenta: "Parte de la venta del día",
    horasAria: "Fracción de días-serie en quiebre en cada hora del día",
    horasTexto: (a, ha, c, hc, hp) =>
      `El quiebre se acumula a lo largo del día: ${a} de los días-serie a las ${ha}:00 y ${c} a las ${hc}:00. La venta tiene su pico a las ${hp}:00, así que un quiebre de tarde esconde menos demanda que uno de mañana, y la recuperación lo pondera por ese perfil.`,
    columnasHoras: ["Hora", "En quiebre", "De la venta del día", "Ventana comercial"],
    porTienda: "Por tienda",
    porCategoria: "Por categoría principal",
    prefijoTienda: "Tienda",
    prefijoCategoria: "Categoría",
    topDe: (n, total) => `las ${n} con más quiebre de ${total}`,
    seriesN: (n) => `${n} series`,
    grupoAria: (titulo) => `${titulo}: fracción de días-serie con quiebre`,
    grupoDetalle: (uplift, vol) => `uplift de recuperación ${uplift} · ${vol} del volumen`,
    notaTiendas: "Fracción de días-serie con quiebre. Las tiendas de arriba son las que más demanda esconden.",
    notaCategorias: "El dataset no trae nombres de categoría, solo ids. Inventarlos sería más legible y falso.",
    columnasGrupo: (prefijo) => [prefijo, "Series", "Con quiebre", "Uplift", "Del volumen"],
    verFilas: (n) => (n === 1 ? "Ver la fila" : `Ver las ${n} filas`),
    porRotacion: "Por rotación",
    columnasRotacion: ["Clase", "Series", "Del catálogo", "Del volumen", "Con quiebre"],
    rotacionNota: (cat, vol) =>
      `La rotación baja es el ${cat} del catálogo y pesa el ${vol} del volumen. El error del modelo en cada clase está en Modelos.`,
    histograma: "Cuánto quiebra cada serie",
    histogramaAria: "Cantidad de series según su fracción de días con quiebre",
    histogramaNota: (limpias, total) =>
      `Series según el porcentaje de sus días con quiebre. ${limpias} de ${total} quiebran en menos del 10 % de sus días: la censura no es un caso raro que se pueda descartar, es el estado normal del panel.`,
    columnasHistograma: ["Días con quiebre", "Series"],
    catalogo: "Catálogo por comportamiento",
    verificaVentana: "La ventana comercial.",
    verificaVentanaTexto: (franjas) =>
      `El dataset marca el quiebre hora por hora y se asume que la tienda vende de 6:00 a 22:00, o sea ${franjas} franjas.`,
    verificaCuenta: (dias, horas, franjas, resultado) =>
      `${dias} de días con quiebre × ${horas} horas promedio ÷ ${franjas} = ${resultado} de horas comerciales en quiebre, contra el ≈20 % que declara la ficha del dataset.`,
    verificaCierre:
      "Que la cuenta cierre es la verificación de que la ventana es la correcta. El código además falla si las horas derivadas de la máscara horaria no coinciden con la columna del dataset.",
    verificaLimpios: "Los días sin quiebre no se tocan.",
    verificaLimpiosTexto:
      "La demanda recuperada es idéntica a la venta observada en esos días por diseño: son la verdad de terreno con la que se mide el sesgo de la recuperación.",
  },

  mapa: {
    error: "No se pudo cargar el mapa de productos.",
    aria: (n) => `Proyección de ${n} productos por comportamiento de demanda`,
    punto: (p, b) => `Producto ${p} · rotación ${b}`,
    leyendaBanda: (b, n) => `rotación ${b} · ${n}`,
    tamano: "tamaño: demanda media",
    texto: (n, f, v) =>
      `${n} productos proyectados con PCA sobre ${f} variables de comportamiento. Las dos componentes capturan el ${v} de la varianza: un punto lejos del centro es un producto cuya combinación de nivel, variabilidad y quiebre no se parece a la del resto.`,
    producto: (p) => `Producto ${p}`,
    rotacion: "Rotación",
    demanda: "Demanda media",
    quiebre: "Días con quiebre",
    tiendas: "Tiendas que lo venden",
    verSerie: "Ver una serie de este producto →",
    elegir: "Elegí un punto para ver el producto.",
  },

  pipeline: {
    titulo: "Pipeline",
    contexto: "Solo lectura: la API no tiene autenticación, así que esta pantalla no dispara nada.",
    estado: "Estado",
    capa: "Capa servida",
    capaMuestra: "muestra commiteada",
    capaTrabajo: "subconjunto de trabajo",
    datosHasta: "Datos hasta",
    modeloHasta: "Modelo entrenado hasta",
    frescura: "Frescura",
    recarga: "Recarga automática",
    cadaSegundos: (s) => `cada ${s} s`,
    apagada: "apagada",
    ultimaCarga: "Cargado por última vez",
    notaEstado:
      "La API mira la fecha de los archivos y recarga sola. La ingesta escribe con reemplazo atómico, así que nunca se lee una capa a medio escribir.",
    archivos: "Archivos y artefactos",
    columnas: ["Qué", "Vigente", "Anterior", "Candidato"],
    panelHorario: "Panel horario",
    demanda: "Demanda recuperada",
    modelo: (base) => `Modelo · ${base}`,
    falta: "falta",
    cargado: "cargado",
    hasta: (f) => `hasta ${f}`,
    notaArtefactos:
      "Un candidato reemplaza al vigente solo si pasa la prueba de humo. El anterior queda para make rollback.",
    ingestas: "Últimas ingestas",
    sinIngestas: "Todavía no se ingirió ningún lote. El panel es el de la carga inicial.",
    columnasIngestas: ["Cuándo", "Qué", "Estado", "Nuevas", "Duplicadas", "Conflictos", "Detalle"],
    comandos: "Cómo se corre",
    pasos: {
      carga: {
        nombre: "Carga inicial",
        que: "Descarga FreshRetailNet-50K, submuestrea por tienda y recupera la censura.",
      },
      lote: {
        nombre: "Armar un lote",
        que: "Exporta un lote en el esquema crudo desde el split eval, para probar la ingesta.",
      },
      ingesta: {
        nombre: "Ingerir un lote",
        que: "Valida, hace upsert por (serie, día), rechaza conflictos, recupera la censura y escribe las capas de forma atómica. La API recarga sola.",
      },
      reentreno: {
        nombre: "Ingerir y reentrenar",
        que: "Además entrena candidatos, les corre una prueba de humo y recién ahí los promueve. El anterior queda como .prev.",
      },
      rollback: {
        nombre: "Volver atrás",
        que: "Intercambia el artefacto vigente con el anterior. Se puede deshacer.",
      },
    },
  },
};
