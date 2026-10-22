/**
 * Audit visual y de accesibilidad.
 *
 * Mide tres cosas que el código no puede afirmar por sí solo:
 *
 *  1. Cuánto del viewport usa la interfaz. El layout es una columna centrada de
 *     1180 px, así que la pregunta es cuánta página queda vacía en pantallas
 *     reales y si eso es lo que hace que no parezca una aplicación.
 *  2. Si el reflow declarado funciona: a 1024–1179 px se ocultan dos columnas y
 *     abajo de 1024 aparece el aviso de ancho mínimo.
 *  3. Si las afirmaciones de accesibilidad del handoff se cumplen — contraste
 *     4,5:1, foco visible, nombres accesibles — medidas con axe y no declaradas.
 */

import { mkdir, writeFile } from "node:fs/promises";
import { AxeBuilder } from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SHOTS = "audit/shots";

interface Pantalla {
  id: string;
  ruta: string;
  /** Texto que garantiza que la pantalla terminó de cargar. */
  ancla: RegExp;
}

/**
 * Las siete pantallas de `docs/rediseno_frontend.md`. Las dos primeras son las
 * de la demo y se miden en los cuatro anchos.
 *
 * Estas rutas llevan `lang=es`: la demo se da en español y las anclas están en
 * español. Cada test abre un contexto nuevo, así que el idioma guardado no pasa
 * de un test a otro. El inglés, que es el idioma por defecto, se mide aparte en
 * `PANTALLAS_EN`, porque los textos más largos o más cortos cambian el layout.
 */
const PANTALLAS: Pantalla[] = [
  { id: "reposicion", ruta: "?screen=reorder&basis=observed&lang=es", ancla: /Ahorro esperado/ },
  { id: "serie", ruta: "?screen=series&basis=recovered&lang=es", ancla: /Por qué este número/ },
  { id: "panel", ruta: "?screen=panel&basis=recovered&lang=es", ancla: /Para hoy/ },
  { id: "alertas", ruta: "?screen=alerts&basis=recovered&lang=es", ancla: /por al menos un motivo/ },
  { id: "modelos", ruta: "?screen=models&basis=recovered&lang=es", ancla: /Error origen por origen/ },
  { id: "datos", ruta: "?screen=data&basis=recovered&lang=es", ancla: /Catálogo por comportamiento/ },
  { id: "pipeline", ruta: "?screen=pipeline&basis=recovered&lang=es", ancla: /Cómo se corre/ },
];

/** Las mismas pantallas sin `lang`: lo que ve quien abre la app por primera vez. */
const PANTALLAS_EN: Pantalla[] = [
  { id: "reposicion", ruta: "?screen=reorder&basis=observed", ancla: /Expected saving/ },
  { id: "serie", ruta: "?screen=series&basis=recovered", ancla: /Why this number/ },
  { id: "panel", ruta: "?screen=panel&basis=recovered", ancla: /For today/ },
  { id: "alertas", ruta: "?screen=alerts&basis=recovered", ancla: /for at least one reason/ },
  { id: "modelos", ruta: "?screen=models&basis=recovered", ancla: /Error origin by origin/ },
  { id: "datos", ruta: "?screen=data&basis=recovered", ancla: /Catalog by behavior/ },
  { id: "pipeline", ruta: "?screen=pipeline&basis=recovered", ancla: /How to run it/ },
];

const ANCHOS = [1024, 1180, 1440, 1920];

interface Medida {
  pantalla: string;
  ancho: number;
  tema: string;
  anchoContenido: number;
  usoViewport: number;
  altoDocumento: number;
  desbordeHorizontal: boolean;
  avisoAnchoMinimo: boolean;
  violacionesAxe: { id: string; impacto: string; nodos: number }[];
  erroresConsola: string[];
}

const medidas: Medida[] = [];

