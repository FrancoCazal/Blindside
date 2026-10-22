// @vitest-environment jsdom
/**
 * Render de las pantallas contra un backend simulado.
 *
 * Verifica lo que un build limpio no verifica: que el árbol se monte, que las
 * cifras salgan con el formato correcto, que el toggle de censura cambie la
 * cantidad sugerida y que los errores de la auditoría no vuelvan (ver
 * `docs/rediseno_frontend.md`, sección 7). Los datos los sirve un `fetch` de
 * juguete, pero las formas son las del contrato real: si `api/schemas.py` cambia,
 * `schema.d.ts` cambia y esto deja de compilar.
 */

import { act, cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { API_BASE } from "./api/client";
import { ProveedorEstado } from "./state";

const HOY = "2024-07-03";

/** Los ids reales de tienda no son contiguos. El filtro tiene que usar estos. */
const TIENDAS = [0, 4, 7, 12, 41];

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
    runs: points.filter((p) => p.is_censored).map((p) => ({ start: p.dt, end: p.dt, n_days: 1 })),
    summary: {
      n_days: 28,
      n_censored_days: 10,
      censored_days_last_28: 10,
      share_censored_days: 0.357,
      max_run_days: 1,
      current_run_days: 0,
      days_since_last_sale: 0,
      estimated_share_last_28: 0.12,
      mean_oos_hours_when_censored: 6,
      uplift_pct: uplift * 100,
      uplift_pct_clean_days: 0,
    },
  };
}

/** Primera página del catálogo, en el orden del servidor (por ahorro). */
const IDS = ["12_412", "4_871", "4_233"];
/** Segunda página, distinta para poder distinguirla. */
const IDS_PAGINA_2 = ["7_101", "7_202"];

/** Cantidades distintas por base: es lo que el toggle tiene que mover. */
const CANTIDAD = { observed: 0.96, recovered: 1.35 };

const FRESCURA = {
  data_date_max: "2024-07-02",
  trained_until: "2024-07-02",
  days_behind: 0,
  status: "al_dia",
  loaded_at: "2026-10-15T00:33:24+00:00",
  last_update_at: null,
  last_update_status: null,
};

function grupo(key: string, label: string, n: number, urgent: boolean) {
  return {
    key,
    label,
    meaning: `Significado de ${label}.`,
    action: `Qué hacer con ${label}, explicado con suficiente detalle.`,
    urgent,
    n_series: n,
    share_series: n / 3066,
    share_volume: 0.05,
    only_this: Math.round(n / 2),
    threshold: `umbral de ${label}`,
    threshold_value: null,
  };
}

const GRUPOS_ALERTA = [
  grupo("quebrado_ahora", "Quebrado ahora", 108, true),
  grupo("riesgo_merma", "Riesgo de merma", 204, true),
  grupo("no_confiable", "Modelo no confiable", 404, false),
  grupo("alto_volumen", "Alto volumen", 307, false),
];

function alerta(id: string, reasons: string[], banda: string, extra: Record<string, number> = {}) {
  const [store, product] = id.split("_").map(Number);
  return {
    series: { series_id: id, store_id: store, product_id: product, city_id: 0 },
    label: `tienda ${store} · producto ${product}`,
    rotation_band: banda,
    reasons,
    demand_mean: 4.47,
    estimated_share: 0.12,
    current_run_days: 0,
    stockout_rate: 0.4,
    mase: 0.8,
    waste_policy: 0.2,
    waste_model: 0.15,
    waste_avoidable: 0.05,
    policy_qty: 10,
    suggested_qty: 9,
    ...extra,
  };
}

const ALERTAS = [
  alerta("60_600", ["quebrado_ahora", "no_confiable"], "alta", { current_run_days: 6, mase: 1.5 }),
  alerta("12_412", ["riesgo_merma"], "media", { waste_policy: 0.62, waste_avoidable: 0.3 }),
  alerta("4_871", ["alto_volumen"], "baja"),
];

