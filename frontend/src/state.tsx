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
 *
 * El idioma y el tema **no** van en la URL: son preferencias de quien mira, no
 * parte de lo que se está mostrando. Viven en `localStorage`. `?lang=es` se
 * acepta al cargar, para abrir la demo en español con un enlace, y se guarda.
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
import { IDIOMA_POR_DEFECTO, esIdioma, fijarIdioma, type Idioma } from "./i18n";

/** Las siete pantallas. Ver `docs/rediseno_frontend.md`, sección 3. */
export type Pantalla = "panel" | "alerts" | "reorder" | "series" | "models" | "data" | "pipeline";
export type Basis = "observed" | "recovered";
/** El tema que se pinta. */
export type Tema = "claro" | "oscuro";
/** Lo que eligió quien mira. `sistema` sigue al sistema operativo, también si cambia. */
export type PreferenciaTema = "sistema" | Tema;

export const PREFERENCIAS_TEMA: PreferenciaTema[] = ["sistema", "claro", "oscuro"];

const CLAVE_IDIOMA = "blindside:idioma";
const CLAVE_TEMA = "blindside:tema";

/**
 * Columnas por las que la tabla de reposición se puede ordenar. El orden se hace
 * **en el servidor** sobre todo el catálogo (`/reorder/catalog`): ordenar la
 * página en el cliente dejaba la serie de mayor ahorro en cualquier página.
 */
export type Columna = "impacto" | "sugerido" | "politica" | "delta" | "serie";
export type Direccion = "asc" | "desc";

export const COLUMNAS: Columna[] = ["impacto", "sugerido", "politica", "delta", "serie"];

/** Pantallas donde el toggle de base cambia alguna cifra. */
export const PANTALLAS_CON_BASE: Pantalla[] = ["reorder", "series"];

export interface AppState {
  pantalla: Pantalla;
  basis: Basis;
  serie: string | null;
  ratio: number;
  /** Filtro de tienda. `null` es todas. Vive en la URL como el resto. */
  tienda: number | null;
  /** Filtro de clase de rotación: baja, media o alta. */
  clase: string | null;
  /** Grupo de alerta elegido en la pantalla de alertas. `null` es todas. */
  grupo: string | null;
  /** Columna de ordenamiento de la tabla de reposición. */
  orden: Columna;
  /** Dirección del ordenamiento. */
  direccion: Direccion;
  /**
   * Desplazamiento de la página, en filas. Va en la URL porque una tabla
   * paginada cuya página no se puede enlazar obliga a repetir la navegación para
   * mostrarle a otra persona lo que se está viendo.
   */
  offset: number;
  /** El tema efectivo: la preferencia resuelta contra el sistema. */
  tema: Tema;
  preferenciaTema: PreferenciaTema;
  idioma: Idioma;
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
  setGrupo: (grupo: string | null) => void;
  /** Ordena por una columna. Repetir la misma invierte la dirección. */
  ordenarPor: (columna: Columna) => void;
  setOffset: (offset: number) => void;
  setPreferenciaTema: (preferencia: PreferenciaTema) => void;
  setIdioma: (idioma: Idioma) => void;
  /** Texto que lee el lector de pantalla cuando cambia un valor. */
  anuncio: string;
  anunciar: (texto: string) => void;
}

const Contexto = createContext<AppState | null>(null);

const PANTALLAS: Pantalla[] = ["panel", "alerts", "reorder", "series", "models", "data", "pipeline"];

/**
 * Pantallas que existieron y se fusionaron. Un enlace viejo redirige en vez de
 * caer en el panel sin explicación: hay guiones y videos con esas URL.
 */
const REDIRECCIONES: Record<string, Pantalla> = {
  overview: "data",
  map: "data",
  compare: "models",
  health: "models",
  explain: "series",
};

/**
 * La app abre en el panel y no en la reposición. El panel responde «qué pasa
 * hoy y qué miro primero» en una pantalla, y lleva a la reposición con un clic.
 * La demo sigue entrando directo con `?screen=reorder`.
 */
const PANTALLA_INICIAL: Pantalla = "panel";

/** Claves de grupo válidas en la URL. Lo que no sea una clave conocida se ignora. */
const GRUPO_VALIDO = /^[a-z_]{3,40}$/;

