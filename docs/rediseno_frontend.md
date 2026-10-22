# Rediseño del frontend · guía de desarrollo

**Estado:** implementado (2026-10-16). Las fases de la sección 9 están cerradas; la sección 11
registra lo que se verificó.
**Redactado:** 2026-10-16, sobre la auditoría de las 10 pantallas con el panel real (3.066 series).
**Reemplaza** la arquitectura de pantallas de `docs/frontend_design.md`: secciones 3.1, 3.2, 4 y 5.
El sistema visual de ese documento (secciones 6, 8, 9 y 10) sigue vigente y no se toca.

---

## 0. Cómo usar este documento

Es la guía para llevar el frontend de React a calidad de producto terminado. Tiene tres usos:

1. **Antes de tocar una pantalla:** leer su especificación en la sección 5. Dice qué pregunta
   responde, qué contenido lleva y en qué orden, de dónde sale cada número y **qué no va**.
2. **Antes de agregar un dato a cualquier pantalla:** buscarlo en la tabla de la sección 2.2. Si
   ya tiene un lugar, se enlaza a ese lugar en vez de repetirlo.
3. **Para saber qué falta:** la sección 9 es el checklist por fase.

---

## 1. Por qué se rediseña

La auditoría encontró tres problemas. Ninguno es estético.

**Siete errores** que muestran números falsos o rompen funciones (detalle y arreglo en la sección
7). El más grave: la lista «Qué pedir hoy» no estaba priorizada; ordenaba las 25 filas de la página
y la página 1 eran las series de la tienda 0 en orden alfabético.

**Repetición.** Seis datos aparecían en cuatro a seis lugares cada uno:

| Dato | Lugares en la versión anterior |
|---|---|
| MASE ± desvío | 5: franja de contexto, KPI del Panel, ranking del Panel, KPI de Reposición, Comparativa |
| Cobertura del intervalo | 3: franja, Panel, Salud |
| Entrenado hasta / frescura | 5: franja, Panel, Salud, Pipeline (dos veces) |
| Rango de fechas del panel | 5: franja, Panel, Datos, Salud, Vista general |
| Series, filas, días con quiebre, horas, uplift | 4: Panel, Vista general (dos veces), Datos |
| «Censura corregida / Es lo que ve el ERP» | 4: tres recuadros y el propio toggle |

**Arquitectura.** Diez pantallas para cinco preguntas, unos 165 px de cromo en tres bandas antes
del contenido, filtros visibles en diez pantallas que aplicaban en dos, y un toggle de base global
que no cambiaba nada en siete de ellas. Vista general no tenía ningún dato que no estuviera en
Datos.

---

## 2. Principios

Son reglas de revisión: un cambio que rompe una de estas no entra.

### 2.1 Las seis reglas

1. **Una pantalla, una pregunta.** Si una pantalla responde dos, son dos pantallas o una de las dos
   preguntas sobra.
2. **Un dato, un lugar.** Cada cifra tiene una pantalla dueña (tabla 2.2). Las demás enlazan.
3. **Los controles viven donde actúan.** El toggle de base, el ratio de costo y los filtros
   aparecen solo en las pantallas cuyas cifras cambian.
4. **Nunca una cifra sin su referencia.** Un MASE va con su desvío, un conteo va contra su total,
   un cambio va contra la política. Se mantiene de la versión anterior.
5. **Texto de producto en la vista, texto técnico plegado.** Nombres de endpoint, fórmulas,
   nombres de columna y de clase van en un desplegable «Cómo se calcula» al pie de la pantalla.
   La excepción es Pipeline, que es una pantalla de operador.
6. **Las conclusiones se derivan del dato.** Un texto que afirma algo sobre los números («el
   modelo no le gana al ingenuo en baja rotación») se calcula de los números o no se escribe. El
   error E3 fue exactamente un texto fijo que la tabla de al lado desmentía.

### 2.2 Dónde vive cada dato

