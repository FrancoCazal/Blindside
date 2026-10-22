/**
 * Preferencias de quien mira: idioma y tema.
 *
 * Es un panel que se despliega desde la barra superior y no una pantalla: dos
 * opciones no justifican una entrada en la navegación. No es modal — no atrapa
 * el foco ni oscurece el fondo — porque elegir un tema y ver el resultado detrás
 * es justamente lo que se quiere. Escape y un clic afuera lo cierran y devuelven
 * el foco al botón.
 *
 * Cada opción es un grupo de botones con `aria-pressed`, el mismo patrón que el
 * toggle de base y el ratio de costo: la interfaz no introduce un control nuevo
 * para lo mismo.
 */

import { useEffect, useId, useRef, useState } from "react";

import { IDIOMAS, t } from "../i18n";
import { PREFERENCIAS_TEMA, useEstado } from "../state";

export function Preferencias() {
  const { idioma, setIdioma, preferenciaTema, setPreferenciaTema } = useEstado();
  const [abierto, setAbierto] = useState(false);
  const contenedor = useRef<HTMLDivElement>(null);
  const boton = useRef<HTMLButtonElement>(null);
  const id = useId();
  const textos = t().preferencias;

  useEffect(() => {
    if (!abierto) return;
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setAbierto(false);
      boton.current?.focus();
    };
    // `pointerdown` y no `click`: el clic que abre el panel no tiene que contar
    // como un clic afuera que lo cierra.
    const alTocar = (e: PointerEvent) => {
      if (contenedor.current && !contenedor.current.contains(e.target as Node)) setAbierto(false);
    };
    window.addEventListener("keydown", alTeclear);
    window.addEventListener("pointerdown", alTocar);
    return () => {
      window.removeEventListener("keydown", alTeclear);
      window.removeEventListener("pointerdown", alTocar);
    };
  }, [abierto]);

  return (
    <div className="preferencias" ref={contenedor}>
      <button
        ref={boton}
        type="button"
        className="selector-disparador"
        aria-expanded={abierto}
        aria-controls={id}
        onClick={() => setAbierto((a) => !a)}
      >
        <IconoAjustes />
        {textos.boton}
      </button>

      {abierto && (
        <div className="preferencias-panel" id={id} role="region" aria-label={textos.titulo}>
          <div className="control">
            <span className="rotulo" id={`${id}-idioma`}>
              {textos.idioma}
            </span>
            <div className="toggle" role="group" aria-labelledby={`${id}-idioma`}>
              {IDIOMAS.map((opcion) => (
                <button
                  key={opcion.id}
                  type="button"
                  lang={opcion.id}
                  aria-pressed={idioma === opcion.id}
                  onClick={() => setIdioma(opcion.id)}
                >
                  {opcion.nombre}
                </button>
              ))}
            </div>
          </div>

          <div className="control">
            <span className="rotulo" id={`${id}-tema`}>
              {textos.tema}
            </span>
            <div className="toggle" role="group" aria-labelledby={`${id}-tema`}>
              {PREFERENCIAS_TEMA.map((opcion) => (
                <button
                  key={opcion}
                  type="button"
                  aria-pressed={preferenciaTema === opcion}
                  onClick={() => setPreferenciaTema(opcion)}
                >
                  {textos.temas[opcion]}
                </button>
              ))}
            </div>
          </div>

          <p className="nota">{textos.nota}</p>
        </div>
      )}
    </div>
  );
}

function IconoAjustes() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor">
      <path d="M2 4.5h7M12 4.5h2M2 11.5h2M7 11.5h7" strokeWidth="1.4" strokeLinecap="round" />
      <circle cx="10.5" cy="4.5" r="1.6" strokeWidth="1.4" />
      <circle cx="5.5" cy="11.5" r="1.6" strokeWidth="1.4" />
    </svg>
  );
}