function leerUrl() {
  const p = new URLSearchParams(window.location.search);
  const pantalla = p.get("screen");
  const basis = p.get("basis");
  const ratio = Number(p.get("ratio"));
  const tienda = p.get("store");
  const clase = p.get("class");
  const orden = p.get("sort");
  const direccion = p.get("dir");
  const offset = Number(p.get("offset"));
  const grupo = p.get("alert");
  const destino = pantalla ? (REDIRECCIONES[pantalla] ?? pantalla) : null;
  return {
    pantalla: (PANTALLAS.includes(destino as Pantalla) ? destino : PANTALLA_INICIAL) as Pantalla,
    grupo: grupo && GRUPO_VALIDO.test(grupo) ? grupo : null,
    basis: (basis === "recovered" ? "recovered" : "observed") as Basis,
    serie: p.get("series"),
    ratio: Number.isFinite(ratio) && ratio > 0 ? ratio : RATIO_POR_DEFECTO,
    tienda: tienda != null && tienda !== "" && Number.isFinite(Number(tienda)) ? Number(tienda) : null,
    clase: clase === "baja" || clase === "media" || clase === "alta" ? clase : null,
    orden: (COLUMNAS.includes(orden as Columna) ? orden : "impacto") as Columna,
    direccion: (direccion === "asc" ? "asc" : "desc") as Direccion,
    offset: Number.isFinite(offset) && offset >= 0 ? Math.floor(offset) : 0,
  };
}

/**
 * `localStorage` puede tirar (modo privado de algunos navegadores, cuota llena).
 * Una preferencia que no se guarda no es motivo para que la app no arranque.
 */
function leerGuardado(clave: string): string | null {
  try {
    return window.localStorage.getItem(clave);
  } catch {
    return null;
  }
}

function guardar(clave: string, valor: string): void {
  try {
    window.localStorage.setItem(clave, valor);
  } catch {
    // Sin persistencia la preferencia dura lo que dura la pestaña.
  }
}

/**
 * `?lang=` gana sobre lo guardado y se guarda, para que un enlace de demo deje el
 * idioma elegido también en las visitas siguientes. Sin nada, inglés: el idioma
 * del navegador no se adivina, porque la demo tiene que verse igual en cualquier
 * máquina.
 */
function idiomaInicial(): Idioma {
  const deUrl = new URLSearchParams(window.location.search).get("lang");
  if (esIdioma(deUrl)) {
    guardar(CLAVE_IDIOMA, deUrl);
    return deUrl;
  }
  const guardado = leerGuardado(CLAVE_IDIOMA);
  return esIdioma(guardado) ? guardado : IDIOMA_POR_DEFECTO;
}

/** Compatible con lo que guardaba el botón anterior: `claro` u `oscuro`. */
function preferenciaInicial(): PreferenciaTema {
  const guardado = leerGuardado(CLAVE_TEMA);
  return PREFERENCIAS_TEMA.includes(guardado as PreferenciaTema)
    ? (guardado as PreferenciaTema)
    : "sistema";
}

const CONSULTA_OSCURO = "(prefers-color-scheme: dark)";

