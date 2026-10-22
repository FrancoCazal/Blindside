/**
 * Lógica pura de las alertas: rótulos y la cifra que justifica cada motivo.
 *
 * Una alerta sin su número es una opinión. Cada motivo muestra la cifra que lo
 * disparó — los días de quiebre, la merma esperada, el MASE de la serie — para
 * que quien lee pueda discutir el umbral en vez de creerlo.
 *
 * Los textos de cada motivo — rótulo, qué significa, qué hacer, umbral — salen
 * del diccionario por la clave del motivo. La API los sirve también, en
 * español, y quedan como respaldo para un motivo que la interfaz no conozca.
 */

import type { AlertGroup, AlertItem } from "./api/client";
import { error as fmtError, magnitud, porcentajeSimple } from "./format";
import { t } from "./i18n";

/** Motivos que piden acción hoy. Coincide con `urgent` de la API. */
export const URGENTES = new Set(["quebrado_ahora", "riesgo_merma"]);

/** Rótulo corto para los sellos. Un motivo desconocido conserva su clave. */
export function rotuloMotivo(clave: string): string {
  return t().motivos[clave]?.corto ?? clave;
}

/** Rótulo, significado y acción de un grupo, en el idioma activo. */
export function textosMotivo(grupo: Pick<AlertGroup, "key" | "label" | "meaning" | "action">) {
  const propio = t().motivos[grupo.key];
  return {
    rotulo: propio?.corto ?? grupo.label,
    significa: propio?.significa ?? grupo.meaning,
    hacer: propio?.hacer ?? grupo.action,
  };
}

/** Horizonte del riesgo de merma, en días. Coincide con el de `/alerts`. */
const HORIZONTE_MERMA = 7;

/**
 * El umbral de un motivo en palabras, a partir de su valor numérico.
 *
 * La API devuelve `threshold_value` para que la interfaz lo redacte en su idioma;
 * si no está o el motivo es desconocido, se usa el texto que sirve la API.
 */
export function textoUmbral(grupo: Pick<AlertGroup, "key" | "threshold" | "threshold_value">): string {
  const redactar = t().umbral[grupo.key];
  const valor = grupo.threshold_value;
  if (!redactar) return grupo.threshold;
  switch (grupo.key) {
    case "alto_volumen":
      return redactar("", "");
    case "no_confiable":
      return valor != null ? redactar(magnitud(valor, 1), "") : grupo.threshold;
    case "quebrado_ahora":
      return valor != null ? redactar(String(Math.round(valor)), "") : grupo.threshold;
    case "senal_escasa":
    case "riesgo_merma":
      return valor != null
        ? redactar(porcentajeSimple(valor * 100), String(HORIZONTE_MERMA))
        : grupo.threshold;
    default:
      return grupo.threshold;
  }
}

/** Por qué un motivo no se calculó, en el idioma activo. */
export function textoNoCalculado(clave: string, respaldo: string): string {
  return t().noCalculado[clave] ?? respaldo;
}

/** La cifra que disparó el motivo, en palabras cortas. */
export function cifraDeMotivo(item: AlertItem, clave: string): string {
  const textos = t().cifraMotivo;
  switch (clave) {
    case "quebrado_ahora":
      return textos.racha(String(item.current_run_days));
    case "riesgo_merma":
      return item.waste_policy != null
        ? textos.merma(porcentajeSimple(item.waste_policy * 100))
        : textos.mermaSinMedir;
    case "no_confiable":
      return item.mase != null ? textos.mase(fmtError(item.mase)) : textos.maseSinMedir;
    case "senal_escasa":
      return textos.estimada(porcentajeSimple(item.estimated_share * 100));
    case "alto_volumen":
      return textos.volumen(magnitud(item.demand_mean));
    default:
      return "";
  }
}
