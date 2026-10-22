/**
 * Lógica de decisión del lado del cliente.
 *
 * Acá vive **todo** lo que la API no sirve todavía, en un solo archivo y con el
 * supuesto escrito al lado de cada cálculo. Que sea un solo lugar es a
 * propósito: cualquier número de la interfaz que no venga del backend sale de
 * este módulo, así que se puede auditar de una sola lectura y se puede borrar de
 * una sola vez cuando el endpoint exista.
 */

import type { HistoryPoint } from "./api/client";
import { porcentajeSimple } from "./format";
import { t } from "./i18n";

/**
 * Presets del control de ratio de costo. `cu` queda en 1 y se mueve `co`, así
 * que el ratio del botón es Co/Cu y el cuantil resultante es q* = Cu/(Cu+Co).
 *
 * La relación entre ratio y cuantil no se explica en un tooltip: se muestra el
 * cuantil resultante en el propio botón. La lectura de cada preset está en el
 * diccionario, con `String(co)` como clave.
 */
export const RATIOS = [{ co: 0.3 }, { co: 0.6 }, { co: 1.0 }, { co: 1.5 }] as const;

export const RATIO_POR_DEFECTO = 0.6;

/** Qué significa un ratio en palabras, o `null` si no es un preset. */
export function lecturaRatio(co: number): string | null {
  return RATIOS.some((r) => r.co === co) ? (t().ratio.lecturas[String(co)] ?? null) : null;
}

/** q* = Cu / (Cu + Co). El cuantil que hay que pronosticar. */
export function cuantilCritico(cu: number, co: number): number {
  return cu / (cu + co);
}

/**
 * La política actual ya no se calcula acá.
 *
 * Era la media móvil de los últimos 21 días de la base activa, y estaba bien
 * calculada, pero el backend la sirve en `policy_qty` sobre la **misma** base con
 * la que pronostica. Tenerla en los dos lados garantizaba que en algún momento no
 * coincidieran, y el número contra el que se lee toda la tabla no puede tener dos
 * versiones. `/reorder` también declara la ventana en `policy_window`.
 */

/** Días con quiebre de los últimos `n`, para la columna de la tabla. */
export function diasConQuiebre(points: HistoryPoint[], n = 14): number[] {
  return points.slice(-n).map((p) => p.oos_hours_open);
}

/**
 * El ahorro esperado por serie ya no se reconstruye acá: `/reorder/catalog`
 * devuelve `saving` (costo de la política menos el de la orden, bajo la misma
 * distribución predictiva) y lo ordena en el servidor sobre todo el catálogo.
 */

/**
 * E[(D − q)+] con D uniforme en [lo, hi].
 *
 * Quedan las dos esperanzas uniformes pero **ya no se usan para decidir nada**: el
 * faltante y el sobrante los calcula el backend integrando sobre la grilla de
 * cuantiles del modelo, que es una distribución estimada y no un supuesto de
 * forma. Están acá porque son la referencia con la que se testeó esa integral: el
 * caso uniforme tiene cierre analítico y es el único contra el que se puede
 * verificar sin simular.
 */
export function esperanzaFaltante(q: number, lo: number, hi: number): number {
  if (hi <= lo) return Math.max(0, lo - q);
  if (q <= lo) return (lo + hi) / 2 - q;
  if (q >= hi) return 0;
  return (hi - q) ** 2 / (2 * (hi - lo));
}

/** E[(q − D)+] con D uniforme en [lo, hi]. */
export function esperanzaSobrante(q: number, lo: number, hi: number): number {
  if (hi <= lo) return Math.max(0, q - lo);
  if (q >= hi) return q - (lo + hi) / 2;
  if (q <= lo) return 0;
  return (q - lo) ** 2 / (2 * (hi - lo));
}

/** Variación relativa entre la sugerencia y la política, en porcentaje. */
export function deltaPct(sugerido: number, politica: number): number {
  if (politica <= 0) return 0;
  return 100 * (sugerido / politica - 1);
}

/**
 * Umbrales del estado de señal, medidos sobre el panel y no elegidos a ojo.
 *
 * La cantidad que discrimina es qué **fracción de la demanda reciente es estimada
 * y no observada**: los lags y rolling que alimentan al modelo se calculan sobre
 * demanda latente, así que con una fracción alta el modelo aprende de su propia
 * corrección. Distribución medida sobre las 3.066 series: mediana 0,17, p90 0,28,
 * máximo 0,46.
 *
 * El corte en 0,30 aísla el 6,6 % del catálogo; el de 0,40, el 0,5 %.
 *
 * **Por qué no se cuentan días censurados.** Era el criterio anterior y estaba mal
 * calibrado: la mediana del panel es 12 días censurados de 28, así que el umbral de
 * 14 marcaba el 35,6 % del catálogo. Una alerta que dispara para un tercio de la
 * población no separa nada.
 */
export const SENAL = {
  /** Por encima de esto, buena parte del pronóstico se apoya en la corrección. */
  parcial: 0.3,
  /** Por encima de esto, la serie casi no tiene venta observada reciente. */
  escasa: 0.4,
  /** Días de quiebre consecutivos al último día que ya ameritan decirlo. */
  rachaVigente: 3,
} as const;

