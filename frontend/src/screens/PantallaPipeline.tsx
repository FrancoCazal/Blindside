/**
 * Pipeline · ¿qué datos y qué modelo se están sirviendo, y cómo se actualizan?
 *
 * Es la única pantalla de operador, y por eso la única donde los nombres de
 * archivo y los comandos van en el texto principal. Es el único lugar de los
 * artefactos: antes aparecían también en Salud del modelo.
 *
 * **Solo lectura.** La API no tiene autenticación, así que esta pantalla dice qué
 * comando correr en vez de ofrecer un botón que lo corra.
 *
 * Los pasos y el detalle de cada ingesta se redactan acá a partir de claves y
 * conteos de la API; el comando y el mensaje crudo de la ingesta se muestran tal
 * cual (el mensaje, en el `title` del detalle).
 *
 * Especificación: `docs/rediseno_frontend.md`, sección 5.7.
 */

import { api, type PipelineStatus, type UpdateRecord } from "../api/client";
import { Encabezado } from "../components/controles";
import { Esqueleto } from "../components/estados";
import { conteo, estadoIngesta, fechaHora, magnitud } from "../format";
import { t } from "../i18n";
import { nombreModelo } from "../modelos";
import { useAsincrono } from "../state";
import { ErrorDeBloque } from "./PantallaPanel";

export function PantallaPipeline() {
  const datos = useAsincrono(() => api.pipeline(), []);
  if (datos.cargando && !datos.datos) return <Esqueleto filas={5} />;
  if (datos.error) {
    return <ErrorDeBloque titulo={t().pipeline.titulo} error={datos.error} onReintentar={datos.recargar} />;
  }
  if (!datos.datos) return null;
  return <Pipeline p={datos.datos} />;
}

/** El detalle de una ingesta, redactado desde sus conteos. Otros tipos muestran el mensaje. */
function detalleIngesta(u: UpdateRecord): string {
  if (u.kind !== "ingest" || u.status == null) return u.message ?? "";
  const n = (v: number | null | undefined) => (v != null ? conteo(v) : "0");
  return t().ingesta.resumen({
    nuevas: n(u.rows_new),
    duplicadas: n(u.rows_duplicate),
    conflictos: n(u.rows_conflict),
    estado: u.status,
  });
}

