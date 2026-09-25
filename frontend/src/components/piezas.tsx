/**
 * Piezas chicas del cromo. Ningún icono de librería: los pocos que hay son SVG
 * inline con trazo de 1,4 a 2 px, como especifica el handoff.
 */

import { useEstado, type Basis } from "../state";
import { magnitud } from "../format";

/**
 * Logotipo: dos líneas que coinciden y en un punto se abren, más la cuña rellena
 * entre ellas. Es la tesis del proyecto dibujada — la venta observada y la
 * demanda latente separándose donde hubo quiebre.
 */
export function Logo({ ancho = 30 }: { ancho?: number }) {
  return (
    <svg
      viewBox="0 0 120 44"
      style={{ width: ancho, height: (ancho * 44) / 120, display: "block" }}
      role="img"
      aria-label="Blindside"
    >
      <path d="M8 26 L52 26 L84 14 L112 14" fill="none" stroke="var(--observado)" strokeWidth="4" />
      <path d="M8 26 L52 26 L112 26" fill="none" stroke="var(--tinta)" strokeWidth="4" />
      <path d="M52 26 L84 14 L112 14 L112 26 Z" fill="var(--recuperado)" />
    </svg>
  );
}

/**
 * Sello de dato sin respaldo en el backend. No se puede cerrar, y la pantalla
 * que lo lleva también lleva una nota que dice qué endpoint falta.
 */
export function SelloSim({ titulo }: { titulo: string }) {
  return (
    <abbr className="sello-sim" title={titulo} style={{ textDecoration: "none" }}>
      sim
    </abbr>
  );
}

export function IconoAdvertencia({ tamano = 18 }: { tamano?: number }) {
  return (
    <svg
      width={tamano}
      height={tamano}
      viewBox="0 0 18 18"
      style={{ display: "block", flex: "none", marginTop: 1 }}
      aria-hidden="true"
    >
      <path d="M9 2 L17 16 L1 16 Z" fill="none" stroke="var(--advertencia)" strokeWidth="1.6" />
      <line x1="9" y1="7" x2="9" y2="11.5" stroke="var(--advertencia)" strokeWidth="1.6" />
      <circle cx="9" cy="13.6" r=".95" fill="var(--advertencia)" />
    </svg>
  );
}

export function IconoLupa() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" style={{ flex: "none" }}>
      <circle cx="5.8" cy="5.8" r="4.4" fill="none" stroke="var(--apagada)" strokeWidth="1.4" />
      <line x1="9.2" y1="9.2" x2="13" y2="13" stroke="var(--apagada)" strokeWidth="1.4" />
    </svg>
  );
}

/**
 * Toggle de censura. El control más importante de la app: cambia las series, las
 * cantidades sugeridas, las métricas de error y el costo esperado.
 *
 * No es un checkbox. Son dos estados con nombre propio, así que es un grupo de
 * dos botones con `aria-pressed`, ← → mueven entre ellos y el atajo global es B.
 * Al cambiar, la región `aria-live` anuncia siempre el nombre del modo. Cuando
 * la pantalla conoce ambas cantidades puede pasar `cantidadAntes` y
 * `cantidadDespues` para anunciar también el cambio; la landing anuncia su total
 * real cuando termina la consulta a `/reorder`.
 */
export function ToggleCensura({
  cantidadAntes,
  cantidadDespues,
}: {
  cantidadAntes?: number;
  cantidadDespues?: number;
}) {
  const { basis, setBasis, anunciar } = useEstado();

  const cambiar = (siguiente: Basis) => {
    if (siguiente === basis) return;
    setBasis(siguiente);
    const nombre = siguiente === "recovered" ? "Demanda recuperada" : "Venta observada";
    if (cantidadAntes != null && cantidadDespues != null) {
      anunciar(
        `${nombre}. La cantidad sugerida pasa de ${magnitud(cantidadAntes)} a ${magnitud(
          cantidadDespues,
        )}`,
      );
    } else {
      anunciar(nombre);
    }
  };

  const alTeclear = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      cambiar("observed");
    }
    if (e.key === "ArrowRight") {
      e.preventDefault();
      cambiar("recovered");
    }
  };

  return (
    <div>
      <div
        role="group"
        aria-label="Base de cálculo"
        aria-keyshortcuts="b"
        className="toggle"
        onKeyDown={alTeclear}
      >
        <button type="button" aria-pressed={basis === "observed"} onClick={() => cambiar("observed")}>
          Venta observada
        </button>
        <button
          type="button"
          aria-pressed={basis === "recovered"}
          onClick={() => cambiar("recovered")}
        >
          Demanda recuperada
        </button>
      </div>
      <div className="regla-acento" data-activa={basis === "recovered"} />
    </div>
  );
}

/** Barras de 14 días de horas de quiebre. 76 × 15 px, barras de 5,4 con 2,2 de gap. */
export function Sparkline({ valores, maximo }: { valores: number[]; maximo: number }) {
  const ancho = 5.4;
  const gap = 2.2;
  const alto = 15;
  return (
    <svg
      width={valores.length * ancho + Math.max(0, valores.length - 1) * gap}
      height={alto}
      style={{ display: "block" }}
      aria-hidden="true"
    >
      {valores.map((v, i) => {
        const h = maximo > 0 ? (v / maximo) * alto : 0;
        return (
          <g key={i}>
            {/* Pista de fondo: sin ella un día sin quiebre se lee como un dato
                que falta, y la serie parece fragmentos sueltos en vez de una
                secuencia de catorce días. Lo vi en las capturas del audit. */}
            <rect x={i * (ancho + gap)} y={alto - 1} width={ancho} height={1} fill="var(--guia)" />
            {v > 0 && (
              <rect
                x={i * (ancho + gap)}
                y={alto - Math.max(1.5, h)}
                width={ancho}
                height={Math.max(1.5, h)}
                fill="var(--horas-quiebre)"
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}
