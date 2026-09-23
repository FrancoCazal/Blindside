/**
 * Shell: 119 px de cromo fijo en tres regiones.
 *
 *   franja de estado  44 px  · logo, serie, toggle. Fondo superficie
 *   navegación        42 px  · dos pantallas hero destacadas, resto agrupado
 *   franja de contexto 33 px · cinco datos de confianza en 11,5 px
 *
 * El estado global y la navegación son dos contenedores visualmente distintos.
 * El toggle y el selector no son navegación y no pueden compartir contenedor con
 * ella: los separa el cambio de fondo (superficie contra papel) más la regla.
 *
 * Los KPIs de exactitud viven en la franja de contexto, en 11,5 px. Son estado,
 * no titular: la decisión es el titular y la evidencia va embebida en los
 * números que importan.
 */

import type { BacktestResponse, Health } from "../api/client";
import { conteoDeTotal, errorConDispersion, etiquetaFecha, porcentajeSimple } from "../format";
import { useEstado, type Pantalla } from "../state";
import { IconoAdvertencia, Logo, ToggleCensura } from "./piezas";

const PRIMARIAS: { id: Pantalla; rotulo: string }[] = [
  { id: "reorder", rotulo: "Reposición" },
  { id: "series", rotulo: "Serie individual" },
];

/**
 * La navegación tiene dos niveles. Primario: las dos pantallas hero. Secundario:
 * el resto agrupado bajo Evidencia y Diagnóstico. Un sidebar de siete ítems
 * iguales sería la estructura equivocada — repite el error del Streamlit, donde
 * todo pesa lo mismo y la decisión queda al lado de una métrica de diagnóstico.
 */
const GRUPOS: { rotulo: string; items: { id: Pantalla; rotulo: string }[] }[] = [
  {
    rotulo: "Evidencia",
    items: [
      { id: "overview", rotulo: "Vista general" },
      { id: "compare", rotulo: "Comparativa" },
    ],
  },
  {
    rotulo: "Diagnóstico",
    items: [
      { id: "explain", rotulo: "Explicabilidad" },
      { id: "health", rotulo: "Salud del modelo" },
      { id: "map", rotulo: "Mapa" },
    ],
  },
];