const RESUMEN_DATOS = {
  panel: null,
  totals: {
    n_rows: 297402,
    n_series: 3066,
    n_days: 97,
    share_censored_days: 0.4389,
    share_zero_sale_days: 0.03,
    mean_oos_hours_when_censored: 7,
    uplift_pct: 21.12,
  },
  daily: Array.from({ length: 10 }, (_, i) => ({
    dt: `2024-06-${String(i + 1).padStart(2, "0")}`,
    observed: 2800 + i * 10,
    recovered: 3400 + i * 12,
    share_censored: 0.44,
    n_series: 3066,
  })),
  weekday: Array.from({ length: 7 }, (_, d) => ({
    dow: d,
    observed_mean: 0.9 + d * 0.05,
    recovered_mean: 1.1 + d * 0.06,
    share_censored: 0.44,
  })),
  hourly: Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    share_stockout: h / 60,
    share_sales: 1 / 24,
    open: h >= 6 && h < 22,
  })),
  hourly_note: null,
  stores: [{ id: 41, n_series: 80, demand_mean: 1, share_volume: 0.03, share_censored: 0.5, uplift_pct: 25 }],
  categories: [{ id: 1, n_series: 300, demand_mean: 1, share_volume: 0.1, share_censored: 0.4, uplift_pct: 20 }],
  rotation: [
    { band: "alta", n_series: 460, share_series: 0.15, share_volume: 0.4, share_censored: 0.54 },
    { band: "baja", n_series: 1533, share_series: 0.5, share_volume: 0.26, share_censored: 0.4 },
  ],
  stockout_hist: Array.from({ length: 10 }, (_, i) => ({
    lo: i / 10,
    hi: (i + 1) / 10,
    n_series: i === 0 ? 0 : 300,
  })),
  source: "FreshRetailNet-50K (Dingdong-Inc, CC BY 4.0)",
};

function filaBacktest(model_name: string, metric: string, mean: number) {
  return { model_name, metric, mean, std: 0.0454, worst_origin: mean + 0.057, best_origin: mean - 0.05, n_origins: 8 };
}

const BACKTEST = {
  target: "demand_latent",
  horizon: 7,
  season_length: 7,
  rows: [
    ...["cqr_lgbm_quantile", "conformal_lgbm_quantile_adaptive", "lgbm_global"].flatMap((m) => [
      filaBacktest(m, "mase", 0.8217),
      filaBacktest(m, "wape", 0.351),
      filaBacktest(m, "mae", 0.47),
    ]),
    filaBacktest("cqr_lgbm_quantile", "coverage", 0.88),
    filaBacktest("cqr_lgbm_quantile", "interval_width", 1.805),
    filaBacktest("conformal_lgbm_quantile_adaptive", "coverage", 0.987),
    filaBacktest("conformal_lgbm_quantile_adaptive", "interval_width", 3.834),
    filaBacktest("moving_average", "mase", 0.905),
    filaBacktest("moving_average", "wape", 0.396),
    filaBacktest("moving_average", "mae", 0.52),
    filaBacktest("seasonal_naive", "mase", 1.1),
    filaBacktest("seasonal_naive", "wape", 0.471),
    filaBacktest("seasonal_naive", "mae", 0.6),
  ],
  external_baseline: null,
};

const DESGLOSE = {
  target: "demand_latent",
  horizon: 7,
  n_origins: 2,
  origins: ["cqr_lgbm_quantile", "moving_average", "seasonal_naive"].flatMap((m, k) =>
    [0, 1].map((o) => ({
      model_name: m,
      origin: o,
      origin_date: `2024-06-0${o + 1}`,
      metric: "mase",
      value: 0.8 + k * 0.15 + o * 0.01,
    })),
  ),
  horizons: ["cqr_lgbm_quantile", "seasonal_naive"].flatMap((m, k) =>
    [1, 2].map((h) => ({ model_name: m, h, metric: "mase", value: 0.75 + k * 0.3 + h * 0.02 })),
  ),
  // El caso de E3: en baja rotación el modelo SÍ le gana al naive estacional.
  bands: [
    { model_name: "cqr_lgbm_quantile", band: "baja", metric: "mase", value: 0.822, n: 100 },
    { model_name: "seasonal_naive", band: "baja", metric: "mase", value: 1.121, n: 100 },
  ],
};

