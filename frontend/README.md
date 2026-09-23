# Frontend de Blindside

React + Vite + TypeScript. La dirección visual sale de `../docs/design_handoff_dfcore/`;
los datos, de la API de `../api/`.

```bash
npm install
npm run dev      # http://127.0.0.1:5173 (la API tiene que estar arriba)
npm test         # vitest: lógica pura + render con fetch simulado
npm run build    # tsc -b && vite build
npm run gen:api  # regenera src/api/schema.d.ts desde openapi.json
```

## Cómo está armado

**Los tipos no se escriben a mano.** `src/api/schema.d.ts` se genera del OpenAPI que produce
FastAPI, así que un rename en `api/schemas.py` rompe la compilación en vez de romper la demo.
Para regenerar: `make api-schema` desde la raíz, que vuelca el esquema y corre el generador.

**Sin librería de gráficos.** El diseño fija `viewBox`, orden de capas y rellenos al píxel, y
una librería pelearía con las tres cosas. Los SVG están escritos a mano en `src/charts/` y la
geometría es funciones puras en `src/chart.ts`, que es lo que se testea.

**La llamada a la API es HTTP directo, no un proxy de Vite.** Un proxy volvería las llamadas
same-origin y esconderían un CORS mal configurado hasta el despliegue. La base se configura con
`VITE_API_BASE` (ver `.env.example`) y el origen del dev server tiene que estar en el allowlist
de la API.

**`src/domain.ts` es el único lugar con números que no vienen del backend.** Hoy: el impacto
esperado por fila, que se calcula tomando la banda conformal como distribución uniforme, y la
política de media móvil de 21 días. Los dos llevan sello `sim` en pantalla y el supuesto escrito
al lado del cálculo. Cuando el backend los sirva, se borra de un solo lugar.

## Estado

| Pantalla | Estado | Datos |
|---|---|---|
| Reposición (landing) | completa, siete columnas | reales, salvo la columna Impacto |
| Serie individual | completa, las diez capas del gráfico | reales |
| Vista general | completa, con la comprobación de la ventana comercial | reales |
| Comparativa | completa: por origen, por horizonte, por banda | reales |
| Explicabilidad | completa, cascada de contribuciones | reales (TreeSHAP de LightGBM) |
| Salud del modelo | completa | reales; la deriva declara que falta el endpoint |
| Selector (Ctrl+K) | completo | reales |
| Mapa de productos | completo | reales (PCA, 67 % de varianza en 2D) |

Estados cubiertos: muestra commiteada, sin artefacto entrenado, API caída, API anterior al
frontend, carga, serie sin quiebres, modo oscuro. Queda sin dibujar el de quiebre continuo
(rachas de hasta 95 días), que el handoff también dejó pendiente.

## Accesibilidad

El par observado / recuperado se distingue por **grosor** además de color, así que funciona en
escala de grises y con daltonismo. Es un requisito y no una mejora: ese par es la información
central del diseño. El toggle es un `role="group"` con dos botones y `aria-pressed`, se mueve con
← →, tiene atajo global `b`, y al cambiar una región `aria-live` anuncia el cambio de valor —
«la cantidad sugerida pasa de 1,12 a 1,35» — y no el nombre del modo. El contorno de foco nunca
se suprime. Con `prefers-reduced-motion` las transiciones pasan a 0 ms y las cifras se reemplazan
sin conteo.
