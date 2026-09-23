/**
 * Pantalla 4a · reposición. Es la landing.
 *
 * Responde «¿qué pido hoy, y cuánto?». El sistema no termina en una predicción,
 * termina en una cantidad, así que la entrada es la lista de reposición y no un
 * resumen de exactitud.
 */

import { useState } from "react";

import {
  api,
  type BacktestResponse,
  type ForecastResponse,
  type ReorderResponse,
  type SeriesHistory,
  type SeriesItem,
} from "../api/client";
import {
  RATIOS,
  cuantilCritico,
  deltaPct,
  diasConQuiebre,
  impactoSimulado,
  politicaMediaMovil,
} from "../domain";
import {
  conteo,
  cuantil,
  error as fmtError,
  etiquetaFecha,
  magnitud,
  porcentaje,
  serieCorta,
} from "../format";
import { useAsincrono, useConteo, useEstado } from "../state";
import { Esqueleto } from "../components/estados";
import { SelloSim, Sparkline } from "../components/piezas";

/** Series que entran a la vista. Un `/forecast` de 500 series es costoso. */
const FILAS = 25;

interface Fila {
  serie: SeriesItem;
  historia: SeriesHistory;
  politica: number;
  sugerido: number;
  delta: number;
  impacto: number;
  quiebre14: number[];
  diasQuiebre28: number;
  rachaMax: number;
  pronostico: ForecastResponse["forecasts"][number]["points"];
}

export function PantallaReposicion({
  backtest,
  onElegirSerie,
}: {
  backtest: BacktestResponse | null;
  onElegirSerie: (id: string) => void;
}) {
  const { basis, ratio, tienda, clase } = useEstado();
  // La fila abierta se resetea al cambiar de base, de ratio o de filtro, y la
  // forma idiomática de resetear estado local es remontar.
  return (
    <Reposicion
      key={`${basis}-${ratio}-${tienda}-${clase}`}
      backtest={backtest}
      onElegirSerie={onElegirSerie}
    />
  );
}

