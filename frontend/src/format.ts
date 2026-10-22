/**
 * Formato de cifras en el idioma activo.
 *
 * Inglés usa en-US (punto decimal, coma de miles, `%` pegado a la cifra) y
 * español usa es-PY (coma decimal, punto de miles, espacio antes del `%`). El
 * locale se lee en cada llamada y no se guarda en una constante: cambiar de
 * idioma remonta el árbol, y una constante de módulo quedaría en el anterior.
 *
 * `sale_amount` del dataset primario viene multiplicado por un coeficiente no
 * divulgado. No hay guaraníes y no hay kilos: **cualquier símbolo de moneda o
 * unidad en la interfaz es un error factual**, y los ejes tampoco los llevan.
 */

import { t } from "./i18n";

/** Menos tipográfico U+2212, no guion. */
const MENOS = "\u2212";

function numero(value: number, decimales: number): string {
  return new Intl.NumberFormat(t().locale, {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  }).format(value);
}

/** Magnitud adimensional: dos decimales, sin símbolo ni unidad. Nunca. */
export function magnitud(value: number, decimales = 2): string {
  return numero(value, decimales);
}

/** Métrica de error: tres decimales, y siempre acompañada de su dispersión. */
export function error(value: number): string {
  return magnitud(value, 3);
}

/** `0.743 ± 0.061`. La dispersión no es opcional: un promedio bueno esconde un
 * origen catastrófico, y el origen catastrófico es el que pasa en producción. */
export function errorConDispersion(mean: number, std: number): string {
  return `${error(mean)} ± ${error(std)}`;
}

/** Porcentaje: un decimal, signo explícito. El espacio antes del % depende del idioma. */
export function porcentaje(value: number, decimales = 1): string {
  const abs = numero(Math.abs(value), decimales);
  const pct = `${t().espacioPorcentaje}%`;
  if (value < 0) return `${MENOS}${abs}${pct}`;
  return `+${abs}${pct}`;
}

/** Porcentaje sin signo explícito, para cantidades que no son una variación. */
export function porcentajeSimple(value: number, decimales = 0): string {
  return `${numero(value, decimales)}${t().espacioPorcentaje}%`;
}

/** Conteo con separador de miles. Siempre se muestra contra su total. */
export function conteo(value: number): string {
  return new Intl.NumberFormat(t().locale).format(value);
}

/** `60 of 3,066`. Un conteo sin su referencia no dice nada. */
export function conteoDeTotal(value: number, total: number | null | undefined): string {
  return total == null ? conteo(value) : `${conteo(value)} ${t().de} ${conteo(total)}`;
}

/** Cuantil con tres decimales, como lo muestran los botones de ratio. */
export function cuantil(q: number): string {
  return magnitud(q, 3);
}

/** Etiqueta corta de eje: `Sep 15` o `15 sep`. En datos, la fecha va en ISO. */
export function etiquetaFecha(iso: string): string {
  const [, mes, dia] = iso.split("-");
  const textos = t();
  return textos.fechaCorta(Number(dia), textos.meses[Number(mes) - 1]);
}

/** Fecha y hora de un timestamp ISO, sin segundos: `2026-10-15 00:40`. */
export function fechaHora(iso: string | null | undefined): string {
  return iso ? iso.replace("T", " ").slice(0, 16) : "—";
}

/** Estado de una ingesta en palabras. La clave cruda (`sin_cambios`) no es texto de producto. */
export function estadoIngesta(clave: string | null | undefined): string {
  if (!clave) return "—";
  return t().ingesta.estados[clave] ?? clave.replaceAll("_", " ");
}

/**
 * Descripción de catálogo de una serie en el idioma activo.
 *
 * La API la sirve armada en español (`tienda 12 · producto 403 · grupo 1 · cat
 * 2/5/9 · ciudad 0`) porque también es el texto sobre el que busca. Acá se
 * desarma por sus partes y se vuelve a redactar; si el formato no es el
 * esperado, se muestra tal cual en vez de inventar.
 */
export function descripcionCatalogo(label: string | null | undefined): string {
  if (!label) return "";
  const parte = (patron: RegExp) => label.match(patron)?.[1];
  const tienda = parte(/\btienda (\d+)/);
  const producto = parte(/\bproducto (\d+)/);
  if (tienda == null || producto == null) return label;
  return t().descripcionSerie({
    tienda,
    producto,
    grupo: parte(/\bgrupo (\d+)/),
    categorias: parte(/\bcat ([\d/]+)/),
    ciudad: parte(/\bciudad (\d+)/),
  });
}

/** Nombre corto de una serie para la tabla: `S12 · P0412` o `T12 · P0412`. */
export function serieCorta(storeId: number, productId: number): string {
  const textos = t();
  return `${textos.codigoTienda}${String(storeId).padStart(2, "0")} · ${textos.codigoProducto}${String(productId).padStart(4, "0")}`;
}
