/**
 * Gráfico de la serie individual. SVG escrito a mano: el diseño fija `viewBox`,
 * orden de capas y rellenos al píxel, y una librería de charts pelearía con las
 * tres cosas.
 *
 * Orden de capas, de atrás hacia adelante:
 *
 *    1 guías horizontales      tinta 10 %, cuatro líneas
 *    2 tramos de quiebre       sombreado vertical, tinta 7 %, de borde a borde
 *    3 eje base y corte        tinta 35 % continuo; tinta 30 % guionado 3/3
 *    4 etiquetas de eje        11 px en apagada, tabular
 *    5 cuña                    vermellón 16 %
 *    6 demanda recuperada      vermellón 2,4 px, solo dentro de los tramos
 *    7 venta observada         gris observado 1,4 px, continua
 *    8 banda conformal         vermellón 12 %, ensanchándose con el horizonte
 *    9 pronóstico              tinta 55 %, 1,8 px, guionado 5/4
 *   10 cantidad sugerida       punto de 4,5 px y plomada hasta el eje
 *
 * La observada va **encima** de la recuperada a propósito: así la separación se
 * lee como que la recuperada emerge desde abajo, no que tapa el dato original.
 */

import type { ForecastPoint, SeriesHistory } from "../api/client";
import {
  FRANJA,
  GRAFICO,
  areaHoras,
  banda,
  cuna,
  escalaX,
  escalaY,
  guias,
  marcasFecha,
  maximoEje,
  polilinea,
  rangosRecuperados,
  tramosDibujables,
} from "../chart";
import { etiquetaFecha, magnitud } from "../format";