function servidor(opciones: { muestra?: boolean } = {}) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    // Se quita la base configurada y no una fija: con VITE_API_BASE en el entorno
    // (pasa al correr el audit de Playwright contra otra API) fallaban todos.
    const ruta = url.replace(API_BASE, "");
    const cuerpo = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};

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
        model_name: "cqr_lgbm_quantile",
        trained_until: "2024-07-02",
        model_error: null,
        models: ["recovered", "observed"].map((basis) => ({
          basis,
          artifact: basis === "recovered" ? "model.joblib" : "model_observed.joblib",
          loaded: true,
          model_name: "cqr_lgbm_quantile",
          target: basis === "recovered" ? "demand_latent" : "sale_amount",
          trained_until: "2024-07-02",
          n_series_seen: 3066,
          n_series_in_panel: 3066,
          error: null,
        })),
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
          store_ids: TIENDAS,
        },
        coverage_nominal: 0.9,
        coverage_by_horizon: [1, 2, 3].map((h) => ({
          h,
          coverage_nominal: 0.9,
          coverage_empirical: 0.85 + h * 0.01,
          n: 100,
        })),
        coverage_note: null,
        freshness: FRESCURA,
      });
    }

    if (ruta.startsWith("/reorder/catalog")) {
      const q = new URLSearchParams(ruta.split("?")[1]);
      const base = q.get("recover_censoring") === "true" ? "recovered" : "observed";
      const desplazamiento = Number(q.get("offset") ?? 0);
      const ids = desplazamiento > 0 ? IDS_PAGINA_2 : IDS;
      // La política queda por encima de la sugerida: en base observada pedir lo
      // que ve el ERP es pedir de menos, y el test lee el signo del delta.
      const politica = CANTIDAD[base] * 1.4;
      return json({
        dt: HOY,
        basis: base,
        model_name: "cqr_lgbm_quantile",
        critical_fraction: 1 / (1 + Number(q.get("co") ?? 0.6)),
        cu: 1,
        co: Number(q.get("co") ?? 0.6),
        policy_window: 21,
        tail_mass: 0.05,
        sort: q.get("sort") ?? "impacto",
        dir: q.get("dir") ?? "desc",
        totals: {
          n_series: 3066,
          qty: base === "recovered" ? 4218 : 3300,
          policy_qty: 4252,
          qty_delta_pct: base === "recovered" ? -0.8 : -22.4,
          cost_model: 848,
          cost_policy: 951,
          cost_delta_pct: -10.86,
          overage_model: 753,
          overage_policy: 839,
          overage_delta_pct: -10.2,
          shortfall_model: 396,
          shortfall_policy: 448,
          shortfall_delta_pct: -11.6,
          n_big_change: 818,
        },
        total: 3066,
        limit: Number(q.get("limit") ?? 25),
        offset: desplazamiento,
        items: ids.map((id, i) => {
          const [store, product] = id.split("_").map(Number);
          return {
            series: { series_id: id, store_id: store, product_id: product, city_id: 0 },
            label: `tienda ${store} · producto ${product}`,
            rotation_band: "alta",
            qty: CANTIDAD[base],
            policy_qty: politica,
            delta_pct: 100 * (CANTIDAD[base] / politica - 1),
            expected_demand: CANTIDAD[base] * 0.9,
            expected_shortfall: 0.2,
            expected_overage: 0.5,
            // Decreciente: es el orden del servidor y el cliente no lo reordena.
            saving: 0.9 - i * 0.2,
            saving_share: 0.01 - i * 0.002,
            cost_delta_pct: -8.64,
            reasons: i === 0 ? ["riesgo_merma"] : [],
          };
        }),
      });
    }

    if (ruta.startsWith("/series?")) {
      const q = new URLSearchParams(ruta.split("?")[1]);
      const consulta = q.get("q");
      const ids = consulta ? [consulta] : IDS;
      return json({
        total: 3066,
        limit: Number(q.get("limit") ?? 100),
        offset: 0,
        query: consulta,
        items: ids.map((id) => {
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
            rotation_band: "alta",
            label: `tienda ${store} · producto ${product}`,
          };
        }),
      });
    }

    if (ruta === "/series/history") {
      const ids = (cuerpo.series_ids as string[]) ?? [];
      return json({ series: ids.map((id, i) => historia(id, 0.2 + i * 0.1)) });
    }

    if (ruta.startsWith("/series/") && ruta.includes("/history")) {
      const id = decodeURIComponent(ruta.split("/")[2]);
      return json(historia(id, 0.3));
    }

    if (ruta === "/forecast") {
      const ids = (cuerpo.series_ids as string[]) ?? [];
      const base = cuerpo.recover_censoring ? "recovered" : "observed";
      return json({
        model_name: "cqr_lgbm_quantile",
        basis: base,
        coverage_nominal: 0.9,
        coverage_empirical: null,
        plan: { plan: { discount: 0.967, holiday_flag: 0, activity_flag: 0 }, source: "panel_median", window_days: 21 },
        forecasts: ids.map((id) => {
          const [store, product] = id.split("_").map(Number);
          return {
            series: { series_id: id, store_id: store, product_id: product, city_id: 0 },
            points: Array.from({ length: 7 }, (_, h) => ({
              dt: `2024-07-${String(3 + h).padStart(2, "0")}`,
              h: h + 1,
              y_pred: CANTIDAD[base] * 0.9,
              pred_lo: CANTIDAD[base] * 0.6,
              pred_hi: CANTIDAD[base] * 1.5,
            })),
          };
        }),
      });
    }

    if (ruta === "/reorder") {
      const ids = (cuerpo.series_ids as string[]) ?? [];
      const base = cuerpo.recover_censoring ? "recovered" : "observed";
      return json({
        critical_fraction: 0.625,
        basis: base,
        model_name: "cqr_lgbm_quantile",
        plan: { plan: { discount: 0.967, holiday_flag: 0, activity_flag: 0 }, source: "panel_median", window_days: 21 },
        policy_window: 21,
        tail_mass: 0.05,
        lines: ids.flatMap((id) => {
          const [store, product] = id.split("_").map(Number);
          return Array.from({ length: 7 }, (_, h) => ({
            series: { series_id: id, store_id: store, product_id: product, city_id: 0 },
            dt: `2024-07-${String(3 + h).padStart(2, "0")}`,
            qty: CANTIDAD[base],
            critical_fraction: 0.625,
            policy_qty: CANTIDAD[base] * 1.4,
            expected_demand: CANTIDAD[base] * 0.9,
            expected_shortfall: 0.2,
            expected_overage: 0.5,
            cost_delta_pct: -8.64,
          }));
        }),
        total_cost_delta_pct: -8.64,
      });
    }

    if (ruta === "/explain") {
      const base = cuerpo.recover_censoring ? "recovered" : "observed";
      const id = String(cuerpo.series_id);
      const [store, product] = id.split("_").map(Number);
      // La cifra explicada es la cantidad sugerida: base + aportes + resto.
      return json({
        series: { series_id: id, store_id: store, product_id: product, city_id: 0 },
        dt: cuerpo.dt,
        basis: base,
        model_name: "cqr_lgbm_quantile",
        quantile: 0.625,
        base_value: 0.5,
        prediction: CANTIDAD[base],
        rest: CANTIDAD[base] - 0.5 - 0.6,
        point_forecast: CANTIDAD[base] * 0.9,
        plan: { plan: { discount: 0.967, holiday_flag: 0, activity_flag: 0 }, source: "panel_median", window_days: 21 },
        contributions: [
          { feature: "latent_roll_mean_7", value: 6.04, contribution: 0.8 },
          { feature: "product_id", value: 600, contribution: -0.2 },
        ],
      });
    }

    if (ruta.startsWith("/alerts")) {
      const q = new URLSearchParams(ruta.split("?")[1] ?? "");
      const g = q.get("group");
      const banda = q.get("rotation_band");
      const serie = q.get("series_id");
      const items = ALERTAS.filter(
        (a) =>
          (!g || a.reasons.includes(g)) &&
          (!banda || a.rotation_band === banda) &&
          (!serie || a.series.series_id === serie),
      );
      return json({
        data_date_max: "2024-07-02",
        basis: "recovered",
        model_name: "cqr_lgbm_quantile",
        n_series: 3066,
        n_flagged: 977,
        groups: GRUPOS_ALERTA,
        unavailable: [],
        total: items.length,
        items: items.slice(0, Number(q.get("limit") ?? 50)),
      });
    }

    if (ruta === "/dataset/summary") return json(RESUMEN_DATOS);

    if (ruta === "/censoring") {
      return json({
        summary: { n_series: 3066 },
        comparison: [
          { grupo: "todos los dias", n: 297402, demanda_observada: 1.0087, demanda_latente: 1.2218, uplift_pct: 21.12 },
          { grupo: "dias limpios", n: 166882, demanda_observada: 0.9793, demanda_latente: 0.9793, uplift_pct: 0 },
          { grupo: "dias censurados", n: 130520, demanda_observada: 1.0463, demanda_latente: 1.5318, uplift_pct: 46.4 },
        ],
        note: "",
      });
    }

    if (ruta === "/products/map") {
      return json({
        method: "pca",
        features: ["demanda_media", "tasa_quiebre"],
        explained_variance: [0.375, 0.299],
        points: [
          { product_id: 600, x: 0, y: 0, rotation_band: "alta", demanda_media: 1.5, tasa_quiebre: 0.7, n_series: 33 },
          { product_id: 104, x: 1, y: 1, rotation_band: "baja", demanda_media: 0.2, tasa_quiebre: 0.3, n_series: 5 },
        ],
      });
    }

    if (ruta === "/pipeline") {
      return json({
        layer: "processed",
        panel_file: { file: "panel.parquet", exists: true, modified: "2026-09-23T20:35:22+00:00", bytes: 1 },
        demand_file: { file: "demand.parquet", exists: true, modified: "2026-09-15T22:54:22+00:00", bytes: 1 },
        freshness: FRESCURA,
        artifacts: [
          {
            basis: "recovered",
            current: { file: "model.joblib", exists: true, modified: "2026-09-24T09:59:30+00:00", bytes: 1 },
            previous: { file: "model.prev.joblib", exists: false },
            candidate: { file: "model.candidate.joblib", exists: false },
            trained_until: "2024-07-02",
            model_name: "cqr_lgbm_quantile",
          },
        ],
        updates: [
          {
            kind: "ingest",
            status: "sin_cambios",
            message: "las 21462 filas del lote ya estaban cargadas con los mismos valores",
            finished_at: "2026-10-15T00:40:56+00:00",
            rows_new: 0,
            rows_duplicate: 21462,
            rows_conflict: 0,
          },
        ],
        steps: [
          {
            key: "ingesta",
            name: "Ingerir un lote",
            command: "make update INPUT=data/incoming/lote.parquet",
            what: "Upsert.",
          },
        ],
        auto_reload_seconds: 2,
      });
    }

    if (ruta === "/backtest") return json(BACKTEST);
    if (ruta === "/backtest/breakdown") return json(DESGLOSE);

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