export function Shell({
  health,
  backtest,
  serieRotulo,
  onAbrirSelector,
  cantidades,
  children,
}: {
  health: Health | null;
  backtest: BacktestResponse | null;
  serieRotulo: string | null;
  onAbrirSelector: () => void;
  cantidades?: { antes: number; despues: number };
  children: React.ReactNode;
}) {
  const { pantalla, irA, basis, tema, alternarTema, anuncio } = useEstado();
  const panel = health?.panel ?? null;
  const modelo = health?.models.find((m) => m.basis === basis) ?? null;

  const mase = (backtest?.rows ?? [])
    .filter((r) => r.metric === "mase")
    .sort((a, b) => a.mean - b.mean)[0];
  const cobertura = health?.coverage_by_horizon ?? [];
  const coberturaMedia =
    cobertura.length > 0
      ? cobertura.reduce((a, c) => a + c.coverage_empirical, 0) / cobertura.length
      : null;

  return (
    <>
      {/* Región que anuncia el cambio de valor a los lectores de pantalla. */}
      <div aria-live="polite" role="status" style={posicionFueraDePantalla}>
        {anuncio}
      </div>

      <header className="shell">
        <div className="franja-estado">
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <Logo />
            <span
              style={{
                fontFamily: "var(--fuente-titulo)",
                fontWeight: 700,
                fontSize: 16,
                letterSpacing: "-.012em",
                color: "var(--tinta)",
              }}
            >
              blindside
            </span>
          </div>

          {/* El sello de muestra no se puede cerrar. Presentar 60 series como
              3.066 es el error que arruina una defensa. */}
          {panel?.is_sample && <span className="sello-muestra">Muestra</span>}

          <button
            type="button"
            onClick={onAbrirSelector}
            style={{
              fontSize: 12.5,
              color: "var(--secundaria)",
              borderBottom: "1px solid var(--regla-control)",
              paddingBottom: 1,
            }}
            aria-keyshortcuts="Control+K"
          >
            {serieRotulo ?? "Elegir serie"}
          </button>

          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
            <button
              type="button"
              className="rotulo"
              onClick={alternarTema}
              aria-label={`Cambiar a modo ${tema === "claro" ? "oscuro" : "claro"}`}
            >
              {tema === "claro" ? "Oscuro" : "Claro"}
            </button>
            <span className="rotulo">Viendo</span>
            <ToggleCensura cantidadAntes={cantidades?.antes} cantidadDespues={cantidades?.despues} />
          </div>
        </div>

        {panel?.is_sample && <BandaMuestra panel={panel} />}

        <nav className="nav" aria-label="Pantallas">
          <div className="nav-primario">
            {PRIMARIAS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => irA(p.id)}
                aria-current={pantalla === p.id ? "page" : undefined}
              >
                {p.rotulo}
              </button>
            ))}
          </div>
          <div className="nav-separador" />
          {GRUPOS.map((grupo) => (
            <div className="nav-grupo" key={grupo.rotulo}>
              <span className="rotulo">{grupo.rotulo}</span>
              {grupo.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => irA(item.id)}
                  aria-current={pantalla === item.id ? "page" : undefined}
                >
                  {item.rotulo}
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="franja-contexto">
          {mase ? (
            <span>
              MASE <strong className="tinta">{errorConDispersion(mase.mean, mase.std)}</strong> · peor
              origen {mase.worst_origin.toFixed(3).replace(".", ",")} ({mase.model_name})
            </span>
          ) : (
            <span>MASE sin medir · falta correr el backtest</span>
          )}

          {coberturaMedia != null ? (
            <span>
              Cobertura empírica {porcentajeSimple(coberturaMedia * 100)} · nominal{" "}
              {porcentajeSimple((health?.coverage_nominal ?? 0.9) * 100)}
            </span>
          ) : (
            <span title={health?.coverage_note ?? undefined}>
              Cobertura empírica sin medir · nominal{" "}
              {porcentajeSimple((health?.coverage_nominal ?? 0.9) * 100)}
            </span>
          )}

          <span>
            Entrenado hasta {modelo?.trained_until ? etiquetaFecha(modelo.trained_until) : "—"}
          </span>

          {/* Esta línea evita una demo fallida: durante el desarrollo se sirvió un
              artefacto entrenado sobre 60 series contra el panel completo. */}
          <span style={panel?.is_sample ? { color: "var(--advertencia)", fontWeight: 600 } : undefined}>
            {modelo?.n_series_in_panel != null && panel
              ? `${conteoDeTotal(modelo.n_series_in_panel, panel.n_series)} series conocidas por el modelo`
              : "El modelo cargado no declara series"}
          </span>
        </div>
      </header>

      <div className="solo-angosto" style={{ padding: "var(--e6) var(--e5)" }}>
        <h2>Hace falta más ancho</h2>
        <p className="nota" style={{ maxWidth: "60ch" }}>
          Esta interfaz está diseñada a 1180 px y soportada hasta 1024. Abajo de eso las cifras de
          decisión bajarían de 19 px y la tabla perdería columnas que sostienen la comparación.
        </p>
      </div>
      <div className="solo-ancho">{children}</div>
    </>
  );
}

function BandaMuestra({ panel }: { panel: NonNullable<Health["panel"]> }) {
  return (
    <div className="banda-muestra" role="note">
      <IconoAdvertencia />
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontFamily: "var(--fuente-titulo)",
            fontWeight: 600,
            fontSize: 14,
            letterSpacing: "-.008em",
            color: "var(--advertencia-texto)",
          }}
        >
          Estos números no son los del panel completo
        </div>
        <div className="tabular" style={{ fontSize: 12.5, color: "var(--secundaria)", marginTop: 3 }}>
          Los datos vienen de <code style={{ fontFamily: "inherit" }}>data/sample/</code>:{" "}
          <strong style={{ fontWeight: 600 }}>
            {conteoDeTotal(panel.n_series, panel.reference_n_series)} series
          </strong>
          , {conteoDeTotal(panel.n_stores, panel.reference_n_stores)} tiendas,{" "}
          {conteoDeTotal(panel.n_products, panel.reference_n_products)} productos. Las métricas de
          error y el uplift de recuperación se calculan sobre esa muestra y no son comparables con
          los del panel completo.
        </div>
      </div>
      <span
        className="nota"
        style={{
          marginLeft: "auto",
          flex: "none",
          alignSelf: "center",
          color: "var(--advertencia-texto)",
          border: "1px solid var(--advertencia-borde)",
          padding: "5px 10px",
        }}
      >
        Cargar el panel: <code style={{ fontFamily: "inherit" }}>make data &amp;&amp; make recover</code>
      </span>
    </div>
  );
}

/** Oculta visualmente sin sacar del árbol de accesibilidad. */
const posicionFueraDePantalla: React.CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  margin: -1,
  padding: 0,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
  border: 0,
};
