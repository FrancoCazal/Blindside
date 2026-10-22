/**
 * Shell de aplicación: barra lateral, una sola barra superior y el contenido.
 *
 * La versión anterior tenía tres bandas — barra superior, filtros y una franja
 * de contexto con MASE, cobertura, fecha de corte y conteos — que sumaban unos
 * 165 px antes del contenido y repetían en todas las pantallas cifras que ya
 * tenían una pantalla dueña. Ver `docs/rediseno_frontend.md`, sección 4.
 *
 * Lo que queda en el cromo es lo que vale para cualquier pantalla: navegar,
 * buscar una serie, saber si se está viendo la muestra o si el modelo quedó
 * atrás de los datos, y las preferencias de idioma y tema.
 */

import { useState } from "react";

import type { Health } from "../api/client";
import { conteo, conteoDeTotal } from "../format";
import { t } from "../i18n";
import { useEstado, type Pantalla } from "../state";
import { IconoAdvertencia, IconoLupa, Logo } from "./piezas";
import { Preferencias } from "./Preferencias";

type Grupo = "operacion" | "analisis" | "sistema";

/** La estructura de la navegación. Los nombres salen del diccionario. */
const GRUPOS: { id: Grupo; items: Pantalla[] }[] = [
  { id: "operacion", items: ["panel", "alerts", "reorder", "series"] },
  { id: "analisis", items: ["models", "data"] },
  { id: "sistema", items: ["pipeline"] },
];

export function Shell({
  health,
  onAbrirSelector,
  children,
}: {
  health: Health | null;
  onAbrirSelector: () => void;
  children: React.ReactNode;
}) {
  const { pantalla, irA, anuncio } = useEstado();
  const [colapsada, setColapsada] = useState(false);
  const panel = health?.panel ?? null;
  const fresca = health?.freshness ?? null;
  const textos = t();
  const nav = textos.nav;

  return (
    <>
      <div aria-live="polite" role="status" style={fueraDePantalla}>
        {anuncio}
      </div>

      <div className="app">
        <nav className="lateral" data-colapsada={colapsada} aria-label={nav.aria}>
          <div className="marca">
            <Logo ancho={colapsada ? 22 : 30} />
            <span className="marca-nombre lateral-texto">blindside</span>
          </div>

          {GRUPOS.map((grupo) => (
            <div className="lateral-seccion" key={grupo.id}>
              <span className="rotulo lateral-texto">{nav.grupos[grupo.id]}</span>
              {grupo.items.map((id) => (
                <button
                  key={id}
                  type="button"
                  className="lateral-item"
                  aria-current={pantalla === id ? "page" : undefined}
                  onClick={() => irA(id)}
                  title={nav.pantallas[id]}
                >
                  {/* La inicial solo se ve con la barra colapsada, donde es lo único que queda. */}
                  <span className="lateral-inicial" aria-hidden="true">
                    {nav.iniciales[id]}
                  </span>
                  <span className="lateral-texto">{nav.pantallas[id]}</span>
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
              {colapsada ? nav.expandir : nav.colapsar}
            </button>
          </div>
        </nav>

        <div className="principal">
          <div className="barra-superior">
            <button
              type="button"
              className="selector-disparador buscador"
              onClick={onAbrirSelector}
              aria-keyshortcuts="Control+K"
              aria-haspopup="dialog"
            >
              <IconoLupa />
              <span className="descripcion">{textos.cromo.buscar}</span>
              <kbd className="tecla">{textos.cromo.tecla}</kbd>
            </button>

            {/* El sello de muestra no se puede cerrar: presentar 60 series como
                3.066 es el error que arruina una defensa. */}
            {panel?.is_sample && <span className="sello-muestra">{textos.cromo.muestra}</span>}

            {fresca?.status === "desfasado" && (
              <button
                type="button"
                className="sello-desfase"
                onClick={() => irA("pipeline")}
                title={textos.cromo.desfaseTitulo}
              >
                <IconoAdvertencia tamano={14} />
                {textos.cromo.desfase(conteo(fresca.days_behind ?? 0))}
              </button>
            )}

            <Preferencias />
          </div>

          {panel?.is_sample && <BandaMuestra panel={panel} />}

          <main className="contenido">
            <div className="solo-angosto">
              <h2>{textos.cromo.angostoTitulo}</h2>
              <p className="nota" style={{ maxWidth: "60ch" }}>
                {textos.cromo.angostoTexto}
              </p>
            </div>
            <div className="solo-ancho">{children}</div>
          </main>
        </div>
      </div>
    </>
  );
}

function BandaMuestra({ panel }: { panel: NonNullable<Health["panel"]> }) {
  const cromo = t().cromo;
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
          {cromo.muestraTitulo}
        </div>
        <div className="tabular" style={{ fontSize: 12.5, color: "var(--secundaria)", marginTop: 3 }}>
          {cromo.muestraTexto(
            conteoDeTotal(panel.n_series, panel.reference_n_series),
            conteoDeTotal(panel.n_stores, panel.reference_n_stores),
            conteoDeTotal(panel.n_products, panel.reference_n_products),
          )}
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
        {cromo.muestraComando}{" "}
        <code style={{ fontFamily: "inherit" }}>make data &amp;&amp; make recover</code>
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
