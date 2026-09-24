// @vitest-environment jsdom
/**
 * Render de la pantalla de reposición contra un backend simulado.
 *
 * Verifica lo que un build limpio no verifica: que el árbol se monte, que las
 * cifras salgan con el formato del handoff y que el toggle de censura cambie la
 * cantidad sugerida. Los datos los sirve un `fetch` de juguete, pero las formas
 * son las del contrato real — si `api/schemas.py` cambia, los tipos de
 * `schema.d.ts` cambian y esto deja de compilar.
 */

import { act, cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { ProveedorEstado } from "./state";

const HOY = "2024-07-03";

function historia(id: string, uplift: number) {
  const points = Array.from({ length: 28 }, (_, i) => {
    const censurado = i % 3 === 0;
    const observed = 1 + (i % 5) * 0.1;
    return {
      dt: `2024-06-${String(i + 1).padStart(2, "0")}`,
      observed,
      recovered: censurado ? observed * (1 + uplift) : observed,
      is_censored: censurado,
      oos_hours_open: censurado ? 6 : 0,
      available_weight: censurado ? 0.6 : 1,
      inflation_factor: censurado ? 1 + uplift : 1,
    };
  });
  const [store, product] = id.split("_").map(Number);
  return {
    series: { series_id: id, store_id: store, product_id: product, city_id: 0 },
    open_hours: 16,
    points,
    runs: points
      .filter((p) => p.is_censored)
      .map((p) => ({ start: p.dt, end: p.dt, n_days: 1 })),
    summary: {
      n_days: 28,
      n_censored_days: 10,
      censored_days_last_28: 10,
      share_censored_days: 0.357,
      max_run_days: 1,
      current_run_days: 0,
      days_since_last_sale: 0,
      // Por debajo de SENAL.parcial (0,30): la serie simulada tiene señal
      // observada, así que el estado de la celda es el normal.
      estimated_share_last_28: 0.12,
      mean_oos_hours_when_censored: 6,
      uplift_pct: uplift * 100,
      uplift_pct_clean_days: 0,
    },
  };
}

const IDS = ["12_412", "4_871", "4_233"];

/** Series distintas para la segunda página, para que el test la pueda distinguir. */
const IDS_PAGINA_2 = ["7_101", "7_202"];

/** Cantidades distintas por base: es lo que el toggle tiene que mover. */
const CANTIDAD = { observed: 0.96, recovered: 1.35 };

function servidor(opciones: { muestra?: boolean } = {}) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const ruta = url.replace("http://127.0.0.1:8000", "");
    const cuerpo = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
    const base = (cuerpo.recover_censoring ? "recovered" : "observed") as "observed" | "recovered";

    const json = (datos: unknown) =>
      new Response(JSON.stringify(datos), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });

    if (ruta === "/health") {
      return json({
        status: "ok",
        version: "0.1.0",
        model_loaded: true,
        model_name: "conformal_lgbm_quantile_adaptive",
        trained_until: "2024-07-02",
        model_error: null,
        models: [
          {
            basis: "recovered",
            artifact: "model.joblib",
            loaded: true,
            model_name: "conformal_lgbm_quantile_adaptive",
            target: "demand_latent",
            trained_until: "2024-07-02",
            n_series_seen: 3066,
            n_series_in_panel: 3066,
            error: null,
          },
          {
            basis: "observed",
            artifact: "model_observed.joblib",
            loaded: true,
            model_name: "conformal_lgbm_quantile_adaptive",
            target: "sale_amount",
            trained_until: "2024-07-02",
            n_series_seen: 3066,
            n_series_in_panel: 3066,
            error: null,
          },
        ],
        panel: {
          source: opciones.muestra ? "sample" : "processed",
          is_sample: Boolean(opciones.muestra),
          n_series: opciones.muestra ? 60 : 3066,
          n_stores: opciones.muestra ? 2 : 38,
          n_products: opciones.muestra ? 31 : 309,
          n_days: 97,
          date_min: "2024-03-28",
          date_max: "2024-07-02",
          reference_n_series: 3066,
          reference_n_stores: 38,
          reference_n_products: 309,
        },
        coverage_nominal: 0.9,
        coverage_by_horizon: [],
        coverage_note: "no hay backtest guardado: correr `make models`",
      });
    }

    if (ruta.startsWith("/series?")) {
      const q = new URLSearchParams(ruta.split("?")[1]);
      const limite = Number(q.get("limit") ?? 100);
      const desplazamiento = Number(q.get("offset") ?? 0);
      // El simulacro respeta el offset a propósito: sin eso, la paginación
      // "funcionaría" en el test mostrando siempre la misma página.
      const ids = desplazamiento > 0 ? IDS_PAGINA_2 : IDS;
      return json({
        total: 3066,
        limit: limite,
        offset: desplazamiento,
        query: null,
        items: ids.slice(0, limite).map((id) => {
          const [store, product] = id.split("_").map(Number);
          return {
            series_id: id,
            store_id: store,
            product_id: product,
            city_id: 0,
            management_group_id: 6,
            first_category_id: 4,
            second_category_id: 28,
            third_category_id: 131,
            label: `tienda ${store} · producto ${product}`,
          };
        }),
      });
    }

    if (ruta === "/series/history") {
      const ids = (cuerpo.series_ids as string[]) ?? [];
      return json({ series: ids.map((id, i) => historia(id, 0.2 + i * 0.1)) });
    }

    if (ruta === "/forecast") {
      const ids = (cuerpo.series_ids as string[]) ?? [];
      return json({
        model_name: "conformal_lgbm_quantile_adaptive",
        basis: base,
        coverage_nominal: 0.9,
        coverage_empirical: null,
        forecasts: ids.map((id) => {
          const [store, product] = id.split("_").map(Number);
          return {
            series: { series_id: id, store_id: store, product_id: product, city_id: 0 },
            points: Array.from({ length: 7 }, (_, h) => ({
              dt: `2024-07-${String(3 + h).padStart(2, "0")}`,
              h: h + 1,
              y_pred: CANTIDAD[base] * (1 + h * 0.01),
              pred_lo: CANTIDAD[base] * 0.6,
              pred_hi: CANTIDAD[base] * 1.5 * (1 + h * 0.03),
            })),
          };
        }),
      });
    }

    if (ruta === "/reorder") {
      const ids = (cuerpo.series_ids as string[]) ?? [];
      const co = Number(cuerpo.co ?? 0.6);
      // La política se simula por encima de la cantidad sugerida a propósito: en
      // base observada pedir lo que ve el ERP es pedir de menos, y el test lo
      // verifica leyendo el signo del delta de la primera fila.
      const politica = CANTIDAD[base] * 1.4;
      const faltante = 0.2;
      const sobrante = 0.5;
      return json({
        critical_fraction: 1 / (1 + co),
        basis: base,
        model_name: "conformal_lgbm_quantile_adaptive",
        plan: {
          plan: { discount: 0.967, holiday_flag: 0, activity_flag: 0 },
          source: "panel_median",
          window_days: 21,
        },
        policy_window: 21,
        tail_mass: 0.05,
        lines: ids.map((id) => {
          const [store, product] = id.split("_").map(Number);
          return {
            series: { series_id: id, store_id: store, product_id: product, city_id: 0 },
            dt: HOY,
            qty: CANTIDAD[base],
            critical_fraction: 1 / (1 + co),
            policy_qty: politica,
            expected_demand: CANTIDAD[base] * 0.9,
            expected_shortfall: faltante,
            expected_overage: sobrante,
            cost_delta_pct: -8.64,
          };
        }),
        total_cost_delta_pct: -8.64,
      });
    }

    if (ruta === "/backtest") {
      return json({
        target: "demand_latent",
        horizon: 7,
        season_length: 7,
        rows: [
          {
            model_name: "lgbm_global",
            metric: "mase",
            mean: 0.8311,
            std: 0.0462,
            worst_origin: 0.8849,
            best_origin: 0.7712,
            n_origins: 8,
          },
        ],
        external_baseline: null,
      });
    }

    return new Response("{}", { status: 404 });
  });
}

