/**
 * Mapa de productos.
 *
 * Proyección PCA de los 309 productos sobre seis features de comportamiento de
 * demanda. La varianza explicada va en pantalla: un scatter sin ella invita a leer
 * distancias que la proyección no conserva.
 *
 * Las bandas de rotación son cortes por cuantil, así que sus tamaños son por
 * construcción. La pregunta que esta pantalla responde no es cuántos productos hay
 * en cada banda sino si el catálogo se separa en grupos de comportamiento o es un
 * continuo — y con 67 % de varianza en dos componentes, se puede mirar.
 */

import { useState } from "react";

import { api, type ProductPoint } from "../api/client";
import { conteo, magnitud, porcentajeSimple } from "../format";
import { useAsincrono } from "../state";
import { Esqueleto } from "../components/estados";

const ANCHO = 620;
const ALTO = 360;
const PAD = 26;

/** Tres opacidades de tinta según banda de rotación, sin color. */
const OPACIDAD: Record<string, number> = { alta: 0.45, media: 0.3, baja: 0.16 };

export function PantallaMapa({
  serieActiva,
  onElegirProducto,
}: {
  serieActiva: string | null;
  onElegirProducto?: (productId: number) => void;
}) {
  const datos = useAsincrono(() => api.productsMap(), []);
  const [activo, setActivo] = useState<ProductPoint | null>(null);

  if (datos.cargando && !datos.datos) return <Esqueleto filas={4} />;
  if (datos.error) throw datos.error;
  if (!datos.datos) return null;

  const { points, explained_variance, features, method } = datos.datos;
  const productoDeLaSerie = serieActiva ? Number(serieActiva.split("_")[1]) : null;
  const destacado = activo ?? points.find((p) => p.product_id === productoDeLaSerie) ?? null;

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const x = escala(Math.min(...xs), Math.max(...xs), PAD, ANCHO - PAD);
  const y = escala(Math.min(...ys), Math.max(...ys), ALTO - PAD, PAD);

  const maxDemanda = Math.max(...points.map((p) => p.demanda_media), 1e-9);
  const conteos = contarBandas(points);
  const varianzaTotal = explained_variance.reduce((a, b) => a + b, 0);

  return (
    <div className="pagina">
      <div className="tarjeta" style={{ padding: "18px var(--e5)", maxWidth: 700 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 4 }}>
          <h2>Mapa de productos</h2>
          <span className="nota">
            {conteo(points.length)} productos · {method.toUpperCase()} ·{" "}
            {porcentajeSimple(varianzaTotal * 100, 1)} de la varianza en 2D
          </span>
        </div>
        <p className="nota" style={{ maxWidth: "80ch", marginBottom: 14 }}>
          Proyección sobre {features.length} features de comportamiento: {features.join(", ")}. Las
          dos componentes capturan {explained_variance.map((v) => porcentajeSimple(v * 100, 1)).join(" y ")}
          , así que la distancia entre puntos lejanos es informativa y la de puntos cercanos no tanto.
        </p>

        <svg
          viewBox={`0 0 ${ANCHO} ${ALTO}`}
          className="grafico"
          style={{ background: "var(--superficie)" }}
          role="img"
          aria-label={`Proyección de ${points.length} productos por comportamiento de demanda`}
        >
          {points.map((p) => {
            const esDestacado = destacado?.product_id === p.product_id;
            const radio = 1.6 + (p.demanda_media / maxDemanda) * 1.9;
            return (
              <g key={p.product_id}>
                <circle
                  cx={x(p.x)}
                  cy={y(p.y)}
                  r={esDestacado ? radio : radio}
                  fill={`color-mix(in srgb, var(--tinta) ${Math.round(
                    (OPACIDAD[p.rotation_band] ?? 0.3) * 100,
                  )}%, transparent)`}
                />
                {esDestacado && (
                  <>
                    <circle
                      cx={x(p.x)}
                      cy={y(p.y)}
                      r="6.5"
                      fill="none"
                      stroke="var(--recuperado)"
                      strokeWidth="1.4"
                    />
                    <circle cx={x(p.x)} cy={y(p.y)} r="1.8" fill="var(--recuperado)" />
                  </>
                )}
                {/* Área de clic generosa: los puntos son de 2 a 3,5 px. */}
                <circle
                  cx={x(p.x)}
                  cy={y(p.y)}
                  r="7"
                  fill="transparent"
                  style={{ cursor: "pointer" }}
                  onClick={() => {
                    setActivo(p);
                    onElegirProducto?.(p.product_id);
                  }}
                >
                  <title>{`Producto ${p.product_id} · rotación ${p.rotation_band}`}</title>
                </circle>
              </g>
            );
          })}
        </svg>

        <div className="leyenda" style={{ marginTop: 10 }}>
          {(["alta", "media", "baja"] as const).map((banda) => (
            <span key={banda}>
              <svg width="12" height="12" aria-hidden="true">
                <circle
                  cx="6"
                  cy="6"
                  r="3.2"
                  fill={`color-mix(in srgb, var(--tinta) ${Math.round(OPACIDAD[banda] * 100)}%, transparent)`}
                />
              </svg>
              rotación {banda} · {conteo(conteos[banda] ?? 0)}
            </span>
          ))}
        </div>

        {destacado && (
          <div className="bloque" style={{ marginTop: 14 }}>
            <div className="rotulo" style={{ marginBottom: 6 }}>
              Producto {destacado.product_id}
            </div>
            <dl
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: "4px 12px",
                margin: 0,
                fontSize: 12,
              }}
            >
              <dt className="apagada">Banda de rotación</dt>
              <dd style={{ margin: 0, textAlign: "right" }}>{destacado.rotation_band}</dd>
              <dt className="apagada">Demanda media</dt>
              <dd style={{ margin: 0, textAlign: "right" }}>{magnitud(destacado.demanda_media)}</dd>
              <dt className="apagada">Días con quiebre</dt>
              <dd style={{ margin: 0, textAlign: "right" }}>
                {porcentajeSimple(destacado.tasa_quiebre * 100, 1)}
              </dd>
              <dt className="apagada">Series (tiendas)</dt>
              <dd style={{ margin: 0, textAlign: "right" }}>{conteo(destacado.n_series)}</dd>
            </dl>
          </div>
        )}

        <p className="nota" style={{ marginTop: 14, maxWidth: "80ch" }}>
          Las bandas son cortes por cuantil de la demanda media — 0,50 y 0,85 —, así que sus tamaños
          son por construcción y no un hallazgo: baja es siempre la mitad del catálogo, media el 35 %
          y alta el 15 %. Lo que esta pantalla muestra es otra cosa: si el catálogo se separa en
          grupos de <em>comportamiento</em> o es un continuo. Un punto lejos del centro es un producto
          cuya combinación de nivel, variabilidad y censura no se parece a la del resto.
        </p>
      </div>
    </div>
  );
}

function escala(min: number, max: number, desde: number, hasta: number) {
  const rango = max - min || 1;
  return (v: number) => desde + ((v - min) / rango) * (hasta - desde);
}

function contarBandas(points: ProductPoint[]): Record<string, number> {
  return points.reduce<Record<string, number>>((acc, p) => {
    acc[p.rotation_band] = (acc[p.rotation_band] ?? 0) + 1;
    return acc;
  }, {});
}
