/**
 * Panel · la pantalla de entrada.
 *
 * Responde tres preguntas en este orden, y el orden es el del uso real:
 *
 * 1. **Qué hay que hacer hoy.** Series quebradas y series donde la política
 *    actual va a dejar mercadería sin vender. Son las dos alertas urgentes.
 * 2. **Qué conviene revisar.** Los motivos analíticos: modelo que no le gana al
 *    ingenuo, señal sostenida por estimación, volumen alto.
 * 3. **Cuánto confiar en todo lo anterior.** Error con su dispersión, cobertura
 *    real del intervalo y frescura de datos y modelo.
 *
 * No hay score compuesto ni «top 10». Los motivos son ortogonales — medido, el
 * top 50 por volumen y el top 50 por error no comparten una serie — así que cada
 * uno lleva su propia lista y su propio remedio.
 */

import {
  api,
  type AlertGroup,
  type AlertItem,
  type BacktestResponse,
  type DatasetSummary,
  type Health,
} from "../api/client";
import { cifraDeMotivo, rotuloMotivo, textoNoCalculado, textoUmbral, textosMotivo } from "../alertas";
import { Esqueleto } from "../components/estados";
import { BarrasHorizontales, DatosDelGrafico, Leyenda, SerieTemporal, type Serie } from "../components/graficos";
import {
  conteo,
  conteoDeTotal,
  descripcionCatalogo,
  error as fmtError,
  errorConDispersion,
  estadoIngesta,
  etiquetaFecha,
  fechaHora,
  magnitud,
  porcentaje,
  porcentajeSimple,
  serieCorta,
} from "../format";
import { t } from "../i18n";
import { OBJETIVO_MEJORA, SERVIDO, agruparModelos, grupoServido, textoMejora } from "../modelos";
import { useAsincrono, useEstado } from "../state";

export function PantallaPanel({
  health,
  backtest,
  backtestCargando = false,
}: {
  health: Health;
  backtest: BacktestResponse | null;
  /** Mientras carga no se dice «sin backtest»: sería falso por un par de segundos. */
  backtestCargando?: boolean;
}) {
  const alertas = useAsincrono(async () => {
    const resumen = await api.alerts({ limit: 1 });
    const urgentes = resumen.groups.filter((g) => g.urgent);
    const listas = await Promise.all(urgentes.map((g) => api.alerts({ group: g.key, limit: 5 })));
    return { resumen, listas: urgentes.map((grupo, i) => ({ grupo, items: listas[i].items })) };
  }, []);
  const datos = useAsincrono(() => api.datasetSummary(), []);
  const textos = t();
  const p = textos.panel;

  return (
    <div className="pagina tablero">
      <Encabezado health={health} />
      <Kpis
        health={health}
        backtest={backtest}
        backtestCargando={backtestCargando}
        alertas={alertas.datos?.resumen ?? null}
        datos={datos.datos}
      />

      {alertas.error ? (
        <ErrorDeBloque titulo={textos.nav.pantallas.alerts} error={alertas.error} onReintentar={alertas.recargar} />
      ) : !alertas.datos ? (
        <Esqueleto filas={4} />
      ) : (
        <>
          <section aria-labelledby="titulo-hoy">
            <div className="tablero-titulo">
              <h2 id="titulo-hoy">{p.paraHoy}</h2>
              <span className="nota">{p.paraHoyNota(etiquetaFecha(alertas.datos.resumen.data_date_max))}</span>
            </div>
            <div className="tablero-urgentes">
              {alertas.datos.listas.map(({ grupo, items }) => (
                <TarjetaUrgente key={grupo.key} grupo={grupo} items={items} />
              ))}
              {alertas.datos.resumen.unavailable
                .filter((u) => u.key === "riesgo_merma")
                .map((u) => (
                  <div className="tarjeta tarjeta-alerta" key={u.key}>
                    <h3>{rotuloMotivo(u.key)}</h3>
                    <p className="nota">{p.noCalculado(textoNoCalculado(u.key, u.reason))}</p>
                  </div>
                ))}
            </div>
          </section>

          <section aria-labelledby="titulo-revisar" style={{ marginTop: "var(--e5)" }}>
            <div className="tablero-titulo">
              <h2 id="titulo-revisar">{p.paraRevisar}</h2>
              <span className="nota">{p.paraRevisarNota}</span>
            </div>
            <TablaGrupos
              grupos={alertas.datos.resumen.groups.filter((g) => !g.urgent)}
              nSeries={alertas.datos.resumen.n_series}
            />
          </section>
        </>
      )}

      <section className="tarjeta tablero-bloque" aria-labelledby="titulo-demanda">
        <div className="tablero-titulo">
          <h2 id="titulo-demanda">{p.demanda}</h2>
          <span className="nota">{p.demandaNota}</span>
        </div>
        {datos.error ? (
          <ErrorDeBloque titulo={textos.nav.pantallas.data} error={datos.error} onReintentar={datos.recargar} />
        ) : datos.datos ? (
          <GraficoDemanda datos={datos.datos} />
        ) : (
          <div className="hueso" style={{ height: 220 }} />
        )}
      </section>

      <div className="tablero-pie">
        <section className="tarjeta tablero-bloque" aria-labelledby="titulo-modelos">
          <div className="tablero-titulo">
            <h2 id="titulo-modelos">{p.modelos}</h2>
            <BotonIr pantalla="models">{p.verModelos}</BotonIr>
          </div>
          {backtestCargando && !backtest ? (
            <div className="hueso" style={{ height: 180 }} />
          ) : (
            <RankingModelos backtest={backtest} />
          )}
        </section>
        <section className="tarjeta tablero-bloque" aria-labelledby="titulo-frescura">
          <div className="tablero-titulo">
            <h2 id="titulo-frescura">{p.datosYModelo}</h2>
            <BotonIr pantalla="pipeline">{p.verPipeline}</BotonIr>
          </div>
          <Frescura health={health} />
        </section>
      </div>
    </div>
  );
}

