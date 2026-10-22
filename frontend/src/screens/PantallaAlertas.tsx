/**
 * Alertas · las series que piden atención, por motivo.
 *
 * Cada motivo es una pestaña con su explicación, su umbral y su remedio, y la
 * tabla muestra **la cifra que disparó** la alerta. Las columnas son las mismas
 * para todos los motivos a propósito: una serie que entra por quiebre puede
 * tener además merma o un MASE malo, y eso se tiene que ver en la misma fila.
 *
 * Los filtros de tienda y de clase viven en la propia pantalla. Antes la clase
 * se mostraba en la barra global y no se aplicaba acá.
 *
 * Especificación: `docs/rediseno_frontend.md`, sección 5.2.
 */

import { api, type AlertGroup, type AlertsResponse } from "../api/client";
import { cifraDeMotivo, rotuloMotivo, textoNoCalculado, textoUmbral, textosMotivo } from "../alertas";
import { SelloMotivo } from "../components/alertas";
import { Encabezado, FiltrosCatalogo } from "../components/controles";
import { Esqueleto } from "../components/estados";
import {
  conteo,
  descripcionCatalogo,
  error as fmtError,
  magnitud,
  porcentajeSimple,
  serieCorta,
} from "../format";
import { t } from "../i18n";
import { useAsincrono, useEstado } from "../state";
import { ErrorDeBloque } from "./PantallaPanel";

const POR_PAGINA = 50;

