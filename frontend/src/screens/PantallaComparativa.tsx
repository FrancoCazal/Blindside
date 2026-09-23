/**
 * Comparativa de modelos.
 *
 * Toda métrica va **con su dispersión entre orígenes**, nunca como número único:
 * un promedio bueno puede esconder un origen catastrófico, y el origen
 * catastrófico es el que pasa en producción. Por eso la columna que decide no es
 * la media sino el peor origen, y por eso las ocho líneas se dibujan.
 */

import { api, type BacktestBreakdown } from "../api/client";
import { conteo, error as fmtError, magnitud, porcentaje } from "../format";
import { useAsincrono } from "../state";
import { Esqueleto } from "../components/estados";

/** Baseline de referencia del objetivo SMART del proyecto. */
const REFERENCIA = "seasonal_naive";
const OBJETIVO_PCT = 20;

export function PantallaComparativa() {
  const datos = useAsincrono(
    async () => {
      const [resumen, detalle] = await Promise.all([api.backtest(), api.backtestBreakdown()]);
      return { resumen, detalle };
    },
    [],
  );

  if (datos.cargando && !datos.datos) return <Esqueleto filas={6} />;
  if (datos.error) throw datos.error;
  if (!datos.datos) return null;

  const { resumen, detalle } = datos.datos;
  const mase = resumen.rows
    .filter((r) => r.metric === "mase")
    .sort((a, b) => a.mean - b.mean);
  const referencia = mase.find((r) => r.model_name === REFERENCIA);

  return (
    <div className="pagina">
      <div className="tarjeta" style={{ padding: "18px var(--e5)" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12 }}>
          <h2>Comparativa de modelos</h2>
          <span className="nota">
            {conteo(detalle.n_origins)} orígenes · horizonte {detalle.horizon} d · target{" "}
            {detalle.target}
          </span>
        </div>

        <table className="tabla">
          <caption
            className="nota"
            style={{ captionSide: "bottom", textAlign: "left", paddingTop: 10 }}
          >
            El naive estacional da MASE por encima de 1 y eso es lo normal: el denominador de MASE es
            su error <em>en muestra</em> sobre el train de cada fold y el numerador es{" "}
            <em>fuera de muestra</em>. Los baselines de media móvil son duros a propósito — le ganan
            al naive estacional por casi 20 % — así que la mejora del modelo global no se mide contra
            un rival elegido para perder.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="izq">
                Modelo
              </th>
              <th scope="col">MASE</th>
              <th scope="col">Desvío</th>
              <th scope="col">Peor origen</th>
              <th scope="col">Δ vs naive estacional</th>
              <th scope="col">≥ {OBJETIVO_PCT} %</th>
            </tr>
          </thead>
          <tbody>
            {mase.map((r) => {
              const mejora = referencia ? 100 * (1 - r.mean / referencia.mean) : 0;
              const cumple = mejora >= OBJETIVO_PCT;
              const esReferencia = r.model_name === REFERENCIA;
              return (
                <tr className="fila" key={r.model_name}>
                  <td className="izq tinta" style={{ fontWeight: cumple ? 600 : 400 }}>
                    {r.model_name}
                  </td>
                  <td className="sugerido">{fmtError(r.mean)}</td>
                  <td className="apagada">± {fmtError(r.std)}</td>
                  <td>{fmtError(r.worst_origin)}</td>
                  <td style={{ fontWeight: cumple ? 600 : 400 }}>
                    {esReferencia ? "—" : porcentaje(mejora)}
                  </td>
                  <td className={cumple ? "acento" : "apagada"}>
                    {esReferencia ? "—" : cumple ? "sí" : "no"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <section className="bloque" style={{ marginTop: 22 }}>
          <h3 style={{ fontSize: 16, marginBottom: 8 }}>MASE origen por origen</h3>
          <p className="nota" style={{ maxWidth: "88ch", marginBottom: 10 }}>
            Una línea por modelo sobre los {conteo(detalle.n_origins)} orígenes de validación. Lo que
            hay que mirar es si alguna línea se despega hacia arriba en algún origen: ahí está el mes
            que sale mal.
          </p>
          <LineasPorOrigen detalle={detalle} />
        </section>

        <section className="bloque" style={{ marginTop: 22 }}>
          <h3 style={{ fontSize: 16, marginBottom: 8 }}>Degradación por horizonte</h3>
          <p className="nota" style={{ maxWidth: "88ch", marginBottom: 10 }}>
            Responde cuánto dura el modelo antes de necesitar reentrenamiento. El error debe{" "}
            <strong style={{ fontWeight: 600 }}>crecer</strong> con el horizonte; si baja, hay un
            desalineamiento de índices. La subida y bajada por día de semana es esperada: con
            estacionalidad semanal el objetivo de h7 cae el mismo día que el origen.
          </p>
          <TablaHorizonte detalle={detalle} />
        </section>

        <section className="bloque" style={{ marginTop: 22 }}>
          <h3 style={{ fontSize: 16, marginBottom: 8 }}>Por banda de rotación</h3>
          <p className="nota" style={{ maxWidth: "88ch", marginBottom: 10 }}>
            Que el modelo complejo no le gane al ingenuo en baja rotación es un resultado esperado y
            publicado, no un fracaso. Se reporta igual: la afirmación solo vale si la desagregación
            existe.
          </p>
          <TablaBandas detalle={detalle} />
        </section>
      </div>
    </div>
  );
}

const ANCHO = 900;
const ALTO = 220;
const PAD = { izq: 46, der: 14, arriba: 12, abajo: 26 };

/** Paleta de la escala de grises más el acento para el mejor modelo. */
function trazo(indice: number, total: number, destacado: boolean): string {
  if (destacado) return "var(--recuperado)";
  const opacidad = 0.66 - (indice / Math.max(1, total)) * 0.34;
  return `color-mix(in srgb, var(--tinta) ${Math.round(opacidad * 100)}%, transparent)`;
}

function LineasPorOrigen({ detalle }: { detalle: BacktestBreakdown }) {
  const filas = detalle.origins.filter((o) => o.metric === "mase");
  if (filas.length === 0) return <p className="nota">Sin datos por origen.</p>;

  const modelos = [...new Set(filas.map((f) => f.model_name))];
  const origenes = [...new Set(filas.map((f) => f.origin))].sort((a, b) => a - b);
  const valores = filas.map((f) => f.value);
  const max = Math.max(...valores) * 1.06;
  const min = Math.min(...valores) * 0.94;

  const x = (i: number) =>
    PAD.izq + (i * (ANCHO - PAD.izq - PAD.der)) / Math.max(1, origenes.length - 1);
  const y = (v: number) =>
    ALTO - PAD.abajo - ((v - min) / (max - min)) * (ALTO - PAD.arriba - PAD.abajo);

  const mejorModelo = modelos
    .map((m) => ({
      m,
      media:
        filas.filter((f) => f.model_name === m).reduce((a, f) => a + f.value, 0) /
        filas.filter((f) => f.model_name === m).length,
    }))
    .sort((a, b) => a.media - b.media)[0]?.m;

  return (
    <div>
      <svg viewBox={`0 0 ${ANCHO} ${ALTO}`} className="grafico" role="img"
        aria-label="MASE por origen de backtest, una línea por modelo">
        {[0, 0.25, 0.5, 0.75, 1].map((f) => {
          const valor = min + f * (max - min);
          return (
            <g key={f}>
              <line x1={PAD.izq} x2={ANCHO - PAD.der} y1={y(valor)} y2={y(valor)} stroke="var(--guia)" />
              <text x={40} y={y(valor) + 3.5} textAnchor="end" fontSize="11" fill="var(--apagada)">
                {magnitud(valor, 2)}
              </text>
            </g>
          );
        })}
        {/* La línea de MASE = 1 es la referencia dura: por arriba, el modelo es
            peor que el naive estacional en muestra. */}
        {min < 1 && max > 1 && (
          <line
            x1={PAD.izq}
            x2={ANCHO - PAD.der}
            y1={y(1)}
            y2={y(1)}
            stroke="var(--eje)"
            strokeDasharray="4 3"
          />
        )}
        <line x1={PAD.izq} x2={ANCHO - PAD.der} y1={ALTO - PAD.abajo} y2={ALTO - PAD.abajo} stroke="var(--eje)" />

        {modelos.map((m, i) => {
          const serie = origenes
            .map((o) => filas.find((f) => f.model_name === m && f.origin === o))
            .filter((f): f is NonNullable<typeof f> => f != null);
          const destacado = m === mejorModelo;
          const d = serie
            .map((f, k) => `${k === 0 ? "M" : "L"}${x(origenes.indexOf(f.origin))} ${y(f.value)}`)
            .join(" ");
          return (
            <g key={m}>
              <path
                d={d}
                fill="none"
                stroke={trazo(i, modelos.length, destacado)}
                strokeWidth={destacado ? 2.4 : 1.4}
              />
              {destacado &&
                serie.map((f) => (
                  <circle
                    key={f.origin}
                    cx={x(origenes.indexOf(f.origin))}
                    cy={y(f.value)}
                    r="3"
                    fill="var(--recuperado)"
                  />
                ))}
            </g>
          );
        })}

        {origenes.map((o, i) => (
          <text key={o} x={x(i)} y={ALTO - 8} textAnchor="middle" fontSize="11" fill="var(--apagada)">
            {o + 1}
          </text>
        ))}
      </svg>

      <div className="leyenda">
        {modelos.map((m, i) => (
          <span key={m}>
            <svg width="22" height="8" aria-hidden="true">
              <line
                x1="0"
                y1="4"
                x2="22"
                y2="4"
                stroke={trazo(i, modelos.length, m === mejorModelo)}
                strokeWidth={m === mejorModelo ? 2.4 : 1.4}
              />
            </svg>
            {m}
          </span>
        ))}
      </div>
    </div>
  );
}

function TablaHorizonte({ detalle }: { detalle: BacktestBreakdown }) {
  const filas = detalle.horizons.filter((h) => h.metric === "mase");
  const modelos = [...new Set(filas.map((f) => f.model_name))];
  const pasos = [...new Set(filas.map((f) => f.h))].sort((a, b) => a - b);
  if (pasos.length === 0) return <p className="nota">Sin datos por horizonte.</p>;

  return (
    <table className="tabla" style={{ maxWidth: 720 }}>
      <thead>
        <tr>
          <th scope="col" className="izq">
            Modelo
          </th>
          {pasos.map((h) => (
            <th scope="col" key={h}>
              h{h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {modelos.map((m) => (
          <tr className="fila" key={m}>
            <td className="izq tinta">{m}</td>
            {pasos.map((h) => {
              const f = filas.find((r) => r.model_name === m && r.h === h);
              return <td key={h}>{f ? fmtError(f.value) : "—"}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TablaBandas({ detalle }: { detalle: BacktestBreakdown }) {
  const filas = detalle.bands.filter((b) => b.metric === "mase");
  if (filas.length === 0) {
    return (
      <p className="nota">
        Sin desagregación por banda: hace falta el panel cargado para definir las clases con el train
        del primer origen.
      </p>
    );
  }
  const modelos = [...new Set(filas.map((f) => f.model_name))];
  const bandas = ["baja", "media", "alta"].filter((b) => filas.some((f) => f.band === b));

  return (
    <table className="tabla" style={{ maxWidth: 620 }}>
      <thead>
        <tr>
          <th scope="col" className="izq">
            Modelo
          </th>
          {bandas.map((b) => (
            <th scope="col" key={b}>
              {b}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {modelos.map((m) => (
          <tr className="fila" key={m}>
            <td className="izq tinta">{m}</td>
            {bandas.map((b) => {
              const f = filas.find((r) => r.model_name === m && r.band === b);
              return <td key={b}>{f ? fmtError(f.value) : "—"}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