function Encabezado({ health }: { health: Health }) {
  const f = health.freshness;
  const p = t().panel;
  return (
    <div className="tablero-encabezado">
      <h1>{p.titulo}</h1>
      <span className="nota">
        {health.panel
          ? p.contexto(
              conteo(health.panel.n_series),
              conteo(health.panel.n_stores),
              conteo(health.panel.n_products),
              health.panel.date_min,
              health.panel.date_max,
            )
          : p.sinPanel}
        {f?.status === "desfasado" && (
          <strong className="aviso-texto">{p.desfase(conteo(f.days_behind ?? 0))}</strong>
        )}
      </span>
    </div>
  );
}

function Kpis({
  health,
  backtest,
  backtestCargando,
  alertas,
  datos,
}: {
  health: Health;
  backtest: BacktestResponse | null;
  backtestCargando: boolean;
  alertas: { n_series: number; n_flagged: number } | null;
  datos: DatasetSummary | null;
}) {
  const servido = grupoServido(agruparModelos(backtest?.rows ?? []));
  const mejor = servido?.mase ?? null;
  const mejora = servido?.mejora ?? null;
  const cob = health.coverage_by_horizon;
  const cobMedia = cob.length ? cob.reduce((a, c) => a + c.coverage_empirical, 0) / cob.length : null;
  const p = t().panel;

  return (
    <div className="kpis" role="list">
      <div className="kpi" data-primario="true" role="listitem">
        <div className="rotulo">{p.kpiAtencion}</div>
        <div className="kpi-valor">{alertas ? conteo(alertas.n_flagged) : "—"}</div>
        <div className="kpi-pie">
          {alertas
            ? p.kpiAtencionPie(
                porcentajeSimple((100 * alertas.n_flagged) / Math.max(1, alertas.n_series), 1),
                conteo(alertas.n_series),
              )
            : p.calculando}
        </div>
      </div>
      <div className="kpi" role="listitem">
        <div className="rotulo">{p.kpiError}</div>
        <div className="kpi-valor">{mejor ? fmtError(mejor.mean) : "—"}</div>
        <div className="kpi-pie">
          {mejor
            ? p.kpiErrorPie(
                fmtError(mejor.std),
                mejora != null ? textoMejora(mejora, (v) => porcentajeSimple(v, 1)) : null,
              )
            : backtestCargando
              ? p.calculando
              : p.sinBacktest}
        </div>
      </div>
      <div className="kpi" role="listitem">
        <div className="rotulo">{p.kpiCobertura}</div>
        <div className="kpi-valor">{cobMedia != null ? porcentajeSimple(cobMedia * 100, 1) : "—"}</div>
        <div className="kpi-pie">
          {cobMedia != null
            ? p.kpiCoberturaPie(porcentajeSimple((health.coverage_nominal ?? 0.9) * 100))
            : p.sinMedir}
        </div>
      </div>
      <div className="kpi" role="listitem">
        <div className="rotulo">{p.kpiEscondida}</div>
        <div className="kpi-valor acento">{datos ? porcentaje(datos.totals.uplift_pct) : "—"}</div>
        <div className="kpi-pie">
          {datos ? p.kpiEscondidaPie(porcentajeSimple(datos.totals.share_censored_days * 100)) : p.calculando}
        </div>
      </div>
    </div>
  );
}