| Dato | Pantalla dueña | Las demás |
|---|---|---|
| Series en alerta, por motivo | Alertas | Panel resume con conteos y enlaza |
| Cantidad sugerida, política, Δ, ahorro | Reposición (catálogo), Serie (una serie) | — |
| Pronóstico día por día e intervalo | Serie | — |
| Por qué este número (SHAP) | Serie | — |
| MASE, WAPE, peor origen, mejora contra el naive | Modelos | Panel muestra el del modelo servido y enlaza |
| Cobertura del intervalo | Modelos | Panel muestra la del modelo servido y enlaza |
| Censura del panel, uplift, perfiles por hora y por tienda | Datos | Panel muestra el uplift total y enlaza |
| Frescura de datos y modelo | Pipeline | Barra superior muestra un sello **solo si está desfasado** |
| Artefactos vigente, anterior y candidato | Pipeline | — |
| Registro de ingestas | Pipeline | Panel muestra la última y enlaza |

### 2.3 Convenciones de nombres y formatos

| Cosa | Se muestra como | No como |
|---|---|---|
| Serie | `T60 · P0600` en español y `S60 · P0600` en inglés, en todas partes, con la descripción de catálogo al lado | `60_600` |
| Mejora contra el naive estacional | «25,3 % menos error» / «25.3% less error» | «+25,3 %» o «−25,3 %» según la pantalla |
| Modelo servido | «LightGBM global · CQR» | `cqr_lgbm_quantile` |
| Sobrante contra demanda | «54 % de lo que se vende», y arriba de 100 % igual en porcentaje con el encabezado explícito | «Merma política 341 %» sin encabezado que lo explique |
| Estado de ingesta | «aplicado», «sin cambios», «rechazado», «en seco» | `sin_cambios` |
| Base de cálculo | «Venta observada» / «Demanda recuperada» | `observed` / `recovered` |

Nombres legibles de modelo (`frontend/src/modelos.ts`):

| Clave | Nombre | Nota |
|---|---|---|
| `cqr_lgbm_quantile` | LightGBM global · CQR | El servido |
| `conformal_lgbm_quantile_adaptive` | LightGBM global · conformal de residuos | |
| `lgbm_global` | LightGBM global · puntual | |
| `ridge` | Ridge | Regresión lineal regularizada |
| `croston_sba` | Croston SBA | Para demanda intermitente |
| `moving_average` | Media móvil 21 días | Es la política actual |
| `seasonal_moving_average` | Media móvil estacional | |
| `seasonal_naive` | Naive estacional | Referencia del MASE |
| `naive` | Naive | |

**Modelos con el mismo pronóstico puntual se agrupan.** Los tres LightGBM comparten la predicción
puntual (MASE 0,822 los tres): los envoltorios conformales solo cambian el intervalo. En las tablas
de error puntual van en una fila, «LightGBM global», con la nota de que las variantes difieren solo
en el intervalo. La agrupación se detecta por igualdad de las métricas puntuales, no por nombre.

---

## 3. Arquitectura de información

### 3.1 De diez pantallas a siete

| Grupo | Pantalla | `?screen=` | Pregunta | Absorbe |
|---|---|---|---|---|
| Operación | **Panel** | `panel` | ¿Qué pasa hoy y por dónde empiezo? | Franja de contexto |
| Operación | **Alertas** | `alerts` | ¿Qué series miro y por qué motivo? | — |
| Operación | **Reposición** | `reorder` | ¿Cuánto pido de cada serie, y dónde se gana más? | — |
| Operación | **Serie** | `series` | ¿Por qué le creo a esta cantidad? | Explicabilidad |
| Análisis | **Modelos** | `models` | ¿Qué tan bueno es el modelo y dónde falla? | Comparativa, cobertura de Salud |
| Análisis | **Datos** | `data` | ¿Cómo es el panel y cuánta demanda esconde? | Vista general, Mapa |
| Sistema | **Pipeline** | `pipeline` | ¿Qué datos y qué modelo se están sirviendo? | Artefactos de Salud, pipeline de Datos |

### 3.2 Enlaces viejos

Los enlaces a pantallas eliminadas **redirigen**, no fallan. Hay videos y guiones con esas URL.

| URL vieja | Va a |
|---|---|
| `?screen=overview` | `data` |
| `?screen=map` | `data` |
| `?screen=compare` | `models` |
| `?screen=health` | `models` |
| `?screen=explain` | `series` |

### 3.3 Navegación lateral

