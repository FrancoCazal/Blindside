/**
 * Setup de los tests de render.
 *
 * jsdom no implementa `matchMedia` y nunca lo hizo. El stub va acá y no en el
 * código de la app: en un navegador real la API existe siempre, y volver
 * defensivo el código de producción para tapar un hueco del entorno de test
 * esconde el hueco en vez de declararlo.
 */

// El setup corre para todos los archivos de test, y los de lógica pura usan
// entorno `node`, donde no hay `window` en absoluto.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = ((consulta: string) => ({
    matches: false,
    media: consulta,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
}
