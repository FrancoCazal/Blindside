/**
 * Controles que viven **dentro** de las pantallas donde actúan.
 *
 * En la versión anterior el toggle de base, los filtros y el ratio estaban en el
 * cromo global: los filtros se veían en diez pantallas y aplicaban en dos, y el
 * toggle no cambiaba nada en siete. Regla 3 de `docs/rediseno_frontend.md`.
 */

import type { ReactNode } from "react";

import { RATIOS, cuantilCritico, lecturaRatio } from "../domain";
import { cuantil, magnitud } from "../format";
import { t } from "../i18n";
import { useEstado } from "../state";

/** Encabezado de pantalla: título, una línea de contexto y controles a la derecha. */
export function Encabezado({
  titulo,
  contexto,
  children,
}: {
  titulo: ReactNode;
  contexto?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="tablero-encabezado">
      <h1>{titulo}</h1>
      {contexto && <span className="nota">{contexto}</span>}
      {children && <div className="encabezado-controles">{children}</div>}
    </div>
  );
}

/**
 * Ratio de costo Co/Cu. Cada botón muestra el cuantil que produce, así que la
 * relación entre ratio y cuantil no necesita tooltip.
 */
export function RatioCosto({ compacto = false }: { compacto?: boolean }) {
  const { ratio, setRatio } = useEstado();
  const textos = t().ratio;
  const lectura = lecturaRatio(ratio) ?? textos.personalizado;
  // En una columna angosta el cuantil no entra en cada botón: va una sola vez,
  // el del ratio elegido, en la línea de lectura.
  return (
    <div className="control">
      <span className="rotulo">{textos.rotulo}</span>
      <div
        className="ratios ratios-compactos"
        data-compacto={compacto ? "true" : undefined}
        role="group"
        aria-label={textos.aria}
      >
        {RATIOS.map((r) => (
          <button
            key={r.co}
            type="button"
            aria-pressed={r.co === ratio}
            onClick={() => setRatio(r.co)}
            title={`${lecturaRatio(r.co)} · q* ${cuantil(cuantilCritico(1, r.co))}`}
          >
            <span className="valor">{magnitud(r.co, 1)}</span>
            {!compacto && <span className="cuantil">q* {cuantil(cuantilCritico(1, r.co))}</span>}
          </button>
        ))}
      </div>
      <span className="nota">
        {compacto && `q* ${cuantil(cuantilCritico(1, ratio))} · `}
        {lectura}
      </span>
    </div>
  );
}

/**
 * Tienda y clase de rotación. La lista de tiendas sale de la API: los ids **no son
 * contiguos** (0, 41, 48…) y armarla con `0…n` dejaba 37 de 38 opciones vacías.
 *
 * Los valores de rotación (`alta`, `media`, `baja`) son los de la API y no se
 * traducen; solo se traduce lo que se lee.
 */
export function FiltrosCatalogo() {
  const { tienda, setTienda, clase, setClase, health } = useEstado();
  const tiendas = health?.panel?.store_ids ?? [];
  const textos = t();
  return (
    <div className="control control-filtros">
      <label className="filtro">
        {textos.filtros.tienda}
        <select
          value={tienda ?? ""}
          onChange={(e) => setTienda(e.target.value === "" ? null : Number(e.target.value))}
        >
          <option value="">{textos.filtros.todas}</option>
          {tiendas.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </label>
      <label className="filtro">
        {textos.filtros.rotacion}
        <select value={clase ?? ""} onChange={(e) => setClase(e.target.value || null)}>
          <option value="">{textos.filtros.todas}</option>
          {(["alta", "media", "baja"] as const).map((banda) => (
            <option key={banda} value={banda}>
              {textos.bandas[banda]}
            </option>
          ))}
        </select>
      </label>
      {(tienda != null || clase != null) && (
        <button
          type="button"
          className="boton-sutil"
          onClick={() => {
            setTienda(null);
            setClase(null);
          }}
        >
          {textos.filtros.limpiar}
        </button>
      )}
    </div>
  );
}

/**
 * Detalle técnico plegado al pie de la pantalla. Los nombres de endpoint, las
 * fórmulas y las verificaciones del método van acá y no en el texto principal.
 */
export function ComoSeCalcula({ titulo, children }: { titulo?: string; children: ReactNode }) {
  return (
    <details className="como-se-calcula">
      <summary>{titulo ?? t().comun.comoSeCalcula}</summary>
      <div className="como-se-calcula-cuerpo">{children}</div>
    </details>
  );
}
