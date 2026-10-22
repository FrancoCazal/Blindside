/**
 * Datos · ¿cómo es el panel y cuánta demanda esconde?
 *
 * El panel servido en las formas que lo explican: el tiempo, la semana, la hora
 * del día, las tiendas, las categorías y la rotación, casi todo con la venta
 * observada al lado de la demanda recuperada, porque el argumento del proyecto es
 * la brecha entre las dos.
 *
 * Absorbe Vista general (la tabla de recuperación y la comprobación de la
 * ventana comercial, plegada) y el Mapa de productos (como bloque). El pipeline
 * se fue a su propia pantalla.
 *
 * Especificación: `docs/rediseno_frontend.md`, sección 5.6.
 */

import { api, type DatasetSummary, type GroupStat } from "../api/client";
import { ComoSeCalcula, Encabezado } from "../components/controles";
import { Esqueleto } from "../components/estados";
import {
  BarrasHorizontales,
  Columnas,
  DatosDelGrafico,
  Leyenda,
  type Serie,
} from "../components/graficos";
import { MapaCatalogo } from "../components/MapaCatalogo";
import { conteo, magnitud, porcentaje, porcentajeSimple } from "../format";
import { t } from "../i18n";
import { useAsincrono } from "../state";
import { ErrorDeBloque, GraficoDemanda } from "./PantallaPanel";

/** Franjas comerciales del día: de 6:00 a 22:00. */
const FRANJAS = 16;

interface FilaCensura {
  grupo: string;
  n: number;
  demanda_observada: number;
  demanda_latente: number;
  uplift_pct: number;
}

export function PantallaDatos({ onElegirSerie }: { onElegirSerie: (id: string) => void }) {
  const datos = useAsincrono(() => api.datasetSummary(), []);
  const censura = useAsincrono(() => api.censoring(), []);
  const textos = t();
  const x = textos.datos;

  if (datos.cargando && !datos.datos) return <Esqueleto filas={6} />;
  if (datos.error) {
    return <ErrorDeBloque titulo={x.titulo} error={datos.error} onReintentar={datos.recargar} />;
  }
  if (!datos.datos) return null;
  const d = datos.datos;
  const horasComerciales =
    d.totals.mean_oos_hours_when_censored != null
      ? (d.totals.share_censored_days * d.totals.mean_oos_hours_when_censored) / FRANJAS
      : null;

  return (
    <div className="pagina tablero">
      <Encabezado
        titulo={x.titulo}
        contexto={`${d.source} · ${d.panel?.is_sample ? x.capaMuestra : x.capaTrabajo}${
          d.panel ? ` · ${d.panel.date_min} → ${d.panel.date_max}` : ""
        }`}
      />

      <div className="kpis" role="list">
        <Kpi rotulo={x.kpiSeries} valor={conteo(d.totals.n_series)} pie={x.kpiSeriesPie(conteo(d.totals.n_days))} />
        <Kpi rotulo={x.kpiFilas} valor={conteo(d.totals.n_rows)} pie={x.kpiFilasPie} />
        <Kpi
          rotulo={x.kpiQuiebre}
          valor={porcentajeSimple(d.totals.share_censored_days * 100, 1)}
          pie={
            d.totals.mean_oos_hours_when_censored != null
              ? x.kpiQuiebrePie(magnitud(d.totals.mean_oos_hours_when_censored, 1))
              : ""
          }
        />
        <Kpi
          rotulo={x.kpiRecuperada}
          valor={porcentaje(d.totals.uplift_pct)}
          pie={x.kpiRecuperadaPie}
          acento
        />
      </div>

      <section className="tarjeta tablero-bloque" aria-labelledby="t-tiempo">
        <div className="tablero-titulo">
          <h2 id="t-tiempo">{x.enElTiempo}</h2>
          <span className="nota">{x.enElTiempoNota}</span>
        </div>
        <GraficoDemanda datos={d} alto={240} />
      </section>

      <section className="tarjeta tablero-bloque" aria-labelledby="t-recuperacion">
        <div className="tablero-titulo">
          <h2 id="t-recuperacion">{x.escondida}</h2>
          <span className="nota">{x.escondidaNota}</span>
        </div>
        {censura.datos ? (
          <TablaCensura filas={censura.datos.comparison as unknown as FilaCensura[]} />
        ) : censura.error ? (
          <p className="nota">{x.errorRecuperacion}</p>
        ) : (
          <div className="hueso" style={{ height: 110 }} />
        )}
      </section>

      <div className="tablero-pie">
        <Semana d={d} />
        <Horas d={d} />
      </div>

      <div className="tablero-pie">
        <PorGrupo
          titulo={x.porTienda}
          id="t-tiendas"
          filas={d.stores}
          prefijo={x.prefijoTienda}
          nota={x.notaTiendas}
        />
        <PorGrupo
          titulo={x.porCategoria}
          id="t-categorias"
          filas={d.categories}
          prefijo={x.prefijoCategoria}
          nota={x.notaCategorias}
        />
      </div>

      <div className="tablero-pie">
        <Rotacion d={d} />
        <Histograma d={d} />
      </div>

      <section className="tarjeta tablero-bloque" aria-labelledby="t-mapa">
        <div className="tablero-titulo">
          <h2 id="t-mapa">{x.catalogo}</h2>
        </div>
        <MapaCatalogo onElegirSerie={onElegirSerie} />
      </section>

      <ComoSeCalcula titulo={textos.comun.comoSeVerifica}>
        <p>
          <strong>{x.verificaVentana}</strong> {x.verificaVentanaTexto(String(FRANJAS))}{" "}
          {horasComerciales != null &&
            `${x.verificaCuenta(
              porcentajeSimple(d.totals.share_censored_days * 100, 1),
              magnitud(d.totals.mean_oos_hours_when_censored ?? 0, 1),
              String(FRANJAS),
              porcentajeSimple(horasComerciales * 100, 1),
            )} `}
          {x.verificaCierre}
        </p>
        <p>
          <strong>{x.verificaLimpios}</strong> {x.verificaLimpiosTexto}
        </p>
      </ComoSeCalcula>
    </div>
  );
}