function irA(ruta: string) {
  window.history.replaceState(null, "", ruta);
}

beforeEach(() => {
  irA("/?screen=reorder");
  vi.stubGlobal("fetch", servidor());
  // Los tests se escribieron con los textos en español. El inglés, que es el
  // idioma por defecto, tiene su bloque propio al final.
  window.localStorage.clear();
  window.localStorage.setItem("blindside:idioma", "es");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("cromo", () => {
  it("tiene una sola barra superior y siete pantallas en tres grupos", async () => {
    irA("/");
    montar();
    const nav = await screen.findByRole("navigation", { name: "Pantallas" });
    const items = within(nav).getAllByRole("button").filter((b) => b.className.includes("lateral-item"));
    expect(items.map((b) => b.textContent?.replace(/^[A-Z][a-z]?/, "").trim())).toEqual([
      "Panel",
      "Alertas",
      "Reposición",
      "Serie",
      "Modelos",
      "Datos",
      "Pipeline",
    ]);
    // Sin franja de contexto ni barra de filtros globales.
    expect(screen.queryByText(/Los filtros afectan/)).toBeNull();
    expect(screen.getByRole("button", { name: /Buscar serie/ })).toBeTruthy();
  });

  it("redirige los enlaces a pantallas que se fusionaron", async () => {
    irA("/?screen=compare");
    montar();
    expect(await screen.findByRole("heading", { level: 1, name: "Modelos" })).toBeTruthy();
    expect(new URLSearchParams(window.location.search).get("screen")).toBe("models");
  });
});

describe("panel de entrada", () => {
  beforeEach(() => irA("/"));

  it("abre en el panel con lo urgente primero y la cifra de cada alerta", async () => {
    montar();
    expect(await screen.findByRole("heading", { name: "Para hoy" })).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Quebrado ahora" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Riesgo de merma" })).toBeTruthy();
    expect(await screen.findByText("6 d seguidos en quiebre")).toBeTruthy();
    expect(await screen.findByText("62 % sin vender con la política")).toBeTruthy();
    expect(screen.getByText("977")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Para revisar" })).toBeTruthy();
  });

  it("dice la mejora en palabras y con la misma convención que Modelos (E4)", async () => {
    montar();
    expect(await screen.findByText(/25,3 % menos error que el naive estacional/)).toBeTruthy();
    // Los tres LightGBM van en una sola barra del ranking.
    expect(screen.getAllByText("LightGBM global · CQR")).toHaveLength(1);
  });

  it("«Ver las N» lleva a las alertas filtradas por ese motivo", async () => {
    montar();
    const boton = await screen.findByRole("button", { name: "Ver las 204 →" });
    await act(async () => {
      boton.click();
    });
    expect(new URLSearchParams(window.location.search).get("screen")).toBe("alerts");
    expect(new URLSearchParams(window.location.search).get("alert")).toBe("riesgo_merma");
    const tabla = await screen.findByRole("table");
    expect(within(tabla).getByText("T12 · P0412")).toBeTruthy();
    expect(within(tabla).queryByText("T60 · P0600")).toBeNull();
  });
});

