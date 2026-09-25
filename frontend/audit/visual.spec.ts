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

const PANTALLAS: Pantalla[] = [
  { id: "4a-reposicion", ruta: "?screen=reorder&basis=observed", ancla: /Qué pedir hoy/ },
  { id: "2a-serie", ruta: "?screen=series&basis=recovered", ancla: /Cantidad sugerida/ },
  { id: "vista-general", ruta: "?screen=overview&basis=recovered", ancla: /ventana comercial/ },
  { id: "comparativa", ruta: "?screen=compare&basis=recovered", ancla: /origen por origen/ },
  { id: "explicabilidad", ruta: "?screen=explain&basis=recovered", ancla: /Por qué este número/ },
  { id: "4c-salud", ruta: "?screen=health&basis=recovered", ancla: /Artefactos cargados/ },
  { id: "4d-mapa", ruta: "?screen=map&basis=recovered", ancla: /Mapa de productos/ },
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
  // La pantalla puede terminar antes que el `/backtest` global. Si se captura ahí,
  // la franja dice "cargando" y el KPI dice "falta correr", aunque el reporte sí
  // exista. No es una variante visual: es una carrera del arnés.
  await expect(page.getByText(/MASE · cargando…/)).toHaveCount(0, { timeout: 90_000 });
  // El tema se guarda en localStorage y gana sobre la preferencia del sistema, así
  // que se fuerza el atributo para que la captura sea del tema pedido.
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

test("abajo de 1024 tiene que aparecer el aviso de ancho minimo", async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 900 });
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/?screen=reorder&basis=observed");
  const aviso = page.getByText(/Hace falta más ancho/);
  await expect(aviso).toBeVisible({ timeout: 60_000 });
  await page.screenshot({ path: `${SHOTS}/aviso-900.png`, fullPage: true });
});

test("modo oscuro en las pantallas hero y el mapa", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  for (const pantalla of [PANTALLAS[0], PANTALLAS[1], PANTALLAS[6]]) {
    const errores = await preparar(page, pantalla, "dark");
    await page.screenshot({ path: `${SHOTS}/${pantalla.id}-1440-oscuro.png`, fullPage: true });
    await medir(page, pantalla.id, 1440, "oscuro", errores);
  }
});

test("el selector y el foco visible", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/?screen=reorder&basis=observed");
  await expect(page.getByText(/Qué pedir hoy/)).toBeVisible({ timeout: 90_000 });

  const disparador = page.getByRole("button", { name: /^Serie/ }).first();
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
  await page.screenshot({ path: `${SHOTS}/4b-selector-1440-claro.png` });
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
