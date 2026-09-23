/**
 * Explicabilidad · por qué este número.
 *
 * Las contribuciones son TreeSHAP calculadas por LightGBM, no simuladas. Se
 * explica el **cuantil crítico** y no la mediana, porque la cifra que la interfaz
 * muestra es la cantidad a pedir: explicar la mediana sería explicar otra cosa.
 *
 * El gráfico es una cascada horizontal desde el valor base: a la derecha lo que
 * empuja la cantidad hacia arriba, a la izquierda lo que la baja. El acento no se
 * usa para «positivo»: se usa para lo recuperado, así que acá los dos sentidos
 * van en la escala de grises y el signo lo lleva la dirección de la barra.
 */

import { api, type ExplainResponse } from "../api/client";
import { cuantil, magnitud } from "../format";
import { useAsincrono, useEstado } from "../state";
import { Esqueleto } from "../components/estados";

export function PantallaExplicabilidad({ serie }: { serie: string }) {
  const { basis } = useEstado();
  const recoverCensoring = basis === "recovered";

  const datos = useAsincrono(async () => {
    // La fecha explicable es el primer día del horizonte: es la que produce la
    // orden de hoy, que es la cifra que el usuario está mirando.
    const pronostico = await api.forecast({ seriesIds: [serie], recoverCensoring });
    const dt = pronostico.forecasts[0]?.points[0]?.dt;
    if (!dt) throw new Error("el pronóstico vino vacío");
    return api.explain({ seriesId: serie, dt, topK: 12, recoverCensoring });
  }, [serie, recoverCensoring]);

  if (datos.cargando && !datos.datos) return <Esqueleto filas={6} />;
  if (datos.error) throw datos.error;
  if (!datos.datos) return null;

  return <Cascada datos={datos.datos} />;
}

function Cascada({ datos }: { datos: ExplainResponse }) {
  const contribuciones = datos.contributions;
  const maxAbs = Math.max(...contribuciones.map((c) => Math.abs(c.contribution)), 1e-9);
  const suma = contribuciones.reduce((a, c) => a + c.contribution, 0);
  const resto = datos.prediction - datos.base_value - suma;

  return (
    <div className="pagina">
      <div className="tarjeta" style={{ padding: "18px var(--e5)" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 4 }}>
          <h2>Por qué este número</h2>
          <span className="nota">
            {datos.series.series_id} · {datos.dt} ·{" "}
            {datos.basis === "recovered" ? "demanda recuperada" : "venta observada"}
          </span>
        </div>
        <p className="nota" style={{ maxWidth: "88ch", marginBottom: 18 }}>
          Contribuciones TreeSHAP del modelo <strong style={{ fontWeight: 600 }}>{datos.model_name}</strong>
          {datos.quantile != null && <> sobre el cuantil {cuantil(datos.quantile)}</>}. Las calcula
          LightGBM, así que son las del modelo que respondió y no una aproximación de otro.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 268px", gap: 26 }}>
          <div>
            {contribuciones.map((c) => {
              const ancho = (Math.abs(c.contribution) / maxAbs) * 50;
              const positiva = c.contribution >= 0;
              return (
                <div
                  key={c.feature}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "210px 1fr 86px",
                    alignItems: "center",
                    gap: 10,
                    height: 26,
                    fontSize: 12,
                  }}
                >
                  <span className="tinta" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                    {c.feature}
                  </span>
                  <div style={{ position: "relative", height: 10 }}>
                    {/* Eje del cero en el medio: la barra crece hacia el lado de
                        su signo, así el sentido se lee sin leer el número. */}
                    <div
                      style={{
                        position: "absolute",
                        left: "50%",
                        top: -3,
                        bottom: -3,
                        width: 1,
                        background: "var(--regla-cabecera)",
                      }}
                    />
                    <div
                      style={{
                        position: "absolute",
                        height: 10,
                        left: positiva ? "50%" : `${50 - ancho}%`,
                        width: `${ancho}%`,
                        background: positiva ? "var(--horas-quiebre)" : "var(--guia)",
                        borderRight: positiva ? "2px solid var(--tinta)" : undefined,
                        borderLeft: positiva ? undefined : "2px solid var(--tinta)",
                      }}
                    />
                  </div>
                  <span className="tabular" style={{ textAlign: "right" }}>
                    {c.contribution >= 0 ? "+" : "\u2212"}
                    {magnitud(Math.abs(c.contribution), 3)}
                  </span>
                </div>
              );
            })}
            <p className="nota" style={{ marginTop: 12, maxWidth: "80ch" }}>
              Valor de cada feature en esta predicción:{" "}
              {contribuciones
                .filter((c) => c.value != null)
                .slice(0, 4)
                .map((c) => `${c.feature} = ${magnitud(c.value as number)}`)
                .join(" · ")}
              .
            </p>
          </div>

          <div className="panel">
            <div>
              <div className="rotulo">Cantidad explicada</div>
              <div className="cifra-decision" style={{ marginTop: 4 }}>
                {magnitud(datos.prediction)}
              </div>
            </div>
            <div className="bloque">
              <dl>
                <dt>Valor base del modelo</dt>
                <dd>{magnitud(datos.base_value, 3)}</dd>
                <dt>Suma de las {contribuciones.length} mostradas</dt>
                <dd>{magnitud(suma, 3)}</dd>
                <dt>Resto de las features</dt>
                <dd>{magnitud(resto, 3)}</dd>
              </dl>
              <div className="nota" style={{ marginTop: 8 }}>
                Base más contribuciones da la predicción exacta: TreeSHAP es aditivo. El «resto» es
                la suma de las features que no entran en el top y existe por eso, no por error de
                redondeo.
              </div>
            </div>
            <div className="consecuencia" data-basis={datos.basis}>
              {datos.basis === "recovered" ? (
                <>
                  Las features de demanda recuperada son las que llevan la corrección de censura
                  adentro: si dominan, la cantidad sube por el quiebre y no por la tendencia.
                </>
              ) : (
                <>
                  Esta explicación es del artefacto entrenado sobre venta observada, así que no
                  incluye el efecto de la censura. Cambiá la base para ver la otra.
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
