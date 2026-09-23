/**
 * Cliente de la API. Los tipos NO se escriben a mano: salen de `schema.d.ts`,
 * que se genera del OpenAPI de FastAPI con `npm run gen:api`. El contrato vive
 * en `api/schemas.py` y un rename allá rompe la compilación acá, que es
 * exactamente lo que se quiere.
 *
 * La base se apunta con VITE_API_BASE. Por defecto va directo a 127.0.0.1:8000
 * y **no** por un proxy de Vite: el proxy haría que las llamadas fueran
 * same-origin y esconderían un CORS mal configurado hasta el despliegue.
 */

import type { components } from "./schema";

type Schemas = components["schemas"];

export type Health = Schemas["Health"];
export type ModelStatus = Schemas["ModelStatus"];
export type PanelInfo = Schemas["PanelInfo"];
export type CoveragePoint = Schemas["CoveragePoint"];
export type SeriesPage = Schemas["SeriesPage"];
export type SeriesItem = Schemas["SeriesItem"];
export type SeriesHistory = Schemas["SeriesHistory"];
export type HistoryPoint = Schemas["HistoryPoint"];
export type StockoutRun = Schemas["StockoutRun"];
export type ForecastResponse = Schemas["ForecastResponse"];
export type ForecastPoint = Schemas["ForecastPoint"];
export type ReorderResponse = Schemas["ReorderResponse"];
export type ReorderLine = Schemas["ReorderLine"];
export type BacktestResponse = Schemas["BacktestResponse"];
export type BacktestBreakdown = Schemas["BacktestBreakdown"];
export type OriginMetric = Schemas["OriginMetric"];
export type HorizonMetric = Schemas["HorizonMetric"];
export type BandMetric = Schemas["BandMetric"];
export type ExplainResponse = Schemas["ExplainResponse"];
export type ShapContribution = Schemas["ShapContribution"];
export type ProductMap = Schemas["ProductMap"];
export type ProductPoint = Schemas["ProductPoint"];
export type Basis = Schemas["Basis"];

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://127.0.0.1:8000";

/**
 * Falla de la API. `kind` distingue los dos casos que se arreglan distinto:
 * `network` es la API caída (pantalla 5c) y `status` es una respuesta con
 * código, que casi siempre trae un `detail` con la instrucción del backend.
 */
export class ApiError extends Error {
  readonly kind: "network" | "status";
  readonly status: number | null;
  readonly endpoint: string;

  constructor(
    message: string,
    opts: { kind: "network" | "status"; status?: number | null; endpoint: string },
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = opts.kind;
    this.status = opts.status ?? null;
    this.endpoint = opts.endpoint;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (cause) {
    // fetch solo rechaza por red, DNS o CORS. Los tres significan que no hay
    // con quién hablar, que es el estado "API caída" y no "sin datos".
    throw new ApiError(cause instanceof Error ? cause.message : "sin conexión", {
      kind: "network",
      endpoint: path,
    });
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* respuesta sin cuerpo JSON: queda el statusText */
    }
    throw new ApiError(detail, { kind: "status", status: response.status, endpoint: path });
  }

  return (await response.json()) as T;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/health"),

  series: (
    params: {
      q?: string;
      storeId?: number;
      rotationBand?: string;
      limit?: number;
      offset?: number;
    } = {},
  ) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.storeId != null) qs.set("store_id", String(params.storeId));
    if (params.rotationBand) qs.set("rotation_band", params.rotationBand);
    qs.set("limit", String(params.limit ?? 100));
    qs.set("offset", String(params.offset ?? 0));
    return request<SeriesPage>(`/series?${qs.toString()}`);
  },

  history: (seriesId: string, days?: number) =>
    request<SeriesHistory>(
      `/series/${encodeURIComponent(seriesId)}/history${days ? `?days=${days}` : ""}`,
    ),

  historyBatch: (seriesIds: string[], days?: number) =>
    post<{ series: SeriesHistory[] }>("/series/history", { series_ids: seriesIds, days }),

  forecast: (args: {
    seriesIds: string[];
    horizon?: number;
    coverage?: number;
    recoverCensoring: boolean;
  }) =>
    post<ForecastResponse>("/forecast", {
      series_ids: args.seriesIds,
      horizon: args.horizon ?? 7,
      coverage: args.coverage ?? 0.9,
      recover_censoring: args.recoverCensoring,
    }),

  reorder: (args: {
    seriesIds: string[];
    horizon?: number;
    cu?: number;
    co: number;
    recoverCensoring: boolean;
  }) =>
    post<ReorderResponse>("/reorder", {
      series_ids: args.seriesIds,
      horizon: args.horizon ?? 7,
      cu: args.cu ?? 1,
      co: args.co,
      recover_censoring: args.recoverCensoring,
    }),

  backtest: () => request<BacktestResponse>("/backtest"),

  backtestBreakdown: () => request<BacktestBreakdown>("/backtest/breakdown"),

  censoring: () =>
    request<{
      summary: Record<string, number>;
      comparison: Record<string, number | string>[];
      note: string;
    }>("/censoring"),

  explain: (args: {
    seriesId: string;
    dt: string;
    topK?: number;
    recoverCensoring: boolean;
  }) =>
    post<ExplainResponse>("/explain", {
      series_id: args.seriesId,
      dt: args.dt,
      top_k: args.topK ?? 12,
      recover_censoring: args.recoverCensoring,
    }),

  productsMap: () => request<ProductMap>("/products/map"),
};