async function preparar(page: Page, pantalla: Pantalla, tema: "light" | "dark") {
  const errores: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errores.push(m.text());
  });
  page.on("pageerror", (e) => errores.push(String(e)));

  await page.emulateMedia({ colorScheme: tema });
  await page.goto(`/${pantalla.ruta}`);
  await expect(page.getByText(pantalla.ancla).first()).toBeVisible({ timeout: 90_000 });
  // Los bloques que cargan aparte muestran un hueso gris. Se espera a que no
  // quede ninguno: capturar ahí mide un estado de carga, no la pantalla.
  await expect(page.locator(".hueso")).toHaveCount(0, { timeout: 90_000 });
  // Un tema elegido en Preferencias gana sobre el del sistema, así que se fuerza
  // el atributo para que la captura sea del tema pedido.
  await page.evaluate((t) => {
    document.documentElement.dataset.theme = t === "dark" ? "dark" : "light";
  }, tema);
  await page.waitForTimeout(400);
  return errores;
}

async function medir(page: Page, pantalla: string, ancho: number, tema: string, errores: string[]) {
  const geo = await page.evaluate(() => {
    const contenido = document.querySelector(".pagina, .tarjeta");
    const caja = contenido?.getBoundingClientRect();
    return {
      anchoContenido: caja ? Math.round(caja.width) : 0,
      viewport: window.innerWidth,
      altoDocumento: document.documentElement.scrollHeight,
      desborde: document.documentElement.scrollWidth > window.innerWidth + 1,
      aviso: Boolean(
        document.querySelector(".solo-angosto") &&
          getComputedStyle(document.querySelector(".solo-angosto")!).display !== "none",
      ),
    };
  });

  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  medidas.push({
    pantalla,
    ancho,
    tema,
    anchoContenido: geo.anchoContenido,
    usoViewport: Math.round((geo.anchoContenido / geo.viewport) * 100),
    altoDocumento: geo.altoDocumento,
    desbordeHorizontal: geo.desborde,
    avisoAnchoMinimo: geo.aviso,
    violacionesAxe: axe.violations.map((v) => ({
      id: v.id,
      impacto: v.impact ?? "n/d",
      nodos: v.nodes.length,
    })),
    erroresConsola: errores,
  });
}

test.beforeAll(async () => {
  await mkdir(SHOTS, { recursive: true });
});

test("captura y mide todas las pantallas a 1440 en claro", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  for (const pantalla of PANTALLAS) {
    const errores = await preparar(page, pantalla, "light");
    await page.screenshot({ path: `${SHOTS}/${pantalla.id}-1440-claro.png`, fullPage: true });
    await medir(page, pantalla.id, 1440, "claro", errores);
  }
});

test("las dos pantallas hero en los cuatro anchos", async ({ page }) => {
  for (const pantalla of PANTALLAS.slice(0, 2)) {
    for (const ancho of ANCHOS) {
      await page.setViewportSize({ width: ancho, height: 900 });
      const errores = await preparar(page, pantalla, "light");
      await page.screenshot({ path: `${SHOTS}/${pantalla.id}-${ancho}-claro.png`, fullPage: true });
      await medir(page, pantalla.id, ancho, "claro", errores);
    }
  }
});

test("las siete pantallas en inglés, el idioma por defecto, a 1440 en claro", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  for (const pantalla of PANTALLAS_EN) {
    const errores = await preparar(page, pantalla, "light");
    expect(await page.evaluate(() => document.documentElement.lang)).toBe("en");
    await page.screenshot({ path: `${SHOTS}/${pantalla.id}-1440-claro-en.png`, fullPage: true });
    await medir(page, `${pantalla.id} · en`, 1440, "claro", errores);
  }
});

