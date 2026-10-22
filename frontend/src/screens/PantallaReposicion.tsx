/**
 * Reposición · cuánto pedir de cada serie, y dónde se gana más.
 *
 * La lista se ordena **en el servidor sobre todo el catálogo** (`/reorder/catalog`).
 * La versión anterior pedía `/reorder` para las 25 series de una página de
 * `/series`, que viene ordenada por id, y ordenaba esas 25: la página 1 de «qué
 * pedir hoy» eran las series de la tienda 0 en orden alfabético.
 *
 * Los cuatro KPI son del catálogo filtrado y todos se leen contra la política
 * actual de la misma base, así que el toggle los mueve. No hay «total a pedir»:
 * sumar cantidades de productos distintos no significa nada.
 *
 * Especificación: `docs/rediseno_frontend.md`, sección 5.3.
 */

import { useEffect, useRef } from "react";

import { api, type CatalogLine, type ReorderCatalog, type SeriesHistory } from "../api/client";
import { SelloMotivo } from "../components/alertas";
import { ComoSeCalcula, Encabezado, FiltrosCatalogo, RatioCosto } from "../components/controles";
import { Esqueleto } from "../components/estados";
import { Sparkline, ToggleCensura } from "../components/piezas";
import { aCsv, diasConQuiebre } from "../domain";
import {
  conteo,
  conteoDeTotal,
  cuantil,
  descripcionCatalogo,
  etiquetaFecha,
  magnitud,
  porcentaje,
  porcentajeSimple,
  serieCorta,
} from "../format";
import { t } from "../i18n";
import { type Columna, useAsincrono, useConteo, useEstado } from "../state";
import { ErrorDeBloque } from "./PantallaPanel";

/** Filas por página. */
const FILAS = 25;

/** Ventana del minigráfico de quiebre. El conteo de la columna usa la misma. */
const DIAS_QUIEBRE = 14;

/**
 * Encabezados del CSV. Son identificadores y no texto de interfaz: no cambian con
 * el idioma, para que una planilla que los lee no se rompa según quién exportó.
 */
const COLUMNAS_CSV = [
  "serie",
  "tienda",
  "producto",
  "clase",
  "fecha",
  "politica",
  "sugerido",
  "delta_pct",
  "faltante_esperado",
  "sobrante_esperado",
  "ahorro_esperado",
  "parte_del_ahorro",
  "motivos",
];