describe("alertas", () => {
  it("aplica el filtro de clase de rotación (E6)", async () => {
    irA("/?screen=alerts&class=baja");
    montar();
    const tabla = await screen.findByRole("table");
    expect(within(tabla).getByText("T04 · P0871")).toBeTruthy();
    expect(within(tabla).queryByText("T60 · P0600")).toBeNull();
    const llamadas = vi.mocked(fetch).mock.calls.map((c) => String(c[0]));
    expect(llamadas.some((u) => u.includes("/alerts") && u.includes("rotation_band=baja"))).toBe(true);
  });

  it("el filtro de tienda ofrece los ids reales y no 0…n (E1)", async () => {
    irA("/?screen=alerts");
    montar();
    await screen.findByRole("table");
    const select = screen.getByRole("combobox", { name: "Tienda" }) as HTMLSelectElement;
    const opciones = Array.from(select.options).map((o) => o.value).filter(Boolean).map(Number);
    expect(opciones).toEqual(TIENDAS);
  });
});

describe("reposición", () => {
  it("arranca en base observada, que es el modo equivocado a propósito", async () => {
    montar();
    const observada = await screen.findByRole("button", { name: "Venta observada" });
    expect(observada.getAttribute("aria-pressed")).toBe("true");
    expect(await screen.findByText(/lo que ve el ERP/)).toBeTruthy();
  });

  it("muestra la página en el orden del servidor, que ordena todo el catálogo (E7)", async () => {
    montar();
    const tabla = await screen.findByRole("table");
    const filas = within(tabla).getAllByRole("row").slice(1);
    expect(filas.map((f) => within(f).getAllByRole("cell")[0].textContent)).toEqual([
      "T12 · P0412",
      "T04 · P0871",
      "T04 · P0233",
    ]);
    const llamadas = vi.mocked(fetch).mock.calls.map((c) => String(c[0]));
    expect(llamadas.some((u) => u.includes("/reorder/catalog") && u.includes("sort=impacto"))).toBe(true);
  });

  it("lista la cantidad sugerida y su delta contra la política", async () => {
    montar();
    const tabla = await screen.findByRole("table");
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
    expect(celdas[col("Δ")].textContent?.startsWith("\u2212")).toBe(true);
    // Sin «Total a pedir»: sumar cantidades de productos distintos no significa nada.
    expect(screen.queryByText(/Total a pedir/)).toBeNull();
    expect(screen.getByText("Ahorro esperado")).toBeTruthy();
  });

  it("cuenta el quiebre de los mismos 14 días del minigráfico (E5)", async () => {
    montar();
    const tabla = await screen.findByRole("table");
    const primera = within(tabla).getByText("T12 · P0412").closest("tr")!;
    // En la historia simulada hay quiebre uno de cada tres días: 5 de los últimos
    // 14, contra 10 de los últimos 28 que mostraba antes.
    expect(within(primera).getByTitle("5 de 14 días con quiebre").textContent).toContain("5 d");
  });

  it("pagina en el servidor: la página siguiente pide otro offset", async () => {
    montar();
    await screen.findByText("T12 · P0412");
    await act(async () => {
      screen.getByRole("button", { name: "Página siguiente" }).click();
    });
    expect(await screen.findByText("T07 · P0101")).toBeTruthy();
    expect(screen.queryByText("T12 · P0412")).toBeNull();
    expect(new URLSearchParams(window.location.search).get("offset")).toBe("25");
  });

  it("ordenar por una columna se pide al servidor y queda en la URL", async () => {
    montar();
    const tabla = await screen.findByRole("table");
    const th = (nombre: string) =>
      within(tabla)
        .getAllByRole("columnheader")
        .find((h) => h.textContent?.includes(nombre))!;
    expect(th("Ahorro").getAttribute("aria-sort")).toBe("descending");
    await act(async () => {
      within(th("Sugerido")).getByRole("button").click();
    });
    const tabla2 = await screen.findByRole("table");
    const th2 = within(tabla2)
      .getAllByRole("columnheader")
      .find((h) => h.textContent?.includes("Sugerido"))!;
    expect(th2.getAttribute("aria-sort")).toBe("descending");
    expect(new URLSearchParams(window.location.search).get("sort")).toBe("sugerido");
    const llamadas = vi.mocked(fetch).mock.calls.map((c) => String(c[0]));
    expect(llamadas.some((u) => u.includes("/reorder/catalog") && u.includes("sort=sugerido"))).toBe(true);
  });

  it("los botones de ratio muestran el cuantil que producen", async () => {
    montar();
    const grupoRatio = await screen.findByRole("group", { name: "Ratio de costo" });
    const cuantiles = within(grupoRatio)
      .getAllByText(/^q\*/)
      .map((n) => n.textContent);
    expect(cuantiles).toEqual(["q* 0,769", "q* 0,625", "q* 0,500", "q* 0,400"]);
  });

  it("el toggle cambia la cantidad sugerida, no solo un dibujo", async () => {
    montar();
    await screen.findByRole("table");
    await act(async () => {
      screen.getByRole("button", { name: "Demanda recuperada" }).click();
    });
    const nuevas = await screen.findAllByText("1,35");
    expect(nuevas.length).toBeGreaterThan(0);
    expect(screen.queryByText(/lo que ve el ERP/)).toBeNull();
  });

  it("el atajo b alterna la base en reposición", async () => {
    montar();
    await screen.findByRole("table");
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "b" }));
    });
    const recuperada = await screen.findByRole("button", { name: "Demanda recuperada" });
    expect(recuperada.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("status").textContent).toMatch(/Demanda recuperada/);
  });
});