test("el panel de preferencias abierto, en los dos temas", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  for (const tema of ["light", "dark"] as const) {
    const errores = await preparar(page, PANTALLAS_EN[2], tema);
    await page.getByRole("button", { name: "Settings" }).click();
    await expect(page.getByRole("region", { name: "Settings" })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/preferencias-1440-${tema === "dark" ? "oscuro" : "claro"}.png` });
    await medir(page, "preferencias", 1440, tema === "dark" ? "oscuro" : "claro", errores);
    // Escape cierra y devuelve el foco al botón que lo abrió.
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "Settings" })).toBeFocused();
  }
});

test("abajo de 1024 tiene que aparecer el aviso de ancho minimo", async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 900 });
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/?screen=reorder&basis=observed&lang=es");
  const aviso = page.getByText(/Hace falta más ancho/);
  await expect(aviso).toBeVisible({ timeout: 60_000 });
  await page.screenshot({ path: `${SHOTS}/aviso-900.png`, fullPage: true });
});

test("modo oscuro en las pantallas de la demo y en datos", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  for (const pantalla of [PANTALLAS[0], PANTALLAS[1], PANTALLAS[5]]) {
    const errores = await preparar(page, pantalla, "dark");
    await page.screenshot({ path: `${SHOTS}/${pantalla.id}-1440-oscuro.png`, fullPage: true });
    await medir(page, pantalla.id, 1440, "oscuro", errores);
  }
});

test("el selector y el foco visible", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/?screen=reorder&basis=observed&lang=es");
  await expect(page.getByText(/Ahorro esperado/)).toBeVisible({ timeout: 90_000 });

  const disparador = page.getByRole("button", { name: /Buscar serie/ }).first();
  await disparador.focus();
  await page.keyboard.press("Control+k");
  const dialogo = page.getByRole("dialog", { name: "Buscar serie" });
  await expect(dialogo).toBeVisible();
  const campo = page.getByRole("combobox", { name: "Buscar serie" });
  const primera = dialogo.getByRole("option").first();
  await expect(primera).toBeVisible({ timeout: 60_000 });
  await expect(campo).toHaveAttribute("aria-activedescendant", /serie-opcion-/);
  const activaAntes = await campo.getAttribute("aria-activedescendant");
  await page.keyboard.press("ArrowDown");
  await expect(campo).not.toHaveAttribute("aria-activedescendant", activaAntes ?? "");

  // Tab queda contenido entre el campo y Cerrar; Escape devuelve el foco al
  // disparador. Axe no detecta focus traps ni retorno de foco ausentes.
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Cerrar" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(campo).toBeFocused();
  await page.screenshot({ path: `${SHOTS}/selector-1440-claro.png` });
  await page.keyboard.press("Escape");
  await expect(disparador).toBeFocused();

  // El contorno de foco no se suprime nunca: se verifica que el navegador dibuje
  // algo al llegar por teclado, no que exista la regla CSS.
  await page.keyboard.press("Tab");
  const estilo = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el) return null;
    const s = getComputedStyle(el);
    return { etiqueta: el.tagName, outline: s.outlineWidth, estilo: s.outlineStyle };
  });
  await page.screenshot({ path: `${SHOTS}/foco-1440-claro.png` });
  await writeFile("audit/foco.json", JSON.stringify(estilo, null, 2), "utf-8");
});

test.afterAll(async () => {
  const lineas = [
    "# Audit visual · medidas",
    "",
    "| Pantalla | Ancho | Tema | Contenido | Uso del viewport | Alto doc | Desborde | Aviso | Violaciones axe | Errores consola |",
    "|---|---|---|---|---|---|---|---|---|---|",
    ...medidas.map(
      (m) =>
        `| ${m.pantalla} | ${m.ancho} | ${m.tema} | ${m.anchoContenido} px | ${m.usoViewport} % | ` +
        `${m.altoDocumento} px | ${m.desbordeHorizontal ? "SI" : "no"} | ` +
        `${m.avisoAnchoMinimo ? "SI" : "no"} | ` +
        `${m.violacionesAxe.map((v) => `${v.id}(${v.impacto}×${v.nodos})`).join(", ") || "ninguna"} | ` +
        `${m.erroresConsola.length} |`,
    ),
    "",
    "## Errores de consola",
    "",
    ...medidas
      .filter((m) => m.erroresConsola.length > 0)
      .map((m) => `- **${m.pantalla} ${m.ancho}/${m.tema}**: ${m.erroresConsola.join(" · ")}`),
  ];
  await writeFile("audit/medidas.md", lineas.join("\n"), "utf-8");
});