Tres grupos con rótulo: Operación, Análisis y Sistema. Las iniciales (`VG`, `SM`) se muestran
**solo** con la barra colapsada, donde son lo único que queda; expandida, el rótulo alcanza.

---

## 4. Cromo

**Una sola barra superior**, de izquierda a derecha:

1. **Buscar serie** (`Ctrl K`). Abre el selector y navega a Serie. No muestra «la serie actual»:
   eso lo dice el encabezado de la pantalla Serie.
2. **Sello de muestra**, si se sirve `data/sample/`. No se puede cerrar.
3. **Sello de modelo desfasado**, solo si los datos son más nuevos que el modelo. Enlaza a
   Pipeline.
4. **Settings / Preferencias**: idioma y tema, en un panel desplegable (sección 12). Reemplaza al
   botón «Modo oscuro».

**Se eliminan** la barra de filtros global y la franja de contexto. Su información tiene dueño
(tabla 2.2).

**El toggle de base** pasa al encabezado de Reposición y de Serie. El atajo `B` sigue siendo
global pero solo actúa en esas dos pantallas.

**Los filtros** (tienda y clase de rotación) pasan adentro de Reposición y Alertas, en la fila de
controles. La lista de tiendas sale de la API (`panel.store_ids`) y no de `0…n`.

La banda de muestra («Estos números no son los del panel completo») se mantiene: es el error que
arruina una defensa.

---

## 5. Pantallas

Formato de cada una: pregunta, contenido en orden de lectura, fuentes, qué no va, estados.

### 5.1 Panel

**Pregunta.** ¿Qué pasa hoy y por dónde empiezo?

**Contenido.**
1. Encabezado: «Panel», con series, tiendas, productos y rango de fechas en una línea.
2. Cuatro KPI: series que piden atención (contra el total), error del modelo servido con desvío y
   mejora contra el naive en palabras, cobertura real contra prometida, demanda escondida por
   quiebres.
3. **Para hoy:** las dos alertas urgentes, cada una con sus cinco primeras series y la cifra que
   las disparó, el remedio y «Ver las N».
4. **Para revisar:** tabla de motivos analíticos con conteo, peso en catálogo y en volumen, y
   remedio.
5. Demanda diaria del panel, observada contra recuperada.
6. Dos bloques al pie: **Modelos** (mejora de cada modelo contra el naive, agrupados y con nombre
   legible, enlaza a Modelos) y **Datos y modelo** (frescura humanizada, enlaza a Pipeline).

**Fuentes.** `/alerts`, `/dataset/summary`, `/backtest`, `/health`.

**No va.** Barras de MASE crudo desde cero (entre 0,82 y 0,91 se ven iguales), claves de estado,
«Cargado por la API».

### 5.2 Alertas

**Pregunta.** ¿Qué series miro y por qué motivo?

**Contenido.**
1. Encabezado con «N de 3.066 series piden atención».
2. Fila de controles: tienda y clase de rotación.
3. Filtro por motivo: «Todas» y los cinco motivos con su conteo.
4. Ficha del motivo elegido: qué significa, qué hacer, umbral y peso.
5. Tabla: serie, clase, motivos, demanda media, fracción estimada, racha vigente, MASE de la
   serie, sobrante con la política (% de lo que se vende), cuánto se evita.

**Fuentes.** `/alerts?group&store_id&rotation_band`.

**No va.** Puntaje compuesto ni «top 10» (D25).

### 5.3 Reposición

**Pregunta.** ¿Cuánto pido de cada serie, y dónde se gana más?

**Contenido.**
1. Encabezado: «Reposición · pedido para el {fecha}» y el toggle de base.
2. Fila de controles: ratio de costo Co/Cu con el cuantil que produce cada botón y su lectura,
   tienda, clase, exportar CSV.
3. Cuatro KPI **de catálogo** (con los filtros aplicados), todos relativos a la política actual
   y todos sensibles al toggle:
   - Ahorro esperado: reducción del costo esperado contra la política.
   - Orden contra la política: Δ % de la cantidad total.
   - Sobrante esperado contra la política (es la merma).
   - Faltante esperado contra la política (es la venta perdida).
