/**
 * Gráficos chicos del panel y de la pantalla de datos.
 *
 * Mismas reglas que el gráfico principal y sin librería: SVG con `viewBox` fijo,
 * tokens de color y nada más. La regla de la paleta no cambia acá — **lo
 * observado es gris y solo lo recuperado lleva acento** —, así que un gráfico que
 * no compara observado contra recuperado se dibuja en la escala de grises.
 *
 * Cada gráfico lleva su tabla de datos en un `<details>`. Es la alternativa
 * textual para lector de pantalla y, además, la forma de leer el número exacto
 * sin tooltips, que en un proyector no sirven.
 */

import { useId, type ReactNode } from "react";

import { etiquetaFecha, magnitud } from "../format";
import { t } from "../i18n";

export interface Serie {
  rotulo: string;
  valores: number[];
  /** `observado` gris fino, `recuperado` vermellón grueso, `neutro` tinta. */
  tipo: "observado" | "recuperado" | "neutro";
}

const TRAZO: Record<Serie["tipo"], { color: string; ancho: number }> = {
  observado: { color: "var(--observado)", ancho: 1.4 },
  recuperado: { color: "var(--recuperado)", ancho: 2.4 },
  neutro: { color: "var(--tinta)", ancho: 1.6 },
};

/** Tabla de datos plegable debajo de un gráfico. */
export function DatosDelGrafico({
  encabezados,
  filas,
  resumen,
}: {
  encabezados: string[];
  filas: (string | number)[][];
  resumen?: string;
}) {
  return (
    <details className="datos-grafico">
      <summary className="nota">{resumen ?? t().comun.verLosDatos}</summary>
      <div className="datos-grafico-cuerpo">
        <table className="tabla">
          <thead>
            <tr>
              {encabezados.map((e, i) => (
                <th scope="col" key={e} className={i === 0 ? "izq" : undefined}>
                  {e}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.map((f, i) => (
              <tr key={i}>
                {f.map((c, j) => (
                  <td key={j} className={j === 0 ? "izq" : undefined}>
                    {c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

/**
 * Serie temporal con una franja de proporción abajo.
 *
 * Arriba van las líneas; abajo, en su propia banda, la fracción de series en
 * quiebre de cada día. Van separadas y no en un doble eje: dos escalas sobre el
 * mismo espacio invitan a leer cruces que no significan nada.
 */
export function SerieTemporal({
  fechas,
  series,
  franja,
  rotuloFranja,
  etiqueta,
  alto = 220,
}: {
  fechas: string[];
  series: Serie[];
  franja?: number[];
  rotuloFranja?: string;
  etiqueta: string;
  alto?: number;
}) {
  const ancho = 1000;
  const pad = { izq: 52, der: 14, arriba: 10, abajo: 22 };
  const altoFranja = franja ? 56 : 0;
  const altoLineas = alto - altoFranja;
  const n = fechas.length;
  const max = Math.max(1e-9, ...series.flatMap((s) => s.valores)) * 1.06;
  const x = (i: number) => pad.izq + (n > 1 ? (i * (ancho - pad.izq - pad.der)) / (n - 1) : 0);
  const y = (v: number) =>
    altoLineas - pad.abajo - (v / max) * (altoLineas - pad.arriba - pad.abajo);
  const marcas = n <= 6 ? fechas.map((_, i) => i) : [0, 1, 2, 3, 4, 5].map((k) => Math.round((k * (n - 1)) / 5));
  const guias = [0.25, 0.5, 0.75, 1].map((f) => f * (max / 1.06));

  return (
    <svg
      viewBox={`0 0 ${ancho} ${alto}`}
      className="grafico"
      role="img"
      aria-label={etiqueta}
    >
      {guias.map((v) => (
        <g key={v}>
          <line x1={pad.izq} x2={ancho - pad.der} y1={y(v)} y2={y(v)} stroke="var(--guia)" />
          <text x={pad.izq - 6} y={y(v) + 3.5} textAnchor="end" fontSize="11" fill="var(--apagada)">
            {magnitud(v, v >= 100 ? 0 : 1)}
          </text>
        </g>
      ))}
      <line
        x1={pad.izq}
        x2={ancho - pad.der}
        y1={altoLineas - pad.abajo}
        y2={altoLineas - pad.abajo}
        stroke="var(--eje)"
      />

      {/* La recuperada se dibuja primero y la observada encima: donde coinciden,
          que es en todos los días sin quiebre, se ve una sola línea. */}
      {[...series]
        .sort((a, b) => (a.tipo === "recuperado" ? -1 : b.tipo === "recuperado" ? 1 : 0))
        .map((s) => (
          <path
            key={s.rotulo}
            d={s.valores.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ")}
            fill="none"
            stroke={TRAZO[s.tipo].color}
            strokeWidth={TRAZO[s.tipo].ancho}
          />
        ))}

      {marcas.map((i) => (
        <text
          key={i}
          x={x(i)}
          y={altoLineas - 6}
          textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}
          fontSize="11"
          fill="var(--apagada)"
        >
          {fechas[i] ? etiquetaFecha(fechas[i]) : ""}
        </text>
      ))}

      {franja && (
        <g>
          <text x={pad.izq} y={altoLineas + 8} textAnchor="start" fontSize="11" fill="var(--apagada)">
            {rotuloFranja ?? ""}
          </text>
          {franja.map((v, i) => {
            // Escala de 0 a 100 %, fija: una franja autoescalada haría ver un 44 %
            // constante como una serie que oscila.
            const h = Math.max(0, Math.min(1, v)) * (altoFranja - 18);
            const paso = n > 1 ? (ancho - pad.izq - pad.der) / (n - 1) : 0;
            return (
              <rect
                key={i}
                x={x(i) - Math.max(1, paso * 0.4)}
                y={alto - 2 - h}
                width={Math.max(2, paso * 0.8)}
                height={h}
                fill="var(--horas-quiebre)"
              />
            );
          })}
          <line x1={pad.izq} x2={ancho - pad.der} y1={alto - 2} y2={alto - 2} stroke="var(--eje)" />
        </g>
      )}
    </svg>
  );
}

/**
 * Columnas agrupadas. Sirve para la semana (observado contra recuperado), la
 * hora del día y el histograma.
 */
export function Columnas({
  categorias,
  series,
  etiqueta,
  formato = (v) => magnitud(v, 2),
  apagadas,
  alto = 210,
}: {
  categorias: string[];
  series: Serie[];
  etiqueta: string;
  formato?: (v: number) => string;
  /** Índices de categoría que se dibujan apagados, p. ej. horas fuera de la ventana. */
  apagadas?: Set<number>;
  alto?: number;
}) {
  // 520 de ancho y no 1000: estos gráficos van en media columna, y con un viewBox
  // del doble las etiquetas de 11 se dibujaban a ~5 px.
  const ancho = 520;
  const pad = { izq: 44, der: 6, arriba: 10, abajo: 22 };
  const max = Math.max(1e-9, ...series.flatMap((s) => s.valores)) * 1.08;
  const util = ancho - pad.izq - pad.der;
  const paso = util / Math.max(1, categorias.length);
  const anchoBarra = (paso * 0.72) / Math.max(1, series.length);
  const y = (v: number) => alto - pad.abajo - (v / max) * (alto - pad.arriba - pad.abajo);
  const cadaCuanto = categorias.length > 16 ? 3 : 1;

  return (
    <svg viewBox={`0 0 ${ancho} ${alto}`} className="grafico" role="img" aria-label={etiqueta}>
      {[0.5, 1].map((f) => {
        const v = (f * max) / 1.08;
        return (
          <g key={f}>
            <line x1={pad.izq} x2={ancho - pad.der} y1={y(v)} y2={y(v)} stroke="var(--guia)" />
            <text x={pad.izq - 6} y={y(v) + 3.5} textAnchor="end" fontSize="11" fill="var(--apagada)">
              {formato(v)}
            </text>
          </g>
        );
      })}
      <line x1={pad.izq} x2={ancho - pad.der} y1={alto - pad.abajo} y2={alto - pad.abajo} stroke="var(--eje)" />
      {categorias.map((c, i) => {
        const x0 = pad.izq + i * paso + paso * 0.14;
        const apagada = apagadas?.has(i);
        return (
          <g key={c} opacity={apagada ? 0.35 : 1}>
            {series.map((s, k) => {
              const v = s.valores[i] ?? 0;
              const color =
                s.tipo === "recuperado"
                  ? "var(--recuperado)"
                  : s.tipo === "observado"
                    ? "var(--observado)"
                    : "var(--horas-quiebre)";
              return (
                <rect
                  key={s.rotulo}
                  x={x0 + k * anchoBarra}
                  y={y(v)}
                  width={Math.max(1, anchoBarra - 1)}
                  height={Math.max(0, alto - pad.abajo - y(v))}
                  fill={color}
                />
              );
            })}
            {i % cadaCuanto === 0 && (
              <text x={pad.izq + i * paso + paso / 2} y={alto - 6} textAnchor="middle" fontSize="11" fill="var(--apagada)">
                {c}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/**
 * Barras horizontales ordenadas, en HTML y no en SVG: las etiquetas son texto
 * real, se seleccionan, y la lista se puede recorrer con lector de pantalla
 * como una lista.
 */
export function BarrasHorizontales({
  filas,
  maximo,
  formato,
  acento,
  etiqueta,
}: {
  filas: { clave: string; rotulo: ReactNode; valor: number; detalle?: string }[];
  maximo?: number;
  formato: (v: number) => string;
  /** Pinta con acento. Solo para magnitudes que son recuperadas. */
  acento?: boolean;
  etiqueta: string;
}) {
  const id = useId();
  const max = maximo ?? Math.max(1e-9, ...filas.map((f) => f.valor));
  return (
    <div>
      <span id={id} className="fuera-de-pantalla">
        {etiqueta}
      </span>
      <ul className="barras-h" aria-labelledby={id}>
      {filas.map((f) => (
        <li key={f.clave} title={f.detalle}>
          <span className="barras-h-rotulo">{f.rotulo}</span>
          <span className="barras-h-pista" aria-hidden="true">
            <span
              className="barras-h-valor"
              data-acento={acento ? "true" : undefined}
              style={{ width: `${Math.max(0, Math.min(100, (100 * f.valor) / max))}%` }}
            />
          </span>
          <span className="barras-h-cifra tabular">{formato(f.valor)}</span>
        </li>
      ))}
      </ul>
    </div>
  );
}

/** Leyenda con la muestra de trazo de cada serie. */
export function Leyenda({ series }: { series: Serie[] }) {
  return (
    <div className="leyenda">
      {series.map((s) => (
        <span key={s.rotulo}>
          <svg width="22" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="22" y2="4" stroke={TRAZO[s.tipo].color} strokeWidth={TRAZO[s.tipo].ancho} />
          </svg>
          {s.rotulo}
        </span>
      ))}
    </div>
  );
}