function TablaCensura({ filas }: { filas: FilaCensura[] }) {
  const x = t().datos;
  return (
    <table className="tabla">
      <thead>
        <tr>
          {x.columnasCensura.map((col, i) => (
            <th key={col} scope="col" className={i === 0 ? "izq" : undefined}>
              {col}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {filas.map((f) => {
          const limpio = Math.abs(f.uplift_pct) < 1e-9;
          return (
            <tr className="fila" key={f.grupo} style={{ cursor: "default" }}>
              <td className="izq tinta">{x.gruposCensura[f.grupo] ?? f.grupo}</td>
              <td className="apagada">{conteo(f.n)}</td>
              <td className="apagada">{magnitud(f.demanda_observada, 3)}</td>
              <td className={limpio ? "apagada" : "acento"}>{magnitud(f.demanda_latente, 3)}</td>
              <td style={{ fontWeight: limpio ? 400 : 600 }}>{porcentaje(f.uplift_pct, 1)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Kpi({
  rotulo,
  valor,
  pie,
  acento,
}: {
  rotulo: string;
  valor: string;
  pie: string;
  acento?: boolean;
}) {
  return (
    <div className="kpi" role="listitem">
      <div className="rotulo">{rotulo}</div>
      <div className={`kpi-valor${acento ? " acento" : ""}`}>{valor}</div>
      <div className="kpi-pie">{pie}</div>
    </div>
  );
}

function Semana({ d }: { d: DatasetSummary }) {
  const textos = t();
  const x = textos.datos;
  const dias = textos.diasSemana;
  const orden = [...d.weekday].sort((a, b) => a.dow - b.dow);
  const series: Serie[] = [
    { rotulo: textos.bases.observed, valores: orden.map((w) => w.observed_mean), tipo: "observado" },
    { rotulo: textos.bases.recovered, valores: orden.map((w) => w.recovered_mean), tipo: "recuperado" },
  ];
  return (
    <section className="tarjeta tablero-bloque" aria-labelledby="t-semana">
      <div className="tablero-titulo">
        <h2 id="t-semana">{x.semana}</h2>
      </div>
      <Columnas categorias={orden.map((w) => dias[w.dow])} series={series} etiqueta={x.semanaAria} />
      <Leyenda series={series} />
      <DatosDelGrafico
        encabezados={x.columnasSemana}
        filas={orden.map((w) => [
          dias[w.dow],
          magnitud(w.observed_mean, 3),
          magnitud(w.recovered_mean, 3),
          porcentajeSimple(w.share_censored * 100, 1),
        ])}
      />
    </section>
  );
}

function Horas({ d }: { d: DatasetSummary }) {
  const textos = t();
  const x = textos.datos;
  if (d.hourly.length === 0) {
    return (
      <section className="tarjeta tablero-bloque" aria-labelledby="t-horas">
        <div className="tablero-titulo">
          <h2 id="t-horas">{x.porHora}</h2>
        </div>
        <p className="nota">{x.sinHoras(d.hourly_note ?? "")}</p>
      </section>
    );
  }
  const cerradas = new Set(d.hourly.filter((h) => !h.open).map((h) => h.hour));
  const series: Serie[] = [
    { rotulo: x.horasSerieQuiebre, valores: d.hourly.map((h) => h.share_stockout), tipo: "neutro" },
    { rotulo: x.horasSerieVenta, valores: d.hourly.map((h) => h.share_sales), tipo: "observado" },
  ];
  const abiertas = d.hourly.filter((h) => h.open);
  const apertura = abiertas[0];
  const cierre = abiertas[abiertas.length - 1];
  const pico = [...abiertas].sort((a, b) => b.share_sales - a.share_sales)[0];
  return (
    <section className="tarjeta tablero-bloque" aria-labelledby="t-horas">
      <div className="tablero-titulo">
        <h2 id="t-horas">{x.horas}</h2>
        <span className="nota">{x.horasNota}</span>
      </div>
      <Columnas
        categorias={d.hourly.map((h) => String(h.hour))}
        series={series}
        apagadas={cerradas}
        formato={(v) => porcentajeSimple(v * 100)}
        etiqueta={x.horasAria}
      />
      <Leyenda series={series} />
      {apertura && cierre && pico && (
        <p className="nota" style={{ marginTop: 6 }}>
          {x.horasTexto(
            porcentajeSimple(apertura.share_stockout * 100),
            String(apertura.hour),
            porcentajeSimple(cierre.share_stockout * 100),
            String(cierre.hour),
            String(pico.hour),
          )}
        </p>
      )}
      <DatosDelGrafico
        encabezados={x.columnasHoras}
        filas={d.hourly.map((h) => [
          `${h.hour}:00`,
          porcentajeSimple(h.share_stockout * 100, 1),
          porcentajeSimple(h.share_sales * 100, 1),
          h.open ? textos.comun.si : textos.comun.no,
        ])}
      />
    </section>
  );
}

function PorGrupo({
  titulo,
  id,
  filas,
  prefijo,
  nota,
}: {
  titulo: string;
  id: string;
  filas: GroupStat[];
  prefijo: string;
  nota: string;
}) {
  const x = t().datos;
  const orden = [...filas].sort((a, b) => b.share_censored - a.share_censored);
  const visibles = orden.slice(0, 12);
  return (
    <section className="tarjeta tablero-bloque" aria-labelledby={id}>
      <div className="tablero-titulo">
        <h2 id={id}>{titulo}</h2>
        <span className="nota">
          {visibles.length < orden.length ? x.topDe(conteo(visibles.length), conteo(orden.length)) : ""}
        </span>
      </div>
      <BarrasHorizontales
        etiqueta={x.grupoAria(titulo)}
        filas={visibles.map((g) => ({
          clave: String(g.id),
          rotulo: (
            <>
              {prefijo} {g.id} <span className="apagada">· {x.seriesN(conteo(g.n_series))}</span>
            </>
          ),
          valor: g.share_censored,
          detalle: x.grupoDetalle(porcentaje(g.uplift_pct), porcentajeSimple(g.share_volume * 100, 1)),
        }))}
        maximo={1}
        formato={(v) => porcentajeSimple(v * 100)}
      />
      <p className="nota" style={{ marginTop: 8 }}>
        {nota}
      </p>
      <DatosDelGrafico
        encabezados={x.columnasGrupo(prefijo)}
        filas={orden.map((g) => [
          g.id,
          conteo(g.n_series),
          porcentajeSimple(g.share_censored * 100, 1),
          porcentaje(g.uplift_pct),
          porcentajeSimple(g.share_volume * 100, 1),
        ])}
        resumen={x.verFilas(orden.length)}
      />
    </section>
  );
}

function Rotacion({ d }: { d: DatasetSummary }) {
  const textos = t();
  const x = textos.datos;
  const baja = d.rotation.find((b) => b.band === "baja");
  return (
    <section className="tarjeta tablero-bloque" aria-labelledby="t-rotacion">
      <div className="tablero-titulo">
        <h2 id="t-rotacion">{x.porRotacion}</h2>
      </div>
      <table className="tabla">
        <thead>
          <tr>
            {x.columnasRotacion.map((col, i) => (
              <th key={col} scope="col" className={i === 0 ? "izq" : undefined}>
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {d.rotation.map((b) => (
            <tr key={b.band} className="fila" style={{ cursor: "default" }}>
              <td className="izq tinta">{textos.bandas[b.band] ?? b.band}</td>
              <td>{conteo(b.n_series)}</td>
              <td>{porcentajeSimple(b.share_series * 100, 1)}</td>
              <td className="sugerido">{porcentajeSimple(b.share_volume * 100, 1)}</td>
              <td>{porcentajeSimple(b.share_censored * 100, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {baja && (
        <p className="nota" style={{ marginTop: 8 }}>
          {x.rotacionNota(porcentajeSimple(baja.share_series * 100), porcentajeSimple(baja.share_volume * 100))}
        </p>
      )}
    </section>
  );
}

function Histograma({ d }: { d: DatasetSummary }) {
  const x = t().datos;
  const series: Serie[] = [
    { rotulo: x.kpiSeries, valores: d.stockout_hist.map((b) => b.n_series), tipo: "neutro" },
  ];
  const totalSeries = d.stockout_hist.reduce((a, b) => a + b.n_series, 0);
  const casiLimpias = d.stockout_hist.filter((b) => b.hi <= 0.1 + 1e-9).reduce((a, b) => a + b.n_series, 0);
  return (
    <section className="tarjeta tablero-bloque" aria-labelledby="t-hist">
      <div className="tablero-titulo">
        <h2 id="t-hist">{x.histograma}</h2>
      </div>
      <Columnas
        categorias={d.stockout_hist.map((b) => `${Math.round(b.lo * 100)}–${Math.round(b.hi * 100)}`)}
        series={series}
        formato={(v) => conteo(Math.round(v))}
        etiqueta={x.histogramaAria}
      />
      <p className="nota" style={{ marginTop: 6 }}>
        {x.histogramaNota(conteo(casiLimpias), conteo(totalSeries))}
      </p>
      <DatosDelGrafico
        encabezados={x.columnasHistograma}
        filas={d.stockout_hist.map((b) => [
          `${porcentajeSimple(Math.round(b.lo * 100))} – ${porcentajeSimple(Math.round(b.hi * 100))}`,
          conteo(b.n_series),
        ])}
      />
    </section>
  );
}