4. Tabla **ordenada en el servidor sobre todo el catálogo**, por defecto por ahorro absoluto
   esperado:
   - Serie, clase, motivos (sellos, solo si hay).
   - Política, sugerido, Δ.
   - Ahorro: barra y porcentaje del ahorro total del catálogo filtrado.
   - Quiebre: minigráfico de 14 días y su conteo **de los mismos 14 días**.
   - Clic en la fila abre la Serie.
5. Paginador.
6. «Cómo se calcula», plegado: esperanzas bajo la distribución predictiva, cota inferior del
   faltante por la masa de cola, política de la misma base.

**Fuentes.** `/reorder/catalog` (nuevo, sección 6.1) y `/series/history` para los minigráficos de
la página.

**No va.**
- «Total a pedir»: suma cantidades de productos distintos y no significa nada.
- KPI y columna de «Señal»: la cubre Alertas como motivo.
- Panel lateral con política, Cu/Co y la nota de cola repetidos.
- Fila expandida: el pronóstico día por día vive en Serie.
- Recuadro «Censura corregida».

### 5.4 Serie

**Pregunta.** ¿Por qué le creo a esta cantidad?

**Contenido.**
1. Encabezado: `T60 · P0600`, descripción de catálogo, clase, sellos de motivo de alerta y el
   toggle de base.
2. Gráfico principal (sin cambios de fondo: es la mejor pieza visual) y, a la derecha, la
   decisión: cantidad sugerida con q*, política y Δ, faltante y sobrante esperados, ahorro.
3. **Próximos 7 días:** tabla con fecha, pronóstico, intervalo 90 % y cantidad sugerida por día.
4. **Por qué este número:** cascada SHAP compacta de la **misma cifra** que la cantidad sugerida
   (E2), con valor base y resto declarados.
5. **Censura de esta serie:** uplift, días con quiebre, horas por día, racha máxima, fracción
   estimada de los últimos 28 días.
6. «Cómo se calcula», plegado: uplift exactamente cero en días limpios, magnitudes adimensionales,
   origen de la política.

**Fuentes.** `/series/{id}/history`, `/forecast`, `/reorder`, `/explain`, `/alerts?series_id`.

**No va.** Recuadro «Censura corregida», nota al pie sobre `/reorder`.

### 5.5 Modelos

**Pregunta.** ¿Qué tan bueno es el modelo y dónde falla?

**Contenido.**
1. KPI del modelo servido: MASE con desvío, peor origen, mejora contra el naive estacional
   (contra el objetivo del 20 %), cobertura contra la nominal.
2. Tabla de modelos agrupados por pronóstico puntual, con nombre legible: MASE, desvío, peor
   origen, WAPE, mejora contra el naive y si cumple el objetivo.
3. **Intervalo:** CQR contra conformal de residuos, con cobertura y ancho medio. Es la evidencia
   de D21 y antes no aparecía en ninguna pantalla.
4. Cobertura por horizonte: puntos con su valor sobre un eje recortado y la nominal guionada.
5. MASE por origen: el modelo servido más dos referencias (naive estacional y media móvil de 21
   días). Los demás modelos, en un desplegable.
6. Por horizonte y por banda de rotación: el servido y las dos referencias, con la conclusión
   **derivada** de los números.

**Fuentes.** `/backtest`, `/backtest/breakdown`, `/health` (cobertura por horizonte del servido).

**No va.** Tres filas idénticas, tablas de 9 × 7, artefactos (van a Pipeline), «Deriva de
features» como sección vacía (va a la lista de limitaciones del README).

### 5.6 Datos

**Pregunta.** ¿Cómo es el panel y cuánta demanda esconde?

**Contenido.**
1. KPI del panel: series, filas, días-serie con quiebre, demanda recuperada.
2. En el tiempo: demanda observada contra recuperada.
3. Recuperación de la demanda censurada: tabla compacta de todos los días, días limpios y días con
   quiebre.
4. Por día de la semana y por hora.
5. Por tienda y por categoría.
6. Por rotación y distribución del quiebre por serie.
7. **Catálogo por comportamiento:** el mapa PCA como bloque, con el producto elegido y enlace a sus
   series.
8. «Cómo se verifica», plegado: la comprobación de la ventana comercial.

**Fuentes.** `/dataset/summary`, `/censoring`, `/products/map`.

**No va.** Afirmaciones sobre el desempeño del modelo (son de Modelos).