export function GraficoSerie({
  historia,
  pronostico,
  cantidadSugerida,
  basis,
}: {
  historia: SeriesHistory;
  pronostico: ForecastPoint[];
  cantidadSugerida: number | null;
  basis: "observed" | "recovered";
}) {
  const puntos = historia.points;
  const fechas = puntos.map((p) => p.dt);
  const total = puntos.length + pronostico.length;
  const x = escalaX(total);

  const conQuiebres = historia.runs.length > 0;
  const mostrarEvidencia = basis === "recovered" && conQuiebres;

  const max = maximoEje([
    ...puntos.map((p) => p.observed),
    ...(basis === "recovered" ? puntos.map((p) => p.recovered) : []),
    ...pronostico.map((p) => p.pred_hi ?? p.y_pred),
    cantidadSugerida ?? 0,
  ]);
  const y = escalaY(max);
  const ejeY = GRAFICO.alto - GRAFICO.padAbajo;

  const observada = puntos.map((p, i) => ({ x: x(i), y: y(p.observed) }));
  const tramos = tramosDibujables(historia.runs, fechas, x);
  const rangos = rangosRecuperados(tramos, puntos.length);

  const serieFuturo = pronostico.map((p, j) => ({ x: x(puntos.length + j), y: y(p.y_pred) }));
  const bandaLo = pronostico.map((p, j) => ({ x: x(puntos.length + j), y: y(p.pred_lo ?? p.y_pred) }));
  const bandaHi = pronostico.map((p, j) => ({ x: x(puntos.length + j), y: y(p.pred_hi ?? p.y_pred) }));
  const corte = pronostico.length > 0 ? (x(puntos.length - 1) + x(puntos.length)) / 2 : null;

  /* Serie limpia (5b): sin una segunda línea que la contraste, el gris de
     observado se lee como desactivado, así que sube a 1,8 px y pasa a tinta
     plena. El acento queda solo en la banda y la cantidad, que es donde sigue
     habiendo una decisión. */
  const trazoObservada = conQuiebres ? 1.4 : 1.8;
  const colorObservada = conQuiebres ? "var(--observado)" : "var(--tinta)";

  return (
    <div>
      <svg
        className="grafico"
        viewBox={`0 0 ${GRAFICO.ancho} ${GRAFICO.alto}`}
        role="img"
        aria-label={descripcion(historia, basis)}
      >
        {/* 1 · guías */}
        {guias(max).map((g, i) => (
          <line
            key={i}
            x1={GRAFICO.padIzq}
            x2={GRAFICO.ancho - GRAFICO.padDer}
            y1={g.y}
            y2={g.y}
            stroke="var(--guia)"
          />
        ))}

        {/* 2 · tramos de quiebre, de borde a borde */}
        {tramos.map((t, i) => (
          <rect
            key={i}
            x={t.x}
            y={GRAFICO.padArriba}
            width={t.ancho}
            height={ejeY - GRAFICO.padArriba}
            fill="var(--quiebre)"
          />
        ))}

        {/* 3 · eje base y corte del pronóstico */}
        <line
          x1={GRAFICO.padIzq}
          x2={GRAFICO.ancho - GRAFICO.padDer}
          y1={ejeY}
          y2={ejeY}
          stroke="var(--eje)"
        />
        {corte != null && (
          <line
            x1={corte}
            x2={corte}
            y1={GRAFICO.padArriba}
            y2={ejeY}
            stroke="var(--corte)"
            strokeDasharray="3 3"
          />
        )}

        {/* 4 · etiquetas de eje */}
        {guias(max).map((g, i) => (
          <text
            key={i}
            x={40}
            y={g.y + 3.5}
            textAnchor="end"
            fontSize="11"
            fill="var(--apagada)"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {magnitud(g.valor, g.valor < 10 ? 1 : 0)}
          </text>
        ))}
        {marcasFecha(fechas).map((i) => (
          <text
            key={i}
            x={x(i)}
            y={GRAFICO.alto - 6}
            textAnchor="middle"
            fontSize="11"
            fill="var(--apagada)"
          >
            {etiquetaFecha(fechas[i])}
          </text>
        ))}

        {/* 5 y 6 · cuña y línea recuperada, solo dentro de los tramos y con un
            día de entrada y uno de salida. Fuera de ellos las dos series son
            idénticas, y superponerlas en todo el rango sugeriría una corrección
            que no existe. */}
        <g className="capa-evidencia" data-visible={mostrarEvidencia}>
          {rangos.map((r, i) => {
            const idx = Array.from({ length: r.hasta - r.desde + 1 }, (_, k) => r.desde + k);
            const obs = idx.map((j) => ({ x: x(j), y: y(puntos[j].observed) }));
            const rec = idx.map((j) => ({ x: x(j), y: y(puntos[j].recovered) }));
            return (
              <g key={i}>
                <path d={cuna(obs, rec)} fill="var(--cuna)" />
                <path
                  d={polilinea(rec)}
                  fill="none"
                  stroke="var(--recuperado)"
                  strokeWidth="2.4"
                  strokeLinejoin="round"
                />
              </g>
            );
          })}
        </g>

        {/* 7 · venta observada, continua en todo el rango y por encima */}
        <path
          d={polilinea(observada)}
          fill="none"
          stroke={colorObservada}
          strokeWidth={trazoObservada}
          strokeLinejoin="round"
        />

        {/* 8 · banda conformal */}
        {bandaLo.length > 0 && <path d={banda(bandaLo, bandaHi)} fill="var(--banda)" />}

        {/* 9 · pronóstico. Nunca lleva acento: el futuro no es un hallazgo. */}
        {serieFuturo.length > 0 && (
          <path
            d={polilinea(serieFuturo)}
            fill="none"
            stroke="var(--pronostico)"
            strokeWidth="1.8"
            strokeDasharray="5 4"
          />
        )}

        {/* 10 · cantidad sugerida */}
        {cantidadSugerida != null && serieFuturo.length > 0 && (
          <g>
            <line
              x1={serieFuturo[0].x}
              x2={serieFuturo[0].x}
              y1={y(cantidadSugerida)}
              y2={ejeY}
              stroke="var(--recuperado)"
              strokeWidth="1"
            />
            <circle cx={serieFuturo[0].x} cy={y(cantidadSugerida)} r="4.5" fill="var(--recuperado)" />
          </g>
        )}
      </svg>

      {/* Franja de horas de quiebre, alineada al mismo eje X. Comparte la fuente
          de cálculo con la métrica de censura del panel: son el mismo número. */}
      <svg
        viewBox={`0 0 ${FRANJA.ancho} ${FRANJA.alto}`}
        className="grafico"
        role="img"
        aria-label={`Horas de quiebre por día, de 0 a ${historia.open_hours} franjas comerciales`}
      >
        <line
          x1={GRAFICO.padIzq}
          x2={FRANJA.ancho - GRAFICO.padDer}
          y1={FRANJA.alto - FRANJA.padAbajo}
          y2={FRANJA.alto - FRANJA.padAbajo}
          stroke="var(--regla-fina)"
        />
        <path d={areaHoras(puntos, historia.open_hours, x)} fill="var(--horas-quiebre)" />
        <text x={40} y={FRANJA.padArriba + 9} textAnchor="end" fontSize="11" fill="var(--apagada)">
          {historia.open_hours}
        </text>
        <text
          x={40}
          y={FRANJA.alto - FRANJA.padAbajo}
          textAnchor="end"
          fontSize="11"
          fill="var(--apagada)"
        >
          0
        </text>
        <text x={GRAFICO.padIzq} y={FRANJA.alto - 2} fontSize="10.5" fill="var(--rotulo)">
          HORAS DE QUIEBRE POR DÍA
        </text>
      </svg>

      <Leyenda conQuiebres={conQuiebres} mostrarEvidencia={mostrarEvidencia} />
    </div>
  );
}

