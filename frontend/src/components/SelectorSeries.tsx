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

  useEffect(() => {
    if (abierto) campo.current?.focus();
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

  if (!abierto) return null;

  const items = pagina?.items ?? [];

  const alTeclear = (e: React.KeyboardEvent) => {
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
            value={consulta}
            onChange={(e) => setConsulta(e.target.value)}
            placeholder="Tienda, producto o código de serie"
            aria-label="Buscar serie"
          />
          <span className="nota" style={{ flex: "none" }}>
            {pagina ? conteoDeTotal(items.length, pagina.total) : "…"}
          </span>
        </div>

        <div role="listbox" aria-label="Resultados">
          {items.map((s, i) => (
            <button
              key={s.series_id}
              type="button"
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
          <span style={{ marginLeft: "auto" }}>b alterna la base de cálculo</span>
        </div>
      </div>
    </div>
  );
}
