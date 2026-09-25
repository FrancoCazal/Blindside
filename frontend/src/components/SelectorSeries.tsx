/**
 * Selector de series (pantalla 4b).
 *
 * Búsqueda y no desplegable: 309 productos, 38 tiendas y 3.066 series. Un
 * `<select>` con 309 opciones no es usable. La búsqueda cubre el código de la
 * serie y la jerarquía de catálogo, que es lo que el dataset trae en vez de
 * nombres de producto.
 */

import { useEffect, useRef, useState } from "react";

import { api, type SeriesItem } from "../api/client";
import { conteoDeTotal } from "../format";
import { IconoLupa } from "./piezas";

/** Referencia estable mientras la búsqueda todavía no devolvió resultados. */
const SIN_RESULTADOS: SeriesItem[] = [];

export function SelectorSeries({
  abierto,
  onCerrar,
  onElegir,
}: {
  abierto: boolean;
  onCerrar: () => void;
  onElegir: (serie: SeriesItem) => void;
}) {
  const [consulta, setConsulta] = useState("");
  const [pagina, setPagina] = useState<{ items: SeriesItem[]; total: number } | null>(null);
  const [activo, setActivo] = useState(0);
  const campo = useRef<HTMLInputElement>(null);
  const dialogo = useRef<HTMLDivElement>(null);
  const focoAnterior = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!abierto) return;
    focoAnterior.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    campo.current?.focus();
    return () => focoAnterior.current?.focus();
  }, [abierto]);

  // Búsqueda incremental contra la API. El servidor filtra: con 3.066 series
  // traer todo al cliente para filtrar acá sería mandar el panel por la red.
  useEffect(() => {
    if (!abierto) return;
    let vivo = true;
    const id = window.setTimeout(() => {
      api
        .series({ q: consulta || undefined, limit: 40 })
        .then((r) => {
          if (vivo) {
            setPagina({ items: r.items, total: r.total });
            setActivo(0);
          }
        })
        .catch(() => {
          if (vivo) setPagina({ items: [], total: 0 });
        });
    }, 90);
    return () => {
      vivo = false;
      window.clearTimeout(id);
    };
  }, [consulta, abierto]);

  const items = pagina?.items ?? SIN_RESULTADOS;
  useEffect(() => {
    if (!abierto || !items[activo]) return;
    document.getElementById(`serie-opcion-${items[activo].series_id}`)?.scrollIntoView({
      block: "nearest",
    });
  }, [abierto, activo, items]);

  if (!abierto) return null;

  const alTeclear = (e: React.KeyboardEvent) => {
    if (e.key === "Tab") {
      const alcanzables = Array.from(
        dialogo.current?.querySelectorAll<HTMLElement>(
          'input:not([tabindex="-1"]), button:not([disabled]):not([tabindex="-1"]), [href], [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter((el) => el.getClientRects().length > 0);
      if (alcanzables.length > 0) {
        const actual = alcanzables.indexOf(document.activeElement as HTMLElement);
        const salePorAtras = e.shiftKey && actual <= 0;
        const salePorAdelante = !e.shiftKey && actual === alcanzables.length - 1;
        if (salePorAtras || salePorAdelante) {
          e.preventDefault();
          (salePorAtras ? alcanzables.at(-1) : alcanzables[0])?.focus();
        }
      }
    }
    if (e.key === "Escape") {
      e.preventDefault();
      onCerrar();
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActivo((i) => Math.min(items.length - 1, i + 1));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActivo((i) => Math.max(0, i - 1));
    }
    if (e.key === "Enter" && items[activo]) {
      e.preventDefault();
      onElegir(items[activo]);
      onCerrar();
    }
  };

  return (
    <div className="overlay" onMouseDown={onCerrar}>
      <div
        ref={dialogo}
        className="selector"
        role="dialog"
        aria-modal="true"
        aria-label="Buscar serie"
        onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={alTeclear}
      >
        <div className="selector-campo">
          <IconoLupa />
          <input
            ref={campo}
            role="combobox"
            aria-expanded="true"
            aria-controls="resultados-series"
            aria-autocomplete="list"
            aria-activedescendant={items[activo] ? `serie-opcion-${items[activo].series_id}` : undefined}
            value={consulta}
            onChange={(e) => setConsulta(e.target.value)}
            placeholder="Tienda, producto o código de serie"
            aria-label="Buscar serie"
          />
          <span className="nota" style={{ flex: "none" }}>
            {pagina ? conteoDeTotal(items.length, pagina.total) : "…"}
          </span>
        </div>

        <div
          id="resultados-series"
          className="selector-resultados"
          role="listbox"
          aria-label="Resultados"
          tabIndex={-1}
        >
          {items.map((s, i) => (
            <button
              id={`serie-opcion-${s.series_id}`}
              key={s.series_id}
              type="button"
              tabIndex={-1}
              className="resultado"
              data-activo={i === activo}
              role="option"
              aria-selected={i === activo}
              onMouseEnter={() => setActivo(i)}
              onClick={() => {
                onElegir(s);
                onCerrar();
              }}
            >
              <span className="rotulo">Serie</span>
              <span className="codigo">{s.series_id}</span>
              <span className="descripcion">{s.label}</span>
            </button>
          ))}
          {items.length === 0 && (
            <div className="nota" style={{ padding: "12px 16px" }}>
              Sin resultados para «{consulta}».
            </div>
          )}
        </div>

        <div className="selector-pie">
          <span>↑↓ mover</span>
          <span>↵ abrir</span>
          <span>esc cerrar</span>
          <button
            type="button"
            className="boton-sutil"
            style={{ marginLeft: "auto" }}
            onClick={onCerrar}
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
