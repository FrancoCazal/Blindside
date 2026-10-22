/**
 * Modelos · ¿qué tan bueno es el modelo y dónde falla?
 *
 * Reemplaza a Comparativa y a la cobertura de Salud. Cambios de fondo:
 *
 * - Los modelos con el mismo pronóstico puntual van en una fila. Los tres
 *   LightGBM daban MASE 0,822 los tres y se mostraban como tres resultados.
 * - La mejora se dice en palabras («25,3 % menos error»), con una sola convención.
 * - Aparece la comparación del **intervalo** — CQR contra conformal de residuos —,
 *   que es la evidencia de D21 y antes no estaba en ninguna pantalla.
 * - Las conclusiones por banda se derivan de los números. Antes un texto fijo
 *   decía que el modelo no le ganaba al ingenuo en baja rotación, con la tabla de
 *   al lado mostrando 0,822 contra 1,121.
 *
 * Especificación: `docs/rediseno_frontend.md`, sección 5.5.
 */

import { api, type BacktestBreakdown, type BacktestResponse, type Health } from "../api/client";
import { ComoSeCalcula, Encabezado } from "../components/controles";
import { Esqueleto } from "../components/estados";
import { DatosDelGrafico } from "../components/graficos";
import { conteo, error as fmtError, magnitud, porcentajeSimple } from "../format";
import { t } from "../i18n";
import {
  OBJETIVO_MEJORA,
  POLITICA,
  REFERENCIA,
  SERVIDO,
  agruparModelos,
  conclusionBanda,
  grupoServido,
  nombreModelo,
  notaModelo,
  textoMejora,
} from "../modelos";
import { useAsincrono } from "../state";
import { ErrorDeBloque } from "./PantallaPanel";

/** Los modelos que se dibujan: el servido y las dos referencias que importan. */
const DIBUJADOS = [SERVIDO, POLITICA, REFERENCIA];

const TRAZO: Record<string, { color: string; ancho: number; guion?: string }> = {
  [SERVIDO]: { color: "var(--tinta)", ancho: 2.4 },
  [POLITICA]: { color: "var(--observado)", ancho: 1.6 },
  [REFERENCIA]: { color: "var(--observado)", ancho: 1.4, guion: "5 4" },
};

/** Orden de las bandas de rotación. Son valores de la API, no texto. */
const BANDAS = ["baja", "media", "alta"];

const pct1 = (v: number) => porcentajeSimple(v, 1);