function Pipeline({ p }: { p: PipelineStatus }) {
  const f = p.freshness;
  const textos = t();
  const x = textos.pipeline;
  const columnas = x.columnasIngestas;
  const frescura =
    f.status === "desfasado"
      ? textos.frescura.desfasado(f.days_behind != null ? conteo(f.days_behind) : "?")
      : (textos.frescura[f.status as "al_dia" | "sin_modelo" | "sin_datos"] ?? f.status);

  return (
    <div className="pagina tablero">
      <Encabezado titulo={x.titulo} contexto={x.contexto} />

      <div className="pipeline">
        <section className="tarjeta tablero-bloque" style={{ marginTop: 0 }} aria-labelledby="t-estado">
          <h2 id="t-estado" className="titulo-bloque">
            {x.estado}
          </h2>
          <div className="bloque" style={{ borderTop: "none", paddingTop: 6 }}>
            <dl>
              <dt>{x.capa}</dt>
              <dd>{p.layer === "sample" ? x.capaMuestra : p.layer === "processed" ? x.capaTrabajo : "—"}</dd>
              <dt>{x.datosHasta}</dt>
              <dd>{f.data_date_max ?? "—"}</dd>
              <dt>{x.modeloHasta}</dt>
              <dd className={f.status === "al_dia" ? undefined : "aviso-texto"}>{f.trained_until ?? "—"}</dd>
              <dt>{x.frescura}</dt>
              <dd className={f.status === "al_dia" ? undefined : "aviso-texto"}>{frescura}</dd>
              <dt>{x.recarga}</dt>
              <dd>
                {p.auto_reload_seconds > 0 ? x.cadaSegundos(magnitud(p.auto_reload_seconds, 0)) : x.apagada}
              </dd>
              <dt>{x.ultimaCarga}</dt>
              <dd>{fechaHora(f.loaded_at)}</dd>
            </dl>
          </div>
          <p className="nota" style={{ marginTop: 10 }}>
            {x.notaEstado}
          </p>
        </section>

        <section className="tarjeta tablero-bloque" style={{ marginTop: 0 }} aria-labelledby="t-archivos">
          <h2 id="t-archivos" className="titulo-bloque">
            {x.archivos}
          </h2>
          <table className="tabla">
            <thead>
              <tr>
                {x.columnas.map((col) => (
                  <th key={col} scope="col" className="izq">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="fila" style={{ cursor: "default" }}>
                <td className="izq tinta">
                  {x.panelHorario} <span className="nota">· {p.panel_file.file}</span>
                </td>
                <td className="izq apagada">{p.panel_file.exists ? fechaHora(p.panel_file.modified) : x.falta}</td>
                <td className="izq apagada">—</td>
                <td className="izq apagada">—</td>
              </tr>
              <tr className="fila" style={{ cursor: "default" }}>
                <td className="izq tinta">
                  {x.demanda} <span className="nota">· {p.demand_file.file}</span>
                </td>
                <td className="izq apagada">{p.demand_file.exists ? fechaHora(p.demand_file.modified) : x.falta}</td>
                <td className="izq apagada">—</td>
                <td className="izq apagada">—</td>
              </tr>
              {p.artifacts.map((a) => (
                <tr key={a.basis} className="fila" style={{ cursor: "default" }}>
                  <td className="izq tinta">
                    {x.modelo(
                      (a.basis === "recovered" ? textos.bases.recovered : textos.bases.observed).toLocaleLowerCase(
                        textos.locale,
                      ),
                    )}{" "}
                    <span className="nota">· {a.current.file}</span>
                  </td>
                  <td className="izq" title={a.model_name ?? undefined}>
                    {a.current.exists ? (
                      <>
                        {a.model_name ? nombreModelo(a.model_name) : x.cargado}
                        <div className="nota">{x.hasta(a.trained_until ?? "—")}</div>
                      </>
                    ) : (
                      <span className="aviso-texto">{x.falta}</span>
                    )}
                  </td>
                  <td className="izq apagada">{a.previous.exists ? fechaHora(a.previous.modified) : "—"}</td>
                  <td className="izq apagada">{a.candidate.exists ? fechaHora(a.candidate.modified) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="nota" style={{ marginTop: 10 }}>
            {x.notaArtefactos}
          </p>
        </section>

        <section className="tarjeta tablero-bloque" style={{ gridColumn: "1 / -1" }} aria-labelledby="t-ingestas">
          <h2 id="t-ingestas" className="titulo-bloque">
            {x.ingestas}
          </h2>
          {p.updates.length === 0 ? (
            <p className="nota">{x.sinIngestas}</p>
          ) : (
            <table className="tabla">
              <thead>
                <tr>
                  <th scope="col" className="izq">
                    {columnas[0]}
                  </th>
                  <th scope="col" className="izq">
                    {columnas[1]}
                  </th>
                  <th scope="col" className="izq">
                    {columnas[2]}
                  </th>
                  <th scope="col">{columnas[3]}</th>
                  <th scope="col">{columnas[4]}</th>
                  <th scope="col">{columnas[5]}</th>
                  <th scope="col" className="izq">
                    {columnas[6]}
                  </th>
                </tr>
              </thead>
              <tbody>
                {p.updates.map((u, i) => (
                  <tr key={`${u.finished_at}-${i}`} className="fila" style={{ cursor: "default" }}>
                    <td className="izq apagada">{fechaHora(u.finished_at)}</td>
                    <td className="izq">{textos.ingesta.tipo[u.kind] ?? u.kind}</td>
                    <td className={`izq${u.status === "rechazado" ? " aviso-texto" : " tinta"}`}>
                      {estadoIngesta(u.status)}
                    </td>
                    <td>{u.rows_new != null ? conteo(u.rows_new) : "—"}</td>
                    <td className="apagada">{u.rows_duplicate != null ? conteo(u.rows_duplicate) : "—"}</td>
                    <td className={u.rows_conflict ? "aviso-texto" : "apagada"}>
                      {u.rows_conflict != null ? conteo(u.rows_conflict) : "—"}
                    </td>
                    <td
                      className="izq nota"
                      style={{ whiteSpace: "normal", maxWidth: "60ch" }}
                      title={u.message ?? undefined}
                    >
                      {detalleIngesta(u)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="tarjeta tablero-bloque" style={{ gridColumn: "1 / -1" }} aria-labelledby="t-comandos">
          <h2 id="t-comandos" className="titulo-bloque">
            {x.comandos}
          </h2>
          <ol className="pasos">
            {p.steps.map((s) => {
              const paso = x.pasos[s.key];
              return (
                <li key={s.key}>
                  <span className="tinta" style={{ fontWeight: 600 }}>
                    {paso?.nombre ?? s.name}
                  </span>
                  <code className="comando">{s.command}</code>
                  <span className="nota">{paso?.que ?? s.what}</span>
                </li>
              );
            })}
          </ol>
        </section>
      </div>
    </div>
  );
}