function Reposicion({
  backtest,
  onElegirSerie,
}: {
  backtest: BacktestResponse | null;
  onElegirSerie: (id: string) => void;
}) {
  const { basis, ratio, setRatio, tienda, clase } = useEstado();
  const recoverCensoring = basis === "recovered";
  const [abierta, setAbierta] = useState(0);

  const datos = useAsincrono<{
    filas: Fila[];
    total: number;
    orden: ReorderResponse | null;
    motivo: string | null;
  }>(async () => {
    const pagina = await api.series({
      limit: FILAS,
      storeId: tienda ?? undefined,
      rotationBand: clase ?? undefined,
    });
    if (pagina.items.length === 0) {
      return { filas: [], total: pagina.total, orden: null, motivo: null };
    }
    const ids = pagina.items.map((s) => s.series_id);
    const [historias, pronostico] = await Promise.all([
      api.historyBatch(ids, 28),
      api.forecast({ seriesIds: ids, recoverCensoring }),
    ]);

    let orden: ReorderResponse | null = null;
    let motivo: string | null = null;
    try {
      orden = await api.reorder({
        seriesIds: ids,
        co: ratio,
        recoverCensoring,
      });
    } catch (e) {
      motivo = e instanceof Error ? e.message : String(e);
    }

    const porSerie = new Map(
      historias.series.map((h) => [h.series.series_id, h]),
    );
    const pronosticoPorSerie = new Map(
      pronostico.forecasts.map((f) => [f.series.series_id, f.points]),
    );
    // La cantidad de la fila es la del **primer** día del horizonte: la
    // pregunta de la pantalla es qué pedir hoy, no cuánto en total en la semana.
    const primeraFecha = orden?.lines[0]?.dt ?? null;
    const cantidadPorSerie = new Map(
      (orden?.lines ?? [])
        .filter((l) => l.dt === primeraFecha)
        .map((l) => [l.series.series_id, l.qty]),
    );

    const filas: Fila[] = pagina.items.map((serie) => {
      const historia = porSerie.get(serie.series_id)!;
      const puntos = pronosticoPorSerie.get(serie.series_id) ?? [];
      const politica = politicaMediaMovil(historia.points, basis);
      const sugerido =
        cantidadPorSerie.get(serie.series_id) ?? puntos[0]?.y_pred ?? 0;
      const impacto = puntos[0]
        ? impactoSimulado(puntos[0], sugerido, politica, 1, ratio).ahorro
        : 0;
      return {
        serie,
        historia,
        politica,
        sugerido,
        delta: deltaPct(sugerido, politica),
        impacto,
        quiebre14: diasConQuiebre(historia.points, 14),
        diasQuiebre28: historia.summary.censored_days_last_28,
        rachaMax: historia.summary.max_run_days,
        pronostico: puntos,
      };
    });

    filas.sort((a, b) => b.impacto - a.impacto);
    return { filas, total: pagina.total, orden, motivo };
  }, [basis, ratio, tienda, clase]);

  if (datos.cargando && !datos.datos) return <Esqueleto filas={FILAS} />;
  if (datos.error) throw datos.error;
  if (!datos.datos) return null;

  const { filas, total, orden, motivo } = datos.datos;
  const qEstrella = orden?.critical_fraction ?? cuantilCritico(1, ratio);
  const totalSugerido = filas.reduce((a, f) => a + f.sugerido, 0);
  const totalPolitica = filas.reduce((a, f) => a + f.politica, 0);
  const impactoTotal = filas.reduce((a, f) => a + f.impacto, 0);
  const maxImpacto = filas.reduce((a, f) => Math.max(a, f.impacto), 0);
  const maxHoras = Math.max(1, ...filas.flatMap((f) => f.quiebre14));
  const enAlerta = filas.filter((f) => f.diasQuiebre28 >= 14).length;
  const mase = (backtest?.rows ?? [])
    .filter((r) => r.metric === "mase")
    .sort((a, b) => a.mean - b.mean)[0];

  if (filas.length === 0) {
    return (
      <div className="pagina">
        <div className="tarjeta" style={{ padding: "20px var(--e5)" }}>
          <h2>Sin series para estos filtros</h2>
          <p className="nota" style={{ marginTop: 8, maxWidth: "70ch" }}>
            Ninguna de las {conteo(total)} series del panel coincide con la combinación de tienda y
            clase de rotación elegida. Limpiá un filtro para volver a ver la lista.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="pagina">
      {/* La regla de los cinco segundos: lo primero que el ojo encuentra es la
          decisión, y después su respaldo. La primera tarjeta ES la cantidad a
          pedir, así que la jerarquía del handoff no se pierde — se refuerza,
          porque antes ese número estaba arriba a la derecha. */}
      <div className="kpis">
        <div className="kpi" data-primario="true">
          <div className="rotulo">Total a pedir</div>
          <div className="kpi-valor">
            <CifraTotal valor={totalSugerido} />
          </div>
          <div className="kpi-pie">
            q* {cuantil(qEstrella)} · {conteo(filas.length)} series · adimensional
          </div>
        </div>
        <div className="kpi">
          <div className="rotulo">Δ contra la política</div>
          <div className={`kpi-valor ${totalSugerido > totalPolitica ? "acento" : ""}`}>
            {porcentaje(deltaPct(totalSugerido, totalPolitica))}
          </div>
          <div className="kpi-pie">media móvil 21 d: {magnitud(totalPolitica)}</div>
        </div>
        <div className="kpi">
          <div className="rotulo">Series en alerta</div>
          <div
            className="kpi-valor"
            style={enAlerta > 0 ? { color: "var(--advertencia-texto)" } : undefined}
          >
            {conteo(enAlerta)}
          </div>
          <div className="kpi-pie">con quiebre en la mitad de los últimos 28 días</div>
        </div>
        <div className="kpi">
          <div className="rotulo">MASE del mejor modelo</div>
          <div className="kpi-valor">{mase ? fmtError(mase.mean) : "—"}</div>
          <div className="kpi-pie">
            {mase
              ? `± ${fmtError(mase.std)} entre orígenes · peor ${fmtError(mase.worst_origin)}`
              : "falta correr el backtest"}
          </div>
        </div>
      </div>

      <div className="tarjeta">
        <div className="cuerpo-reposicion" style={{ padding: "20px var(--e5) 8px" }}>
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 12,
                marginBottom: 12,
              }}
            >
              <h2>Qué pedir hoy</h2>
              <span className="nota">
                {conteo(filas.length)} de {conteo(total)} series · ordenadas por
                impacto esperado
              </span>
            </div>

            <table className="tabla">
              <caption
                className="nota"
                style={{
                  captionSide: "bottom",
                  textAlign: "left",
                  paddingTop: 10,
                }}
              >
                El orden y la columna de impacto se calculan en el cliente a
                partir de la banda conformal, tomándola como distribución
                uniforme{" "}
                <SelloSim titulo="/reorder devuelve expected_shortfall, expected_overage y cost_delta_pct en cero: sin verdad de terreno no hay faltante realizado" />
                . La política es la media móvil de 21 días de la base activa.
                Las cantidades, el pronóstico y la banda vienen de la API.
              </caption>
              <thead>
                <tr>
                  <th scope="col" className="izq">
                    Serie
                  </th>
                  <th scope="col" className="col-opcional">
                    Clase
                  </th>
                  <th scope="col" className="col-opcional">
                    Quiebre 14 d
                  </th>
                  <th scope="col">Política</th>
                  <th scope="col">Sugerido</th>
                  <th scope="col">Δ</th>
                  <th scope="col">
                    Impacto
                    <SelloSim titulo="Calculado en el cliente; el backend no lo sirve" />
                  </th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f, i) => (
                  <FilaSerie
                    key={f.serie.series_id}
                    fila={f}
                    abierta={i === abierta}
                    maxImpacto={maxImpacto}
                    maxHoras={maxHoras}
                    onAbrir={() => setAbierta(i === abierta ? -1 : i)}
                    onIrASerie={() => onElegirSerie(f.serie.series_id)}
                  />
                ))}
              </tbody>
            </table>
          </div>

          <div className="panel panel-reposicion">
            <div>
              <div className="rotulo">Ratio de costo Co / Cu</div>
              <div
                className="ratios"
                style={{ marginTop: 6 }}
                role="group"
                aria-label="Ratio de costo"
              >
                {RATIOS.map((r) => (
                  <button
                    key={r.co}
                    type="button"
                    aria-pressed={r.co === ratio}
                    onClick={() => setRatio(r.co)}
                  >
                    <span className="valor">{magnitud(r.co, 1)}</span>
                    <span className="cuantil">
                      q* {cuantil(cuantilCritico(1, r.co))}
                    </span>
                  </button>
                ))}
              </div>
              <div className="nota" style={{ marginTop: 6 }}>
                {RATIOS.find((r) => r.co === ratio)?.lectura}
              </div>
            </div>

            {/* El total, el delta y las series en alerta ya están en las tarjetas
                de KPI, arriba a la izquierda. Repetirlos acá competía con ellos;
                queda solo lo que las tarjetas no dicen. */}
            <div className="bloque">
              <dl>
                <dt>Política actual</dt>
                <dd>{magnitud(totalPolitica)}</dd>
                <dt>
                  Impacto acumulado
                  <SelloSim titulo="Calculado en el cliente" />
                </dt>
                <dd>{magnitud(impactoTotal)}</dd>
                <dt>Cu / Co</dt>
                <dd>1 / {magnitud(ratio, 1)}</dd>
              </dl>
            </div>

            <div className="consecuencia" data-basis={basis}>
              {basis === "recovered" ? (
                <>
                  <strong style={{ fontWeight: 600 }}>
                    Censura corregida.
                  </strong>{" "}
                  Es la base de las cantidades de esta lista.
                </>
              ) : (
                <>
                  <strong style={{ fontWeight: 600 }}>
                    Es lo que ve el ERP.
                  </strong>{" "}
                  Subestima la demanda en los días con quiebre: pedir esto
                  reproduce el quiebre de la semana que viene.
                </>
              )}
            </div>

            {motivo && (
              <div
                className="nota"
                style={{ color: "var(--advertencia-texto)" }}
              >
                Las cantidades no vienen del newsvendor: {motivo}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function FilaSerie({
  fila,
  abierta,
  maxImpacto,
  maxHoras,
  onAbrir,
  onIrASerie,
}: {
  fila: Fila;
  abierta: boolean;
  maxImpacto: number;
  maxHoras: number;
  onAbrir: () => void;
  onIrASerie: () => void;
}) {
  const maxPron = Math.max(
    ...fila.pronostico.map((p) => p.pred_hi ?? p.y_pred),
    1,
  );
  const idDetalle = `detalle-${fila.serie.series_id}`;
  return (
    <>
      {/* El `aria-expanded` va en un **botón dentro de la celda** y no en el `tr`:
          ARIA solo lo permite en filas de `grid` o `treegrid`, y esta es una tabla
          común. El audit con axe lo marcó como violación seria en las 25 filas.
          La fila sigue siendo clickeable con el mouse; el teclado llega al botón,
          que es el control de verdad. */}
      <tr className="fila" onClick={onAbrir}>
        <td className="izq serie">
          <button
            type="button"
            aria-expanded={abierta}
            aria-controls={idDetalle}
            onClick={(e) => {
              e.stopPropagation();
              onAbrir();
            }}
            style={{ font: "inherit", color: "inherit", textAlign: "left" }}
          >
            {serieCorta(fila.serie.store_id, fila.serie.product_id)}
          </button>
        </td>
        {/* La clase es la banda de rotación con los mismos cortes del backtest:
            en baja rotación no se espera que el modelo complejo gane, así que hay
            que poder ver de qué clase es cada fila sin salir de la tabla. */}
        <td className="col-opcional apagada">
          {fila.serie.rotation_band ?? "—"}
        </td>
        <td className="col-opcional">
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              justifyContent: "flex-end",
            }}
          >
            <Sparkline valores={fila.quiebre14} maximo={maxHoras} />
            <span className="apagada">{conteo(fila.diasQuiebre28)} d</span>
          </div>
        </td>
        <td className="apagada">{magnitud(fila.politica)}</td>
        <td className="sugerido">{magnitud(fila.sugerido)}</td>
        <td style={{ fontWeight: fila.delta >= 20 ? 600 : 400 }}>
          {porcentaje(fila.delta)}
        </td>
        <td>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              justifyContent: "flex-end",
            }}
          >
            <span
              className="barra-impacto"
              style={{
                width:
                  maxImpacto > 0 ? `${(fila.impacto / maxImpacto) * 78}px` : 0,
              }}
            />
            <span>{magnitud(fila.impacto)}</span>
          </div>
        </td>
      </tr>

      {abierta && (
        <tr className="fila-expandida">
          <td colSpan={7} id={idDetalle}>
            <div className="detalle">
              <div>
                <div className="rotulo" style={{ marginBottom: 6 }}>
                  Pronóstico a 7 días
                </div>
                {fila.pronostico.map((p) => (
                  <div className="dia" key={p.dt}>
                    <span className="apagada">{etiquetaFecha(p.dt)}</span>
                    <span
                      className="barra-dia"
                      style={{
                        width: `${Math.max(2, (p.y_pred / maxPron) * 100)}%`,
                      }}
                    />
                    <span className="apagada" style={{ textAlign: "right" }}>
                      {p.pred_lo != null && p.pred_hi != null
                        ? `${magnitud(p.pred_lo)} – ${magnitud(p.pred_hi)}`
                        : "sin banda"}
                    </span>
                    <span
                      className="tinta"
                      style={{ textAlign: "right", fontWeight: 600 }}
                    >
                      {magnitud(p.y_pred)}
                    </span>
                  </div>
                ))}
              </div>
              <div>
                <div className="rotulo" style={{ marginBottom: 6 }}>
                  Por qué difiere
                </div>
                <dl
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr auto",
                    gap: "6px 12px",
                    margin: 0,
                    fontSize: 12,
                  }}
                >
                  <dt className="apagada">Días con quiebre (28 d)</dt>
                  <dd style={{ margin: 0, textAlign: "right" }}>
                    {conteo(fila.diasQuiebre28)}
                  </dd>
                  <dt className="apagada">Racha máxima</dt>
                  <dd style={{ margin: 0, textAlign: "right" }}>
                    {conteo(fila.rachaMax)} d
                  </dd>
                  <dt className="apagada">Uplift de la serie</dt>
                  <dd
                    style={{ margin: 0, textAlign: "right" }}
                    className="acento"
                  >
                    {porcentaje(fila.historia.summary.uplift_pct)}
                  </dd>
                </dl>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onIrASerie();
                  }}
                  style={{
                    marginTop: 10,
                    fontSize: 11.5,
                    color: "var(--tinta)",
                    borderBottom: "1px solid var(--regla-control)",
                  }}
                >
                  Ver la serie completa →
                </button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function CifraTotal({ valor }: { valor: number }) {
  const mostrado = useConteo(valor);
  return (
    <span className="cifra-decision cifra-total">{magnitud(mostrado)}</span>
  );
}