export function PantallaReposicion({ onElegirSerie }: { onElegirSerie: (id: string) => void }) {
  const { basis, ratio, tienda, clase, orden, direccion, offset, anunciar, health } = useEstado();
  const recoverCensoring = basis === "recovered";

  const datos = useAsincrono<{
    catalogo: ReorderCatalog;
    historias: Map<string, SeriesHistory>;
  }>(async () => {
    const catalogo = await api.reorderCatalog({
      recoverCensoring,
      co: ratio,
      storeId: tienda,
      rotationBand: clase,
      sort: orden,
      dir: direccion,
      limit: FILAS,
      offset,
    });
    const ids = catalogo.items.map((i) => i.series.series_id);
    const historias = new Map<string, SeriesHistory>();
    if (ids.length > 0) {
      const lote = await api.historyBatch(ids, 28);
      for (const h of lote.series) historias.set(h.series.series_id, h);
    }
    return { catalogo, historias };
  }, [basis, ratio, tienda, clase, orden, direccion, offset]);

  // Al cambiar de base se anuncia la cifra que cambió, cuando llega. El `ref`
  // evita repetirlo al re-renderizar la misma respuesta.
  const ultimo = useRef<string | null>(null);
  const totales = datos.datos?.catalogo.totals ?? null;
  useEffect(() => {
    if (datos.cargando || !totales) return;
    const clave = `${basis}-${ratio}-${tienda}-${clase}-${totales.qty_delta_pct}`;
    if (ultimo.current === clave) return;
    const primera = ultimo.current == null;
    ultimo.current = clave;
    if (primera) return;
    const textos = t();
    anunciar(textos.reposicion.anuncio(textos.bases[basis], porcentaje(totales.qty_delta_pct)));
  }, [anunciar, basis, clase, datos.cargando, ratio, tienda, totales]);

  const textos = t();
  const r = textos.reposicion;

  if (datos.cargando && !datos.datos) return <Esqueleto filas={FILAS} />;
  if (datos.error) {
    return <ErrorDeBloque titulo={r.titulo} error={datos.error} onReintentar={datos.recargar} />;
  }
  if (!datos.datos) return null;

  const { catalogo, historias } = datos.datos;
  const tot = catalogo.totals;
  const maxParte = Math.max(1e-9, ...catalogo.items.map((i) => i.saving_share));
  const c = r.columnas;

  const exportar = async () => {
    // Exporta el catálogo filtrado entero, no la página: el servidor ya lo tiene
    // calculado y en caché, así que son unas pocas llamadas de 500 filas.
    const filas: CatalogLine[] = [];
    for (let desde = 0; desde < catalogo.total; desde += 500) {
      const parte = await api.reorderCatalog({
        recoverCensoring,
        co: ratio,
        storeId: tienda,
        rotationBand: clase,
        sort: orden,
        dir: direccion,
        limit: 500,
        offset: desde,
      });
      filas.push(...parte.items);
    }
    const csv = aCsv(
      COLUMNAS_CSV,
      filas.map((f) => [
        f.series.series_id,
        f.series.store_id,
        f.series.product_id,
        f.rotation_band ?? "",
        catalogo.dt,
        f.policy_qty,
        f.qty,
        f.delta_pct ?? null,
        f.expected_shortfall,
        f.expected_overage,
        f.saving,
        f.saving_share,
        (f.reasons ?? []).join(" "),
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

  return (
    <div className="pagina">
      <Encabezado
        titulo={r.titulo}
        contexto={r.contexto(
          etiquetaFecha(catalogo.dt),
          conteoDeTotal(catalogo.total, health?.panel?.n_series),
          r.orden[orden],
        )}
      >
        <ToggleCensura />
      </Encabezado>

      <div className="fila-controles">
        <RatioCosto />
        <FiltrosCatalogo />
        <button type="button" className="boton-sutil" onClick={() => void exportar()} style={{ marginLeft: "auto" }}>
          {textos.comun.exportarCsv}
        </button>
      </div>

      {basis === "observed" && (
        <p className="aviso-base" role="note">
          {r.avisoObservada}
        </p>
      )}

      <div className="kpis" role="list">
        <div className="kpi" data-primario="true" role="listitem">
          <div className="rotulo">{r.kpiAhorro}</div>
          <div className="kpi-valor">
            <CifraAnimada valor={-tot.cost_delta_pct} formato={(v) => porcentajeSimple(v, 1)} />
          </div>
          <div className="kpi-pie">{r.kpiAhorroPie}</div>
        </div>
        <Kpi
          rotulo={r.kpiOrden}
          valor={porcentaje(tot.qty_delta_pct)}
          pie={r.kpiOrdenPie(conteoDeTotal(tot.n_big_change, tot.n_series))}
        />
        <Kpi rotulo={r.kpiSobrante} valor={porcentaje(tot.overage_delta_pct)} pie={r.kpiSobrantePie} />
        <Kpi rotulo={r.kpiFaltante} valor={porcentaje(tot.shortfall_delta_pct)} pie={r.kpiFaltantePie} />
      </div>

      <div className="tarjeta">
        {catalogo.items.length === 0 ? (
          <p className="nota" style={{ padding: "20px var(--e5)" }}>
            {r.vacio}
          </p>
        ) : (
          <table className="tabla tabla-reposicion">
            <caption className="fuera-de-pantalla">{r.caption(catalogo.dt, r.orden[orden])}</caption>
            <thead>
              <tr>
                <ThOrden columna="serie" etiqueta={c.serie} className="izq" />
                <th scope="col" className="izq col-opcional">
                  {c.clase}
                </th>
                <th scope="col" className="izq">
                  {c.motivos}
                </th>
                <ThOrden columna="politica" etiqueta={c.politica} />
                <ThOrden columna="sugerido" etiqueta={c.sugerido} />
                <ThOrden columna="delta" etiqueta={c.delta} />
                <ThOrden columna="impacto" etiqueta={c.ahorro} />
                <th scope="col" className="col-opcional" title={c.quiebreTitulo(String(DIAS_QUIEBRE))}>
                  {c.quiebre(String(DIAS_QUIEBRE))}
                </th>
              </tr>
            </thead>
            <tbody>
              {catalogo.items.map((f) => (
                <FilaSerie
                  key={f.series.series_id}
                  linea={f}
                  historia={historias.get(f.series.series_id) ?? null}
                  maxParte={maxParte}
                  onAbrir={() => onElegirSerie(f.series.series_id)}
                />
              ))}
            </tbody>
          </table>
        )}
        <Paginador total={catalogo.total} />
      </div>

      <ComoSeCalcula>
        <p>
          {r.comoCuantil(
            cuantil(catalogo.critical_fraction),
            etiquetaFecha(catalogo.dt),
            magnitud(catalogo.co, 1),
            magnitud(catalogo.cu, 0),
          )}
        </p>
        <p>
          {r.comoPolitica(
            String(catalogo.policy_window),
            catalogo.model_name,
            porcentajeSimple(catalogo.tail_mass * 100, 1),
          )}
        </p>
        <p>{r.comoAhorro}</p>
      </ComoSeCalcula>
    </div>
  );
}

function Kpi({ rotulo, valor, pie }: { rotulo: string; valor: string; pie: string }) {
  return (
    <div className="kpi" role="listitem">
      <div className="rotulo">{rotulo}</div>
      <div className="kpi-valor">{valor}</div>
      <div className="kpi-pie">{pie}</div>
    </div>
  );
}

function CifraAnimada({ valor, formato }: { valor: number; formato: (v: number) => string }) {
  const mostrado = useConteo(valor);
  return <span className="cifra-decision cifra-total">{formato(mostrado)}</span>;
}

/**
 * Encabezado que ordena. Es un `<button>` dentro del `<th>`: un th con manejador
 * no es alcanzable por teclado. `aria-sort` le dice al lector por qué columna está
 * ordenada.
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
  const r = t().reposicion;
  const activa = orden === columna;
  const aria = activa ? (direccion === "desc" ? "descending" : "ascending") : "none";
  return (
    <th scope="col" className={className} aria-sort={aria}>
      <button
        type="button"
        className="th-orden"
        onClick={() => ordenarPor(columna)}
        aria-label={r.ordenarPor(r.orden[columna])}
      >
        {etiqueta}
        <span aria-hidden="true" className="flecha">
          {activa ? (direccion === "desc" ? "▾" : "▴") : ""}
        </span>
      </button>
    </th>
  );
}

function FilaSerie({
  linea,
  historia,
  maxParte,
  onAbrir,
}: {
  linea: CatalogLine;
  historia: SeriesHistory | null;
  maxParte: number;
  onAbrir: () => void;
}) {
  const horas = historia ? diasConQuiebre(historia.points, DIAS_QUIEBRE) : [];
  const diasConQ = horas.filter((h) => h > 0).length;
  const maxHoras = historia?.open_hours ?? 16;
  const delta = linea.delta_pct;
  const textos = t();

  return (
    <tr className="fila" onClick={onAbrir}>
      <td className="izq serie">
        <button
          type="button"
          className="enlace-fila"
          title={descripcionCatalogo(linea.label)}
          onClick={(e) => {
            e.stopPropagation();
            onAbrir();
          }}
        >
          {serieCorta(linea.series.store_id, linea.series.product_id)}
        </button>
      </td>
      <td className="izq apagada col-opcional">
        {linea.rotation_band ? (textos.bandas[linea.rotation_band] ?? linea.rotation_band) : "—"}
      </td>
      <td className="izq">
        <span className="sellos">
          {(linea.reasons ?? []).map((k) => (
            <SelloMotivo key={k} clave={k} />
          ))}
        </span>
      </td>
      <td className="apagada">{magnitud(linea.policy_qty)}</td>
      <td className="sugerido">{magnitud(linea.qty)}</td>
      <td style={{ fontWeight: delta != null && Math.abs(delta) >= 20 ? 600 : 400 }}>
        {delta != null ? porcentaje(delta) : "—"}
      </td>
      <td>
        <div className="celda-barra">
          <span
            className="barra-impacto"
            style={{ width: `${(Math.max(0, linea.saving_share) / maxParte) * 64}px` }}
          />
          <span>{porcentajeSimple(linea.saving_share * 100, 1)}</span>
        </div>
      </td>
      <td className="col-opcional">
        {historia ? (
          <div
            className="celda-barra"
            title={textos.reposicion.diasConQuiebre(conteo(diasConQ), String(DIAS_QUIEBRE))}
          >
            <Sparkline valores={horas} maximo={maxHoras} />
            <span className="apagada">{textos.comun.dias(conteo(diasConQ))}</span>
          </div>
        ) : (
          "—"
        )}
      </td>
    </tr>
  );
}

function Paginador({ total }: { total: number }) {
  const { offset, setOffset } = useEstado();
  const comun = t().comun;
  const desde = total === 0 ? 0 : offset + 1;
  const hasta = Math.min(offset + FILAS, total);
  const pagina = Math.floor(offset / FILAS) + 1;
  const paginas = Math.max(1, Math.ceil(total / FILAS));
  return (
    <div className="paginador">
      <span className="nota">
        {comun.paginacion(conteo(desde), conteo(hasta), conteo(total), conteo(pagina), conteo(paginas))}
      </span>
      <div className="paginador-botones">
        <button type="button" onClick={() => setOffset(0)} disabled={offset === 0} aria-label={comun.primeraPagina}>
          ««
        </button>
        <button
          type="button"
          onClick={() => setOffset(offset - FILAS)}
          disabled={offset === 0}
          aria-label={comun.paginaAnterior}
        >
          «
        </button>
        <button
          type="button"
          onClick={() => setOffset(offset + FILAS)}
          disabled={hasta >= total}
          aria-label={comun.paginaSiguiente}
        >
          »
        </button>
      </div>
    </div>
  );
}