function montar() {
  return render(
    <ProveedorEstado>
      <App />
    </ProveedorEstado>,
  );
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  vi.stubGlobal("fetch", servidor());
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("pantalla de reposición", () => {
  it("arranca en base observada, que es el modo equivocado a propósito", async () => {
    montar();
    const observada = await screen.findByRole("button", { name: "Venta observada" });
    expect(observada.getAttribute("aria-pressed")).toBe("true");
    // La consecuencia se escribe como consecuencia, no como estado.
    expect(await screen.findByText(/Es lo que ve el ERP/)).toBeTruthy();
  });

  it("lista las series con la cantidad sugerida y su delta contra la política", async () => {
    montar();
    const tabla = await screen.findByRole("table");
    const filas = within(tabla).getAllByRole("row");
    // Una fila por serie más el encabezado, y la primera arranca abierta.
    expect(filas.length).toBeGreaterThanOrEqual(IDS.length + 1);
    expect(within(tabla).getByText("T12 · P0412")).toBeTruthy();

    // La celda se busca por el encabezado y no por índice fijo: este test ya se
    // rompió dos veces al agregar una columna, y lo que quiere verificar es el
    // contenido de «Sugerido», no en qué posición está.
    const encabezados = within(tabla)
      .getAllByRole("columnheader")
      .map((th) => th.textContent?.replace(/[▾▴]/g, "").trim() ?? "");
    const col = (nombre: string) => {
      const i = encabezados.indexOf(nombre);
      expect(i, `no hay columna «${nombre}» en ${encabezados.join(" · ")}`).toBeGreaterThanOrEqual(0);
      return i;
    };

    const primera = within(tabla).getByText("T12 · P0412").closest("tr")!;
    const celdas = within(primera).getAllByRole("cell");
    expect(celdas[col("Sugerido")].textContent).toBe("0,96");
    // La política sale de /reorder y el simulacro la pone por encima de la
    // cantidad sugerida, así que el delta es negativo: pedir lo que ve el ERP es
    // pedir de menos.
    expect(celdas[col("Δ")].textContent?.startsWith("\u2212")).toBe(true);
  });

  it("pagina de verdad: la página siguiente pide otro offset y trae otras series", async () => {
    montar();
    await screen.findByText("T12 · P0412");

    const siguiente = screen.getByRole("button", { name: "Página siguiente" });
    expect(siguiente.hasAttribute("disabled")).toBe(false);
    // En la primera página no hay a dónde volver.
    expect(screen.getByRole("button", { name: "Página anterior" }).hasAttribute("disabled")).toBe(
      true,
    );

    await act(async () => {
      siguiente.click();
    });

    // Las series de la segunda página, y las de la primera ya no están.
    expect(await screen.findByText("T07 · P0101")).toBeTruthy();
    expect(screen.queryByText("T12 · P0412")).toBeNull();
    // Y el offset viaja en la URL, así que la página se puede enlazar.
    expect(new URLSearchParams(window.location.search).get("offset")).toBe("25");
  });

  it("ordenar por una columna lo refleja en aria-sort y en la URL", async () => {
    montar();
    const tabla = await screen.findByRole("table");

    // Por defecto ordena por impacto, descendente, y no ensucia la URL.
    const th = (nombre: string) =>
      within(tabla)
        .getAllByRole("columnheader")
        .find((h) => h.textContent?.includes(nombre))!;
    expect(th("Impacto").getAttribute("aria-sort")).toBe("descending");
    expect(new URLSearchParams(window.location.search).get("sort")).toBeNull();

    await act(async () => {
      within(th("Sugerido")).getByRole("button").click();
    });
    expect(th("Sugerido").getAttribute("aria-sort")).toBe("descending");
    expect(th("Impacto").getAttribute("aria-sort")).toBe("none");
    expect(new URLSearchParams(window.location.search).get("sort")).toBe("sugerido");

    // Repetir la misma columna invierte la dirección.
    await act(async () => {
      within(th("Sugerido")).getByRole("button").click();
    });
    expect(th("Sugerido").getAttribute("aria-sort")).toBe("ascending");
    expect(new URLSearchParams(window.location.search).get("dir")).toBe("asc");
  });

  it("los botones de ratio muestran el cuantil que producen", async () => {
    montar();
    const grupo = await screen.findByRole("group", { name: "Ratio de costo" });
    const cuantiles = within(grupo)
      .getAllByText(/^q\*/)
      .map((n) => n.textContent);
    expect(cuantiles).toEqual(["q* 0,769", "q* 0,625", "q* 0,500", "q* 0,400"]);
  });

  it("el toggle cambia la cantidad sugerida, no solo la serie dibujada", async () => {
    const { rerender } = montar();
    await screen.findByRole("table");

    const recuperada = screen.getByRole("button", { name: "Demanda recuperada" });
    recuperada.click();
    rerender(
      <ProveedorEstado>
        <App />
      </ProveedorEstado>,
    );

    // 1,35 es la cantidad de la base recuperada; 0,96 la de la observada.
    const nuevas = await screen.findAllByText("1,35");
    expect(nuevas.length).toBeGreaterThan(0);
    expect(await screen.findByText(/Censura corregida/)).toBeTruthy();
  });
  it("el atajo global b alterna la base sin tocar el mouse", async () => {
    montar();
    await screen.findByRole("table");
    expect(screen.getByRole("button", { name: "Venta observada" }).getAttribute("aria-pressed")).toBe(
      "true",
    );

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "b", bubbles: true }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "b" }));

    const recuperada = await screen.findByRole("button", { name: "Demanda recuperada" });
    expect(recuperada.getAttribute("aria-pressed")).toBe("true");
  });
});

describe("estado de muestra", () => {
  it("marca la muestra en tres lugares y el sello no se puede cerrar", async () => {
    vi.stubGlobal("fetch", servidor({ muestra: true }));
    montar();

    expect(await screen.findByText("Muestra")).toBeTruthy();
    expect(await screen.findByText(/Estos números no son los del panel completo/)).toBeTruthy();
    expect(await screen.findByText(/60 de 3.066 series/)).toBeTruthy();
    // El sello es un span sin botón de cierre: no hay nada que apretar.
    expect(screen.queryByRole("button", { name: /cerrar/i })).toBeNull();
  });
});