function Leyenda({
  conQuiebres,
  mostrarEvidencia,
}: {
  conQuiebres: boolean;
  mostrarEvidencia: boolean;
}) {
  return (
    <div className="leyenda">
      <span>
        <svg width="22" height="8" aria-hidden="true">
          <line
            x1="0"
            y1="4"
            x2="22"
            y2="4"
            stroke={conQuiebres ? "var(--observado)" : "var(--tinta)"}
            strokeWidth={conQuiebres ? 1.4 : 1.8}
          />
        </svg>
        Venta observada
      </span>
      {mostrarEvidencia && (
        <span>
          <svg width="22" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="22" y2="4" stroke="var(--recuperado)" strokeWidth="2.4" />
          </svg>
          Demanda recuperada
        </span>
      )}
      <span>
        <svg width="22" height="8" aria-hidden="true">
          <line
            x1="0"
            y1="4"
            x2="22"
            y2="4"
            stroke="var(--pronostico)"
            strokeWidth="1.8"
            strokeDasharray="5 4"
          />
        </svg>
        Pronóstico
      </span>
      <span>
        <svg width="22" height="10" aria-hidden="true">
          <rect x="0" y="1" width="22" height="8" fill="var(--banda)" />
        </svg>
        Banda conformal 90 %
      </span>
      {conQuiebres && (
        <span>
          <svg width="22" height="10" aria-hidden="true">
            <rect x="0" y="1" width="22" height="8" fill="var(--quiebre)" />
          </svg>
          Día con quiebre
        </span>
      )}
      {!conQuiebres && (
        <span
          style={{
            fontSize: 11,
            letterSpacing: ".14em",
            textTransform: "uppercase",
            border: "1px solid var(--regla-control)",
            padding: "2px 6px",
            color: "var(--rotulo)",
          }}
        >
          Serie limpia
        </span>
      )}
    </div>
  );
}

function descripcion(historia: SeriesHistory, basis: "observed" | "recovered"): string {
  const s = historia.summary;
  const base = basis === "recovered" ? "demanda recuperada" : "venta observada";
  return (
    `Serie ${historia.series.series_id}: ${base} de ${historia.points.length} días, ` +
    `${s.n_censored_days} con quiebre de stock, racha máxima de ${s.max_run_days} días.`
  );
}
