/**
 * Nombres legibles de modelo, agrupación por pronóstico puntual y mejora contra
 * el naive estacional.
 *
 * Es lógica pura y tiene test. Existe por dos errores de la versión anterior:
 * la interfaz mostraba `conformal_lgbm_quantile_adaptive` como nombre, y la misma
 * mejora salía como «−25,3 %» en el Panel y «+25,3 %» en la Comparativa. Acá hay
 * una sola convención, y es en palabras: «25,3 % menos error».
 */

import type { BacktestResponse } from "./api/client";
import { t } from "./i18n";

type Fila = BacktestResponse["rows"][number];

/** Modelo de referencia del MASE y del objetivo del proyecto. */
export const REFERENCIA = "seasonal_naive";

/** La política actual: media móvil de 21 días. */
export const POLITICA = "moving_average";

/** El modelo que sirve la API. */
export const SERVIDO = "cqr_lgbm_quantile";

/** Objetivo SMART del proyecto: al menos 20 % menos error que el naive estacional. */
export const OBJETIVO_MEJORA = 20;

/** Nombre para mostrar. Un modelo desconocido conserva su clave: mejor que inventar. */
export function nombreModelo(clave: string): string {
  return t().modelos.nombres[clave] ?? clave;
}

export function notaModelo(clave: string): string | undefined {
  return t().modelos.notas[clave];
}

/** Métricas puntuales: las que no dependen del intervalo. */
const PUNTUALES = ["mase", "wape", "mae"] as const;

export interface GrupoModelo {
  /** Clave del modelo que representa al grupo: el servido si está, si no el primero. */
  clave: string;
  nombre: string;
  /** Todas las claves con el mismo pronóstico puntual. */
  miembros: string[];
  mase: Fila;
  wape: Fila | null;
  /** Mejora del MASE contra el naive estacional, en porcentaje. Positivo es mejor. */
  mejora: number | null;
  cumpleObjetivo: boolean;
  esReferencia: boolean;
}

/**
 * Agrupa los modelos cuyo pronóstico puntual es el mismo.
 *
 * CQR y el conformal de residuos envuelven al mismo LightGBM cuantílico y dan
 * exactamente las mismas métricas puntuales: los envoltorios solo cambian el
 * intervalo. Mostrarlos como dos filas sugiere dos resultados cuando es uno. Se
 * agrupan por igualdad de las métricas puntuales y no por nombre: el LightGBM
 * puntual da un MASE casi igual (0,822) pero es otro modelo, entrenado con otra
 * pérdida, y queda en su fila.
 */
export function agruparModelos(rows: Fila[]): GrupoModelo[] {
  const porModelo = new Map<string, Map<string, Fila>>();
  for (const r of rows) {
    if (!porModelo.has(r.model_name)) porModelo.set(r.model_name, new Map());
    porModelo.get(r.model_name)!.set(r.metric, r);
  }
  const ref = porModelo.get(REFERENCIA)?.get("mase")?.mean ?? null;

  const firma = (m: Map<string, Fila>) =>
    PUNTUALES.map((k) => (m.get(k) ? m.get(k)!.mean.toFixed(6) : "-")).join("|");

  const grupos = new Map<string, string[]>();
  for (const [clave, metricas] of porModelo) {
    if (!metricas.has("mase")) continue;
    const f = firma(metricas);
    grupos.set(f, [...(grupos.get(f) ?? []), clave]);
  }

  const salida: GrupoModelo[] = [];
  for (const miembros of grupos.values()) {
    const ordenados = [...miembros].sort((a, b) =>
      a === SERVIDO ? -1 : b === SERVIDO ? 1 : a.localeCompare(b),
    );
    const clave = ordenados[0];
    const metricas = porModelo.get(clave)!;
    const mase = metricas.get("mase")!;
    const mejora = ref != null && clave !== REFERENCIA ? 100 * (1 - mase.mean / ref) : null;
    salida.push({
      clave,
      // El nombre es el del representante, no uno genérico: el LightGBM puntual
      // es otro modelo con un error casi igual, y llamar al grupo «LightGBM
      // global» a secas dejaba dos filas con el mismo nombre.
      nombre: nombreModelo(clave),
      miembros: ordenados,
      mase,
      wape: metricas.get("wape") ?? null,
      mejora,
      cumpleObjetivo: mejora != null && mejora >= OBJETIVO_MEJORA,
      esReferencia: clave === REFERENCIA,
    });
  }
  return salida.sort((a, b) => a.mase.mean - b.mase.mean);
}

/** El grupo que contiene al modelo servido, o el mejor si no está. */
export function grupoServido(grupos: GrupoModelo[]): GrupoModelo | null {
  return grupos.find((g) => g.miembros.includes(SERVIDO)) ?? grupos[0] ?? null;
}

/**
 * Mejora en palabras. Una sola convención para toda la interfaz: un número
 * positivo es menos error, y se dice así en vez de con un signo.
 */
export function textoMejora(mejora: number, formato: (v: number) => string): string {
  const textos = t().modelos;
  return mejora >= 0 ? textos.menosError(formato(mejora)) : textos.masError(formato(-mejora));
}

/**
 * Conclusión sobre una banda de rotación, derivada de los números.
 *
 * La versión anterior decía, con texto fijo, que el modelo no le ganaba al
 * ingenuo en baja rotación, y la tabla de al lado mostraba 0,822 contra 1,121.
 */
export function conclusionBanda(modelo: number, referencia: number, banda: string): string {
  const mejora = 100 * (1 - modelo / referencia);
  const textos = t();
  // La banda llega como valor de la API (`baja`) y se nombra en el idioma activo.
  const nombre = textos.bandas[banda] ?? banda;
  if (mejora >= 5) return textos.modelos.bandaGana(nombre);
  if (mejora > -5) return textos.modelos.bandaEmpata(nombre);
  return textos.modelos.bandaPierde(nombre);
}