describe("serie", () => {
  it("explica la misma cifra que sugiere (E2) y muestra los motivos de alerta", async () => {
    irA("/?screen=series&series=60_600&basis=recovered");
    montar();
    expect(await screen.findByRole("heading", { level: 1, name: "T60 · P0600" })).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Por qué este número" })).toBeTruthy();
    // Cantidad sugerida y cifra explicada: la misma.
    const cuenta = screen.getByText("Cantidad sugerida", { selector: "dt" }).nextElementSibling;
    expect(cuenta?.textContent).toBe("1,35");
    // Los motivos de la serie, con la cifra que los disparó.
    expect(screen.getByText("6 d seguidos en quiebre")).toBeTruthy();
    // El valor de un id no se formatea como magnitud.
    expect(screen.getByText(/= 600$/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Próximos 7 días" })).toBeTruthy();
  });
});

describe("modelos", () => {
  it("agrupa los modelos idénticos y deriva la conclusión por banda (E3)", async () => {
    irA("/?screen=models");
    montar();
    expect(await screen.findByRole("heading", { level: 1, name: "Modelos" })).toBeTruthy();
    const tabla = screen.getAllByRole("table")[0];
    expect(within(tabla).getAllByText("LightGBM global · CQR")).toHaveLength(1);
    expect(within(tabla).getByText("25,3 % menos error")).toBeTruthy();
    expect(await screen.findByText(/En rotación baja el modelo le gana al naive estacional/)).toBeTruthy();
    // El intervalo: CQR contra conformal de residuos, que antes no estaba.
    expect(screen.getByRole("heading", { name: "El intervalo" })).toBeTruthy();
    expect(screen.getByText(/CQR cubre 88,0 %/)).toBeTruthy();
  });
});

describe("datos y pipeline", () => {
  it("datos muestra los gráficos, la recuperación y el catálogo, sin pipeline", async () => {
    irA("/?screen=data");
    montar();
    expect(await screen.findByRole("heading", { level: 1, name: "Datos" })).toBeTruthy();
    expect(screen.getByRole("img", { name: /Demanda total diaria/ })).toBeTruthy();
    // La tabla de recuperación, con los textos del backend traducidos.
    const recuperacion = (await screen.findByText("Días sin quiebre")).closest("table")!;
    expect(within(recuperacion).getByText("Días con quiebre")).toBeTruthy();
    expect(within(recuperacion).queryByText("dias limpios")).toBeNull();
    expect(screen.getByRole("heading", { name: "Catálogo por comportamiento" })).toBeTruthy();
    expect(screen.queryByText(/make update/)).toBeNull();
  });

  it("pipeline muestra el registro y los comandos, sin botones que escriban", async () => {
    irA("/?screen=pipeline");
    montar();
    expect(await screen.findByRole("heading", { level: 1, name: "Pipeline" })).toBeTruthy();
    expect(screen.getByText("make update INPUT=data/incoming/lote.parquet")).toBeTruthy();
    expect(screen.getByText("sin cambios")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /ingerir|reentrenar|rollback/i })).toBeNull();
  });
});

