/**
 * Catálogo por comportamiento: el mapa PCA de productos como bloque de Datos.
 *
 * Antes era una pantalla entera de 700 px con un párrafo explicando lo que el
 * mapa no muestra. Sirve como evidencia del análisis no supervisado, no como
 * pantalla de operación, así que vive como un bloque. Lo nuevo: el producto
 * elegido lleva a sus series.
 *
 * La varianza explicada va en pantalla: un scatter sin ella invita a leer
 * distancias que la proyección no conserva.
 */

import { useState } from "react";

import { api, type ProductPoint } from "../api/client";
import { conteo, magnitud, porcentajeSimple } from "../format";
import { t } from "../i18n";
import { useAsincrono } from "../state";

const ANCHO = 620;
const ALTO = 330;
const PAD = 24;

/** Tres opacidades de tinta según banda de rotación, sin color. */
const OPACIDAD: Record<string, number> = { alta: 0.5, media: 0.32, baja: 0.16 };

export function MapaCatalogo({ onElegirSerie }: { onElegirSerie: (id: string) => void }) {
  const datos = useAsincrono(() => api.productsMap(), []);
  const [activo, setActivo] = useState<ProductPoint | null>(null);
  const [buscando, setBuscando] = useState(false);

  const textos = t();
  const m = textos.mapa;
  const banda = (b: string) => textos.bandas[b] ?? b;

  if (datos.error) return <p className="nota">{m.error}</p>;
  if (!datos.datos) return <div className="hueso" style={{ height: ALTO }} />;

  const { points, explained_variance, features } = datos.datos;
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const x = escala(Math.min(...xs), Math.max(...xs), PAD, ANCHO - PAD);
  const y = escala(Math.min(...ys), Math.max(...ys), ALTO - PAD, PAD);
  const maxDemanda = Math.max(...points.map((p) => p.demanda_media), 1e-9);
  const varianza = explained_variance.reduce((a, b) => a + b, 0);
  const conteos = points.reduce<Record<string, number>>((acc, p) => {
    acc[p.rotation_band] = (acc[p.rotation_band] ?? 0) + 1;
    return acc;
  }, {});

  const irASerie = async (p: ProductPoint) => {
    setBuscando(true);
    try {
      // La serie de más demanda del producto no se conoce acá: se toma la primera
      // tienda que lo vende, que alcanza para llegar a su historia.
      // `_4` también matchea `_40`, `_400`…: se pide el máximo y se filtra exacto.
      const r = await api.series({ q: `_${p.product_id}`, limit: 5000 });
      const serie = r.items.find((s) => s.product_id === p.product_id);
      if (serie) onElegirSerie(serie.series_id);
    } finally {
      setBuscando(false);
    }
  };

  return (
    <div className="mapa">
      <div>
        <svg
          viewBox={`0 0 ${ANCHO} ${ALTO}`}
          className="grafico"
          style={{ background: "var(--superficie)" }}
          role="img"
          aria-label={m.aria(conteo(points.length))}
        >
          {points.map((p) => {
            const esActivo = activo?.product_id === p.product_id;
            const radio = 1.8 + (p.demanda_media / maxDemanda) * 2.2;
            return (
              <g key={p.product_id}>
                <circle
                  cx={x(p.x)}
                  cy={y(p.y)}
                  r={radio}
                  fill={`color-mix(in srgb, var(--tinta) ${Math.round((OPACIDAD[p.rotation_band] ?? 0.3) * 100)}%, transparent)`}
                />
                {esActivo && (
                  <circle cx={x(p.x)} cy={y(p.y)} r="7" fill="none" stroke="var(--tinta)" strokeWidth="1.6" />
                )}
                <circle
                  cx={x(p.x)}
                  cy={y(p.y)}
                  r="7"
                  fill="transparent"
                  style={{ cursor: "pointer" }}
                  onClick={() => setActivo(p)}
                >
                  <title>{m.punto(String(p.product_id), banda(p.rotation_band))}</title>
                </circle>
              </g>
            );
          })}
        </svg>
        <div className="leyenda">
          {(["alta", "media", "baja"] as const).map((b) => (
            <span key={b}>
              <svg width="12" height="12" aria-hidden="true">
                <circle
                  cx="6"
                  cy="6"
                  r="3.4"
                  fill={`color-mix(in srgb, var(--tinta) ${Math.round(OPACIDAD[b] * 100)}%, transparent)`}
                />
              </svg>
              {m.leyendaBanda(textos.bandas[b], conteo(conteos[b] ?? 0))}
            </span>
          ))}
          <span>{m.tamano}</span>
        </div>
      </div>

      <div className="mapa-lateral">
        <p className="nota">
          {m.texto(conteo(points.length), conteo(features.length), porcentajeSimple(varianza * 100, 1))}
        </p>
        {activo ? (
          <div className="bloque">
            <div className="rotulo" style={{ marginBottom: 6 }}>
              {m.producto(String(activo.product_id))}
            </div>
            <dl>
              <dt>{m.rotacion}</dt>
              <dd>{banda(activo.rotation_band)}</dd>
              <dt>{m.demanda}</dt>
              <dd>{magnitud(activo.demanda_media)}</dd>
              <dt>{m.quiebre}</dt>
              <dd>{porcentajeSimple(activo.tasa_quiebre * 100, 1)}</dd>
              <dt>{m.tiendas}</dt>
              <dd>{conteo(activo.n_series)}</dd>
            </dl>
            <button
              type="button"
              className="boton-sutil"
              style={{ marginTop: 10 }}
              disabled={buscando}
              onClick={() => void irASerie(activo)}
            >
              {m.verSerie}
            </button>
          </div>
        ) : (
          <p className="nota">{m.elegir}</p>
        )}
      </div>
    </div>
  );
}

function escala(min: number, max: number, desde: number, hasta: number) {
  const rango = max - min || 1;
  return (v: number) => desde + ((v - min) / rango) * (hasta - desde);
}