export function PantallaModelos({
  health,
  backtest,
  backtestCargando,
}: {
  health: Health;
  backtest: BacktestResponse | null;
  backtestCargando: boolean;
}) {
  const detalle = useAsincrono(() => api.backtestBreakdown(), []);
  const textos = t();
  const m = textos.modelosPantalla;

  if (backtestCargando && !backtest) return <Esqueleto filas={6} />;
  if (!backtest) {
    return (
      <div className="pagina">
        <Encabezado titulo={m.titulo} />
        <p className="nota">{m.sinBacktest}</p>
      </div>
    );
  }

  const grupos = agruparModelos(backtest.rows);
  const servido = grupoServido(grupos);
  const intervalo = (clave: string, metrica: string) =>
    backtest.rows.find((r) => r.model_name === clave && r.metric === metrica) ?? null;
  const conIntervalo = [...new Set(backtest.rows.filter((r) => r.metric === "coverage").map((r) => r.model_name))];
  const nominal = health.coverage_nominal ?? 0.9;
  const coberturaServido = intervalo(SERVIDO, "coverage");
  const nOrigenes = servido?.mase.n_origins ?? 0;
  const objetivo = porcentajeSimple(OBJETIVO_MEJORA);
  const c = m.columnas;

  return (
    <div className="pagina tablero">
      <Encabezado titulo={m.titulo} contexto={m.contexto(conteo(nOrigenes), String(backtest.horizon))} />

      {servido && (
        <div className="kpis" role="list">
          <div className="kpi" data-primario="true" role="listitem">
            <div className="rotulo">{m.kpiError}</div>
            <div className="kpi-valor">{fmtError(servido.mase.mean)}</div>
            <div className="kpi-pie">{m.kpiErrorPie(fmtError(servido.mase.std), servido.nombre)}</div>
          </div>
          <div className="kpi" role="listitem">
            <div className="rotulo">{m.kpiPeor}</div>
            <div className="kpi-valor">{fmtError(servido.mase.worst_origin)}</div>
            <div className="kpi-pie">{m.kpiPeorPie(fmtError(servido.mase.best_origin))}</div>
          </div>
          <div className="kpi" role="listitem">
            <div className="rotulo">{m.kpiNaive}</div>
            <div className="kpi-valor">{servido.mejora != null ? pct1(servido.mejora) : "—"}</div>
            <div className="kpi-pie">{m.kpiNaivePie(objetivo, servido.cumpleObjetivo)}</div>
          </div>
          <div className="kpi" role="listitem">
            <div className="rotulo">{m.kpiCobertura}</div>
            <div className="kpi-valor">
              {coberturaServido ? pct1(coberturaServido.mean * 100) : "—"}
            </div>
            <div className="kpi-pie">
              {m.kpiCoberturaPie(
                porcentajeSimple(nominal * 100),
                coberturaServido ? magnitud(Math.abs(nominal - coberturaServido.mean) * 100, 1) : null,
                coberturaServido != null && coberturaServido.mean < nominal,
              )}
            </div>
          </div>
        </div>
      )}

      <section className="tarjeta tablero-bloque" aria-labelledby="t-tabla" style={{ marginTop: 0 }}>
        <div className="tablero-titulo">
          <h2 id="t-tabla">{m.tabla}</h2>
          <span className="nota">{m.tablaNota}</span>
        </div>
        <table className="tabla">
          <thead>
            <tr>
              <th scope="col" className="izq">
                {c.modelo}
              </th>
              <th scope="col">{c.mase}</th>
              <th scope="col">{c.desvio}</th>
              <th scope="col">{c.peor}</th>
              <th scope="col">{c.wape}</th>
              <th scope="col">{c.naive}</th>
              <th scope="col">{c.objetivo(objetivo)}</th>
            </tr>
          </thead>
          <tbody>
            {grupos.map((g) => {
              const esServido = g.miembros.includes(SERVIDO);
              const nota =
                g.miembros.length > 1 ? m.variantes(conteo(g.miembros.length)) : notaModelo(g.clave);
              return (
                <tr className="fila" key={g.clave} style={{ cursor: "default" }}>
                  <td className="izq" title={g.miembros.join(", ")}>
                    <span className="tinta" style={{ fontWeight: esServido ? 600 : 400 }}>
                      {g.nombre}
                    </span>
                    {nota && <span className="nota"> · {nota}</span>}
                  </td>
                  <td className="sugerido">{fmtError(g.mase.mean)}</td>
                  <td className="apagada">± {fmtError(g.mase.std)}</td>
                  <td>{fmtError(g.mase.worst_origin)}</td>
                  <td className="apagada">{g.wape ? fmtError(g.wape.mean) : "—"}</td>
                  <td>{g.esReferencia ? m.referencia : g.mejora != null ? textoMejora(g.mejora, pct1) : "—"}</td>
                  <td className={g.cumpleObjetivo ? "tinta" : "apagada"}>
                    {g.esReferencia ? "—" : g.cumpleObjetivo ? textos.comun.si : textos.comun.no}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="nota" style={{ marginTop: 10, maxWidth: "96ch" }}>
          {m.notaNaive}
        </p>
      </section>

      <div className="tablero-pie">
        <section className="tarjeta tablero-bloque" aria-labelledby="t-intervalo">
          <div className="tablero-titulo">
            <h2 id="t-intervalo">{m.intervalo}</h2>
            <span className="nota">{m.prometido(porcentajeSimple(nominal * 100))}</span>
          </div>
          {conIntervalo.length === 0 ? (
            <p className="nota">{m.sinIntervalo}</p>
          ) : (
            <>
              <table className="tabla">
                <thead>
                  <tr>
                    <th scope="col" className="izq">
                      {m.metodo}
                    </th>
                    <th scope="col">{m.cobertura}</th>
                    <th scope="col">{m.ancho}</th>
                  </tr>
                </thead>
                <tbody>
                  {conIntervalo.map((clave) => {
                    const cob = intervalo(clave, "coverage");
                    const ancho = intervalo(clave, "interval_width");
                    return (
                      <tr className="fila" key={clave} style={{ cursor: "default" }}>
                        <td className="izq tinta" style={{ fontWeight: clave === SERVIDO ? 600 : 400 }}>
                          {nombreModelo(clave).replace(textos.modelos.prefijoLgbm, "")}
                          {clave === SERVIDO && <span className="nota"> · {m.servido}</span>}
                        </td>
                        <td className="sugerido">{cob ? pct1(cob.mean * 100) : "—"}</td>
                        <td>{ancho ? magnitud(ancho.mean, 2) : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <ConclusionIntervalo
                cqr={intervalo(SERVIDO, "coverage")?.mean ?? null}
                cqrAncho={intervalo(SERVIDO, "interval_width")?.mean ?? null}
                residuos={intervalo("conformal_lgbm_quantile_adaptive", "coverage")?.mean ?? null}
                residuosAncho={intervalo("conformal_lgbm_quantile_adaptive", "interval_width")?.mean ?? null}
              />
            </>
          )}
        </section>

        <section className="tarjeta tablero-bloque" aria-labelledby="t-cobh">
          <div className="tablero-titulo">
            <h2 id="t-cobh">{m.coberturaH}</h2>
          </div>
          <CoberturaPorHorizonte health={health} />
        </section>
      </div>

      {detalle.error ? (
        <ErrorDeBloque titulo={m.desglose} error={detalle.error} onReintentar={detalle.recargar} />
      ) : !detalle.datos ? (
        <div className="hueso" style={{ height: 240, marginTop: "var(--e5)" }} />
      ) : (
        <>
          <section className="tarjeta tablero-bloque" aria-labelledby="t-origen">
            <div className="tablero-titulo">
              <h2 id="t-origen">{m.origen}</h2>
              <span className="nota">{m.origenNota}</span>
            </div>
            <LineasPorOrigen detalle={detalle.datos} />
          </section>

          <div className="tablero-pie">
            <section className="tarjeta tablero-bloque" aria-labelledby="t-horizonte">
              <div className="tablero-titulo">
                <h2 id="t-horizonte">{m.horizonte}</h2>
              </div>
              <TablaComparada
                filas={detalle.datos.horizons.filter((h) => h.metric === "mase")}
                columna={(f) => `h${f.h}`}
                orden={(a, b) => Number(a.slice(1)) - Number(b.slice(1))}
              />
              <ConclusionHorizonte detalle={detalle.datos} />
            </section>

            <section className="tarjeta tablero-bloque" aria-labelledby="t-banda">
              <div className="tablero-titulo">
                <h2 id="t-banda">{m.banda}</h2>
              </div>
              <TablaComparada
                filas={detalle.datos.bands.filter((b) => b.metric === "mase")}
                columna={(f) => f.band}
                orden={(a, b) => BANDAS.indexOf(a) - BANDAS.indexOf(b)}
                rotular={(banda) => textos.bandas[banda] ?? banda}
              />
              <ConclusionBandas detalle={detalle.datos} />
            </section>
          </div>
        </>
      )}

      <ComoSeCalcula>
        <p>{m.comoBacktest(conteo(nOrigenes), String(backtest.horizon))}</p>
        <p>{m.comoAgrupado}</p>
      </ComoSeCalcula>
    </div>
  );
}

function ConclusionIntervalo({
  cqr,
  cqrAncho,
  residuos,
  residuosAncho,
}: {
  cqr: number | null;
  cqrAncho: number | null;
  residuos: number | null;
  residuosAncho: number | null;
}) {
  if (cqr == null || residuos == null || !cqrAncho || !residuosAncho) return null;
  const veces = residuosAncho / cqrAncho;
  return (
    <p className="nota" style={{ marginTop: 10 }}>
      {t().modelosPantalla.conclusionIntervalo(pct1(cqr * 100), magnitud(veces, 1), pct1(residuos * 100))}
    </p>
  );
}

/**
 * Cobertura por paso del horizonte como puntos sobre un eje recortado. Las barras
 * desde cero de la versión anterior hacían invisible la diferencia entre 85 % y
 * 89 %, que es justo lo que hay que ver.
 */
function CoberturaPorHorizonte({ health }: { health: Health }) {
  const m = t().modelosPantalla;
  const puntos = health.coverage_by_horizon;
  const nominal = health.coverage_nominal ?? 0.9;
  if (puntos.length === 0) {
    return (
      <p className="nota">
        {m.sinMedicion} {health.coverage_note}
      </p>
    );
  }
  const ancho = 520;
  const alto = 170;
  const pad = { izq: 40, der: 10, arriba: 14, abajo: 22 };
  const valores = [...puntos.map((p) => p.coverage_empirical), nominal];
  const min = Math.floor((Math.min(...valores) - 0.02) * 20) / 20;
  const max = Math.min(1, Math.ceil((Math.max(...valores) + 0.02) * 20) / 20);
  const x = (i: number) => pad.izq + ((i + 0.5) * (ancho - pad.izq - pad.der)) / puntos.length;
  const y = (v: number) => alto - pad.abajo - ((v - min) / (max - min)) * (alto - pad.arriba - pad.abajo);
  const guias = Array.from({ length: Math.round((max - min) / 0.05) + 1 }, (_, k) => min + k * 0.05);

  return (
    <>
      <svg viewBox={`0 0 ${ancho} ${alto}`} className="grafico" role="img"
        aria-label={m.coberturaAria(porcentajeSimple(nominal * 100))}>
        {guias.map((g) => (
          <g key={g}>
            <line x1={pad.izq} x2={ancho - pad.der} y1={y(g)} y2={y(g)} stroke="var(--guia)" />
            <text x={pad.izq - 6} y={y(g) + 3.5} textAnchor="end" fontSize="11" fill="var(--apagada)">
              {porcentajeSimple(g * 100)}
            </text>
          </g>
        ))}
        <line x1={pad.izq} x2={ancho - pad.der} y1={y(nominal)} y2={y(nominal)} stroke="var(--eje)" strokeDasharray="5 4" />
        {puntos.map((p, i) => (
          <g key={p.h}>
            <line x1={x(i)} x2={x(i)} y1={y(nominal)} y2={y(p.coverage_empirical)} stroke="var(--horas-quiebre)" />
            <circle cx={x(i)} cy={y(p.coverage_empirical)} r="4" fill="var(--tinta)" />
            <text x={x(i)} y={y(p.coverage_empirical) - 8} textAnchor="middle" fontSize="11" fill="var(--secundaria)">
              {magnitud(p.coverage_empirical * 100, 1)}
            </text>
            <text x={x(i)} y={alto - 6} textAnchor="middle" fontSize="11" fill="var(--apagada)">
              {m.dia(String(p.h))}
            </text>
          </g>
        ))}
      </svg>
      <p className="nota" style={{ marginTop: 6 }}>
        {m.coberturaNota}
      </p>
    </>
  );
}

function LineasPorOrigen({ detalle }: { detalle: BacktestBreakdown }) {
  const m = t().modelosPantalla;
  const filas = detalle.origins.filter((o) => o.metric === "mase" && DIBUJADOS.includes(o.model_name));
  if (filas.length === 0) return <p className="nota">{m.sinOrigen}</p>;
  const origenes = [...new Set(filas.map((f) => f.origin))].sort((a, b) => a - b);
  const ancho = 1000;
  const alto = 220;
  const pad = { izq: 46, der: 14, arriba: 12, abajo: 26 };
  const valores = filas.map((f) => f.value);
  const max = Math.max(...valores, 1) * 1.04;
  const min = Math.min(...valores) * 0.96;
  const x = (i: number) => pad.izq + (i * (ancho - pad.izq - pad.der)) / Math.max(1, origenes.length - 1);
  const y = (v: number) => alto - pad.abajo - ((v - min) / (max - min)) * (alto - pad.arriba - pad.abajo);
  const fecha = new Map(filas.map((f) => [f.origin, f.origin_date]));

  return (
    <>
      <svg viewBox={`0 0 ${ancho} ${alto}`} className="grafico" role="img" aria-label={m.origenAria}>
        {[0, 0.5, 1].map((f) => {
          const v = min + f * (max - min);
          return (
            <g key={f}>
              <line x1={pad.izq} x2={ancho - pad.der} y1={y(v)} y2={y(v)} stroke="var(--guia)" />
              <text x={pad.izq - 6} y={y(v) + 3.5} textAnchor="end" fontSize="11" fill="var(--apagada)">
                {magnitud(v, 2)}
              </text>
            </g>
          );
        })}
        {min < 1 && max > 1 && (
          <g>
            <line x1={pad.izq} x2={ancho - pad.der} y1={y(1)} y2={y(1)} stroke="var(--eje)" strokeDasharray="2 3" />
            <text x={ancho - pad.der} y={y(1) - 4} textAnchor="end" fontSize="11" fill="var(--apagada)">
              MASE 1
            </text>
          </g>
        )}
        {DIBUJADOS.map((modelo) => {
          const serie = origenes
            .map((o) => filas.find((f) => f.model_name === modelo && f.origin === o))
            .filter((f): f is NonNullable<typeof f> => f != null);
          if (serie.length === 0) return null;
          const trazo = TRAZO[modelo];
          return (
            <g key={modelo}>
              <path
                d={serie.map((f, k) => `${k === 0 ? "M" : "L"}${x(origenes.indexOf(f.origin))} ${y(f.value)}`).join(" ")}
                fill="none"
                stroke={trazo.color}
                strokeWidth={trazo.ancho}
                strokeDasharray={trazo.guion}
              />
              {modelo === SERVIDO &&
                serie.map((f) => (
                  <circle key={f.origin} cx={x(origenes.indexOf(f.origin))} cy={y(f.value)} r="3" fill={trazo.color} />
                ))}
            </g>
          );
        })}
        {origenes.map((o, i) => (
          <text key={o} x={x(i)} y={alto - 8} textAnchor="middle" fontSize="11" fill="var(--apagada)">
            {fecha.get(o)?.slice(5) ?? o + 1}
          </text>
        ))}
      </svg>
      <div className="leyenda">
        {DIBUJADOS.map((modelo) => (
          <span key={modelo}>
            <svg width="22" height="8" aria-hidden="true">
              <line x1="0" y1="4" x2="22" y2="4" stroke={TRAZO[modelo].color} strokeWidth={TRAZO[modelo].ancho} strokeDasharray={TRAZO[modelo].guion} />
            </svg>
            {nombreModelo(modelo)}
          </span>
        ))}
      </div>
      <DatosDelGrafico
        encabezados={[m.origenColumna, ...DIBUJADOS.map(nombreModelo)]}
        filas={origenes.map((o) => [
          fecha.get(o) ?? String(o + 1),
          ...DIBUJADOS.map((modelo) => {
            const f = filas.find((r) => r.model_name === modelo && r.origin === o);
            return f ? fmtError(f.value) : "—";
          }),
        ])}
        resumen={m.origenDatos}
      />
    </>
  );
}

/** Tabla de MASE del modelo servido y las dos referencias, con columnas dadas. */
function TablaComparada<T extends { model_name: string; value: number }>({
  filas,
  columna,
  orden,
  rotular = (c) => c,
}: {
  filas: T[];
  columna: (f: T) => string;
  orden: (a: string, b: string) => number;
  /** Cómo se lee la clave de columna. La clave sigue siendo el valor de la API. */
  rotular?: (columna: string) => string;
}) {
  const m = t().modelosPantalla;
  const columnas = [...new Set(filas.map(columna))].sort(orden);
  if (columnas.length === 0) return <p className="nota">{m.sinDesglose}</p>;
  return (
    <table className="tabla">
      <thead>
        <tr>
          <th scope="col" className="izq">
            {m.columnas.modelo}
          </th>
          {columnas.map((c) => (
            <th scope="col" key={c}>
              {rotular(c)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {DIBUJADOS.map((modelo) => (
          <tr className="fila" key={modelo} style={{ cursor: "default" }}>
            <td className="izq tinta" style={{ fontWeight: modelo === SERVIDO ? 600 : 400 }}>
              {nombreModelo(modelo)}
            </td>
            {columnas.map((c) => {
              const f = filas.find((r) => r.model_name === modelo && columna(r) === c);
              return (
                <td key={c} className={modelo === SERVIDO ? "sugerido" : "apagada"}>
                  {f ? fmtError(f.value) : "—"}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ConclusionHorizonte({ detalle }: { detalle: BacktestBreakdown }) {
  const propios = detalle.horizons
    .filter((h) => h.metric === "mase" && h.model_name === SERVIDO)
    .sort((a, b) => a.h - b.h);
  if (propios.length < 2) return null;
  const primero = propios[0];
  const ultimo = propios[propios.length - 1];
  const peor = [...propios].sort((a, b) => b.value - a.value)[0];
  return (
    <p className="nota" style={{ marginTop: 10 }}>
      {t().modelosPantalla.conclusionHorizonte(
        String(primero.h),
        fmtError(primero.value),
        String(ultimo.h),
        fmtError(ultimo.value),
        String(peor.h),
        fmtError(peor.value),
      )}
    </p>
  );
}

function ConclusionBandas({ detalle }: { detalle: BacktestBreakdown }) {
  const mase = detalle.bands.filter((b) => b.metric === "mase");
  const frases = BANDAS.map((banda) => {
    const modelo = mase.find((b) => b.band === banda && b.model_name === SERVIDO);
    const ref = mase.find((b) => b.band === banda && b.model_name === REFERENCIA);
    return modelo && ref ? conclusionBanda(modelo.value, ref.value, banda) : null;
  }).filter(Boolean);
  if (frases.length === 0) return null;
  return (
    <p className="nota" style={{ marginTop: 10 }}>
      {frases.join(" ")} {t().modelosPantalla.notaBandas}
    </p>
  );
}
