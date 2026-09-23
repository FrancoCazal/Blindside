/**
 * Shell de aplicación: barra lateral, barra superior, barra de filtros, contenido.
 *
 * Reemplaza al cromo horizontal de 119 px en tres bandas. El audit visual mostró
 * por qué: con el cromo a ancho completo y el cuerpo en una columna de 1180 px, la
 * interfaz usaba el 61 % del viewport a 1920 px y se leía como un informe impreso
 * con una barra de aplicación encima. Y los nueve destinos en una tira horizontal
 * no se leían como dos grupos, que era justamente lo que el agrupado buscaba.
 *
 * La jerarquía del handoff se conserva y se refuerza: las dos pantallas hero pesan
 * más que el resto — otra familia tipográfica y mayor tamaño —, los KPI de
 * exactitud siguen siendo estado y no titular, y la decisión es lo primero que el
 * ojo encuentra. Lo que cambia es la estructura, no la jerarquía.
 */

import { useState } from "react";

import type { BacktestResponse, Health } from "../api/client";
import { conteoDeTotal, errorConDispersion, etiquetaFecha, porcentajeSimple } from "../format";
import { useEstado, type Pantalla } from "../state";
import { IconoAdvertencia, Logo, ToggleCensura } from "./piezas";

interface Item {
  id: Pantalla;
  rotulo: string;
  inicial: string;
}

const HERO: Item[] = [
  { id: "reorder", rotulo: "Reposición", inicial: "R" },
  { id: "series", rotulo: "Serie individual", inicial: "S" },
];

const GRUPOS: { rotulo: string; items: Item[] }[] = [
  {
    rotulo: "Evidencia",
    items: [
      { id: "overview", rotulo: "Vista general", inicial: "VG" },
      { id: "compare", rotulo: "Comparativa", inicial: "C" },
    ],
  },
  {
    rotulo: "Diagnóstico",
    items: [
      { id: "explain", rotulo: "Explicabilidad", inicial: "E" },
      { id: "health", rotulo: "Salud del modelo", inicial: "SM" },
      { id: "map", rotulo: "Mapa", inicial: "M" },
    ],
  },
];

