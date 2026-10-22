# Frontend de Blindside

React + Vite + TypeScript. La dirección visual sale de `../docs/design_handoff_dfcore/`; la
arquitectura de pantallas y la regla de dónde vive cada dato, de
[`../docs/rediseno_frontend.md`](../docs/rediseno_frontend.md); los datos, de la API de `../api/`.

```bash
npm install
npm run dev      # http://127.0.0.1:5173 (la API tiene que estar arriba)
npm test         # vitest: lógica pura + render con fetch simulado
npm run build    # tsc -b && vite build
npm run gen:api  # regenera src/api/schema.d.ts desde openapi.json
npx playwright test   # audit visual y de accesibilidad contra el build (necesita la API)
```

Desde la raíz, `make front` levanta el dev server con node directo: con `npm run dev` adentro de
`make`, Ctrl+C en Windows dejaba la terminal colgada.

## Pantallas

Siete, en tres grupos. Cada una responde una pregunta; la especificación completa está en la
sección 5 de la guía.

| Grupo | Pantalla | `?screen=` | Fuentes |
|---|---|---|---|
| Operación | Panel | `panel` | `/alerts`, `/dataset/summary`, `/backtest`, `/health` |
| Operación | Alertas | `alerts` | `/alerts` |
| Operación | Reposición | `reorder` | `/reorder/catalog`, `/series/history` |
| Operación | Serie | `series` | `/series/{id}/history`, `/forecast`, `/reorder`, `/explain`, `/alerts` |
| Análisis | Modelos | `models` | `/backtest`, `/backtest/breakdown`, `/health` |
| Análisis | Datos | `data` | `/dataset/summary`, `/censoring`, `/products/map` |
| Sistema | Pipeline | `pipeline` | `/pipeline` |

Los enlaces a pantallas que se fusionaron redirigen: `overview` y `map` van a Datos, `compare` y
`health` a Modelos, `explain` a Serie.

## Cómo está armado

**Los tipos no se escriben a mano.** `src/api/schema.d.ts` se genera del OpenAPI que produce
FastAPI, así que un rename en `api/schemas.py` rompe la compilación en vez de romper la demo.
Para regenerar: `make api-schema` desde la raíz.

**Sin librería de gráficos.** El diseño fija `viewBox`, orden de capas y rellenos al píxel. El
gráfico de la serie está en `src/charts/` con la geometría en `src/chart.ts`; los gráficos chicos
del Panel, Datos y Modelos en `src/components/graficos.tsx`. Cada gráfico lleva su tabla de datos
en un desplegable, que es la alternativa textual y la forma de leer el número exacto.

**La llamada a la API es HTTP directo, no un proxy de Vite.** Un proxy volvería las llamadas
same-origin y escondería un CORS mal configurado hasta el despliegue. La base se configura con
`VITE_API_BASE` (ver `.env.example`) y el origen del dev server tiene que estar en el allowlist
de la API.

**El cliente no calcula ninguna cifra de decisión.** La cantidad, la política, el ahorro, el orden
del catálogo y la merma vienen de la API. Lo que queda del lado del cliente es presentación pura y
tiene test: `src/domain.ts` (etiquetas de feature, señal reciente, CSV), `src/modelos.ts` (nombres
legibles, agrupación de modelos con el mismo pronóstico, mejora contra el naive y las conclusiones
derivadas de los números) y `src/alertas.ts` (la cifra que justifica cada motivo).

**Los controles viven donde actúan** (`src/components/controles.tsx`). El toggle de censura y el
ratio de costo están en Reposición y en Serie; los filtros de tienda y clase, en Reposición y en
Alertas. El atajo `B` solo actúa en las dos pantallas donde el toggle cambia una cifra.

## Estados

Cubiertos: muestra commiteada (sello que no se cierra y banda), modelo desfasado de los datos
(sello en la barra superior que lleva a Pipeline), sin artefacto entrenado, API caída, API anterior
al frontend, carga con huesos que reservan la geometría, serie sin quiebres y modo oscuro.

## Idioma y tema

Inglés por defecto, español como opción. Los dos se eligen en **Settings** (barra superior), junto
con el tema: Sistema, Claro u Oscuro. Se guardan en `localStorage`; `?lang=es` en el enlace abre
en español y lo deja guardado.

Los textos están en `src/i18n/`: `en.ts` es la forma de referencia y `es.ts` tiene que cumplir el
mismo tipo, así que una clave que falta en un idioma no compila. En el código se leen con `t()`.
La API devuelve claves y números (motivo de alerta, umbral, paso del pipeline) y la interfaz los
redacta en el idioma activo. Detalle en la sección 12 de la guía.

## Accesibilidad

El par observado / recuperado se distingue por **grosor** además de color, así que funciona en
escala de grises y con daltonismo. El toggle es un `role="group"` con dos botones y `aria-pressed`,
se mueve con ← →, y al cambiar una región `aria-live` anuncia la cifra que cambió. Las tablas
ordenables usan un botón dentro del `th` y `aria-sort`. El contorno de foco nunca se suprime. Con
`prefers-reduced-motion` las transiciones pasan a 0 ms y las cifras se reemplazan sin conteo.

`npx playwright test` corre axe (WCAG 2.1 A y AA) sobre las siete pantallas, en español y en
inglés, en claro y oscuro y a 1024, 1180, 1440 y 1920 px, y mide desborde horizontal. La última corrida dio cero violaciones y
cero desbordes. Es una verificación automática: no reemplaza una prueba con lectores de pantalla.
