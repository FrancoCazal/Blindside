/**
 * Idioma de la interfaz. Inglés por defecto, español como opción.
 *
 * El idioma activo vive en el módulo y no en un contexto de React porque lo leen
 * también funciones puras — el formato de cifras, los nombres de modelo, las
 * etiquetas de feature — que se llaman fuera de cualquier componente. El
 * proveedor de estado lo fija antes de renderizar y lo expone también en el
 * contexto: `App` lo consume, así que un cambio de idioma vuelve a pintar todo el
 * árbol sin remontarlo. Eso exige que ningún componente memorice texto
 * (`useMemo`, `React.memo`) sin poner el idioma en las dependencias.
 *
 * Los textos que sirve la API — umbrales, nombres de motivo, pasos del
 * pipeline — se traducen acá por clave: la API devuelve códigos y números, y la
 * interfaz los redacta. Quedan en español los mensajes de error del backend, que
 * son diagnósticos para quien opera el sistema.
 */

import { en, type Textos } from "./en";
import { es } from "./es";

export type Idioma = "en" | "es";
export type { Textos };

export const IDIOMAS: { id: Idioma; nombre: string }[] = [
  { id: "en", nombre: "English" },
  { id: "es", nombre: "Español" },
];

export const IDIOMA_POR_DEFECTO: Idioma = "en";

const DICCIONARIOS: Record<Idioma, Textos> = { en, es };

let actual: Idioma = IDIOMA_POR_DEFECTO;

export function idiomaActual(): Idioma {
  return actual;
}

export function fijarIdioma(idioma: Idioma): void {
  actual = idioma;
  // `lang` del documento: el lector de pantalla elige la voz por este atributo,
  // y una voz en inglés leyendo español es ininteligible.
  if (typeof document !== "undefined") {
    document.documentElement.lang = idioma;
    document.title = DICCIONARIOS[idioma].tituloDocumento;
  }
}

/** Los textos del idioma activo. Se llama en el render, no se guarda. */
export function t(): Textos {
  return DICCIONARIOS[actual];
}

export function esIdioma(valor: unknown): valor is Idioma {
  return valor === "en" || valor === "es";
}
