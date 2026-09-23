/**
 * Estado de la aplicación.
 *
 * `basis` y `series` viven **en la URL** y son independientes entre sí: cambiar
 * de serie no cambia la base de cálculo, y cambiar de pantalla no resetea
 * ninguna de las dos. Que estén en la URL tiene una razón de demo: un enlace
 * reproduce exactamente lo que se vio, y el video de respaldo no depende de
 * repetir clics en el orden correcto.
 *
 * `basis` arranca en `observed` a propósito. La demo empieza en el modo
 * equivocado — el que ve el ERP — y se corrige en vivo.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { api, type Health as Salud } from "./api/client";
import { RATIO_POR_DEFECTO } from "./domain";

export type Pantalla = "reorder" | "series" | "overview" | "compare" | "explain" | "health" | "map";
export type Basis = "observed" | "recovered";
export type Tema = "claro" | "oscuro";

export interface AppState {
  pantalla: Pantalla;
  basis: Basis;
  serie: string | null;
  ratio: number;
  /** Filtro de tienda. `null` es todas. Vive en la URL como el resto. */
  tienda: number | null;
  /** Filtro de clase de rotación: baja, media o alta. */
  clase: string | null;
  tema: Tema;
  /**
   * Estado del panel y de los artefactos. Es estado **global**: de acá salen la
   * barra de filtros, el sello de muestra, la franja de contexto y la decisión de
   * mostrar la pantalla de «sin artefacto». Por eso lo posee el proveedor y no una
   * pantalla.
   */
  health: Salud | null;
  healthCargando: boolean;
  healthError: unknown;
  recargarHealth: () => void;
  irA: (pantalla: Pantalla) => void;
  setBasis: (basis: Basis) => void;
  setSerie: (serie: string) => void;
  setRatio: (ratio: number) => void;
  setTienda: (tienda: number | null) => void;
  setClase: (clase: string | null) => void;
  alternarTema: () => void;
  /** Texto que lee el lector de pantalla cuando cambia un valor. */
  anuncio: string;
  anunciar: (texto: string) => void;
}

const Contexto = createContext<AppState | null>(null);

const PANTALLAS: Pantalla[] = [
  "reorder",
  "series",
  "overview",
  "compare",
  "explain",
  "health",
  "map",
];

function leerUrl() {
  const p = new URLSearchParams(window.location.search);
  const pantalla = p.get("screen");
  const basis = p.get("basis");
  const ratio = Number(p.get("ratio"));
  const tienda = p.get("store");
  const clase = p.get("class");
  return {
    pantalla: (PANTALLAS.includes(pantalla as Pantalla) ? pantalla : "reorder") as Pantalla,
    basis: (basis === "recovered" ? "recovered" : "observed") as Basis,
    serie: p.get("series"),
    ratio: Number.isFinite(ratio) && ratio > 0 ? ratio : RATIO_POR_DEFECTO,
    tienda: tienda != null && tienda !== "" && Number.isFinite(Number(tienda)) ? Number(tienda) : null,
    clase: clase === "baja" || clase === "media" || clase === "alta" ? clase : null,
  };
}

function temaInicial(): Tema {
  const guardado = window.localStorage.getItem("blindside:tema");
  if (guardado === "claro" || guardado === "oscuro") return guardado;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "oscuro" : "claro";
}

