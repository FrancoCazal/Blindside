/**
 * Estados de falla y de espera.
 *
 * «API caída» y «sin datos» se distinguen porque se arreglan distinto: el
 * primero es un proceso que no está corriendo, el segundo es una capa de datos
 * que no se generó. Mostrar el mismo cartel para los dos hace perder el tiempo
 * de quien lo lee.
 */

import { useEffect, useState } from "react";

import { API_BASE, ApiError } from "../api/client";

export function ApiCaida({ error, onReintentar }: { error: unknown; onReintentar: () => void }) {
  const [segundos, setSegundos] = useState(15);
  const [ultimoIntento] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => {
      setSegundos((s) => {
        if (s <= 1) {
          onReintentar();
          return 15;
        }
        return s - 1;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [onReintentar]);

  const api = error instanceof ApiError ? error : null;
  const esRed = api?.kind === "network";

  return (
    <div className="pagina">
      <svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true" style={{ display: "block" }}>
        <circle cx="17" cy="17" r="15" fill="none" stroke="var(--apagada)" strokeWidth="2" />
        <line x1="10" y1="24" x2="24" y2="10" stroke="var(--apagada)" strokeWidth="2" />
      </svg>
      <h2 style={{ fontSize: 21, marginTop: 14 }}>
        {esRed ? "No hay respuesta de la API" : "La API respondió con un error"}
      </h2>
      <p className="nota" style={{ maxWidth: "74ch", marginTop: 6 }}>
        {esRed ? (
          <>
            El dashboard no encuentra nada escuchando en <strong>{API_BASE}</strong>. No es que no
            haya datos: es que no hay proceso. Si la API está corriendo, esto también pasa cuando el
            origen del navegador no está en el allowlist de CORS.
          </>
        ) : (
          <>La API está en pie y rechazó la consulta. El detalle de abajo viene del backend.</>
        )}
      </p>

      <table className="tabla" style={{ maxWidth: 560, marginTop: 18 }}>
        <tbody>
          <Fila rotulo="Último intento" valor={ultimoIntento.toLocaleTimeString("es-PY")} />
          <Fila rotulo="Próximo reintento" valor={`en ${segundos} s`} />
          <Fila rotulo="Endpoint" valor={api?.endpoint ?? "—"} />
          <Fila
            rotulo={esRed ? "Motivo" : `Código ${api?.status ?? "—"}`}
            valor={api?.message ?? String(error)}
          />
        </tbody>
      </table>

      <div className="consecuencia" style={{ marginTop: 18, maxWidth: 560 }}>
        <code style={{ fontFamily: "inherit" }}>make api</code> o bien{" "}
        <code style={{ fontFamily: "inherit" }}>
          uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
        </code>
      </div>

      <button
        type="button"
        onClick={onReintentar}
        style={{
          marginTop: 18,
          background: "var(--tinta)",
          color: "var(--papel)",
          padding: "9px 16px",
          fontSize: 13,
          fontWeight: 600,
        }}
      >
        Reintentar ahora
      </button>
    </div>
  );
}

function Fila({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <tr className="fila">
      <td className="izq" style={{ color: "var(--apagada)" }}>
        {rotulo}
      </td>
      <td className="izq tinta">{valor}</td>
    </tr>
  );
}

/**
 * Esqueleto de carga. Reserva la geometría exacta de la pantalla final: nada se
 * mueve al llegar los datos. Las filas se desvanecen hacia abajo para que el
 * esqueleto no compita con el encabezado, que ya tiene contenido real. Sin
 * brillo animado — el único elemento en movimiento es la regla de progreso.
 */
export function Esqueleto({ filas = 8 }: { filas?: number }) {
  return (
    <div className="pagina" aria-busy="true" aria-live="polite">
      <div className="progreso" />
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 300px", gap: 26, marginTop: 20 }}>
        <div>
          <div className="hueso" style={{ height: 14, width: 180, marginBottom: 16 }} />
          {Array.from({ length: filas }, (_, i) => (
            <div
              key={i}
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 92px 118px 96px 104px 84px 110px",
                gap: 8,
                height: 34,
                alignItems: "center",
                opacity: i < 3 ? 1 : i < 6 ? 0.6 : 0.3,
                borderBottom: "1px solid var(--regla-fina)",
              }}
            >
              {Array.from({ length: 7 }, (_, c) => (
                <div key={c} className="hueso" style={{ height: 9 }} />
              ))}
            </div>
          ))}
        </div>
        <div>
          <div className="hueso" style={{ height: 42, marginBottom: 18 }} />
          <div className="hueso" style={{ height: 80, marginBottom: 18 }} />
          <div className="hueso" style={{ height: 64 }} />
        </div>
      </div>
      <span style={{ position: "absolute", left: -9999 }}>Cargando datos del panel</span>
    </div>
  );
}