### 5.7 Pipeline

**Pregunta.** ¿Qué datos y qué modelo se están sirviendo, y cómo se actualizan?

**Contenido.**
1. Estado: capa servida, archivos, frescura, recarga automática.
2. Artefactos: vigente, anterior y candidato por base.
3. Últimas ingestas.
4. Cómo se corre: los comandos.

**Fuentes.** `/pipeline`.

**No va.** Botones que disparen nada: la API no tiene autenticación.

---

## 6. Contrato de API

### 6.1 `GET /reorder/catalog` (nuevo)

Orden sugerida para **todo** el catálogo, ordenada y paginada en el servidor. Resuelve E7.

Parámetros: `recover_censoring`, `co` (`cu` queda en 1), `store_id`, `rotation_band`,
`sort` (`impacto`, `delta`, `sugerido`, `politica`, `serie`), `dir`, `limit`, `offset`.

Respuesta: la fecha del pedido, base, modelo, q*, ventana de la política, masa de cola, totales
del catálogo filtrado (cantidad, política, costo esperado del modelo y de la política, sobrante y
faltante de cada uno, series con cambio mayor al 20 %), el total de filas y la página. Cada línea
trae serie, descripción, clase, cantidades, Δ, esperanzas, ahorro, participación en el ahorro
total y los motivos de alerta de la serie.

Cálculo: el mismo `_reorder_frame` de `/reorder`, sobre el catálogo entero y el primer día del
horizonte. Cuesta unos 2 s por combinación de base y ratio, y se cachea hasta la próxima
recarga. Las alertas reusan esa caché para la combinación por defecto.

### 6.2 Cambios en endpoints existentes

| Endpoint | Cambio | Motivo |
|---|---|---|
| `/health` | `panel.store_ids` | E1 |
| `/alerts` | parámetros `rotation_band` y `series_id` | E6 y motivos en Serie |
| `/explain` | `prediction` pasa a ser la cifra explicada (cuantil crítico); se agregan `rest` y `point_forecast` | E2 |

---

## 7. Errores

| # | Error | Causa | Arreglo | Test |
|---|---|---|---|---|
| E1 | El filtro de tienda ofrecía `0…37`; 37 de 38 opciones daban lista vacía | La lista se armaba con `n_stores` en vez de los ids | `panel.store_ids` desde la API | API: los ids coinciden con el panel. Front: las opciones son las de la API |
| E2 | «Cantidad explicada» 5,14 contra «Cantidad sugerida» 5,53 para la misma serie y día | `/explain` devolvía la mediana como `prediction` mientras las contribuciones eran del booster de q*; el «resto» se calculaba en el cliente para cerrar contra la mediana | `prediction` = base + todas las contribuciones, que es la salida del cuantil crítico; `rest` lo calcula el servidor | La predicción explicada coincide con la cantidad de `/reorder` |
| E3 | «El modelo no le gana al ingenuo en baja rotación», con la tabla mostrando 0,822 contra 1,121 | Texto fijo | La conclusión se deriva de los números de la banda | Front: el texto cambia según los datos |
| E4 | −25,3 % en el Panel y +25,3 % en Comparativa | Dos convenciones de signo | «X % menos error» en todas partes | Front |
| E5 | «Quiebre 14 d» mostraba el conteo de 28 días | Se usaba `censored_days_last_28` | Conteo de los mismos 14 días del minigráfico | Front |
| E6 | El filtro de clase no se aplicaba en Alertas | No se enviaba | `rotation_band` en `/alerts` | API y front |
| E7 | «Qué pedir hoy» ordenaba solo la página | El orden se hacía en el cliente sobre 25 filas | `/reorder/catalog` | API: la primera fila es la de mayor ahorro del catálogo |

---

## 8. Componentes

| Componente | Archivo | Uso |
|---|---|---|
| `ToggleCensura` | `components/piezas.tsx` | Encabezado de Reposición y Serie |
| `RatioCosto` | `components/controles.tsx` | Reposición y Serie |
| `FiltrosCatalogo` | `components/controles.tsx` | Reposición y Alertas |
| `ComoSeCalcula` | `components/controles.tsx` | Pie de cada pantalla |
| `SelloMotivo` | `components/alertas.tsx` | Alertas, Reposición, Serie |
| `SerieTemporal`, `Columnas`, `BarrasHorizontales` | `components/graficos.tsx` | Panel, Datos, Modelos |
| `nombreModelo`, `agruparModelos` | `modelos.ts` | Panel y Modelos |

