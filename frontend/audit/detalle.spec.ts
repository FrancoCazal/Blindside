/**
 * Segundo pase del audit: el detalle de lo que el primero encontró.
 *
 * axe informa qué regla falla; acá se extrae **por qué**: los colores concretos,
 * la razón de contraste medida y el texto afectado. Sin eso un fallo de contraste
 * no se puede arreglar, solo saber que existe.
 */

import { writeFile } from "node:fs/promises";
import { AxeBuilder } from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

interface FalloContraste {
  pantalla: string;
  tema: string;
  texto: string;
  selector: string;
  frente: string;
  fondo: string;
  razon: number;
  esperado: number;
  tamano: string;
}

const fallos: FalloContraste[] = [];
const otros: string[] = [];
const desbordes: string[] = [];

const CASOS = [
  { id: "4a-reposicion", ruta: "?screen=reorder&basis=observed", ancla: /Qué pedir hoy/ },
  { id: "2a-serie", ruta: "?screen=series&basis=recovered", ancla: /Cantidad sugerida/ },
  { id: "4d-mapa", ruta: "?screen=map&basis=recovered", ancla: /Mapa de productos/ },
];

for (const caso of CASOS) {
  for (const tema of ["light", "dark"] as const) {
    test(`detalle ${caso.id} ${tema}`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.emulateMedia({ colorScheme: tema });
      await page.goto(`/${caso.ruta}`);
      await expect(page.getByText(caso.ancla).first()).toBeVisible({ timeout: 90_000 });
      await expect(page.getByText(/MASE · cargando…/)).toHaveCount(0, { timeout: 90_000 });
      await page.evaluate((t) => {
        document.documentElement.dataset.theme = t === "dark" ? "dark" : "light";
      }, tema);
      await page.waitForTimeout(300);

      const resultado = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();

      for (const violacion of resultado.violations) {
        if (violacion.id === "color-contrast") {
          for (const nodo of violacion.nodes) {
            const datos = (nodo.any[0]?.data ?? {}) as Record<string, unknown>;
            fallos.push({
              pantalla: caso.id,
              tema,
              texto: (nodo.html ?? "").slice(0, 90).replace(/\s+/g, " "),
              selector: String(nodo.target[0]),
              frente: String(datos.fgColor ?? "?"),
              fondo: String(datos.bgColor ?? "?"),
              razon: Number(datos.contrastRatio ?? 0),
              esperado: Number(datos.expectedContrastRatio ?? 0) || 4.5,
              tamano: `${datos.fontSize ?? "?"} ${datos.fontWeight ?? ""}`,
            });
          }
        } else {
          otros.push(
            `${caso.id}/${tema} · ${violacion.id} (${violacion.impact}) · ${violacion.nodes.length} nodos · ${violacion.help} · ejemplo: ${(violacion.nodes[0]?.html ?? "").slice(0, 110).replace(/\s+/g, " ")}`,
          );
        }
      }
    });
  }
}

test("quien desborda a 1024", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/?screen=reorder&basis=observed");
  await expect(page.getByText(/Qué pedir hoy/)).toBeVisible({ timeout: 90_000 });

  const culpables = await page.evaluate(() => {
    const limite = window.innerWidth;
    const salida: string[] = [];
    for (const el of Array.from(document.querySelectorAll<HTMLElement>("*"))) {
      const caja = el.getBoundingClientRect();
      if (caja.right > limite + 1 || caja.width > limite + 1) {
        const padre = el.parentElement;
        salida.push(
          `${el.tagName.toLowerCase()}${el.className ? "." + String(el.className).split(" ")[0] : ""} ` +
            `ancho=${Math.round(caja.width)} derecha=${Math.round(caja.right)} ` +
            `(padre ${padre?.tagName.toLowerCase()}${padre?.className ? "." + String(padre.className).split(" ")[0] : ""})`,
        );
      }
    }
    return { limite, salida: salida.slice(0, 14), total: salida.length };
  });
  desbordes.push(`viewport ${culpables.limite} · ${culpables.total} elementos desbordan`);
  desbordes.push(...culpables.salida);
});

test.afterAll(async () => {
  const lineas = [
    "# Detalle del audit",
    "",
    "## Contraste",
    "",
    "| Pantalla | Tema | Tamaño | Frente | Fondo | Razón | Exigido | Elemento |",
    "|---|---|---|---|---|---|---|---|",
    ...fallos.map(
      (f) =>
        `| ${f.pantalla} | ${f.tema} | ${f.tamano} | \`${f.frente}\` | \`${f.fondo}\` | ` +
        `**${f.razon.toFixed(2)}** | ${f.esperado} | \`${f.selector}\` ${f.texto} |`,
    ),
    "",
    "## Otras violaciones",
    "",
    ...otros.map((o) => `- ${o}`),
    "",
    "## Desborde horizontal a 1024",
    "",
    ...desbordes.map((d) => `- ${d}`),
  ];
  await writeFile("audit/detalle.md", lineas.join("\n"), "utf-8");
});