export type EstadoSenal = "observada" | "parcial" | "escasa";

export interface Senal {
  estado: EstadoSenal;
  /** Fracción de la demanda de los últimos 28 días que es estimada. */
  fraccionEstimada: number;
  /** Días de quiebre consecutivos que terminan en el último día. */
  rachaVigente: number;
  /** Texto corto para la celda. */
  rotulo: string;
  /** Explicación para el `title`, que es donde va el detalle. */
  detalle: string;
}

/**
 * Clasifica cuánto se puede confiar en la señal reciente de una serie.
 *
 * No es un juicio sobre el modelo sino sobre sus **insumos**: una serie cuya
 * demanda reciente es mayormente estimada recibe un pronóstico construido sobre la
 * propia corrección de censura. El intervalo conformal **no** refleja esa
 * incertidumbre extra — mide el error del modelo, no el de la recuperación —, así
 * que la interfaz tiene que decirlo por su cuenta.
 */
export function clasificarSenal(resumen: {
  estimated_share_last_28: number;
  current_run_days: number;
  days_since_last_sale?: number | null;
}): Senal {
  const frac = resumen.estimated_share_last_28;
  const racha = resumen.current_run_days;
  const sinVenta = resumen.days_since_last_sale;

  const estado: EstadoSenal =
    frac >= SENAL.escasa ? "escasa" : frac >= SENAL.parcial ? "parcial" : "observada";

  const textos = t().senal;
  const partes = [textos.detalleEstimada(porcentajeSimple(frac * 100))];
  if (racha > 0) partes.push(textos.detalleRacha(racha));
  if (sinVenta != null && sinVenta > 0) partes.push(textos.detalleSinVenta(sinVenta));

  const rotulo =
    estado === "escasa"
      ? textos.escasa
      : estado === "parcial"
        ? textos.parcial
        : racha >= SENAL.rachaVigente
          ? textos.enQuiebre(racha)
          : textos.observada;

  return {
    estado,
    fraccionEstimada: frac,
    rachaVigente: racha,
    rotulo,
    detalle: partes.join(" · "),
  };
}

/**
 * Nombre de negocio para una feature de SHAP.
 *
 * La API devuelve el nombre técnico porque es parte del contrato del modelo y
 * permite auditarlo. La interfaz muestra una traducción estable y conserva el
 * técnico en `title`/`aria-label`: «Por qué este número» no puede exigir saber
 * que `latent_roll_mean_7` significa una media de siete días.
 */
export function etiquetaFeature(feature: string): string {
  const textos = t().features;
  if (textos.exactas[feature]) return textos.exactas[feature];

  const rezagoClima = feature.match(/^(precpt|avg_temperature|avg_humidity|avg_wind_level|discount)_lag_(\d+)$/);
  if (rezagoClima) {
    const dias = Number(rezagoClima[2]);
    return `${textos.clima[rezagoClima[1]]} · ${dias === 0 ? textos.elDiaDelOrigen : textos.haceDias(String(dias))}`;
  }

  const movil = feature.match(/^(?:latent|observed|sale)_roll_(mean|median|std|min|max)_(\d+)$/);
  if (movil) return textos.ventana(textos.operaciones[movil[1]], movil[2]);

  const rezago = feature.match(/^(?:latent|observed|sale)_lag_(\d+)$/);
  if (rezago) {
    const dias = Number(rezago[1]);
    return dias === 0 ? textos.demandaDelOrigen : textos.demandaHace(String(dias));
  }

  const texto = feature.replaceAll("_", " ");
  return texto.charAt(0).toLocaleUpperCase(t().locale) + texto.slice(1);
}

/** Features cuyo valor es un id o una bandera: se muestran sin decimales. */
const CATEGORICAS = new Set([
  "city_id",
  "store_id",
  "management_group_id",
  "first_category_id",
  "second_category_id",
  "third_category_id",
  "product_id",
  "holiday_flag",
  "activity_flag",
  "dow",
  "day_of_month",
  "week_of_year",
  "month",
  "is_weekend",
  "is_month_start",
  "is_month_end",
  "h",
]);

/**
 * Valor de una feature para mostrar. Un id de producto no es una magnitud:
 * «Producto = 600,00» se leía como una cantidad.
 */
export function valorFeature(feature: string, valor: number | null | undefined): string {
  if (valor == null) return t().comun.sinDato;
  if (CATEGORICAS.has(feature)) return String(Math.round(valor));
  return new Intl.NumberFormat(t().locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(
    valor,
  );
}

/**
 * Arma un CSV a partir de filas ya calculadas.
 *
 * Existe acá y no en la pantalla porque es lógica pura y tiene test. El separador
 * es la coma y los campos de texto van entre comillas con las comillas internas
 * duplicadas, que es lo que pide RFC 4180: un `series_id` no las lleva hoy, pero
 * escribir un generador de CSV que se rompe con una coma es sembrar un bug.
 */
export function aCsv(encabezados: string[], filas: (string | number | null)[][]): string {
  const celda = (v: string | number | null): string => {
    if (v == null) return "";
    if (typeof v === "number") return Number.isFinite(v) ? String(v) : "";
    return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
  };
  return [encabezados.map(celda).join(","), ...filas.map((f) => f.map(celda).join(","))].join("\r\n");
}