---

## 9. Fases

### Fase 0 · Documento
- [x] Esta guía.
- [x] Nota en `docs/frontend_design.md` sobre qué secciones reemplaza.

### Fase 1 · API
- [x] `/reorder/catalog` con caché por base y ratio (E7).
- [x] `panel.store_ids` en `/health` (E1).
- [x] `/alerts` con `rotation_band` y `series_id` (E6).
- [x] `/explain` con la cifra explicada correcta y `rest` (E2).
- [x] Tests de API de cada cambio; regenerar `openapi.json` y `schema.d.ts`.

### Fase 2 · Cromo y navegación
- [x] Siete pantallas, tres grupos, redirección de URL viejas.
- [x] Una sola barra superior; sello de desfase; sin franja de contexto ni filtros globales.
- [x] Toggle y atajo `B` solo donde actúan.
- [x] Selector con `T60 · P0600`, sin rótulo repetido por fila.

### Fase 3 · Reposición
- [x] Controles en la pantalla, KPI de catálogo, tabla del servidor, minigráfico de 14 días (E5).

### Fase 4 · Serie
- [x] Motivos, decisión, próximos 7 días, por qué este número, censura de la serie.

### Fase 5 · Modelos
- [x] Nombres legibles, agrupación, intervalo CQR contra conformal, cobertura por horizonte,
      conclusiones derivadas (E3, E4).

### Fase 6 · Datos y Pipeline
- [x] Datos con la tabla de recuperación, el mapa como bloque y la comprobación plegada.
- [x] Pipeline como pantalla propia.
- [x] Panel y Alertas ajustados (ranking por mejora, estados humanizados, filtros en pantalla).

### Fase 7 · Cierre
- [x] Vitest, ruff, pytest, build.
- [x] Specs de Playwright con las rutas nuevas.
- [x] README, `frontend/README.md`, `docs/demo_guion.md`.

---

## 10. Criterios de terminado

- Ningún dato de la tabla 2.2 aparece fuera de su dueño salvo como resumen que enlaza.
- Ninguna pantalla muestra nombres de endpoint, de columna o de clase fuera de «Cómo se calcula» y
  de Pipeline.
- La primera fila de Reposición es la de mayor ahorro esperado de todo el catálogo filtrado.
- La cantidad explicada en Serie coincide con la cantidad sugerida.
- Todas las opciones del filtro de tienda devuelven al menos una serie.
- Los enlaces viejos redirigen.
- Tests verdes en Python y en el frontend; build limpio.

---

## 11. Verificación

Corrida del 2026-10-16 sobre el panel real (3.066 series):

| Qué | Resultado |
|---|---|
| Tests de Python (`pytest -m "not slow"`), con los de `/reorder/catalog`, `store_ids`, filtros de alertas y `/explain` | verdes |
| Tests del frontend (Vitest): lógica pura y render de las siete pantallas contra un backend simulado, en los dos idiomas | 70 verdes |
| `tsc -b`, `vite build`, `ruff check` | limpios |
| Audit de Playwright con axe (WCAG 2.1 A y AA), siete pantallas en español y en inglés, claro y oscuro, 1024 a 1920 px, y el panel de preferencias abierto | 14 verdes, 0 violaciones, 0 desbordes, 0 errores de consola |
| E2 con el artefacto real, serie `60_600`, 3 jul | cifra explicada 5,5295 = cantidad de `/reorder` 5,5295 |
| E7 con el panel real | primera fila `234_802`, la de mayor ahorro del catálogo; antes era `0_104` por orden alfabético |
| E1 con el panel real | `store_ids` = `[0, 41, 48, 60, …]`, 38 tiendas, todas con series |
| Costo de `/reorder/catalog` | ~4 s la primera vez por base y ratio, ~0,2 s después (caché hasta la próxima recarga) |

**Lo que no cubre:** axe es una verificación automática y no reemplaza una prueba con lectores de
pantalla ni una revisión de accesibilidad experta.

