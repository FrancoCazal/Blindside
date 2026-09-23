import { Component, useEffect, useState, type ReactNode } from "react";

import { API_BASE, api, type SeriesItem } from "./api/client";
import { ApiCaida, Esqueleto, SinArtefacto } from "./components/estados";
import { Shell } from "./components/Shell";
import { SelectorSeries } from "./components/SelectorSeries";
import { PantallaComparativa } from "./screens/PantallaComparativa";
import { PantallaExplicabilidad } from "./screens/PantallaExplicabilidad";
import { PantallaMapa } from "./screens/PantallaMapa";
import { PantallaReposicion } from "./screens/PantallaReposicion";
import { PantallaSalud } from "./screens/PantallaSalud";
import { PantallaSerie } from "./screens/PantallaSerie";
import { PantallaVistaGeneral } from "./screens/PantallaVistaGeneral";
import { useAsincrono, useAtajo, useEstado } from "./state";

export default function App() {
  const { pantalla, serie, setSerie, irA, basis, setBasis } = useEstado();
  const [selectorAbierto, setSelectorAbierto] = useState(false);
  const [rotuloSerie, setRotuloSerie] = useState<string | null>(null);

  // /health es el estado global de la app: de acá salen panel-vs-muestra, si el
  // toggle tiene las dos bases y si la API está en pie.
  const salud = useAsincrono(() => api.health(), []);
  const backtest = useAsincrono(
    () => api.backtest().catch(() => null),
    [],
  );

  useAtajo("k", () => setSelectorAbierto(true), true);
  useAtajo("Escape", () => setSelectorAbierto(false));
  // El toggle de censura tiene atajo global porque es el control que se acciona
  // en vivo durante la demo, y buscar el botón con el mouse en un proyector
  // rompe el ritmo de la explicación.
  useAtajo("b", () => setBasis(basis === "observed" ? "recovered" : "observed"));

  // Sin serie elegida se toma la primera del panel, para que la pantalla de
  // serie individual nunca aparezca vacía.
  useEffect(() => {
    if (serie || salud.datos == null) return;
    api
      .series({ limit: 1 })
      .then((p) => {
        const primera = p.items[0];
        if (primera) {
          setSerie(primera.series_id);
          setRotuloSerie(primera.label);
        }
      })
      .catch(() => undefined);
  }, [serie, salud.datos, setSerie]);

  if (salud.cargando && !salud.datos) return <Esqueleto />;
  if (salud.error) return <ApiCaida error={salud.error} onReintentar={salud.recargar} />;

  // Una API anterior a este frontend responde 200 con menos campos, y el fallo
  // aparecería después como un TypeError en cualquier pantalla. Pasa de verdad:
  // el contenedor de Docker sirve la imagen con la que se construyó, así que
  // después de tocar `api/` hay que reconstruirla. Vale más decirlo acá.
  if (salud.datos && !Array.isArray(salud.datos.models)) {
    return <ApiVieja onReintentar={salud.recargar} />;
  }

  const elegir = (s: SeriesItem) => {
    setSerie(s.series_id);
    setRotuloSerie(s.label);
    irA("series");
  };

  // Sin ningún artefacto cargado, las pantallas que emiten una cantidad no tienen
  // nada que mostrar. Las de evidencia sí, así que el estado no es global.
  const modelos = salud.datos?.models ?? [];
  const sinModelo = modelos.length > 0 && modelos.every((m) => !m.loaded);
  const necesitaModelo = pantalla === "reorder" || pantalla === "series" || pantalla === "explain";

  return (
    <>
      <Shell
        health={salud.datos}
        backtest={backtest.datos}
        serieRotulo={rotuloSerie ?? serie}
        onAbrirSelector={() => setSelectorAbierto(true)}
      >
        <LimiteDeFalla onReintentar={salud.recargar}>
          {sinModelo && necesitaModelo ? (
            <SinArtefacto modelos={modelos} onReintentar={salud.recargar} />
          ) : (
            <>
              {pantalla === "reorder" && (
                <PantallaReposicion
                  onElegirSerie={(id) => {
                    setSerie(id);
                    irA("series");
                  }}
                />
              )}
              {pantalla === "series" && (serie ? <PantallaSerie serie={serie} /> : <Esqueleto />)}
              {pantalla === "overview" && salud.datos && (
                <PantallaVistaGeneral health={salud.datos} />
              )}
              {pantalla === "compare" && <PantallaComparativa />}
              {pantalla === "explain" &&
                (serie ? <PantallaExplicabilidad serie={serie} /> : <Esqueleto />)}
              {pantalla === "health" && salud.datos && <PantallaSalud health={salud.datos} />}
              {pantalla === "map" && <PantallaMapa serieActiva={serie} />}
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
  return (
    <div className="pagina">
      <h2>La API es anterior a esta interfaz</h2>
      <p className="nota" style={{ maxWidth: "74ch", marginTop: 8 }}>
        <code style={{ fontFamily: "inherit" }}>{API_BASE}/health</code> responde, pero sin el
        estado por base de cálculo ni los conteos del panel. Esta interfaz los necesita para saber
        si el toggle de censura tiene las dos bases cargadas y si lo que se está sirviendo es el
        panel o la muestra.
      </p>
      <div className="consecuencia" style={{ marginTop: 18, maxWidth: 620 }}>
        Si estás corriendo la API en Docker, la imagen tiene el código con el que se construyó:{" "}
        <code style={{ fontFamily: "inherit" }}>docker compose up -d --build api</code>. En local,{" "}
        <code style={{ fontFamily: "inherit" }}>make api</code> ya toma los cambios.
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
        Reintentar
      </button>
    </div>
  );
}

/**
 * Una pantalla que falla no puede llevarse el cromo: la franja de contexto sigue
 * siendo información útil cuando la consulta de abajo se cayó, y perderla deja al
 * usuario sin saber qué modelo estaba cargado.
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
