import { Component, useEffect, useState, type ReactNode } from "react";

import { API_BASE, api, type SeriesItem } from "./api/client";
import { ApiCaida, Esqueleto, SinArtefacto } from "./components/estados";
import { SelectorSeries } from "./components/SelectorSeries";
import { Shell } from "./components/Shell";
import { PantallaAlertas } from "./screens/PantallaAlertas";
import { PantallaDatos } from "./screens/PantallaDatos";
import { PantallaModelos } from "./screens/PantallaModelos";
import { PantallaPanel } from "./screens/PantallaPanel";
import { PantallaPipeline } from "./screens/PantallaPipeline";
import { PantallaReposicion } from "./screens/PantallaReposicion";
import { PantallaSerie } from "./screens/PantallaSerie";
import { t } from "./i18n";
import { PANTALLAS_CON_BASE, useAsincrono, useAtajo, useEstado } from "./state";

export default function App() {
  const {
    pantalla,
    serie,
    setSerie,
    irA,
    basis,
    setBasis,
    anunciar,
    health,
    healthCargando,
    healthError,
    recargarHealth,
  } = useEstado();
  const [selectorAbierto, setSelectorAbierto] = useState(false);

  // El backtest lo leen el Panel y Modelos. Se pide una vez para las dos.
  const backtest = useAsincrono(() => api.backtest().catch(() => null), []);

  useAtajo("k", () => setSelectorAbierto(true), true);
  useAtajo("Escape", () => setSelectorAbierto(false));
  // El atajo del toggle actúa solo donde el toggle cambia una cifra. En el resto
  // de las pantallas cambiar la base no tiene efecto visible, y anunciar «Demanda
  // recuperada» sin que nada cambie es peor que no hacer nada.
  useAtajo("b", () => {
    if (!PANTALLAS_CON_BASE.includes(pantalla)) return;
    const siguiente = basis === "observed" ? "recovered" : "observed";
    setBasis(siguiente);
    anunciar(t().bases[siguiente]);
  });

  // Sin serie elegida se toma la primera del panel, para que la pantalla de
  // serie individual nunca aparezca vacía.
  useEffect(() => {
    if (serie || health == null) return;
    api
      .series({ limit: 1 })
      .then((p) => {
        const primera = p.items[0];
        if (primera) setSerie(primera.series_id);
      })
      .catch(() => undefined);
  }, [serie, health, setSerie]);

  if (healthCargando && !health) return <Esqueleto />;
  if (healthError) return <ApiCaida error={healthError} onReintentar={recargarHealth} />;

  // Una API anterior a este frontend responde 200 con menos campos, y el fallo
  // aparecería después como un TypeError en cualquier pantalla. Pasa de verdad:
  // el contenedor de Docker sirve la imagen con la que se construyó, así que
  // después de tocar `api/` hay que reconstruirla. Vale más decirlo acá.
  if (health && (!Array.isArray(health.models) || !Array.isArray(health.panel?.store_ids))) {
    return <ApiVieja onReintentar={recargarHealth} />;
  }

  const elegir = (s: SeriesItem) => {
    setSerie(s.series_id);
    irA("series");
  };
  const abrirSerie = (id: string) => {
    setSerie(id);
    irA("series");
  };

  // Sin ningún artefacto cargado, las pantallas que emiten una cantidad no tienen
  // nada que mostrar. Las de evidencia sí, así que el estado no es global.
  const modelos = health?.models ?? [];
  const sinModelo = modelos.length > 0 && modelos.every((m) => !m.loaded);
  const necesitaModelo = pantalla === "reorder" || pantalla === "series";

  return (
    <>
      <Shell health={health} onAbrirSelector={() => setSelectorAbierto(true)}>
        <LimiteDeFalla onReintentar={recargarHealth}>
          {sinModelo && necesitaModelo ? (
            <SinArtefacto modelos={modelos} onReintentar={recargarHealth} />
          ) : (
            <>
              {pantalla === "panel" && health && (
                <PantallaPanel
                  health={health}
                  backtest={backtest.datos}
                  backtestCargando={backtest.cargando}
                />
              )}
              {pantalla === "alerts" && <PantallaAlertas onElegirSerie={abrirSerie} />}
              {pantalla === "reorder" && <PantallaReposicion onElegirSerie={abrirSerie} />}
              {pantalla === "series" && (serie ? <PantallaSerie serie={serie} /> : <Esqueleto />)}
              {pantalla === "models" && health && (
                <PantallaModelos
                  health={health}
                  backtest={backtest.datos}
                  backtestCargando={backtest.cargando}
                />
              )}
              {pantalla === "data" && <PantallaDatos onElegirSerie={abrirSerie} />}
              {pantalla === "pipeline" && <PantallaPipeline />}
            </>
          )}
        </LimiteDeFalla>
      </Shell>

      <SelectorSeries
        abierto={selectorAbierto}
        onCerrar={() => setSelectorAbierto(false)}
        onElegir={elegir}
      />
    </>
  );
}

function ApiVieja({ onReintentar }: { onReintentar: () => void }) {
  const textos = t();
  return (
    <div className="pagina" style={{ padding: "var(--e6)" }}>
      <h2>{textos.estados.apiViejaTitulo}</h2>
      <p className="nota" style={{ maxWidth: "74ch", marginTop: 8 }}>
        {textos.estados.apiViejaTexto(`${API_BASE}/health`)}
      </p>
      <div className="consecuencia" style={{ marginTop: 18, maxWidth: 620 }}>
        {textos.estados.apiViejaComando}
      </div>
      <button type="button" onClick={onReintentar} className="boton-primario" style={{ marginTop: 18 }}>
        {textos.comun.reintentar}
      </button>
    </div>
  );
}

/**
 * Una pantalla que falla no puede llevarse el cromo: la navegación sigue siendo
 * útil cuando la consulta de abajo se cayó.
 */
class LimiteDeFalla extends Component<
  { children: ReactNode; onReintentar: () => void },
  { error: unknown }
> {
  state = { error: null as unknown };

  static getDerivedStateFromError(error: unknown) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <ApiCaida
          error={this.state.error}
          onReintentar={() => {
            this.setState({ error: null });
            this.props.onReintentar();
          }}
        />
      );
    }
    return this.props.children;
  }
}
