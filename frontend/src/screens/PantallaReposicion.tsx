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
  SENAL,
  type Senal,
  aCsv,
  clasificarSenal,
  cuantilCritico,
  deltaPct,
  diasConQuiebre,
  impactoDeLinea,
} from "../domain";
import {
  conteo,
  conteoDeTotal,
  cuantil,
  error as fmtError,
  etiquetaFecha,
  magnitud,
  porcentaje,
  serieCorta,
} from "../format";
import { type Columna, useAsincrono, useConteo, useEstado } from "../state";
import { Esqueleto } from "../components/estados";
import { Sparkline } from "../components/piezas";

/** Series que entran a la vista. Un `/forecast` de 500 series es costoso. */
const FILAS = 25;

/** Cómo se nombra cada columna en el subtítulo de la tabla. */
const ROTULO_ORDEN: Record<Columna, string> = {
  impacto: "impacto esperado",
  sugerido: "cantidad sugerida",
  politica: "política actual",
  delta: "delta contra la política",
  senal: "fracción de demanda estimada",
  serie: "identificador de serie",
};

interface Fila {
  serie: SeriesItem;
  historia: SeriesHistory;
  politica: number;
  sugerido: number;
  delta: number;
  impacto: number;
  /** E[(D-q)+] bajo la distribución del modelo. Cota inferior: ver tail_mass. */
  faltante: number;
  /** E[(q-D)+]. En perecederos es merma esperada. */
  sobrante: number;
  /** Cuánto de la señal reciente es observada y cuánto estimada. */
  senal: Senal;
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

/**
 * Encabezado que ordena al hacer clic.
 *
 * Es un `<button>` dentro del `<th>` y no un `<th onClick>`: un th con manejador
 * no es alcanzable por teclado ni se anuncia como control. `aria-sort` en el th es
 * lo que le dice al lector de pantalla por qué columna está ordenada la tabla.
 */
function ThOrden({
  columna,
  etiqueta,
  className,
}: {
  columna: Columna;
  etiqueta: string;
  className?: string;
}) {
  const { orden, direccion, ordenarPor } = useEstado();
  const activa = orden === columna;
  const aria = activa ? (direccion === "desc" ? "descending" : "ascending") : "none";
  return (
    <th scope="col" className={className} aria-sort={aria}>
      <button
        type="button"
        className="th-orden"
        onClick={() => ordenarPor(columna)}
        aria-label={`Ordenar por ${etiqueta}`}
      >
        {etiqueta}
        <span aria-hidden="true" className="flecha">
          {activa ? (direccion === "desc" ? "▾" : "▴") : ""}
        </span>
      </button>
    </th>
  );
}

/** Navegación entre páginas. El total viene del envelope de `/series`. */
function Paginador({ total }: { total: number }) {
  const { offset, setOffset } = useEstado();
  const desde = total === 0 ? 0 : offset + 1;
  const hasta = Math.min(offset + FILAS, total);
  const haySiguiente = hasta < total;
  const hayAnterior = offset > 0;
  const pagina = Math.floor(offset / FILAS) + 1;
  const paginas = Math.max(1, Math.ceil(total / FILAS));

  return (
    <div className="paginador">
      <span className="nota">
        {conteoDeTotal(desde, total).replace(/^\d+/, `${desde}–${hasta}`)} · página {pagina} de{" "}
        {paginas}
      </span>
      <div className="paginador-botones">
        <button
          type="button"
          onClick={() => setOffset(0)}
          disabled={!hayAnterior}
          aria-label="Primera página"
        >
          ««
        </button>
        <button
          type="button"
          onClick={() => setOffset(offset - FILAS)}
          disabled={!hayAnterior}
          aria-label="Página anterior"
        >
          «
        </button>
        <button
          type="button"
          onClick={() => setOffset(offset + FILAS)}
          disabled={!haySiguiente}
          aria-label="Página siguiente"
        >
          »
        </button>
      </div>
    </div>
  );
}

function Reposicion({
  backtest,
  onElegirSerie,
}: {
  backtest: BacktestResponse | null;
  onElegirSerie: (id: string) => void;
}) {
  const { basis, ratio, setRatio, tienda, clase, orden: columna, direccion, offset } = useEstado();
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
      offset,
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
    // Todo lo económico de la fila sale de la misma línea de `/reorder`, que
    // ahora devuelve la política, el faltante y el sobrante esperados y el delta
    // de costo. Antes la política se recalculaba acá desde la historia y el
    // impacto se estimaba con la banda como uniforme; las dos cosas eran
    // supuestos viviendo en la capa de presentación.
    const lineaPorSerie = new Map(
      (orden?.lines ?? [])
        .filter((l) => l.dt === primeraFecha)
        .map((l) => [l.series.series_id, l]),
    );

    const filas: Fila[] = pagina.items.map((serie) => {
      const historia = porSerie.get(serie.series_id)!;
      const puntos = pronosticoPorSerie.get(serie.series_id) ?? [];
      const linea = lineaPorSerie.get(serie.series_id);
      const politica = linea?.policy_qty ?? 0;
      const sugerido = linea?.qty ?? puntos[0]?.y_pred ?? 0;
      return {
        serie,
        historia,
        politica,
        sugerido,
        delta: deltaPct(sugerido, politica),
        // El costo esperado de la política menos el de la orden, o sea cuánto
        // ahorra la sugerencia en esta serie. Sale de `cost_delta_pct`, que el
        // backend calcula evaluando las dos cantidades bajo la misma
        // distribución predictiva.
        impacto: impactoDeLinea(linea, ratio),
        faltante: linea?.expected_shortfall ?? 0,
        sobrante: linea?.expected_overage ?? 0,
        senal: clasificarSenal(historia.summary),
        quiebre14: diasConQuiebre(historia.points, 14),
        diasQuiebre28: historia.summary.censored_days_last_28,
        rachaMax: historia.summary.max_run_days,
        pronostico: puntos,
      };
    });

    // El orden se aplica sobre la página, no sobre las 3.066 series: `/series`
    // no ordena por impacto porque el impacto no existe hasta pedir `/reorder`.
    // Es una limitación real y está dicha al pie de la tabla.
    const signo = direccion === "desc" ? -1 : 1;
    const clave = (f: Fila): number | string => {
      switch (columna) {
        case "serie":
          return f.serie.series_id;
        case "politica":
          return f.politica;
        case "sugerido":
          return f.sugerido;
        case "delta":
          return f.delta;
        case "senal":
          return f.senal.fraccionEstimada;
        default:
          return f.impacto;
      }
    };
    filas.sort((a, b) => {
      const ka = clave(a);
      const kb = clave(b);
      if (typeof ka === "string" || typeof kb === "string") {
        return signo * String(ka).localeCompare(String(kb), "es");
      }
      return signo * (ka - kb);
    });
    return { filas, total: pagina.total, orden, motivo };
  }, [basis, ratio, tienda, clase, columna, direccion, offset]);

  if (datos.cargando && !datos.datos) return <Esqueleto filas={FILAS} />;
  if (datos.error) throw datos.error;
  if (!datos.datos) return null;

  const { filas, total, orden, motivo } = datos.datos;
  const qEstrella = orden?.critical_fraction ?? cuantilCritico(1, ratio);
  const totalSugerido = filas.reduce((a, f) => a + f.sugerido, 0);
  const totalPolitica = filas.reduce((a, f) => a + f.politica, 0);
  const impactoTotal = filas.reduce((a, f) => a + f.impacto, 0);
  const faltanteTotal = filas.reduce((a, f) => a + f.faltante, 0);
  const sobranteTotal = filas.reduce((a, f) => a + f.sobrante, 0);
  const maxImpacto = filas.reduce((a, f) => Math.max(a, f.impacto), 0);
  const maxHoras = Math.max(1, ...filas.flatMap((f) => f.quiebre14));
  // La alerta es "el pronóstico de esta serie se apoya en la corrección de
  // censura", no "esta serie tuvo quiebres". El criterio anterior contaba días
  // censurados con umbral 14 de 28, y la mediana del panel es 12: marcaba el
  // 35,6 % del catálogo, o sea que no separaba nada. Ver SENAL en domain.ts.
  const enAlerta = filas.filter((f) => f.senal.estado !== "observada").length;
  const mase = (backtest?.rows ?? [])
    .filter((r) => r.metric === "mase")
    .sort((a, b) => a.mean - b.mean)[0];

  /**
   * Descarga la página visible como CSV.
   *
   * Exporta **lo que se está viendo** y no las 3.066 series, y eso es deliberado:
   * las columnas económicas salen de `/reorder`, que se pide por lote de series, así
   * que un export completo serían 123 llamadas y una espera sin indicación de
   * progreso. El nombre del archivo lleva la base y los filtros para que dos
   * descargas distintas no se pisen.
   */
  const exportar = () => {
    const csv = aCsv(
      [
        "serie",
        "tienda",
        "producto",
        "clase",
        "politica",
        "sugerido",
        "delta_pct",
        "impacto",
        "faltante_esperado",
        "sobrante_esperado",
        "fraccion_estimada_28d",
        "racha_quiebre_vigente_d",
        "dias_quiebre_28d",
      ],
      filas.map((f) => [
        f.serie.series_id,
        f.serie.store_id,
        f.serie.product_id,
        f.serie.rotation_band ?? "",
        f.politica,
        f.sugerido,
        f.delta,
        f.impacto,
        f.faltante,
        f.sobrante,
        f.senal.fraccionEstimada,
        f.senal.rachaVigente,
        f.diasQuiebre28,
      ]),
    );
    const partes = ["reposicion", basis, tienda != null ? `t${tienda}` : null, clase].filter(Boolean);
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = `${partes.join("-")}.csv`;
    enlace.click();
    URL.revokeObjectURL(url);
  };

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
          <div className="rotulo">Señal recuperada</div>
          <div
            className="kpi-valor"
            style={enAlerta > 0 ? { color: "var(--advertencia-texto)" } : undefined}
          >
            {conteoDeTotal(enAlerta, filas.length)}
          </div>
          <div className="kpi-pie">
            más del {Math.round(SENAL.parcial * 100)} % de su demanda reciente es estimada
          </div>
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
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <span className="nota">
                  {conteoDeTotal(filas.length, total)} · ordenadas por {ROTULO_ORDEN[columna]}
                </span>
                <button type="button" className="boton-sutil" onClick={exportar}>
                  Exportar CSV
                </button>
              </div>
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
                Todo lo económico de la tabla viene de <code>/reorder</code>. El
                faltante y el sobrante esperados salen de integrar E[(D−q)⁺] sobre
                la distribución que describen los cuantiles del modelo; son
                esperanzas implicadas por el modelo, no resultados medidos. El
                faltante es una <strong>cota inferior</strong>: la grilla termina en
                el cuantil 0,95 y el {porcentaje((orden?.tail_mass ?? 0) * 100, 1)}{" "}
                de masa de arriba no está descrito. El delta compara la orden contra
                la media móvil de {orden?.policy_window ?? 21} días{" "}
                <strong>de la misma base</strong>, con las dos cantidades evaluadas
                bajo la misma distribución.
              </caption>
              <thead>
                <tr>
                  <ThOrden columna="serie" etiqueta="Serie" className="izq" />
                  <th scope="col" className="col-opcional">
                    Clase
                  </th>
                  <th scope="col" className="col-opcional">
                    Quiebre 14 d
                  </th>
                  <ThOrden columna="senal" etiqueta="Señal" className="col-opcional" />
                  <ThOrden columna="politica" etiqueta="Política" />
                  <ThOrden columna="sugerido" etiqueta="Sugerido" />
                  <ThOrden columna="delta" etiqueta="Δ" />
                  <ThOrden columna="impacto" etiqueta="Impacto" />
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

            <Paginador total={total} />
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
                <dt>Ahorro esperado</dt>
                <dd>{magnitud(impactoTotal)}</dd>
                <dt>Faltante esperado</dt>
                <dd>{magnitud(faltanteTotal)}</dd>
                <dt>Sobrante esperado</dt>
                <dd>{magnitud(sobranteTotal)}</dd>
                <dt>Cu / Co</dt>
                <dd>1 / {magnitud(ratio, 1)}</dd>
              </dl>
              <div className="nota" style={{ marginTop: 8 }}>
                Esperanzas bajo la distribución del modelo, no resultados medidos.
                El faltante es cota inferior: el{" "}
                {porcentaje((orden?.tail_mass ?? 0) * 100, 1)} de masa por encima
                del cuantil 0,95 no está descrito.
              </div>
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
        {/* Cuánto de la señal reciente es observada. No es un juicio sobre el
            modelo sino sobre sus insumos: con una fracción alta el pronóstico se
            apoya en la propia corrección de censura, y el intervalo conformal no
            refleja esa incertidumbre porque mide el error del modelo y no el de la
            recuperación. */}
        <td className="col-opcional">
          <span className="senal" data-estado={fila.senal.estado} title={fila.senal.detalle}>
            {fila.senal.rotulo}
          </span>
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
          <td colSpan={8} id={idDetalle}>
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