function TarjetaUrgente({ grupo, items }: { grupo: AlertGroup; items: AlertItem[] }) {
  const { irA, setGrupo, setSerie } = useEstado();
  const p = t().panel;
  const motivo = textosMotivo(grupo);
  return (
    <div className="tarjeta tarjeta-alerta" data-urgente="true">
      <div className="tarjeta-alerta-cabeza">
        <h3>{motivo.rotulo}</h3>
        <span className="tarjeta-alerta-cifra tabular">{conteo(grupo.n_series)}</span>
      </div>
      <p className="nota">{motivo.significa}</p>
      {items.length > 0 ? (
        <ul className="lista-alerta">
          {items.map((it) => (
            <li key={it.series.series_id}>
              <button
                type="button"
                onClick={() => {
                  setSerie(it.series.series_id);
                  irA("series");
                }}
                title={descripcionCatalogo(it.label)}
              >
                <span className="codigo tabular">
                  {serieCorta(it.series.store_id, it.series.product_id)}
                </span>
                <span className="nota">{cifraDeMotivo(it, grupo.key)}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="nota">{p.ningunaHoy}</p>
      )}
      <div className="tarjeta-alerta-pie">
        <span className="nota">
          <strong className="tinta" style={{ fontWeight: 600 }}>
            {p.queHacer}
          </strong>{" "}
          {motivo.hacer}
        </span>
        <button
          type="button"
          className="boton-sutil"
          onClick={() => {
            setGrupo(grupo.key);
            irA("alerts");
          }}
        >
          {p.verLas(conteo(grupo.n_series))}
        </button>
      </div>
    </div>
  );
}

function TablaGrupos({ grupos, nSeries }: { grupos: AlertGroup[]; nSeries: number }) {
  const { irA, setGrupo } = useEstado();
  const p = t().panel;
  if (grupos.length === 0) return <p className="nota">{p.sinMotivos}</p>;
  return (
    <table className="tabla tarjeta">
      <thead>
        <tr>
          <th scope="col" className="izq">
            {p.motivo}
          </th>
          <th scope="col">{p.series}</th>
          <th scope="col">{p.delCatalogo}</th>
          <th scope="col">{p.delVolumen}</th>
          <th scope="col" className="izq">
            {p.queHacerColumna}
          </th>
          <th scope="col">
            <span className="fuera-de-pantalla">{p.abrir}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {grupos.map((g) => {
          const motivo = textosMotivo(g);
          return (
            <tr
              key={g.key}
              className="fila"
              onClick={() => {
                setGrupo(g.key);
                irA("alerts");
              }}
            >
              <td className="izq tinta" style={{ fontWeight: 600 }} title={textoUmbral(g)}>
                {motivo.rotulo}
              </td>
              <td className="sugerido">{conteoDeTotal(g.n_series, nSeries)}</td>
              <td>{porcentajeSimple(g.share_series * 100, 1)}</td>
              <td>
                <span className="barra-volumen" aria-hidden="true">
                  <span style={{ width: `${Math.min(100, g.share_volume * 100)}%` }} />
                </span>{" "}
                {porcentajeSimple(g.share_volume * 100, 1)}
              </td>
              <td className="izq nota" style={{ whiteSpace: "normal", maxWidth: "52ch" }}>
                {motivo.hacer}
              </td>
              <td>
                <button
                  type="button"
                  className="boton-sutil"
                  onClick={(e) => {
                    e.stopPropagation();
                    setGrupo(g.key);
                    irA("alerts");
                  }}
                  aria-label={p.verSeriesDe(motivo.rotulo)}
                >
                  {p.ver}
                </button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function GraficoDemanda({ datos, alto = 220 }: { datos: DatasetSummary; alto?: number }) {
  const textos = t();
  const p = textos.panel;
  const series: Serie[] = [
    { rotulo: textos.bases.observed, valores: datos.daily.map((d) => d.observed), tipo: "observado" },
    { rotulo: textos.bases.recovered, valores: datos.daily.map((d) => d.recovered), tipo: "recuperado" },
  ];
  return (
    <>
      <SerieTemporal
        fechas={datos.daily.map((d) => d.dt)}
        series={series}
        franja={datos.daily.map((d) => d.share_censored)}
        rotuloFranja={p.franjaEscala}
        etiqueta={p.demandaAria}
        alto={alto}
      />
      <div style={{ display: "flex", alignItems: "baseline", gap: 18 }}>
        <Leyenda series={series} />
        <span className="leyenda">
          <span>
            <svg width="12" height="8" aria-hidden="true">
              <rect width="12" height="8" fill="var(--horas-quiebre)" />
            </svg>
            {p.seriesEnQuiebre}
          </span>
        </span>
      </div>
      <DatosDelGrafico
        encabezados={p.columnasDemanda}
        filas={datos.daily.map((d) => [
          d.dt,
          magnitud(d.observed, 1),
          magnitud(d.recovered, 1),
          porcentajeSimple(d.share_censored * 100, 1),
        ])}
      />
    </>
  );
}

/**
 * Mejora de cada modelo contra el naive estacional. Las barras del MASE crudo
 * desde cero no comunicaban nada: entre 0,82 y 0,91 se veían del mismo largo.
 * La mejora sí separa, y es la cifra contra la que se fijó el objetivo.
 */
function RankingModelos({ backtest }: { backtest: BacktestResponse | null }) {
  const p = t().panel;
  const grupos = agruparModelos(backtest?.rows ?? []).filter(
    (g) => g.mejora != null && !g.esReferencia,
  );
  if (grupos.length === 0) return <p className="nota">{p.sinBacktestTexto}</p>;
  const visibles = grupos.slice(0, 6);
  return (
    <>
      <BarrasHorizontales
        etiqueta={p.rankingAria}
        filas={visibles.map((g) => ({
          clave: g.clave,
          rotulo: (
            <span
              style={{ fontWeight: g.miembros.includes(SERVIDO) ? 600 : 400 }}
              className={g.miembros.includes(SERVIDO) ? "tinta" : undefined}
            >
              {g.nombre}
            </span>
          ),
          valor: Math.max(0, g.mejora ?? 0),
          detalle: `MASE ${errorConDispersion(g.mase.mean, g.mase.std)}`,
        }))}
        maximo={Math.max(OBJETIVO_MEJORA, ...visibles.map((g) => g.mejora ?? 0)) * 1.05}
        formato={(v) => porcentajeSimple(v, 1)}
      />
      <p className="nota" style={{ marginTop: 8 }}>
        {p.rankingNota(porcentajeSimple(OBJETIVO_MEJORA))}
      </p>
    </>
  );
}

function Frescura({ health }: { health: Health }) {
  const f = health.freshness;
  const textos = t();
  const p = textos.panel;
  if (!f) return <p className="nota">{p.sinFrescura}</p>;
  const estado: Record<string, string> = {
    al_dia: textos.frescura.al_dia,
    desfasado: textos.frescura.desfasado(f.days_behind != null ? conteo(f.days_behind) : "?"),
    sin_modelo: textos.frescura.sin_modelo,
    sin_datos: textos.frescura.sin_datos,
  };
  return (
    <div className="bloque" style={{ borderTop: "none", paddingTop: 0 }}>
      <dl>
        <dt>{p.datosHasta}</dt>
        <dd>{f.data_date_max ?? "—"}</dd>
        <dt>{p.modeloHasta}</dt>
        <dd>{f.trained_until ?? "—"}</dd>
        <dt>{p.estado}</dt>
        <dd className={f.status === "al_dia" ? undefined : "aviso-texto"}>{estado[f.status]}</dd>
        <dt>{p.ultimaIngesta}</dt>
        <dd>
          {f.last_update_at
            ? `${fechaHora(f.last_update_at)} · ${estadoIngesta(f.last_update_status)}`
            : textos.comun.ninguna}
        </dd>
      </dl>
    </div>
  );
}

function BotonIr({ pantalla, children }: { pantalla: "models" | "pipeline"; children: string }) {
  const { irA } = useEstado();
  return (
    <button type="button" className="boton-sutil" onClick={() => irA(pantalla)} style={{ marginLeft: "auto" }}>
      {children} →
    </button>
  );
}

export function ErrorDeBloque({
  titulo,
  error,
  onReintentar,
}: {
  titulo: string;
  error: unknown;
  onReintentar: () => void;
}) {
  const mensaje = error instanceof Error ? error.message : String(error);
  const comun = t().comun;
  return (
    <div className="consecuencia" data-basis="observed" role="alert" style={{ margin: "12px 0" }}>
      <strong className="tinta">{comun.noSePudoCargar(titulo)}</strong> {mensaje}{" "}
      <button type="button" className="boton-sutil" onClick={onReintentar}>
        {comun.reintentar}
      </button>
    </div>
  );
}