export function Shell({
  health,
  backtest,
  backtestCargando,
  serieRotulo,
  onAbrirSelector,
  children,
}: {
  health: Health | null;
  backtest: BacktestResponse | null;
  backtestCargando?: boolean;
  serieRotulo: string | null;
  onAbrirSelector: () => void;
  children: React.ReactNode;
}) {
  const { pantalla, irA, basis, tema, alternarTema, anuncio, serie } = useEstado();
  const [colapsada, setColapsada] = useState(false);
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
      <div aria-live="polite" role="status" style={fueraDePantalla}>
        {anuncio}
      </div>

      <div className="app">
        <nav className="lateral" data-colapsada={colapsada} aria-label="Pantallas">
          <div className="marca">
            <Logo ancho={colapsada ? 22 : 30} />
            <span className="marca-nombre lateral-texto">blindside</span>
          </div>

          <div className="lateral-seccion">
            {HERO.map((item) => (
              <button
                key={item.id}
                type="button"
                className="lateral-item"
                data-hero="true"
                aria-current={pantalla === item.id ? "page" : undefined}
                onClick={() => irA(item.id)}
                title={item.rotulo}
              >
                <span className="lateral-inicial">{item.inicial}</span>
                <span className="lateral-texto">{item.rotulo}</span>
              </button>
            ))}
          </div>

          {GRUPOS.map((grupo) => (
            <div className="lateral-seccion" key={grupo.rotulo}>
              <span className="rotulo lateral-texto">{grupo.rotulo}</span>
              {grupo.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="lateral-item"
                  aria-current={pantalla === item.id ? "page" : undefined}
                  onClick={() => irA(item.id)}
                  title={item.rotulo}
                >
                  <span className="lateral-inicial">{item.inicial}</span>
                  <span className="lateral-texto">{item.rotulo}</span>
                </button>
              ))}
            </div>
          ))}

          <div className="lateral-pie">
            <button
              type="button"
              className="rotulo"
              onClick={() => setColapsada((c) => !c)}
              aria-expanded={!colapsada}
            >
              {colapsada ? "»" : "« Colapsar"}
            </button>
          </div>
        </nav>

        <div className="principal">
          <div className="barra-superior">
            {/* El sello de muestra no se puede cerrar: presentar 60 series como
                3.066 es el error que arruina una defensa. */}
            {panel?.is_sample && <span className="sello-muestra">Muestra</span>}

            <button
              type="button"
              className="selector-disparador"
              onClick={onAbrirSelector}
              aria-keyshortcuts="Control+K"
              aria-haspopup="dialog"
            >
              <span className="rotulo" style={{ flex: "none" }}>
                Serie
              </span>
              <span className="codigo">{serie ?? "—"}</span>
              <span className="descripcion">{serieRotulo ?? "elegir"}</span>
              <span aria-hidden="true" style={{ marginLeft: "auto", color: "var(--apagada)" }}>
                ⌄
              </span>
            </button>

            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
              <button
                type="button"
                className="selector-disparador"
                style={{ maxWidth: "none" }}
                onClick={alternarTema}
                aria-label={`Cambiar a modo ${tema === "claro" ? "oscuro" : "claro"}`}
              >
                {tema === "claro" ? "Modo oscuro" : "Modo claro"}
              </button>
              <span className="rotulo">Viendo</span>
              <ToggleCensura />
            </div>
          </div>

          {panel?.is_sample && <BandaMuestra panel={panel} />}

          <BarraFiltros />

          <div className="franja-contexto">
            {mase ? (
              <span>
                MASE <strong className="tinta">{errorConDispersion(mase.mean, mase.std)}</strong> ·
                peor origen {mase.worst_origin.toFixed(3).replace(".", ",")} ({mase.model_name})
              </span>
            ) : (
              <span>
                {backtestCargando ? "MASE · cargando…" : "MASE sin medir · falta correr el backtest"}
              </span>
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

            {/* Esta línea evita una demo fallida: durante el desarrollo se sirvió
                un artefacto entrenado sobre 60 series contra el panel completo. */}
            <span
              style={panel?.is_sample ? { color: "var(--advertencia)", fontWeight: 600 } : undefined}
            >
              {modelo?.n_series_in_panel != null && panel
                ? `${conteoDeTotal(modelo.n_series_in_panel, panel.n_series)} series conocidas por el modelo`
                : "El modelo cargado no declara series"}
            </span>

            <span>
              Datos {panel?.is_sample ? "de la muestra" : "del panel"} ·{" "}
              {panel ? `${panel.date_min} → ${panel.date_max}` : "—"}
            </span>
          </div>

          <main className="contenido">
            <div className="solo-angosto">
              <h2>Hace falta más ancho</h2>
              <p className="nota" style={{ maxWidth: "60ch" }}>
                Esta interfaz está diseñada a 1180 px de contenido y soportada hasta 1024. Abajo de
                eso las cifras de decisión bajarían de 19 px y la tabla perdería columnas que
                sostienen la comparación.
              </p>
            </div>
            <div className="solo-ancho">{children}</div>
          </main>
        </div>
      </div>
    </>
  );
}

/**
 * Barra de filtros. Es lo que faltaba para que esto se pueda usar: antes solo se
 * podía elegir *una* serie o ver las primeras 25 de 3.066, así que no había forma
 * de responder «qué pido para la tienda 12».
 *
 * Los filtros viven en la URL como el resto del estado, así que un enlace
 * reproduce la vista exacta.
 */
function BarraFiltros() {
  const { tienda, setTienda, clase, setClase, health } = useEstado();
  const tiendas = health?.panel ? Array.from({ length: health.panel.n_stores }, (_, i) => i) : [];

  return (
    <div className="barra-filtros">
      <span className="rotulo">Filtros</span>

      <label className="filtro">
        Tienda
        <select
          value={tienda ?? ""}
          onChange={(e) => setTienda(e.target.value === "" ? null : Number(e.target.value))}
        >
          <option value="">todas</option>
          {tiendas.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <label className="filtro">
        Clase de rotación
        <select value={clase ?? ""} onChange={(e) => setClase(e.target.value || null)}>
          <option value="">todas</option>
          <option value="alta">alta</option>
          <option value="media">media</option>
          <option value="baja">baja</option>
        </select>
      </label>

      {(tienda != null || clase != null) && (
        <button
          type="button"
          className="nota"
          onClick={() => {
            setTienda(null);
            setClase(null);
          }}
          style={{ textDecoration: "underline" }}
        >
          limpiar
        </button>
      )}

      <span className="nota" style={{ marginLeft: "auto" }}>
        Los filtros afectan la lista de reposición, no el modelo.
      </span>
    </div>
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
const fueraDePantalla: React.CSSProperties = {
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
