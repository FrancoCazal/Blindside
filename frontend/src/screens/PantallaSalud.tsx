/**
 * Pantalla 4c · salud del modelo.
 *
 * Tres bloques, y lo que importa es que cada uno diga de dónde sale su número:
 * artefacto y cobertura son reales; la deriva de features **no existe** en el
 * backend, así que en vez de mostrar valores sintéticos con sello, este bloque
 * dice qué endpoint falta. El proyecto mide justamente la brecha entre lo
 * prometido y lo medido: inventar una medición acá sería contradecirlo.
 */

import type { Health } from "../api/client";
import { conteoDeTotal, magnitud, porcentajeSimple } from "../format";

export function PantallaSalud({ health }: { health: Health }) {
  const nominal = health.coverage_nominal ?? 0.9;
  const cobertura = health.coverage_by_horizon;
  const panel = health.panel;

  return (
    <div className="pagina">
      <div className="tarjeta" style={{ maxWidth: 556, padding: "18px var(--e5)" }}>
        <h2 style={{ marginBottom: 14 }}>Salud del modelo</h2>

        <section>
          <h3 style={{ fontSize: 16, marginBottom: 8 }}>Artefactos cargados</h3>
          {health.models.map((m) => (
            <div key={m.basis} style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <span className="tinta" style={{ fontWeight: 600, fontSize: 13 }}>
                  {m.basis === "recovered" ? "Demanda recuperada" : "Venta observada"}
                </span>
                <span className="nota">{m.artifact}</span>
                <span
                  className="nota"
                  style={{ marginLeft: "auto", color: m.loaded ? "var(--apagada)" : "var(--advertencia-texto)" }}
                >
                  {m.loaded ? "cargado" : "no disponible"}
                </span>
              </div>
              {m.loaded ? (
                <dl
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr auto",
                    gap: "4px 12px",
                    margin: "6px 0 0",
                    fontSize: 12,
                  }}
                >
                  <dt className="apagada">Modelo</dt>
                  <dd style={{ margin: 0, textAlign: "right" }}>{m.model_name}</dd>
                  <dt className="apagada">Target de entrenamiento</dt>
                  <dd style={{ margin: 0, textAlign: "right" }}>{m.target}</dd>
                  <dt className="apagada">Entrenado hasta</dt>
                  <dd style={{ margin: 0, textAlign: "right" }}>{m.trained_until}</dd>
                  <dt className="apagada">Series conocidas en el panel</dt>
                  <dd style={{ margin: 0, textAlign: "right" }}>
                    {conteoDeTotal(m.n_series_in_panel ?? 0, panel?.n_series)}
                  </dd>
                </dl>
              ) : (
                <div className="nota" style={{ marginTop: 4, color: "var(--advertencia-texto)" }}>
                  {m.error ?? "falta el artefacto; entrenar con make train"}
                </div>
              )}
            </div>
          ))}
        </section>

        <section className="bloque" style={{ marginTop: 14 }}>
          <h3 style={{ fontSize: 16, marginBottom: 8 }}>Cobertura empírica por horizonte</h3>
          {cobertura.length > 0 ? (
            <>
              <svg viewBox="0 0 300 120" className="grafico" role="img" aria-label="Cobertura por horizonte">
                {/* El nominal es una línea guionada: las barras que caen por
                    debajo se leen como desvío hacia abajo. */}
                <line
                  x1="0"
                  x2="300"
                  y1={100 - nominal * 90}
                  y2={100 - nominal * 90}
                  stroke="var(--eje)"
                  strokeDasharray="4 3"
                />
                {cobertura.map((c, i) => {
                  const ancho = 300 / cobertura.length;
                  const alto = c.coverage_empirical * 90;
                  return (
                    <g key={c.h}>
                      <rect
                        x={i * ancho + ancho * 0.2}
                        y={100 - alto}
                        width={ancho * 0.6}
                        height={alto}
                        fill="var(--horas-quiebre)"
                      />
                      <text
                        x={i * ancho + ancho / 2}
                        y={114}
                        textAnchor="middle"
                        fontSize="9"
                        fill="var(--apagada)"
                      >
                        h{c.h}
                      </text>
                    </g>
                  );
                })}
              </svg>
              <div className="nota" style={{ marginTop: 6 }}>
                Nominal {porcentajeSimple(nominal * 100)}. La degradación no es monótona y eso es
                correcto: con estacionalidad semanal el objetivo de h7 cae el mismo día de la semana
                que el origen.
              </div>
            </>
          ) : (
            <div className="nota">
              Sin medición. {health.coverage_note}
            </div>
          )}
        </section>

        <section className="bloque" style={{ marginTop: 14 }}>
          <h3 style={{ fontSize: 16, marginBottom: 8 }}>Deriva de features</h3>
          <div className="nota">
            No hay endpoint de deriva en la API, así que esta pantalla no la muestra. El diseño la
            contemplaba con datos sintéticos y sello <code style={{ fontFamily: "inherit" }}>sim</code>;
            preferimos el hueco declarado antes que tres barras inventadas en la pantalla que habla
            de confiabilidad del modelo.
          </div>
        </section>

        {panel && (
          <section className="bloque" style={{ marginTop: 14 }}>
            <h3 style={{ fontSize: 16, marginBottom: 8 }}>Datos servidos</h3>
            <dl
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: "4px 12px",
                margin: 0,
                fontSize: 12,
              }}
            >
              <dt className="apagada">Capa</dt>
              <dd style={{ margin: 0, textAlign: "right" }}>
                {panel.is_sample ? "data/sample (muestra commiteada)" : "data/processed"}
              </dd>
              <dt className="apagada">Series</dt>
              <dd style={{ margin: 0, textAlign: "right" }}>
                {conteoDeTotal(panel.n_series, panel.reference_n_series)}
              </dd>
              <dt className="apagada">Tiendas</dt>
              <dd style={{ margin: 0, textAlign: "right" }}>
                {conteoDeTotal(panel.n_stores, panel.reference_n_stores)}
              </dd>
              <dt className="apagada">Productos</dt>
              <dd style={{ margin: 0, textAlign: "right" }}>
                {conteoDeTotal(panel.n_products, panel.reference_n_products)}
              </dd>
              <dt className="apagada">Rango</dt>
              <dd style={{ margin: 0, textAlign: "right" }}>
                {panel.date_min} → {panel.date_max} ({magnitud(panel.n_days, 0)} d)
              </dd>
            </dl>
          </section>
        )}
      </div>
    </div>
  );
}
