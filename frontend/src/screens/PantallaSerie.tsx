/**
 * Serie · ¿por qué le creo a esta cantidad?
 *
 * Junta en una pantalla lo que antes estaba en tres: el gráfico y la cantidad (la
 * serie individual), el pronóstico día por día (la fila expandida de reposición)
 * y la atribución por feature (explicabilidad). Las tres responden la misma
 * pregunta sobre la misma serie, y separarlas obligaba a recordar qué serie se
 * había elegido en otra pantalla.
 *
 * La cifra explicada es **la misma** que la cantidad sugerida. Antes no: la
 * explicación era de la mediana (5,14) y la orden del cuantil crítico (5,53).
 *
 * Especificación: `docs/rediseno_frontend.md`, sección 5.4.
 */

import { useEffect, useRef } from "react";

import {
  api,
  type AlertItem,
  type ExplainResponse,
  type ForecastResponse,
  type ReorderResponse,
  type SeriesHistory,
} from "../api/client";
import { cifraDeMotivo } from "../alertas";
import { GraficoSerie } from "../charts/GraficoSerie";
import { SelloMotivo } from "../components/alertas";
import { ComoSeCalcula, Encabezado, RatioCosto } from "../components/controles";
import { Esqueleto } from "../components/estados";
import { ToggleCensura } from "../components/piezas";
import { clasificarSenal, cuantilCritico, deltaPct, etiquetaFeature, valorFeature } from "../domain";
import {
  conteo,
  cuantil,
  descripcionCatalogo,
  etiquetaFecha,
  magnitud,
  porcentaje,
  porcentajeSimple,
  serieCorta,
} from "../format";
import { t } from "../i18n";
import { useAsincrono, useConteo, useEstado } from "../state";
import { ErrorDeBloque } from "./PantallaPanel";

interface Datos {
  historia: SeriesHistory;
  pronostico: ForecastResponse;
  orden: ReorderResponse | null;
  ordenError: string | null;
  explicacion: ExplainResponse | null;
  alerta: AlertItem | null;
  rotulo: string | null;
  clase: string | null;
}

