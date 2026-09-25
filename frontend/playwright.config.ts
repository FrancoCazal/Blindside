import { defineConfig } from "@playwright/test";

/**
 * Configuración del audit visual. No es la suite de tests — esa es vitest y corre
 * en segundos sin navegador. Esto sirve el build de producción y lo mira.
 *
 * `webServer` levanta y baja el preview por su cuenta, así que no queda ningún
 * proceso colgado si la corrida falla.
 *
 * Se sirve el **build** y no el dev server: es lo que va a ver el panel, y el dev
 * server inyecta su propio cliente de recarga que no está en producción.
 */
export default defineConfig({
  testDir: "audit",
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    // El Chrome ya instalado en el sistema. Sin descarga de navegadores.
    channel: "chrome",
    baseURL: "http://127.0.0.1:4173",
    // Capturas nítidas para poder juzgar tipografía de 10,5 px.
    deviceScaleFactor: 2,
  },
  webServer: {
    // `preview` no construye: si `dist/` existe, sirve lo que haya. Eso hizo que
    // el audit diera 12/12 contra un build viejo que todavía mostraba un sello
    // `sim` borrado del source. Construir acá vuelve la evidencia autocontenida.
    command: "npm run build && npm run preview",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