export function ProveedorEstado({ children }: { children: ReactNode }) {
  const [url, setUrl] = useState(leerUrl);
  const [idioma, setIdiomaEstado] = useState<Idioma>(() => {
    // El idioma se fija en el módulo antes del primer render de los hijos: las
    // funciones de formato lo leen de ahí.
    const inicial = idiomaInicial();
    fijarIdioma(inicial);
    return inicial;
  });
  const [preferenciaTema, setPreferenciaTemaEstado] = useState<PreferenciaTema>(preferenciaInicial);
  const [sistemaOscuro, setSistemaOscuro] = useState(() => window.matchMedia(CONSULTA_OSCURO).matches);
  const [anuncio, setAnuncio] = useState("");
  const salud = useAsincrono(() => api.health(), []);

  const tema: Tema = preferenciaTema === "sistema" ? (sistemaOscuro ? "oscuro" : "claro") : preferenciaTema;

  // Con «Sistema», cambiar el tema del sistema operativo cambia la app sin recargar.
  useEffect(() => {
    const consulta = window.matchMedia(CONSULTA_OSCURO);
    const alCambiar = (e: MediaQueryListEvent) => setSistemaOscuro(e.matches);
    consulta.addEventListener("change", alCambiar);
    return () => consulta.removeEventListener("change", alCambiar);
  }, []);

  const setIdioma = useCallback((nuevo: Idioma) => {
    // Primero el módulo y después el estado: el render que dispara el estado ya
    // tiene que leer el idioma nuevo. Como `App` consume este contexto y ningún
    // componente está memorizado, todo el árbol se vuelve a pintar sin
    // remontarse: no se pierden los datos cargados ni el foco.
    fijarIdioma(nuevo);
    guardar(CLAVE_IDIOMA, nuevo);
    setIdiomaEstado(nuevo);
  }, []);

  const setPreferenciaTema = useCallback((preferencia: PreferenciaTema) => {
    guardar(CLAVE_TEMA, preferencia);
    setPreferenciaTemaEstado(preferencia);
  }, []);

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
    if (url.grupo) p.set("alert", url.grupo);
    // Solo lo que no es el default, para que la URL siga siendo legible.
    if (url.orden !== "impacto") p.set("sort", url.orden);
    if (url.direccion !== "desc") p.set("dir", url.direccion);
    if (url.offset > 0) p.set("offset", String(url.offset));
    const nueva = `${window.location.pathname}?${p.toString()}`;
    if (nueva !== `${window.location.pathname}${window.location.search}`) {
      // Un enlace viejo se reemplaza en vez de apilarse: «atrás» no tiene que
      // volver a una pantalla que ya no existe.
      // Lo mismo con `?lang=`: ya se leyó y se guardó, y quitarlo de la URL no es
      // un paso de navegación al que «atrás» tenga que volver.
      const anterior = new URLSearchParams(window.location.search);
      const vieja = anterior.get("screen");
      if ((vieja && REDIRECCIONES[vieja]) || anterior.has("lang")) {
        window.history.replaceState(null, "", nueva);
      } else window.history.pushState(null, "", nueva);
    }
  }, [url]);

  useEffect(() => {
    const alVolver = () => setUrl(leerUrl());
    window.addEventListener("popstate", alVolver);
    return () => window.removeEventListener("popstate", alVolver);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = tema === "oscuro" ? "dark" : "light";
  }, [tema]);

  const valor = useMemo<AppState>(
    () => ({
      ...url,
      tema,
      preferenciaTema,
      idioma,
      health: salud.datos,
      healthCargando: salud.cargando,
      healthError: salud.error,
      recargarHealth: salud.recargar,
      // Cambiar de pantalla vuelve a la primera página: el desplazamiento de la
      // tabla de reposición no significa nada en la lista de alertas.
      irA: (pantalla) =>
        setUrl((u) => (u.pantalla === pantalla ? u : { ...u, pantalla, offset: 0 })),
      setBasis: (basis) => setUrl((u) => ({ ...u, basis })),
      setSerie: (serie) => setUrl((u) => ({ ...u, serie })),
      setRatio: (ratio) => setUrl((u) => ({ ...u, ratio })),
      // Cambiar de filtro vuelve a la primera página: mantener el offset dejaría
      // la tabla vacía cuando el filtro nuevo tiene menos filas que el
      // desplazamiento anterior, y eso se lee como un error de la app.
      setTienda: (tienda) => setUrl((u) => ({ ...u, tienda, offset: 0 })),
      setClase: (clase) => setUrl((u) => ({ ...u, clase, offset: 0 })),
      setGrupo: (grupo) => setUrl((u) => ({ ...u, grupo, offset: 0 })),
      ordenarPor: (columna) =>
        setUrl((u) => ({
          ...u,
          orden: columna,
          // Repetir la misma columna invierte; cambiar de columna arranca
          // descendente, que es lo que se espera de una tabla de impacto.
          direccion: u.orden === columna && u.direccion === "desc" ? "asc" : "desc",
          offset: 0,
        })),
      setOffset: (offset) => setUrl((u) => ({ ...u, offset: Math.max(0, offset) })),
      setPreferenciaTema,
      setIdioma,
      anuncio,
      anunciar: setAnuncio,
    }),
    [
      url,
      tema,
      preferenciaTema,
      idioma,
      setPreferenciaTema,
      setIdioma,
      anuncio,
      salud.datos,
      salud.cargando,
      salud.error,
      salud.recargar,
    ],
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