export function ProveedorEstado({ children }: { children: ReactNode }) {
  const [url, setUrl] = useState(leerUrl);
  const [tema, setTema] = useState<Tema>(temaInicial);
  const [anuncio, setAnuncio] = useState("");
  const salud = useAsincrono(() => api.health(), []);

  // El estado se refleja en la URL sin recargar, y el botón «atrás» del
  // navegador vuelve al estado anterior en vez de salir de la app.
  useEffect(() => {
    const p = new URLSearchParams();
    p.set("screen", url.pantalla);
    p.set("basis", url.basis);
    if (url.serie) p.set("series", url.serie);
    if (url.ratio !== RATIO_POR_DEFECTO) p.set("ratio", String(url.ratio));
    if (url.tienda != null) p.set("store", String(url.tienda));
    if (url.clase) p.set("class", url.clase);
    const nueva = `${window.location.pathname}?${p.toString()}`;
    if (nueva !== `${window.location.pathname}${window.location.search}`) {
      window.history.pushState(null, "", nueva);
    }
  }, [url]);

  useEffect(() => {
    const alVolver = () => setUrl(leerUrl());
    window.addEventListener("popstate", alVolver);
    return () => window.removeEventListener("popstate", alVolver);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = tema === "oscuro" ? "dark" : "light";
    window.localStorage.setItem("blindside:tema", tema);
  }, [tema]);

  const valor = useMemo<AppState>(
    () => ({
      ...url,
      tema,
      health: salud.datos,
      healthCargando: salud.cargando,
      healthError: salud.error,
      recargarHealth: salud.recargar,
      irA: (pantalla) => setUrl((u) => ({ ...u, pantalla })),
      setBasis: (basis) => setUrl((u) => ({ ...u, basis })),
      setSerie: (serie) => setUrl((u) => ({ ...u, serie })),
      setRatio: (ratio) => setUrl((u) => ({ ...u, ratio })),
      setTienda: (tienda) => setUrl((u) => ({ ...u, tienda })),
      setClase: (clase) => setUrl((u) => ({ ...u, clase })),
      alternarTema: () => setTema((t) => (t === "claro" ? "oscuro" : "claro")),
      anuncio,
      anunciar: setAnuncio,
    }),
    [url, tema, anuncio, salud.datos, salud.cargando, salud.error, salud.recargar],
  );

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useEstado(): AppState {
  const valor = useContext(Contexto);
  if (!valor) throw new Error("useEstado fuera del proveedor");
  return valor;
}

/** Atajo de teclado global. */
export function useAtajo(tecla: string, accion: () => void, conModificador = false) {
  const ref = useRef(accion);
  // La asignación va en un efecto y no en el render: escribir un ref durante el
  // render lo vuelve sensible al doble render de StrictMode.
  useEffect(() => {
    ref.current = accion;
  }, [accion]);
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => {
      const destino = e.target as HTMLElement | null;
      const escribiendo =
        destino?.tagName === "INPUT" || destino?.tagName === "TEXTAREA" || destino?.isContentEditable;
      const modificador = e.metaKey || e.ctrlKey;
      if (conModificador && !modificador) return;
      if (!conModificador && (modificador || escribiendo)) return;
      if (e.key.toLowerCase() !== tecla.toLowerCase()) return;
      e.preventDefault();
      ref.current();
    };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [tecla, conModificador]);
}

/** ¿El usuario pidió menos movimiento? */
export function usaMenosMovimiento(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Conteo de una cifra hacia su nuevo valor, entre 200 y 700 ms de la secuencia
 * del toggle. Con `prefers-reduced-motion` el valor se reemplaza en seco.
 */
export function useConteo(valor: number, duracion = 500, retardo = 200): number {
  const [mostrado, setMostrado] = useState(valor);
  const desde = useRef(valor);

  useEffect(() => {
    if (usaMenosMovimiento()) {
      setMostrado(valor);
      desde.current = valor;
      return;
    }
    const inicial = desde.current;
    if (inicial === valor) return;
    let cuadro = 0;
    let arranque = 0;
    const paso = (t: number) => {
      if (!arranque) arranque = t;
      const avance = Math.min(1, Math.max(0, (t - arranque - retardo) / duracion));
      // Misma curva que el resto de la secuencia.
      const suave = avance < 0.5 ? 2 * avance * avance : 1 - (-2 * avance + 2) ** 2 / 2;
      setMostrado(inicial + (valor - inicial) * suave);
      if (avance < 1) cuadro = requestAnimationFrame(paso);
      else desde.current = valor;
    };
    cuadro = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(cuadro);
  }, [valor, duracion, retardo]);

  return mostrado;
}

/** Carga asíncrona con estados explícitos. `recargar` es el botón de reintento. */
export interface Asincrono<T> {
  datos: T | null;
  cargando: boolean;
  error: unknown;
  recargar: () => void;
}

export function useAsincrono<T>(fn: () => Promise<T>, deps: unknown[]): Asincrono<T> {
  const [datos, setDatos] = useState<T | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [intento, setIntento] = useState(0);
  const fnRef = useRef(fn);

  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);

  useEffect(() => {
    let vivo = true;
    setCargando(true);
    setError(null);
    fnRef
      .current()
      .then((valor) => {
        if (vivo) {
          setDatos(valor);
          setCargando(false);
        }
      })
      .catch((e) => {
        if (vivo) {
          setError(e);
          setCargando(false);
        }
      });
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, intento]);

  const recargar = useCallback(() => setIntento((i) => i + 1), []);
  return { datos, cargando, error, recargar };
}
