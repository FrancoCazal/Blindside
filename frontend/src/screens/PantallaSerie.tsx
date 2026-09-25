/**
 * Pantalla 2a · serie individual.
 *
 * Responde «¿por qué le creo a esta cantidad?». Es la imagen que el panel se
 * tiene que llevar: la venta observada contra la demanda recuperada, con los
 * tramos de quiebre sombreados detrás, y la cantidad a pedir a la derecha.
 */

import { useEffect, useRef } from "react";

import { api, type ForecastResponse, type ReorderResponse, type SeriesHistory } from "../api/client";
import { GraficoSerie } from "../charts/GraficoSerie";
import { RATIOS, cuantilCritico, deltaPct } from "../domain";
import { conteo, cuantil, magnitud, porcentaje, porcentajeSimple } from "../format";
import { useAsincrono, useConteo, useEstado } from "../state";
import { Esqueleto } from "../components/estados";

export function PantallaSerie({ serie }: { serie: string }) {
  const { basis, ratio, anunciar } = useEstado();
  const recoverCensoring = basis === "recovered";

  const datos = useAsincrono<{
    historia: SeriesHistory;
    pronostico: ForecastResponse;
    orden: ReorderResponse | null;
    ordenError: string | null;
  }>(async () => {
    const [historia, pronostico] = await Promise.all([
      api.history(serie),
      api.forecast({ seriesIds: [serie], recoverCensoring }),
    ]);
    // La orden puede no estar disponible — si el artefacto cargado no produce
    // cuantiles, el backend responde 501 con el motivo. La pantalla tiene que
    // seguir en pie mostrando la evidencia, que es lo que no depende del modelo.
    try {
      const orden = await api.reorder({ seriesIds: [serie], co: ratio, recoverCensoring });
      return { historia, pronostico, orden, ordenError: null };
    } catch (e) {
      return {
        historia,
        pronostico,
        orden: null,
        ordenError: e instanceof Error ? e.message : String(e),
      };
    }
  }, [serie, recoverCensoring, ratio]);

  const cantidad = datos.datos?.orden?.lines[0]?.qty ?? null;
  const previa = useRef<number | null>(null);

  // El anuncio se emite cuando llega el número nuevo, no al hacer clic: al
  // momento del clic todavía no se sabe a cuánto pasa la cantidad.
  useEffect(() => {
    if (cantidad == null) return;
    const antes = previa.current;
    previa.current = cantidad;
    if (antes == null || antes === cantidad) return;
    const nombre = basis === "recovered" ? "Demanda recuperada" : "Venta observada";
    anunciar(`${nombre}. La cantidad sugerida pasa de ${magnitud(antes)} a ${magnitud(cantidad)}`);
  }, [cantidad, basis, anunciar]);

  if (datos.cargando && !datos.datos) return <Esqueleto />;
  if (datos.error) throw datos.error;
  if (!datos.datos) return null;

  const { historia, pronostico, orden, ordenError } = datos.datos;
  // La política sale de `/reorder` y no de recalcular la media móvil acá: es la
  // misma cifra que usa la tabla de reposición, y calcularla en dos lugares es
  // garantizar que en algún momento no coincidan.
  const politica = orden?.lines[0]?.policy_qty ?? 0;
  const ventana = orden?.policy_window ?? 21;
  const qEstrella = orden?.critical_fraction ?? cuantilCritico(1, ratio);
  const resumen = historia.summary;

  return (
    <div className="pagina">
      <div className="tarjeta cuerpo-serie">
        <div style={{ padding: "16px var(--e5) 14px", borderRight: "1px solid var(--regla-fina)" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12 }}>
            <h2>{historia.series.series_id}</h2>
            <span className="nota">
              tienda {historia.series.store_id} · producto {historia.series.product_id} ·{" "}
              {conteo(historia.points.length)} días
            </span>
          </div>

          <GraficoSerie
            historia={historia}
            pronostico={pronostico.forecasts[0]?.points ?? []}
            cantidadSugerida={cantidad}
            basis={basis}
          />
        </div>

        <div className="panel" style={{ padding: "16px var(--e5) 14px" }}>
          <div>
            <div className="rotulo">Cantidad sugerida</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
              {cantidad != null ? (
                <Cifra valor={cantidad} />
              ) : (
                <span className="cifra-decision" style={{ color: "var(--apagada)" }}>
                  —
                </span>
              )}
              <span style={{ fontSize: 12, color: "var(--apagada)" }}>q* {cuantil(qEstrella)}</span>
            </div>
            {ordenError && (
              <div className="nota" style={{ marginTop: 6, color: "var(--advertencia-texto)" }}>
                {ordenError}
              </div>
            )}
          </div>

          <div className="bloque">
            <div className="rotulo" style={{ marginBottom: 8 }}>
              Contra la política actual
            </div>
            <dl>
              <dt>Media móvil {ventana} d</dt>
              <dd>{magnitud(politica)}</dd>
              <dt>Δ sugerido</dt>
              <dd className={cantidad != null && cantidad > politica ? "acento" : undefined}>
                {cantidad != null ? porcentaje(deltaPct(cantidad, politica)) : "—"}
              </dd>
              <dt>Cu / Co</dt>
              <dd>
                1 / {magnitud(ratio, 1)}
              </dd>
            </dl>
            <div className="nota" style={{ marginTop: 8 }}>
              {RATIOS.find((r) => r.co === ratio)?.lectura ?? "Ratio de costo personalizado"}
            </div>
          </div>

          <div className="bloque">
            <div className="rotulo" style={{ marginBottom: 8 }}>
              Censura de esta serie
            </div>
            <dl>
              <dt>Uplift de recuperación</dt>
              <dd className="acento">{porcentaje(resumen.uplift_pct)}</dd>
              <dt>Días con quiebre</dt>
              <dd>
                {conteo(resumen.n_censored_days)} de {conteo(resumen.n_days)}
              </dd>
              <dt>Horas por día en quiebre</dt>
              <dd>
                {resumen.mean_oos_hours_when_censored != null
                  ? magnitud(resumen.mean_oos_hours_when_censored, 1)
                  : "—"}{" "}
                / {historia.open_hours}
              </dd>
              <dt>Racha máxima</dt>
              <dd>{conteo(resumen.max_run_days)} d</dd>
              <dt>Uplift en días limpios</dt>
              <dd>{porcentajeSimple(resumen.uplift_pct_clean_days, 2)}</dd>
            </dl>
            <div className="nota" style={{ marginTop: 8 }}>
              El uplift de exactamente 0 % en los días sin quiebre es por diseño: esos días son la
              verdad de terreno con la que se mide el sesgo, así que corregirlos destruiría la
              medición.
            </div>
          </div>

          <div className="consecuencia" data-basis={basis}>
            {basis === "recovered" ? (
              <>
                <strong style={{ fontWeight: 600 }}>Censura corregida.</strong> Es la base de la
                cantidad sugerida.
              </>
            ) : (
              <>
                <strong style={{ fontWeight: 600 }}>Es lo que ve el ERP.</strong> Subestima la
                demanda en los días con quiebre, y por eso la cantidad sugerida queda corta.
              </>
            )}
          </div>

          <div className="nota">
            Magnitudes adimensionales: <code style={{ fontFamily: "inherit" }}>sale_amount</code>{" "}
            viene multiplicado por un coeficiente no divulgado, así que no hay moneda ni kilos.
          </div>
        </div>
      </div>

      <p className="nota" style={{ maxWidth: "92ch", marginTop: 14 }}>
        La política de comparación y su ventana vienen de <code>/reorder</code>: es la media móvil
        de 21 días de la misma base activa. El pronóstico, la banda conformal y la cantidad
        sugerida también vienen de la API; esta pantalla no recalcula ninguna decisión.
      </p>
    </div>
  );
}

function Cifra({ valor }: { valor: number }) {
  const mostrado = useConteo(valor);
  return <span className="cifra-decision">{magnitud(mostrado)}</span>;
}
