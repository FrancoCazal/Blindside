/**
 * Lógica de decisión del lado del cliente.
 *
 * Acá vive **todo** lo que la API no sirve todavía, en un solo archivo y con el
 * supuesto escrito al lado de cada cálculo. Que sea un solo lugar es a
 * propósito: cualquier número de la interfaz que no venga del backend sale de
 * este módulo, así que se puede auditar de una sola lectura y se puede borrar de
 * una sola vez cuando el endpoint exista.
 */

import type { ForecastPoint, HistoryPoint } from "./api/client";

/**
 * Presets del control de ratio de costo. `cu` queda en 1 y se mueve `co`, así
 * que el ratio del botón es Co/Cu y el cuantil resultante es q* = Cu/(Cu+Co).
 *
 * La relación entre ratio y cuantil no se explica en un tooltip: se muestra el
 * cuantil resultante en el propio botón.
 */
export const RATIOS = [
  { co: 0.3, lectura: "Producto seco: el sobrante es capital inmovilizado" },
  {
    co: 0.6,
    lectura: "Perecedero: el sobrante es pérdida total al vencimiento",
  },
  { co: 1.0, lectura: "Los dos errores cuestan igual: el óptimo es la mediana" },
  { co: 1.5, lectura: "El sobrante duele más que el quiebre" },
] as const;

export const RATIO_POR_DEFECTO = 0.6;

/** q* = Cu / (Cu + Co). El cuantil que hay que pronosticar. */
export function cuantilCritico(cu: number, co: number): number {
  return cu / (cu + co);
}

/**
 * Política actual: media móvil de los últimos `ventana` días de la base activa.
 *
 * Es la regla que el proyecto viene a reemplazar — en el retail de perecederos
 * la reposición se decide con el promedio de las últimas semanas — y es también
 * uno de los baselines del backtest, así que la comparación de la tabla es
 * contra algo medido y no contra un hombre de paja.
 */
export function politicaMediaMovil(
  points: HistoryPoint[],
  basis: "observed" | "recovered",
  ventana = 21,
): number {
  const serie = points.slice(-ventana).map((p) => (basis === "recovered" ? p.recovered : p.observed));
  if (serie.length === 0) return 0;
  return serie.reduce((a, b) => a + b, 0) / serie.length;
}

/** Días con quiebre de los últimos `n`, para la columna de la tabla. */
export function diasConQuiebre(points: HistoryPoint[], n = 14): number[] {
  return points.slice(-n).map((p) => p.oos_hours_open);
}

export interface ImpactoSimulado {
  /** Costo esperado de la cantidad sugerida, adimensional. */
  costoSugerido: number;
  /** Costo esperado de la política de media móvil. */
  costoPolitica: number;
  /** Cuánto se ahorra. Positivo = la sugerencia cuesta menos. */
  ahorro: number;
  /** Ahorro como fracción del costo de la política. */
  ahorroPct: number;
}

/**
 * Impacto esperado de usar la cantidad sugerida en vez de la política.
 *
 * **Este número es simulado y va rotulado `sim` en la interfaz.** `/reorder`
 * devuelve `expected_shortfall`, `expected_overage` y `cost_delta_pct` en cero a
 * propósito: sin verdad de terreno no hay faltante ni sobrante realizado, y el
 * backend prefiere no inventar una estimación. Acá se calcula una, y el supuesto
 * es explícito: se toma la **banda conformal como distribución uniforme** entre
 * `pred_lo` y `pred_hi`.
 *
 * El supuesto es grueso y está mal en la dirección conocida: la demanda de
 * perecederos tiene cola derecha larga (el p99 sobre la mediana llega a 12× en
 * este panel), así que una uniforme subestima el faltante de los días de pico.
 * Sirve para **ordenar** series por impacto, que es para lo que se usa, y no
 * para prometer un ahorro.
 */
export function impactoSimulado(
  punto: ForecastPoint,
  cantidadSugerida: number,
  cantidadPolitica: number,
  cu: number,
  co: number,
): ImpactoSimulado {
  const lo = punto.pred_lo ?? punto.y_pred;
  const hi = punto.pred_hi ?? punto.y_pred;
  const costo = (q: number) => {
    const faltante = esperanzaFaltante(q, lo, hi);
    const sobrante = esperanzaSobrante(q, lo, hi);
    return cu * faltante + co * sobrante;
  };
  const costoSugerido = costo(cantidadSugerida);
  const costoPolitica = costo(cantidadPolitica);
  const ahorro = costoPolitica - costoSugerido;
  return {
    costoSugerido,
    costoPolitica,
    ahorro,
    ahorroPct: costoPolitica > 0 ? ahorro / costoPolitica : 0,
  };
}

/** E[(D − q)+] con D uniforme en [lo, hi]. */
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
