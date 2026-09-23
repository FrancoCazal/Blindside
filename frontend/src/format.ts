/**
 * Formato de cifras. Locale es-PY: coma decimal, punto de miles.
 *
 * `sale_amount` del dataset primario viene multiplicado por un coeficiente no
 * divulgado. No hay guaraníes y no hay kilos: **cualquier símbolo de moneda o
 * unidad en la interfaz es un error factual**, y los ejes tampoco los llevan.
 */

const LOCALE = "es-PY";

/** Menos tipográfico U+2212, no guion. */
const MENOS = "\u2212";

/** Magnitud adimensional: dos decimales, sin símbolo ni unidad. Nunca. */
export function magnitud(value: number, decimales = 2): string {
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  }).format(value);
}

/** Métrica de error: tres decimales, y siempre acompañada de su dispersión. */
export function error(value: number): string {
  return magnitud(value, 3);
}

/** `0,743 ± 0,061`. La dispersión no es opcional: un promedio bueno esconde un
 * origen catastrófico, y el origen catastrófico es el que pasa en producción. */
export function errorConDispersion(mean: number, std: number): string {
  return `${error(mean)} ± ${error(std)}`;
}

/** Porcentaje: un decimal, espacio antes del signo de %, signo explícito. */
export function porcentaje(value: number, decimales = 1): string {
  const abs = new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  }).format(Math.abs(value));
  if (value < 0) return `${MENOS}${abs} %`;
  return `+${abs} %`;
}

/** Porcentaje sin signo explícito, para cantidades que no son una variación. */
export function porcentajeSimple(value: number, decimales = 0): string {
  return `${new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  }).format(value)} %`;
}

/** Conteo con separador de miles. Siempre se muestra contra su total. */
export function conteo(value: number): string {
  return new Intl.NumberFormat(LOCALE).format(value);
}

/** `60 de 3.066`. Un conteo sin su referencia no dice nada. */
export function conteoDeTotal(value: number, total: number | null | undefined): string {
  return total == null ? conteo(value) : `${conteo(value)} de ${conteo(total)}`;
}

/** Cuantil con tres decimales, como lo muestran los botones de ratio. */
export function cuantil(q: number): string {
  return magnitud(q, 3);
}

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/** Etiqueta corta de eje: `15 sep`. En datos, la fecha va en ISO. */
export function etiquetaFecha(iso: string): string {
  const [, mes, dia] = iso.split("-");
  return `${Number(dia)} ${MESES[Number(mes) - 1]}`;
}

/** Nombre corto de una serie para la tabla: `T12 · P0412`. */
export function serieCorta(storeId: number, productId: number): string {
  return `T${String(storeId).padStart(2, "0")} · P${String(productId).padStart(4, "0")}`;
}