**Pendiente fuera de este documento:** la imagen de Docker sirve el código con el que se
construyó; después de este cambio hay que reconstruirla (`docker compose up -d --build`) o el
frontend muestra «La API es anterior a esta interfaz».

---

## 12. Idioma y tema

**Inglés por defecto, español como opción.** Se elige en **Settings** (en español,
**Preferencias**), un panel que se despliega desde la barra superior con dos grupos de botones
`aria-pressed`: idioma (English / Español) y tema (Sistema / Claro / Oscuro). No es modal: se ve
el resultado detrás mientras se elige. Escape y un clic afuera lo cierran y devuelven el foco al
botón. Dos opciones no justifican una pantalla.

**Dónde se guarda.** En `localStorage` (`blindside:idioma`, `blindside:tema`), no en la URL: son
preferencias de quien mira, no parte de lo que se muestra. `?lang=es` se acepta al cargar, se
guarda y se saca de la URL; sirve para abrir la demo en español con un enlace. Sin nada guardado
el idioma es inglés: el del navegador no se adivina, para que la demo se vea igual en cualquier
máquina. El tema «Sistema» sigue a `prefers-color-scheme`, también si cambia con la app abierta.

**Cómo está armado** (`frontend/src/i18n/`):

| Archivo | Qué es |
|---|---|
| `en.ts` | Los textos en inglés y la **forma de referencia**: `type Textos = typeof en` |
| `es.ts` | Los textos en español, tipados como `Textos`: una clave que falta no compila |
| `index.ts` | `t()`, `fijarIdioma()`, `idiomaActual()`, `IDIOMA_POR_DEFECTO` |

Sin librería: dos idiomas fijos no la justifican, y el repo no suma dependencias para lo que se
resuelve en un archivo tipado. El idioma activo vive en el módulo y no solo en un contexto de
React porque lo leen funciones puras (`format.ts`, `modelos.ts`, `domain.ts`, `alertas.ts`). El
proveedor de estado lo fija antes del primer render y lo expone en el contexto; como `App` lo
consume y ningún componente está memorizado, un cambio de idioma vuelve a pintar el árbol **sin
remontarlo**: no se pierden los datos cargados ni el foco. Si algún día se memoriza un componente
con texto, el idioma tiene que ir en sus dependencias.

**La API devuelve códigos y la interfaz redacta.** Los textos que antes llegaban armados en
español se traducen por clave:

| Qué | Clave | De dónde sale el texto |
|---|---|---|
| Rótulo, significado y acción de un motivo de alerta | `AlertGroup.key` | `t().motivos[key]` |
| Umbral de un motivo | `AlertGroup.threshold_value` (nuevo) | `t().umbral[key](valor)` |
| Por qué un motivo no se calculó | `unavailable[].key` | `t().noCalculado[key]` |
| Paso del pipeline | `PipelineStep.key` (nuevo) | `t().pipeline.pasos[key]`; el comando sale de la API |
| Detalle de una ingesta | conteos y `status` | `t().ingesta.resumen(...)`; el mensaje crudo queda en el `title` |
| Descripción de catálogo de una serie | `label` (`tienda 12 · producto 403 · …`) | se desarma y se vuelve a redactar |

Si la clave es desconocida — una API más nueva con un motivo que la interfaz no conoce — se usa el
texto de la API. Quedan en español, a propósito, los mensajes de error del backend: son
diagnóstico para quien opera la API. Los valores de filtro (`alta`, `media`, `baja`) siguen siendo
los de la API y solo se traduce lo que se lee. Los encabezados del CSV exportado no cambian con el
idioma: son identificadores, y una planilla que los lee no tiene que romperse según quién exportó.

**Formatos.** Inglés usa `en-US` (`0.96`, `3,066`, `25.3%`, `Jul 3`); español usa `es-PY`
(`0,96`, `3.066`, `25,3 %`, `3 jul`). La búsqueda de series acepta los dos idiomas: «store 12» y
«tienda 12» encuentran lo mismo.

**Tests.** Los de render y de lógica existentes fijan español, que es como se escribieron; un
bloque aparte verifica el inglés por defecto, el cambio de idioma sin cerrar el panel, `?lang=es`,
la persistencia y el tema. El audit de Playwright corre las siete pantallas en los dos idiomas.