export function PantallaAlertas({ onElegirSerie }: { onElegirSerie: (id: string) => void }) {
  const { grupo, setGrupo, tienda, clase, offset, setOffset } = useEstado();
  const datos = useAsincrono(
    () =>
      api.alerts({ group: grupo, storeId: tienda, rotationBand: clase, limit: POR_PAGINA, offset }),
    [grupo, tienda, clase, offset],
  );
  const textos = t();
  const a = textos.alertas;

  if (datos.cargando && !datos.datos) return <Esqueleto filas={8} />;
  if (datos.error) {
    return (
      <div className="pagina">
        <ErrorDeBloque titulo={a.titulo} error={datos.error} onReintentar={datos.recargar} />
        {grupo && (
          <button type="button" className="boton-sutil" onClick={() => setGrupo(null)}>
            {a.verTodos}
          </button>
        )}
      </div>
    );
  }
  if (!datos.datos) return null;

  const r = datos.datos;
  const activo = r.groups.find((g) => g.key === grupo) ?? null;
  const c = a.columnas;

  return (
    <div className="pagina">
      <Encabezado
        titulo={a.titulo}
        contexto={a.contexto(conteo(r.n_flagged), conteo(r.n_series), r.data_date_max)}
      />

      <div className="fila-controles">
        <FiltrosCatalogo />
        {(tienda != null || clase != null) && <span className="nota">{a.enFiltro(conteo(r.total))}</span>}
      </div>

      <div className="pestanas" role="group" aria-label={a.filtrarAria}>
        <Pestana activa={grupo == null} onClick={() => setGrupo(null)} rotulo={a.todas} cifra={r.n_flagged} />
        {r.groups.map((g) => (
          <Pestana
            key={g.key}
            activa={g.key === grupo}
            onClick={() => setGrupo(g.key)}
            rotulo={textosMotivo(g).rotulo}
            cifra={g.n_series}
            urgente={g.urgent}
          />
        ))}
      </div>

      {activo ? <FichaGrupo g={activo} /> : <FichaTodas r={r} />}

      {r.unavailable.length > 0 && (
        <div className="consecuencia" data-basis="observed" style={{ margin: "12px 0" }}>
          {r.unavailable.map((u) => (
            <div key={u.key}>
              {a.noCalculado(rotuloMotivo(u.key), textoNoCalculado(u.key, u.reason))}
            </div>
          ))}
        </div>
      )}

      <div className="tarjeta" style={{ marginTop: "var(--e4)" }}>
        <table className="tabla">
          <caption className="fuera-de-pantalla">
            {a.caption(activo ? textosMotivo(activo).rotulo : null)}
          </caption>
          <thead>
            <tr>
              <th scope="col" className="izq">
                {c.serie}
              </th>
              <th scope="col" className="izq col-opcional">
                {c.clase}
              </th>
              <th scope="col" className="izq">
                {c.motivos}
              </th>
              <th scope="col">{c.demanda}</th>
              <th scope="col" title={c.estimadaTitulo}>
                {c.estimada}
              </th>
              <th scope="col" title={c.rachaTitulo}>
                {c.racha}
              </th>
              <th scope="col" title={c.maseTitulo}>
                {c.mase}
              </th>
              <th scope="col" title={c.sinVenderTitulo}>
                {c.sinVender}
              </th>
              <th scope="col" title={c.seEvitaTitulo}>
                {c.seEvita}
              </th>
            </tr>
          </thead>
          <tbody>
            {r.items.map((it) => (
              <tr
                key={it.series.series_id}
                className="fila"
                onClick={() => onElegirSerie(it.series.series_id)}
              >
                <td className="izq serie">
                  <button
                    type="button"
                    className="enlace-fila"
                    title={descripcionCatalogo(it.label)}
                    onClick={(e) => {
                      e.stopPropagation();
                      onElegirSerie(it.series.series_id);
                    }}
                  >
                    {serieCorta(it.series.store_id, it.series.product_id)}
                  </button>
                </td>
                <td className="izq apagada col-opcional">
                  {it.rotation_band ? (textos.bandas[it.rotation_band] ?? it.rotation_band) : "—"}
                </td>
                <td className="izq">
                  <span className="sellos" title={it.reasons.map((k) => cifraDeMotivo(it, k)).join(" · ")}>
                    {it.reasons.map((k) => (
                      <SelloMotivo key={k} clave={k} />
                    ))}
                  </span>
                </td>
                <td>{magnitud(it.demand_mean)}</td>
                <td className={it.estimated_share > 0.3 ? "aviso-texto" : "apagada"}>
                  {porcentajeSimple(it.estimated_share * 100)}
                </td>
                <td className={it.current_run_days >= 5 ? "aviso-texto" : "apagada"}>
                  {it.current_run_days > 0 ? textos.comun.dias(conteo(it.current_run_days)) : "—"}
                </td>
                <td className={it.mase != null && it.mase > 1 ? "aviso-texto" : "apagada"}>
                  {it.mase != null ? fmtError(it.mase) : "—"}
                </td>
                <td className={it.waste_policy != null && it.waste_policy >= 0.5 ? "aviso-texto" : "apagada"}>
                  {it.waste_policy != null ? porcentajeSimple(it.waste_policy * 100) : "—"}
                </td>
                <td>{it.waste_avoidable != null ? porcentajeSimple(it.waste_avoidable * 100) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {r.items.length === 0 && (
          <p className="nota" style={{ padding: "14px var(--e5)" }}>
            {a.vacio}
          </p>
        )}

        <div className="paginador">
          <span className="nota">
            {r.total === 0
              ? textos.comun.ceroSeries
              : textos.comun.rango(
                  conteo(offset + 1),
                  conteo(Math.min(offset + POR_PAGINA, r.total)),
                  conteo(r.total),
                )}
          </span>
          <div className="paginador-botones">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset(offset - POR_PAGINA)}
              aria-label={textos.comun.paginaAnterior}
            >
              ‹
            </button>
            <button
              type="button"
              disabled={offset + POR_PAGINA >= r.total}
              onClick={() => setOffset(offset + POR_PAGINA)}
              aria-label={textos.comun.paginaSiguiente}
            >
              ›
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Pestana({
  activa,
  onClick,
  rotulo,
  cifra,
  urgente,
}: {
  activa: boolean;
  onClick: () => void;
  rotulo: string;
  cifra: number;
  urgente?: boolean;
}) {
  return (
    <button
      type="button"
      aria-pressed={activa}
      className="pestana"
      data-urgente={urgente ? "true" : undefined}
      onClick={onClick}
    >
      {rotulo} <span className="tabular apagada">{conteo(cifra)}</span>
    </button>
  );
}

function FichaGrupo({ g }: { g: AlertGroup }) {
  const a = t().alertas;
  const motivo = textosMotivo(g);
  return (
    <div className="ficha-grupo">
      <div>
        <div className="rotulo">{a.queSignifica}</div>
        <p>{motivo.significa}</p>
      </div>
      <div>
        <div className="rotulo">{a.queHacer}</div>
        <p className="tinta">{motivo.hacer}</p>
      </div>
      <div>
        <div className="rotulo">{a.umbral}</div>
        <p>{textoUmbral(g)}</p>
        <p className="nota">
          {a.peso(
            porcentajeSimple(g.share_series * 100, 1),
            porcentajeSimple(g.share_volume * 100, 1),
            conteo(g.only_this),
          )}
        </p>
      </div>
    </div>
  );
}

function FichaTodas({ r }: { r: AlertsResponse }) {
  return (
    <div className="ficha-grupo">
      <div style={{ gridColumn: "1 / -1" }}>
        <p>
          {t().alertas.todasTexto(
            porcentajeSimple((100 * (r.n_series - r.n_flagged)) / Math.max(1, r.n_series)),
          )}
        </p>
      </div>
    </div>
  );
}
