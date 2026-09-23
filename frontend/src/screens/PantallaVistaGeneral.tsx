/**
 * Vista general · el panel y su censura.
 *
 * Es la pantalla que muestra la **comprobación de la ventana comercial**: que el
 * supuesto de 16 franjas de 6:00 a 22:00 reproduzca el ≈20 % de horas en quiebre
 * que declara la ficha del dataset. Si esa cuenta no cerrara, todo el factor de
 * inflación de la recuperación estaría mal, así que se muestra hecha y no
 * afirmada.
 */

import { api, type Health } from "../api/client";
import { conteo, magnitud, porcentaje, porcentajeSimple } from "../format";
import { useAsincrono } from "../state";
import { Esqueleto } from "../components/estados";

/** Forma real de `comparison` en `/censoring`, verificada contra el backend. */
interface FilaCensura {
  grupo: string;
  n: number;
  demanda_observada: number;
  demanda_latente: number;
  uplift_pct: number;
}

export function PantallaVistaGeneral({ health }: { health: Health }) {
  const datos = useAsincrono(() => api.censoring(), []);

  if (datos.cargando && !datos.datos) return <Esqueleto filas={4} />;
  if (datos.error) throw datos.error;
  if (!datos.datos) return null;

  const { summary, comparison, note } = datos.datos;
  const panel = health.panel;
  const franjas = 16;
  const diasConQuiebre = summary.share_censored_days ?? 0;
  const horas = summary.mean_oos_hours_when_censored ?? 0;
  // 43,9 % de dias con quiebre x 7,0 horas promedio / 16 franjas = 19,2 % de
  // horas comerciales en quiebre, que es el ~20 % de la ficha del dataset.
  const horasComerciales = (diasConQuiebre * horas) / franjas;

  return (
    <div className="pagina">
      <div className="tarjeta" style={{ padding: "18px var(--e5)" }}>
        <h2 style={{ marginBottom: 4 }}>El panel y su censura</h2>
        <p className="nota" style={{ maxWidth: "88ch", marginBottom: 18 }}>
          Cuando hubo quiebre de stock la venta registrada es cero, pero la demanda real no lo era.
          Entrenar sobre la venta observada produce el efecto spiral-down: se pide de menos, hay más
          quiebres, se observa menos demanda, se pide de menos todavía.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 22 }}>
          <Kpi rotulo="Series" valor={conteo(panel?.n_series ?? summary.n_series)} pie={
            panel?.reference_n_series ? `de ${conteo(panel.reference_n_series)} del panel` : "tienda × producto"
          } />
          <Kpi rotulo="Filas" valor={conteo(summary.n_rows)} pie={`${conteo(summary.n_days)} días`} />
          <Kpi
            rotulo="Días con quiebre"
            valor={porcentajeSimple(diasConQuiebre * 100, 1)}
            pie="del total de días-serie"
          />
          <Kpi
            rotulo="Horas en quiebre"
            valor={magnitud(horas, 1)}
            pie={`de ${franjas} franjas comerciales`}
          />
        </div>

        <section className="bloque" style={{ marginTop: 22 }}>
          <h3 style={{ fontSize: 16, marginBottom: 8 }}>Comprobación de la ventana comercial</h3>
          <div
            className="consecuencia"
            style={{ borderLeftColor: "var(--tinta)", maxWidth: "78ch" }}
          >
            <span className="tabular">
              {porcentajeSimple(diasConQuiebre * 100, 1)} de días con quiebre ×{" "}
              {magnitud(horas, 1)} horas promedio ÷ {franjas} franjas ={" "}
              <strong className="tinta" style={{ fontWeight: 600 }}>
                {porcentajeSimple(horasComerciales * 100, 1)} de horas comerciales en quiebre
              </strong>
            </span>
            <div className="nota" style={{ marginTop: 6 }}>
              La ficha de FreshRetailNet-50K declara ≈20 %. Que la cuenta cierre es la verificación
              de que la ventana asumida — 16 franjas, de 6:00 a 22:00 — es la correcta. El código
              además falla si las horas derivadas de la máscara horaria no coinciden con la columna
              del dataset, así que el supuesto se comprueba en cada corrida y no una sola vez.
            </div>
          </div>
        </section>

        <section className="bloque" style={{ marginTop: 22 }}>
          <h3 style={{ fontSize: 16, marginBottom: 8 }}>Recuperación de demanda censurada</h3>
          <table className="tabla" style={{ maxWidth: 620 }}>
            <thead>
              <tr>
                <th scope="col" className="izq">
                  Grupo
                </th>
                <th scope="col">Días-serie</th>
                <th scope="col">Demanda observada</th>
                <th scope="col">Demanda latente</th>
                <th scope="col">Uplift</th>
              </tr>
            </thead>
            <tbody>
              {(comparison as unknown as FilaCensura[]).map((fila) => {
                // El uplift de exactamente 0 % en los días limpios es por diseño:
                // son la verdad de terreno con la que se mide el sesgo, así que
                // corregirlos destruiría la medición.
                const limpio = Math.abs(fila.uplift_pct) < 1e-9;
                return (
                  <tr className="fila" key={fila.grupo}>
                    <td className="izq tinta">{fila.grupo}</td>
                    <td className="apagada">{conteo(fila.n)}</td>
                    <td className="apagada">{magnitud(fila.demanda_observada, 4)}</td>
                    <td className={limpio ? "apagada" : "acento"}>
                      {magnitud(fila.demanda_latente, 4)}
                    </td>
                    <td style={{ fontWeight: limpio ? 400 : 600 }}>
                      {porcentaje(fila.uplift_pct, 2)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="nota" style={{ maxWidth: "88ch", marginTop: 10 }}>
            {note}
          </p>
        </section>
      </div>
    </div>
  );
}

function Kpi({ rotulo, valor, pie }: { rotulo: string; valor: string; pie: string }) {
  return (
    <div>
      <div className="rotulo">{rotulo}</div>
      <div
        className="tabular tinta"
        style={{ fontSize: 20, fontWeight: 500, marginTop: 4, lineHeight: 1.1 }}
      >
        {valor}
      </div>
      <div className="nota">{pie}</div>
    </div>
  );
}