describe("estado de muestra", () => {
  it("marca la muestra en dos lugares y el sello no se puede cerrar", async () => {
    vi.stubGlobal("fetch", servidor({ muestra: true }));
    montar();
    expect(await screen.findByText("Muestra")).toBeTruthy();
    expect(await screen.findByText(/Estos números no son los del panel completo/)).toBeTruthy();
    expect(await screen.findByText(/60 de 3.066 series/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /cerrar/i })).toBeNull();
  });
});

describe("idioma y tema", () => {
  // Sin preferencia guardada: es lo que ve quien abre la app por primera vez.
  beforeEach(() => window.localStorage.clear());

  const abrirPreferencias = async (nombre: RegExp) => {
    // Se busca afuera de `act`: adentro, el render que trae el botón no se aplica
    // hasta que `act` termina, y la búsqueda espera para siempre.
    const boton = await screen.findByRole("button", { name: nombre });
    await act(async () => {
      boton.click();
    });
  };

  it("arranca en inglés, con cifras y códigos en inglés", async () => {
    montar();
    const nav = await screen.findByRole("navigation", { name: "Screens" });
    expect(within(nav).getByRole("button", { name: "Dashboard" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Search series/ })).toBeTruthy();
    expect(document.documentElement.lang).toBe("en");
    // Punto decimal y tienda abreviada S en la tabla de reposición.
    expect((await screen.findAllByText("0.96")).length).toBeGreaterThan(0);
    expect(await screen.findByText("S12 · P0412")).toBeTruthy();
  });

  it("cambia el idioma desde Settings sin cerrar el panel y lo recuerda", async () => {
    montar();
    await abrirPreferencias(/^Settings$/);
    await act(async () => {
      within(screen.getByRole("group", { name: "Language" }))
        .getByRole("button", { name: "Español" })
        .click();
    });
    const nav = await screen.findByRole("navigation", { name: "Pantallas" });
    expect(within(nav).getByRole("button", { name: "Panel" })).toBeTruthy();
    expect((await screen.findAllByText("0,96")).length).toBeGreaterThan(0);
    // El panel sigue abierto y el botón elegido queda marcado.
    const idioma = screen.getByRole("group", { name: "Idioma" });
    expect(within(idioma).getByRole("button", { name: "Español" }).getAttribute("aria-pressed")).toBe("true");
    expect(document.documentElement.lang).toBe("es");
    expect(window.localStorage.getItem("blindside:idioma")).toBe("es");
  });

  it("acepta ?lang=es en el enlace, lo guarda y lo saca de la URL", async () => {
    irA("/?screen=alerts&lang=es");
    montar();
    expect(await screen.findByRole("heading", { level: 1, name: "Alertas" })).toBeTruthy();
    expect(window.localStorage.getItem("blindside:idioma")).toBe("es");
    expect(new URLSearchParams(window.location.search).has("lang")).toBe(false);
  });

  it("el tema se elige entre sistema, claro y oscuro, y se guarda", async () => {
    montar();
    await abrirPreferencias(/^Settings$/);
    const tema = screen.getByRole("group", { name: "Theme" });
    // Por defecto sigue al sistema, que en el stub de test es claro.
    expect(within(tema).getByRole("button", { name: "System" }).getAttribute("aria-pressed")).toBe("true");
    expect(document.documentElement.dataset.theme).toBe("light");
    await act(async () => {
      within(tema).getByRole("button", { name: "Dark" }).click();
    });
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem("blindside:tema")).toBe("oscuro");
    await act(async () => {
      within(tema).getByRole("button", { name: "System" }).click();
    });
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem("blindside:tema")).toBe("sistema");
  });

  it("Escape cierra el panel y devuelve el foco al botón", async () => {
    montar();
    await abrirPreferencias(/^Settings$/);
    expect(screen.getByRole("region", { name: "Settings" })).toBeTruthy();
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(screen.queryByRole("region", { name: "Settings" })).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: /^Settings$/ }));
  });
});