export function PantallaSerie({ serie }: { serie: string }) {
  const { basis, ratio, anunciar } = useEstado();
  const recoverCensoring = basis === "recovered";

  const datos = useAsincrono<Datos>(async () => {
    const [historia, pronostico, alertas, item] = await Promise.all([
      api.history(serie),
      api.forecast({ seriesIds: [serie], recoverCensoring }),
      api.alerts({ seriesId: serie, limit: 1 }).catch(() => null),
      api.series({ q: serie, limit: 5 }).catch(() => null),
    ]);
    // La orden y la explicación pueden no estar disponibles — un artefacto sin
    // cuantiles responde 501 —, y la pantalla sigue en pie con la evidencia.
    let orden: ReorderResponse | null = null;
    let ordenError: string | null = null;
    try {
      orden = await api.reorder({ seriesIds: [serie], co: ratio, recoverCensoring });
    } catch (e) {
      ordenError = e instanceof Error ? e.message : String(e);
    }
    const dt = orden?.lines[0]?.dt ?? pronostico.forecasts[0]?.points[0]?.dt;
    const explicacion = dt
      ? await api.explain({ seriesId: serie, dt, topK: 8, recoverCensoring }).catch(() => null)
      : null;
    const meta = item?.items.find((s) => s.series_id === serie) ?? null;
    return {
      historia,
      pronostico,
      orden,
      ordenError,
      explicacion,
      alerta: alertas?.items[0] ?? null,
      rotulo: meta?.label ?? null,
      clase: meta?.rotation_band ?? null,
    };
  }, [serie, recoverCensoring, ratio]);

  const cantidad = datos.datos?.orden?.lines[0]?.qty ?? null;
  const previa = useRef<number | null>(null);

  // El anuncio se emite cuando llega el número nuevo, no al hacer clic.
  useEffect(() => {
    if (cantidad == null) return;
    const antes = previa.current;
    previa.current = cantidad;
    if (antes == null || antes === cantidad) return;
    const textos = t();
    anunciar(textos.toggle.anuncioCantidad(textos.bases[basis], magnitud(antes), magnitud(cantidad)));
  }, [cantidad, basis, anunciar]);

  const textos = t();
  const s = textos.serie;

  if (datos.cargando && !datos.datos) return <Esqueleto />;
  if (datos.error) {
    return <ErrorDeBloque titulo={textos.nav.pantallas.series} error={datos.error} onReintentar={datos.recargar} />;
  }
  if (!datos.datos) return null;

  const { historia, pronostico, orden, ordenError, explicacion, alerta, rotulo, clase } = datos.datos;
  const ref = historia.series;
  const linea = orden?.lines[0] ?? null;
  const politica = linea?.policy_qty ?? 0;
  const qEstrella = orden?.critical_fraction ?? cuantilCritico(1, ratio);
  const resumen = historia.summary;
  const senal = clasificarSenal(resumen);
  const puntos = pronostico.forecasts[0]?.points ?? [];
  const lineasPorDia = new Map((orden?.lines ?? []).map((l) => [l.dt, l]));

  return (
    <div className="pagina">
      <Encabezado
        titulo={serieCorta(ref.store_id, ref.product_id)}
        contexto={[
          rotulo ? descripcionCatalogo(rotulo) : null,
          clase ? s.rotacion(textos.bandas[clase] ?? clase) : null,
          s.dias(conteo(historia.points.length)),
        ]
          .filter(Boolean)
          .join(" · ")}
      >
        <ToggleCensura />
      </Encabezado>

      {alerta && alerta.reasons.length > 0 && (
        <div className="franja-motivos" role="note">
          <span className="rotulo">{s.enAlerta}</span>
          {alerta.reasons.map((k) => (
            <span key={k} className="motivo-con-cifra">
              <SelloMotivo clave={k} />
              <span className="nota">{cifraDeMotivo(alerta, k)}</span>
            </span>
          ))}
        </div>
      )}

      <div className="tarjeta cuerpo-serie">
        <div style={{ padding: "16px var(--e5) 14px", borderRight: "1px solid var(--regla-fina)" }}>
          <GraficoSerie
            historia={historia}
            pronostico={puntos}
            cantidadSugerida={cantidad}
            basis={basis}
          />
        </div>

        <div className="panel" style={{ padding: "16px var(--e5) 14px" }}>
          <div>
            <div className="rotulo">
              {s.cantidad}
              {linea ? ` · ${etiquetaFecha(linea.dt)}` : ""}
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
              {cantidad != null ? (
                <Cifra valor={cantidad} />
              ) : (
                <span className="cifra-decision" style={{ color: "var(--apagada)" }}>
                  —
                </span>
              )}
              <span className="nota">q* {cuantil(qEstrella)}</span>
            </div>
            {ordenError && (
              <div className="nota aviso-texto" style={{ marginTop: 6 }}>
                {ordenError}
              </div>
            )}
          </div>

          {linea && (
            <div className="bloque">
              <dl>
                <dt>{s.politica}</dt>
                <dd>{magnitud(politica)}</dd>
                <dt>{s.cambio}</dt>
                <dd className={cantidad != null && cantidad > politica ? "acento" : undefined}>
                  {politica > 0 && cantidad != null ? porcentaje(deltaPct(cantidad, politica)) : "—"}
                </dd>
                <dt>{s.ahorro}</dt>
                <dd>{porcentajeSimple(-linea.cost_delta_pct, 1)}</dd>
                <dt>{s.faltante}</dt>
                <dd>{magnitud(linea.expected_shortfall)}</dd>
                <dt>{s.sobrante}</dt>
                <dd>{magnitud(linea.expected_overage)}</dd>
              </dl>
            </div>
          )}

          <div className="bloque">
            <RatioCosto compacto />
          </div>
        </div>
      </div>

      <div className="tablero-pie">
        <section className="tarjeta tablero-bloque" aria-labelledby="t-dias">
          <div className="tablero-titulo">
            <h2 id="t-dias">{s.proximos}</h2>
          </div>
          <table className="tabla">
            <thead>
              <tr>
                {s.columnas.map((col, i) => (
                  <th key={col} scope="col" className={i === 0 ? "izq" : undefined}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {puntos.map((p) => {
                const l = lineasPorDia.get(p.dt);
                return (
                  <tr key={p.dt} className="fila" style={{ cursor: "default" }}>
                    <td className="izq apagada">{etiquetaFecha(p.dt)}</td>
                    <td>{magnitud(p.y_pred)}</td>
                    <td className="apagada">
                      {p.pred_lo != null && p.pred_hi != null
                        ? `${magnitud(p.pred_lo)} – ${magnitud(p.pred_hi)}`
                        : "—"}
                    </td>
                    <td className="apagada">{l ? magnitud(l.policy_qty) : "—"}</td>
                    <td className="sugerido">{l ? magnitud(l.qty) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="nota" style={{ marginTop: 8 }}>
            {s.proximosNota(cuantil(qEstrella))}
          </p>
        </section>

        <section className="tarjeta tablero-bloque" aria-labelledby="t-porque">
          <div className="tablero-titulo">
            <h2 id="t-porque">{s.porQue}</h2>
            {explicacion && (
              <span className="nota">
                {magnitud(explicacion.prediction)} · {etiquetaFecha(explicacion.dt)}
              </span>
            )}
          </div>
          {explicacion ? <Cascada datos={explicacion} /> : <p className="nota">{s.sinExplicacion}</p>}
        </section>
      </div>

      <section className="tarjeta tablero-bloque" aria-labelledby="t-censura">
        <div className="tablero-titulo">
          <h2 id="t-censura">{s.censura}</h2>
          <span className="nota">{senal.detalle}</span>
        </div>
        <div className="fila-cifras">
          <Cifrita rotulo={s.recuperada} valor={porcentaje(resumen.uplift_pct)} acento />
          <Cifrita
            rotulo={s.diasQuiebre}
            valor={s.deTotal(conteo(resumen.n_censored_days), conteo(resumen.n_days))}
          />
          <Cifrita
            rotulo={s.horasQuiebre}
            valor={
              resumen.mean_oos_hours_when_censored != null
                ? s.deTotal(magnitud(resumen.mean_oos_hours_when_censored, 1), conteo(historia.open_hours))
                : "—"
            }
          />
          <Cifrita rotulo={s.rachaMaxima} valor={textos.comun.dias(conteo(resumen.max_run_days))} />
          <Cifrita rotulo={s.estimada28} valor={porcentajeSimple(resumen.estimated_share_last_28 * 100)} />
        </div>
      </section>

      <ComoSeCalcula>
        <p>{s.comoCantidad(cuantil(qEstrella), String(orden?.policy_window ?? 21))}</p>
        {explicacion && (
          <p>
            {s.comoShap(
              explicacion.model_name,
              explicacion.quantile != null ? cuantil(explicacion.quantile) : s.critico,
              magnitud(explicacion.base_value, 3),
              explicacion.point_forecast != null ? magnitud(explicacion.point_forecast) : "—",
            )}
          </p>
        )}
        <p>{s.comoLimpios(porcentajeSimple(resumen.uplift_pct_clean_days, 2))}</p>
      </ComoSeCalcula>
    </div>
  );
}

function Cifra({ valor }: { valor: number }) {
  const mostrado = useConteo(valor);
  return <span className="cifra-decision">{magnitud(mostrado)}</span>;
}

function Cifrita({
  rotulo,
  valor,
  acento,
}: {
  rotulo: string;
  valor: string;
  acento?: boolean;
}) {
  return (
    <div>
      <div className="rotulo">{rotulo}</div>
      <div className={`cifrita tabular${acento ? " acento" : ""}`}>{valor}</div>
    </div>
  );
}

/**
 * Cascada horizontal desde el valor base. A la derecha lo que sube la cantidad,
 * a la izquierda lo que la baja. El acento no se usa para «positivo» — está
 * reservado para lo recuperado —, así que el signo lo lleva la dirección.
 */
function Cascada({ datos }: { datos: ExplainResponse }) {
  const s = t().serie;
  const contribuciones = datos.contributions;
  const maxAbs = Math.max(...contribuciones.map((c) => Math.abs(c.contribution)), 1e-9);
  return (
    <div>
      <ul className="cascada" aria-label={s.cascadaAria}>
        {contribuciones.map((c) => {
          const ancho = (Math.abs(c.contribution) / maxAbs) * 50;
          const positiva = c.contribution >= 0;
          return (
            <li key={c.feature} title={s.variableTecnica(c.feature)}>
              <span className="cascada-rotulo">
                {etiquetaFeature(c.feature)}
                <span className="apagada"> = {valorFeature(c.feature, c.value)}</span>
              </span>
              <span className="cascada-pista" aria-hidden="true">
                <span className="cascada-cero" />
                <span
                  className="cascada-barra"
                  data-signo={positiva ? "mas" : "menos"}
                  style={{ left: positiva ? "50%" : `${50 - ancho}%`, width: `${ancho}%` }}
                />
              </span>
              <span className="tabular cascada-cifra">
                {positiva ? "+" : "\u2212"}
                {magnitud(Math.abs(c.contribution), 2)}
              </span>
            </li>
          );
        })}
      </ul>
      <dl className="cascada-cuenta">
        <dt>{s.valorBase}</dt>
        <dd>{magnitud(datos.base_value, 2)}</dd>
        <dt>{s.estasVariables(conteo(contribuciones.length))}</dt>
        <dd>{aporteConSigno(contribuciones.reduce((a, c) => a + c.contribution, 0))}</dd>
        <dt>{s.resto}</dt>
        <dd>{aporteConSigno(datos.rest ?? 0)}</dd>
        <dt className="tinta">{s.cantidad}</dt>
        <dd className="tinta" style={{ fontWeight: 600 }}>
          {magnitud(datos.prediction, 2)}
        </dd>
      </dl>
    </div>
  );
}

/** Un aporte con signo explícito y menos tipográfico. No es un porcentaje. */
function aporteConSigno(v: number): string {
  return `${v >= 0 ? "+" : "\u2212"}${magnitud(Math.abs(v), 2)}`;
}
