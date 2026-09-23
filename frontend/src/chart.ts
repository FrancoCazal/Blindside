/**
 * Geometría del gráfico principal. Funciones puras, sin React y sin librería de
 * charts: el diseño especifica `viewBox` fijo, orden de capas y rellenos al
 * píxel, y una librería pelearía con las tres cosas.
 */

import type { HistoryPoint, StockoutRun } from "./api/client";

export const GRAFICO = {
  ancho: 1000,
  alto: 300,
  /** 46 a la izquierda: las etiquetas del eje Y terminan en 40. */
  padIzq: 46,
  padDer: 14,
  padArriba: 12,
  /** 22 abajo para las fechas. */
  padAbajo: 22,
  guias: 4,
} as const;

export const FRANJA = { ancho: 1000, alto: 60, padArriba: 6, padAbajo: 14 } as const;

/**
 * Máximo del eje Y: autoescalado de 0 al máximo × 1,06.
 *
 * No es opcional. En este panel el p99 sobre la mediana llega a 12×, así que con
 * eje fijo una serie con pico promocional queda pegada al piso y la pantalla que
 * tiene que convencer no muestra nada.
 */
export function maximoEje(valores: number[]): number {
  const max = valores.reduce((a, b) => (b > a ? b : a), 0);
  return max > 0 ? max * 1.06 : 1;
}

export function escalaX(total: number, geo = GRAFICO): (i: number) => number {
  const util = geo.ancho - geo.padIzq - geo.padDer;
  const paso = total > 1 ? util / (total - 1) : 0;
  return (i) => geo.padIzq + i * paso;
}

export function escalaY(max: number, geo = GRAFICO): (v: number) => number {
  const util = geo.alto - geo.padArriba - geo.padAbajo;
  return (v) => geo.alto - geo.padAbajo - (max > 0 ? (v / max) * util : 0);
}

/** Alturas de las guías horizontales, de arriba hacia abajo. */
export function guias(max: number, geo = GRAFICO): { y: number; valor: number }[] {
  const y = escalaY(max, geo);
  return Array.from({ length: geo.guias }, (_, k) => {
    const valor = (max * (k + 1)) / geo.guias;
    return { y: y(valor), valor };
  });
}

export interface TramoDibujable {
  x: number;
  ancho: number;
  /** Índices del primer y último día del tramo dentro de la serie. */
  desde: number;
  hasta: number;
  dias: number;
}

/**
 * Tramos de quiebre listos para dibujar.
 *
 * Las rachas de un solo día se dibujan con **ancho mínimo de 3 px sin borde**:
 * la mediana de racha en el panel real es de 2 días, así que sin mínimo la mitad
 * del fenómeno desaparece del gráfico.
 */
export function tramosDibujables(
  runs: StockoutRun[],
  fechas: string[],
  x: (i: number) => number,
  anchoMinimo = 3,
): TramoDibujable[] {
  const indice = new Map(fechas.map((f, i) => [f, i]));
  const tramos: TramoDibujable[] = [];
  for (const run of runs) {
    const desde = indice.get(run.start);
    const hasta = indice.get(run.end);
    if (desde == null || hasta == null) continue;
    const x0 = x(desde);
    const x1 = x(hasta);
    const ancho = Math.max(x1 - x0, anchoMinimo);
    tramos.push({ x: x0, ancho, desde, hasta, dias: run.n_days });
  }
  return tramos;
}

/**
 * Rangos donde se dibuja la línea recuperada: cada tramo de quiebre con un día
 * de entrada y uno de salida.
 *
 * Fuera de los tramos las dos series son idénticas, y dibujarlas superpuestas en
 * todo el rango produce un artefacto visual que sugiere una corrección que no
 * existe.
 */
export function rangosRecuperados(
  tramos: TramoDibujable[],
  largo: number,
): { desde: number; hasta: number }[] {
  return tramos.map((t) => ({
    desde: Math.max(0, t.desde - 1),
    hasta: Math.min(largo - 1, t.hasta + 1),
  }));
}

export function polilinea(puntos: { x: number; y: number }[]): string {
  if (puntos.length === 0) return "";
  return puntos.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(" ");
}

/** Cuña rellena entre la observada y la recuperada, para un rango de índices. */
export function cuna(
  observada: { x: number; y: number }[],
  recuperada: { x: number; y: number }[],
): string {
  if (observada.length === 0) return "";
  const ida = recuperada.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)} ${p.y.toFixed(2)}`);
  const vuelta = [...observada]
    .reverse()
    .map((p) => `L${p.x.toFixed(2)} ${p.y.toFixed(2)}`);
  return `${ida.join(" ")} ${vuelta.join(" ")} Z`;
}

/** Banda conformal: área entre `pred_lo` y `pred_hi`, que se ensancha con h. */
export function banda(
  lo: { x: number; y: number }[],
  hi: { x: number; y: number }[],
): string {
  if (lo.length === 0) return "";
  const arriba = hi.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)} ${p.y.toFixed(2)}`);
  const abajo = [...lo].reverse().map((p) => `L${p.x.toFixed(2)} ${p.y.toFixed(2)}`);
  return `${arriba.join(" ")} ${abajo.join(" ")} Z`;
}

/** Área de horas de quiebre, escalada de 0 a las franjas comerciales del día. */
export function areaHoras(
  points: HistoryPoint[],
  openHours: number,
  x: (i: number) => number,
  geo = FRANJA,
): string {
  if (points.length === 0) return "";
  const base = geo.alto - geo.padAbajo;
  const util = base - geo.padArriba;
  const y = (h: number) => base - (openHours > 0 ? (h / openHours) * util : 0);
  const cresta = points.map(
    (p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(2)} ${y(p.oos_hours_open).toFixed(2)}`,
  );
  const ultimo = x(points.length - 1).toFixed(2);
  return `${cresta.join(" ")} L${ultimo} ${base} L${x(0).toFixed(2)} ${base} Z`;
}

/** Etiquetas de fecha del eje X: primera, última y algunas intermedias. */
export function marcasFecha(fechas: string[], cuantas = 5): number[] {
  if (fechas.length <= cuantas) return fechas.map((_, i) => i);
  const paso = (fechas.length - 1) / (cuantas - 1);
  return Array.from({ length: cuantas }, (_, k) => Math.round(k * paso));
}
