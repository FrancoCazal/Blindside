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
 * Ahorro esperado de una línea de `/reorder`, en unidades de costo.
 *
 * **Este número ya no es simulado.** El backend devuelve `expected_shortfall` y
 * `expected_overage` integrados sobre la distribución predictiva del modelo, y
 * `cost_delta_pct` comparando la orden contra la política de media móvil con las
 * dos cantidades evaluadas bajo **la misma** distribución. Acá solo se reconstruye
 * el ahorro absoluto a partir del costo de la orden y ese porcentaje, porque la
 * tabla ordena por magnitud y no por porcentaje: una serie que ahorra 30 % sobre
 * una base ínfima no es la que hay que mirar primero.
 *
 * Lo que había antes en este archivo era una estimación propia con la banda
 * conformal tomada como uniforme. Se fue: un supuesto de distribución en la capa
 * de presentación es invisible y no tiene test.
 */
export function impactoDeLinea(
  linea:
    | {
        expected_shortfall: number;
        expected_overage: number;
        cost_delta_pct: number;
      }
    | undefined,
  ratio: number,
): number {
  if (!linea) return 0;
  const costoOrden = linea.expected_shortfall + ratio * linea.expected_overage;
  const factor = 1 + linea.cost_delta_pct / 100;
  // costoOrden = costoPolitica * factor, así que el ahorro es la diferencia.
  if (factor <= 0) return 0;
  const costoPolitica = costoOrden / factor;
  return costoPolitica - costoOrden;
}

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
