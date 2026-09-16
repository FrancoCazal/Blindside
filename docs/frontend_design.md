# Diseño del frontend · demand-forecasting-core

**Estado:** especificación para diseñar. No hay código de frontend todavía.
**Frente H** del plan (sección 13). Depende del contrato de API, que ya está congelado.
**Redactado:** 2026-09-15

---

## 0. Cómo usar este documento

Esto define **estructura, comportamiento, jerarquía y restricciones**. No define paleta,
tipografía ni espaciado: eso sale del draft visual. El plan es explícito en que el frontend se
hace «con criterio visual, no con componentes por defecto», así que la estética es decisión de
diseño y este doc solo pone los guardarrieles que salen de los datos y de la defensa.

Lo que sí conviene leer antes de dibujar: la sección 2 (el constraint de los 2 minutos), la 6
(restricciones duras de los datos, con números medidos) y la 7 (qué endpoints existen de verdad).
Esas tres son las que invalidan diseños que parecen razonables.

---

## 1. Para qué existe esta superficie

El proyecto ya tiene un dashboard Streamlit con siete pantallas funcionando. El plan define los
roles sin ambigüedad:

> «Se entregan dos superficies. La de Streamlit satisface el requisito literal del programa y es
> la red de seguridad. **La de React es la que se muestra en la defensa.**»

O sea que el frontend no existe para agregar funcionalidad. Existe para dos cosas:

1. **Ser el artefacto que el panel recuerda.** Es el que va al case study y a francocazal.com.
2. **Contar la tesis del proyecto sin que haya que explicarla.** La tesis es que la demanda que
   ve el ERP está censurada por los quiebres de stock, y que corregir eso cambia la decisión de
   compra. Si el frontend logra que eso se *vea*, ahorra tres minutos de discurso.

Si el frontend termina siendo Streamlit con mejor CSS, no vale el esfuerzo. La diferencia tiene
que estar en la jerarquía y en la interacción, no en el pulido.

### Las dos audiencias, que quieren cosas opuestas

| Audiencia | Qué necesita | Qué le molesta |
|---|---|---|
| **Panel evaluador** | Evidencia de rigor: antifugas, dispersión entre orígenes, calibración del intervalo, comparación contra baselines | Un dashboard bonito sin números defendibles |
| **Operador de compras** | Una cantidad y una razón para confiar en ella | Métricas que no sabe interpretar ocupando la pantalla |

Un layout que sirva a los dos por igual termina sirviendo a ninguno. La resolución propuesta está
en 3.3.

---

## 2. El constraint que manda sobre todo lo demás

**La demo son 2 minutos**, y llega en el puesto 6 de 7 de la presentación, después de que ya se
explicaron validación, antifugas y resultados.

Siete pantallas en 2 minutos son 17 segundos cada una. Es imposible, y si se intenta el panel no
retiene nada. Eso reencuadra el problema: no se está diseñando *un dashboard de siete pantallas*,
se está diseñando **dos pantallas que cargan la demo y cinco que existen como profundidad para
responder preguntas**.

La jerarquía tiene que estar **en el diseño**, no en un menú lateral donde las siete pesan igual.
Si pesan igual, Streamlit ya hace eso.

### Presupuesto de la demo, minuto a minuto

| Tiempo | Pantalla | Qué se muestra | Qué queda demostrado |
|---|---|---|---|
| 0:00–0:20 | Reposición | La landing es una lista de cantidades a pedir | El sistema termina en una decisión, no en un gráfico |
| 0:20–1:20 | Serie individual | Observado vs recuperado, tramos de quiebre sombreados, banda conformal | El efecto spiral-down, visto en vez de explicado |
| 1:20–1:50 | Toggle global | Se acciona una vez y cambia todo el sistema | Que la corrección de censura *mueve la decisión* |
| 1:50–2:00 | Cierre | Vuelta a Reposición con el toggle en «recuperada» | La cantidad que se pide es distinta, y por qué |

Todo lo demás se navega **solo si el panel pregunta**. Está diseñado para eso: profundidad
disponible, no profundidad exhibida.

---

## 3. Decisiones estructurales

Estas cuatro son las que definen si el frontend aporta algo. Cada una es una decisión, no una
recomendación: si se cambia alguna, cambia el diseño entero.

### 3.1 Toggle global de censura, persistente en el header

**La decisión más importante del diseño.**

Todo número de este sistema existe en dos versiones: lo que ve el ERP (**venta observada**) y lo
que realmente pasó (**demanda recuperada**). No es un detalle de implementación, es la tesis.

Propuesta: un control **siempre visible en el header**, no enterrado en un panel de filtros.

```
┌──────────────────────────────────────────────────────────────────────┐
│  ◈ dfcore        Viendo:  [ Venta observada │ Demanda recuperada ]   │
└──────────────────────────────────────────────────────────────────────┘
```

Al accionarlo cambia **todo a la vez**: las series, las cantidades sugeridas, las métricas de
error, el costo esperado. Con animación de transición, porque el movimiento *es* el mensaje: se
tiene que percibir que los números se corren hacia arriba.

Por qué es tan valioso:

- Es la respuesta visual a una de las preguntas esperadas de la defensa: «¿los quiebres de stock
  no te sesgan la demanda?».
- Convierte una explicación de tres minutos en una interacción de diez segundos.
- Ningún dashboard genérico de forecasting tiene esto, porque ningún dataset genérico trae la
  censura anotada. Es diferencial que sale de los datos, no de la estética.

**Requisitos de comportamiento:**

- El estado vive en la URL (`?basis=observed|recovered`), para poder abrir la app ya en el estado
  que se quiere mostrar y para que el video de respaldo sea reproducible.
- Persiste al navegar entre pantallas. Cambiar de pantalla no lo resetea.
- Tiene una etiqueta de consecuencia, no solo de estado. Algo del tipo *«Venta observada — es lo
  que ve el ERP. Subestima la demanda en los días con quiebre»*.
- En «observada» conviene un tratamiento visual de advertencia sutil, para que se lea como el
  modo *incorrecto pero real*, no como una opción neutral equivalente.

### 3.2 Decision-first: la landing es la lista de reposición

El plan dice que el sistema «no termina en una predicción, termina en una cantidad a pedir». Si
la pantalla de entrada es un overview de KPIs con tarjetas arriba y gráficos abajo, **contradice
eso**: pone la predicción en el centro y esconde la decisión.

La landing es la **lista de reposición**: lo que abriría un responsable de compras un lunes a la
mañana. Una tabla ordenada por impacto con la cantidad ya calculada.

Los KPIs de exactitud van arriba pero **chicos**, como contexto de confianza, no como
protagonistas. Son el equivalente visual de una barra de estado, no de un titular.

### 3.3 Evidencia embebida en los números que importan

Resolución de la tensión entre las dos audiencias.

En vez de separar «modo operación» y «modo evidencia» (que duplica el trabajo de diseño), cada
número operativo importante tiene un **affordance para abrir su respaldo**. Un ícono discreto que
despliega un panel lateral con «cómo se validó esto».

Se aplica a **tres números y nada más**, para que el patrón no se diluya:

| Número | Qué muestra su respaldo |
|---|---|
| La cantidad sugerida | La fracción crítica `q* = Cu/(Cu+Co)`, y que la predicción del modelo cuantílico **es** la orden |
| El MASE del modelo | Los 8 orígenes con su dispersión, y la comparación contra los cinco baselines |
| La banda del intervalo | Cobertura nominal contra empírica, y el ancho medio |

Las pantallas de profundidad que no encajan en este patrón (comparativa de modelos, SHAP, drift)
viven al final de la navegación, aceptadas explícitamente como «no son para operar».

### 3.4 La pantalla de serie individual es el hero visual

Si el panel se acuerda de **una sola imagen**, tiene que ser esta: la venta observada contra la
demanda recuperada, con los tramos de quiebre sombreados y la banda conformal sobre el pronóstico.
Resume el proyecto entero en un gráfico.

Es donde va el mayor esfuerzo de diseño, y probablemente el único gráfico del sistema que
justifica ser custom en vez de un componente de librería.

---

## 4. Inventario de pantallas y jerarquía

| Nivel | Pantalla | Rol | Demo | Datos disponibles hoy |
|---|---|---|---|---|
| **Hero** | **Reposición** | La decisión. Landing | 40 s | Parcial (ver 7.2) |
| **Hero** | **Serie individual** | La tesis, vista | 60 s | **Falta endpoint** (7.1) |
| Soporte | Vista general | Contexto de confianza y estado | 20 s | Sí |
| Profundidad | Comparativa de modelos | Rigor: dispersión entre orígenes | Si preguntan | Parcial (7.3) |
| Profundidad | Explicabilidad (SHAP) | Confianza en una predicción concreta | Si preguntan | **No existe** |
| Profundidad | Salud del modelo (drift) | Responde «cuánto dura el modelo» | Si preguntan | **No existe** |
| Descartable | Mapa de productos (UMAP) | Es lindo y aporta poco a la defensa | No | **No existe** |

**Sobre el mapa UMAP:** está en el plan pero es el candidato natural a recorte. Un scatter de
proyección coloreado por cluster es visualmente atractivo y no responde ninguna pregunta que el
panel vaya a hacer. Si el tiempo aprieta, sale primero. Vale decidirlo ahora en vez de descubrirlo
el último día.

### Navegación

Con dos pantallas hero y cuatro de profundidad, un sidebar de siete ítems iguales es la estructura
equivocada. Propuesta:

- **Nivel primario:** Reposición y Series. Dos ítems, visualmente dominantes.
- **Nivel secundario:** el resto, agrupado bajo algo tipo «Evidencia» o «Diagnóstico», visualmente
  subordinado.
- El toggle de censura y el selector de tienda/producto **no son navegación**, son estado global.
  No van en el mismo contenedor visual que la navegación.

---

## 5. Especificación por pantalla

### 5.1 Reposición · landing

**Pregunta que responde:** ¿qué pido hoy, y cuánto?

**Contenido:**

- Franja superior de contexto, tipografía chica: MASE del modelo activo con su dispersión, hasta
  cuándo entrenó, cobertura empírica del intervalo, cantidad de series en alerta.
- **Tabla de cantidades sugeridas**, ordenada por impacto descendente. Es el 70 % de la pantalla.
- Controles de economía: `Cu` y `Co` editables, con `q*` recalculándose **en vivo**.
- Filtros: tienda, banda de rotación, y un filtro por «tiene quiebre reciente».

**La interacción que vale la pena:** mover `Co` (el costo de quedarse largo) y ver la tabla entera
recalcularse. Es la forma más directa de mostrar que la decisión sale de la economía y no de un
promedio. Con `Cu = 1` fijo, mover `Co` de 0,15 a 1,5 mueve `q*` de 0,87 a 0,40, y las cantidades
se mueven con él.

Vale mostrar la interpretación al lado del número, no solo el número:

| `Co/Cu` | `q*` | Lectura |
|---|---|---|
| 0,3 | 0,769 | Producto seco: el sobrante es capital inmovilizado |
| **0,6** | **0,625** | **Perecedero: el sobrante es pérdida total al vencimiento** |
| 1,0 | 0,500 | Los dos errores cuestan igual: el óptimo es la mediana |
| 1,5 | 0,400 | El sobrante duele más que el quiebre |

**Columnas de la tabla:** tienda, producto, fecha, **cantidad sugerida**, cantidad que pediría la
política actual, delta entre las dos, y una marca de si la serie viene quebrando.

La columna de delta contra la política actual es la que hace la tabla persuasiva: no muestra un
número, muestra una diferencia con una razón.

### 5.2 Serie individual · el hero

**Pregunta que responde:** ¿por qué le creo a esta cantidad?

**El gráfico principal**, en capas de atrás hacia adelante:

1. **Tramos de quiebre**, sombreados verticalmente. El fondo del relato.
2. **Venta observada**, línea. Lo que ve el ERP.
3. **Demanda recuperada**, línea diferenciada. Lo que realmente pasó. Solo se separa de la
   anterior dentro de los tramos sombreados — eso es información, no un artefacto.
4. **Pronóstico**, continuando la serie, visualmente distinto del histórico.
5. **Banda conformal** alrededor del pronóstico, ensanchándose con el horizonte.
6. **Cantidad sugerida**, marcada sobre el pronóstico. Es el punto donde el gráfico se vuelve una
   decisión.

**Debajo:** un panel chico con las horas de quiebre por día. Es lo que hace concreta la anotación
horaria del dataset, que es lo que vuelve *medible* la corrección en vez de solo afirmable.

**Restricciones de este gráfico** — medidas sobre el panel real, ver sección 6:

- Las rachas de quiebre tienen **mediana de 2 días** y el **44 % son de un solo día**. Sobre 97
  días en ~800 px, un día son ~8 px. Un sombreado de 8 px con borde se ve como ruido. Hay que
  decidir el tratamiento: sin borde, o un mínimo de ancho, o marcadores en vez de bandas para las
  rachas de un día.
- Hay rachas de **hasta 95 días**: series que estuvieron en quiebre casi todo el período. El
  diseño tiene que sobrevivir a un gráfico con el fondo entero sombreado sin volverse ilegible.
- El eje Y tiene un problema de rango: la mediana de la demanda es **0,80** y el máximo **53,0**.
  Un eje lineal global aplasta el 90 % de las series. Hay que autoescalar por serie, y aun así una
  serie con un pico promocional va a tener el resto de la línea pegado al piso.

### 5.3 Vista general · contexto

**Pregunta que responde:** ¿en qué estado está el sistema y le puedo creer?

- Estado del artefacto: qué modelo está cargado, hasta cuándo entrenó, cuántas series conoce.
- Resumen de censura del panel: días con quiebre, horas de quiebre promedio, uplift de la
  recuperación en las tres agrupaciones (todos / limpios / censurados).
- El cumplimiento del objetivo: MASE del modelo contra el naive estacional, con el **peor origen**
  al lado. El peor origen es la columna que importa para operar.

**Un dato que conviene mostrar y que casi nadie mostraría:** la comprobación de que la ventana
comercial asumida es la correcta. 43,9 % de días con quiebre × 7,0 horas / 16 franjas = 19,2 % de
horas comerciales en quiebre, que reproduce el «≈20 %» declarado en la ficha del dataset. Es una
verificación cruzada contra un tercero y comunica rigor sin decir «somos rigurosos».

### 5.4 Comparativa de modelos · profundidad

**Pregunta que responde:** ¿comparado contra qué?

- Tabla de los modelos con MASE medio, desvío entre orígenes, peor origen, mejora porcentual.
- **Una línea por modelo a través de los 8 orígenes.** Es el gráfico que hace visible la
  dispersión y el que respalda «no reporto un número único». Requiere un endpoint que hoy no
  existe (ver 7.3).
- Degradación por horizonte, con una nota: **no es monótona y eso está bien**. Con estacionalidad
  semanal el error en h=7 puede bajar legítimamente, porque el objetivo cae el mismo día de la
  semana que el origen. Anticiparlo en la interfaz evita una pregunta incómoda.
- Desagregación por banda de rotación, con la nota de que el modelo complejo puede no ganar en
  baja rotación y que eso es un resultado publicado, no un fracaso.

### 5.5 Explicabilidad, salud del modelo, mapa de productos

No hay datos detrás de ninguna de las tres. Ver sección 7.4. Dos caminos válidos, y conviene
elegir explícitamente antes de diseñar:

- **Diseñarlas igual**, y que el diseño defina qué endpoints hay que construir.
- **No diseñarlas**, y declararlas como roadmap en el case study.

Recomendación: diseñar solo la de explicabilidad, porque un waterfall de SHAP sobre una predicción
concreta es la pieza que convierte «el modelo dice 1,35» en «el modelo dice 1,35 porque el martes
pasado vendió 1,2 y hay promoción». Las otras dos como roadmap.

---

## 6. Restricciones duras de los datos

**Medidas sobre el panel real de 3066 series y 297.402 filas.** No son preferencias: un diseño que
las ignore no va a funcionar con estos datos.

### 6.1 Las magnitudes son adimensionales

`sale_amount` viene multiplicado por un coeficiente no divulgado. **No hay guaraníes, no hay
dólares, no hay unidades físicas.** El diseño no puede usar símbolos de moneda ni sugerir que los
números son pesos.

Los ahorros y los impactos van en **porcentaje**. La única excepción sería la vista del caso
Focal Point, que todavía no existe.

Esto también aplica a los ejes: nada de `$` ni `kg`.

### 6.2 Distribución con cola derecha larga

| Serie | Media | p50 | p90 | p99 | Máximo |
|---|---|---|---|---|---|
| Venta observada | 1,009 | 0,700 | 2,100 | 5,600 | 23,8 |
| Demanda recuperada | 1,222 | 0,804 | 2,589 | 6,750 | 53,0 |

**Del p50 al máximo hay un factor de 66.** Consecuencias:

- Un eje Y lineal compartido entre series es inutilizable. Autoescalado por serie, obligatorio.
- En la tabla de reposición, ordenar por cantidad descendente pone arriba los productos de alta
  rotación siempre. Vale considerar un orden por **impacto relativo** además del absoluto, o el
  operador ve las mismas veinte líneas todos los días.
- Los números necesitan formato consistente con **decimales**: la mediana es 0,80, así que
  redondear a entero destruye la información. Dos decimales, o uno con separador de miles cuando
  aplica.

### 6.3 La cola de baja rotación es más chica de lo que el plan asume

El plan repite que «la cola de baja rotación es la mayoría del catálogo en perecederos». **En este
subconjunto no es así:**

- Series con más del 30 % de días en cero: **0,8 %**
- Series con demanda media menor a 0,5: **2,6 %**
- Percentil 10 de la media por serie: 0,546

Es consecuencia del submuestreo: se eligieron tiendas completas de las ciudades 0-2, y salieron
mayoritariamente de alta rotación. **Implicación de diseño:** una pantalla o un filtro dedicado a
la cola de baja rotación tendría muy pocos datos que mostrar. El filtro por banda de rotación
sigue teniendo sentido, pero no conviene diseñar nada que asuma que la cola es lo dominante.

También es una discrepancia que conviene corregir en el plan antes de la defensa.

### 6.4 Escala de la interfaz

| Dimensión | Valor |
|---|---|
| Series (tienda × producto) | 3.066 |
| Tiendas | 38 |
| Productos únicos | 309 |
| Días de historia | 97 |
| **Filas de la tabla de reposición con horizonte 7** | **21.462** |

21.462 filas **necesitan virtualización**. Un `<table>` con todas las filas en el DOM no es una
opción. Y necesita agregación por defecto: probablemente mostrar una fila por serie con el total
del horizonte, y expandir a los 7 días al hacer clic.

Los selectores de producto (309 opciones) y de serie (3.066) necesitan búsqueda, no un `<select>`.

### 6.5 Rachas de quiebre

| Métrica | Valor |
|---|---|
| Rachas de días censurados consecutivos | 53.072 |
| Mediana de la racha | 2 días |
| p90 | 5 días |
| Máximo | **95 días** |
| Rachas de un solo día | **44 %** |

Ya discutido en 5.2. El caso de 95 días es el que rompe diseños: una serie que estuvo en quiebre
prácticamente todo el período.

---

## 7. Contrato de API: qué existe y qué falta

Esto es lo más útil antes de dibujar. Hay pantallas que **no tienen datos detrás**, y si el diseño
las asume, después hay que construir endpoints o recortar el diseño.

### Lo que la API sirve hoy

| Endpoint | Devuelve | Estado |
|---|---|---|
| `GET /health` | Estado, versión, si hay modelo, hasta cuándo entrenó | Verificado |
| `GET /series` | Catálogo para poblar selectores | Verificado |
| `POST /forecast` | Pronóstico futuro con `pred_lo` / `pred_hi` | Implementado |
| `POST /reorder` | Cantidad por serie y día, con `critical_fraction` | Implementado, parcial |
| `GET /backtest` | Métricas por modelo con media, desvío, peor y mejor origen | Implementado |
| `GET /censoring` | Resumen de censura y comparación observado vs latente | Verificado |

### 7.1 Hueco crítico: no hay endpoint de historia

**Es el más importante y bloquea la pantalla hero.**

`/forecast` devuelve solo el futuro. La pantalla de serie individual necesita el histórico día por
día, con la venta observada, la demanda recuperada, y las horas de quiebre. Sin eso no hay gráfico.

Es fácil de tapar:

```
GET /series/{series_id}/history?basis=observed|recovered&from=&to=
→ [{ dt, sale_amount, demand_latent, oos_hours_open, is_censored, available_weight }]
```

Los datos existen todos en `data/processed/demand.parquet`. Es un endpoint de lectura, sin
modelo.

### 7.2 `/reorder` devuelve ceros en tres campos

`expected_shortfall`, `expected_overage` y `cost_delta_pct` están en el contrato Pydantic pero se
devuelven en `0.0`. El motivo es correcto: **sin verdad de terreno no hay faltante realizado**, y
inventar una estimación sería peor que devolver cero.

Para llenarlos hay que alimentarlos desde el backtest, no desde la inferencia. La columna «delta
contra la política actual» de 5.1 depende de esto.

### 7.3 `/backtest` no da métricas por origen

Devuelve el agregado con dispersión (media, desvío, peor, mejor). Alcanza para mostrar un rango,
**no alcanza** para el gráfico de una línea por modelo a través de los 8 orígenes, que es el más
valioso de esa pantalla.

Necesita un endpoint adicional o un parámetro `?by=origin`. El detalle ya se persiste en
`reports/backtest_models.parquet`, así que es exponer algo que existe.

### 7.4 Sin datos: explicabilidad, anomalías, drift, UMAP

- `/explain` y `/anomalies` están en el contrato Pydantic **pero no implementados**, y lo que va
  debajo tampoco existe: no hay SHAP, no hay Isolation Forest.
- No hay detección de drift.
- No hay clustering ni proyección UMAP.

Cualquier pantalla que dependa de esto es diseño sobre datos que hay que construir primero.

### 7.5 Un riesgo operativo que el frontend debería exponer

Pasó de verdad durante el desarrollo: un artefacto entrenado sobre la muestra de 60 series
sirviendo el panel de 3.066 devolvía **la misma cantidad a reponer para todos los productos**,
con la API respondiendo 200 OK. Ninguna métrica lo detecta.

Ya hay un guard en el backend que falla en vez de responder, pero el frontend debería mostrar en
la franja de contexto **cuántas series conoce el modelo cargado** contra cuántas hay en el panel.
Es una línea de texto y evita una demo fallida.

---

## 8. Sistema visual · guardarrieles, no prescripción

La paleta, la tipografía y el espaciado salen del draft. Lo que sí conviene fijar antes:

### 8.1 Semántica de color reservada

Cuatro significados necesitan color propio y consistente en todo el sistema. Conviene resolverlos
en el draft porque son los que se repiten en cada pantalla:

| Significado | Dónde aparece |
|---|---|
| **Venta observada** | Línea del histórico, modo «observada» del toggle |
| **Demanda recuperada** | Línea del histórico, modo «recuperada», es el color «correcto» |
| **Quiebre de stock** | Sombreado de tramos, barras de horas, marcas en la tabla |
| **Pronóstico e intervalo** | Línea de futuro y banda conformal |

Restricción: el par observada/recuperada tiene que distinguirse **también sin color**, porque en
el gráfico hero las dos líneas se superponen exactamente fuera de los tramos de quiebre. Trazo
distinto, grosor distinto, o ambos.

### 8.2 Modo claro y oscuro

Está en el plan. La consecuencia real es que el sombreado de quiebres tiene que funcionar en los
dos: un gris translúcido que se lee bien sobre blanco desaparece sobre fondo oscuro.

### 8.3 Densidad

El plan pide «densidad de información alta pero legible». La tabla de reposición es donde eso se
decide: es la pantalla que un operador mira todos los días, y el aire de más es scroll de más.

---

## 9. Accesibilidad

No es un agregado al final: dos decisiones del diseño dependen de esto.

- **El par observada/recuperada no puede distinguirse solo por color.** Ya está en 8.1, pero el
  motivo es de accesibilidad además de legibilidad.
- **El toggle de censura es el control más importante de la app**, así que necesita ser operable
  por teclado, tener estado anunciado por lector de pantalla, y una etiqueta que diga qué cambia,
  no solo cómo se llama.

Lo demás es lo estándar y conviene tenerlo desde el arranque en vez de retrofitearlo: contraste
suficiente en texto y en los elementos de los gráficos, foco visible, jerarquía de encabezados
real, tablas con `<th>` y `scope`, y los gráficos con una alternativa textual o una tabla de datos
accesible detrás.

Los gráficos son la parte difícil. Un `<canvas>` es opaco para un lector de pantalla, así que si
se usa canvas hay que dar la tabla equivalente.

> Verificar cumplimiento WCAG completo requiere testing manual con tecnologías asistivas y
> revisión de un especialista en accesibilidad. Este documento fija las decisiones de diseño que
> lo hacen posible, no certifica cumplimiento.

---

## 10. Estados que hay que diseñar y se suelen olvidar

Cada uno de estos va a ocurrir, algunos durante la defensa:

| Estado | Cuándo | Qué mostrar |
|---|---|---|
| **Sin artefacto** | `/health` responde `model_loaded: false` | Qué comando correr. Es el estado inicial de un clon del repo |
| **API caída** | El backend no levantó o se cayó | Distinguirlo de «sin datos», que se arregla distinto |
| **Usando la muestra** | Los datos vienen de `data/sample/` | **Advertencia visible.** 60 series presentadas como 3.066 es exactamente el error que arruina una defensa |
| **Serie sin quiebres** | Series limpias | El gráfico hero pierde su elemento central. Tiene que verse bien igual |
| **Serie con quiebre continuo** | Rachas de hasta 95 días | El fondo entero sombreado |
| **Carga** | `/reorder` con 500 series es costoso | Skeleton, no un spinner sobre pantalla en blanco |
| **Modelo sin cuantiles** | `/reorder` responde 501 | Explicar que hace falta un modelo cuantílico, no un error genérico |

El de «usando la muestra» es el más importante de los siete. El backend ya avisa por log; el
frontend tiene que avisar en pantalla.

---

## 11. Stack y estructura

Definido en el plan (sección 12): **React + TypeScript + Vite + Tailwind**, con Recharts para los
gráficos.

```
frontend/
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/
    │   ├── client.ts          # fetch tipado contra la API
    │   └── types.ts           # generado o espejado de api/schemas.py
    ├── state/
    │   └── basis.tsx          # el toggle de censura, en URL
    ├── components/
    │   ├── charts/            # el gráfico hero vive acá
    │   ├── table/             # tabla virtualizada
    │   └── ui/                # primitivas
    ├── screens/
    │   ├── Reorder.tsx
    │   ├── Series.tsx
    │   ├── Overview.tsx
    │   └── Models.tsx
    └── mocks/                 # datos simulados contra el contrato
```

**`src/mocks/` no es opcional.** El plan pone al frontend fuera del camino crítico precisamente
porque «arranca contra el contrato con datos simulados sin esperar al backend». Los mocks tienen
que ser fieles al contrato de `api/schemas.py`, incluidos los casos raros de la sección 10.

Sobre Recharts: alcanza para la comparativa de modelos y la degradación por horizonte. Para el
gráfico hero, con seis capas superpuestas y sombreado de tramos, conviene evaluar si Recharts da
el control necesario o si esa pieza justifica algo de más bajo nivel.

---

## 12. Qué queda explícitamente afuera

Declararlo evita que aparezca como deuda no dicha:

- **Autenticación.** La API no la tiene, es deliberado para el alcance del prototipo, y está
  documentado en el README. El frontend tampoco. Bloqueante para la Fase 2 multi-tenant.
- **Escritura.** El frontend es de lectura. No confirma órdenes, no persiste decisiones, no
  escribe en el backend. Es un sistema de apoyo a la decisión, no un sistema transaccional.
- **Multi-tenant.** Fase 2.
- **Móvil.** Se diseña para escritorio. Una tabla de 21.462 filas con siete columnas no tiene
  versión móvil razonable, y la audiencia real usa monitor.
- **Internacionalización.** Español, y punto.

---

## 13. Preguntas abiertas para cerrar en el draft

Las que cambian el diseño según cómo se respondan:

1. **¿Se diseñan las siete pantallas o solo las que tienen datos?** Determina si hay que construir
   SHAP, drift y UMAP antes de la defensa. Recomendación en la sección 5.5.
2. **¿El toggle de censura anima la transición?** Si sí, es la interacción más memorable de la
   demo. Si no, es un filtro más.
3. **¿La tabla de reposición se agrupa por serie o muestra los 7 días?** Afecta la virtualización
   y la lectura.
4. **¿El mapa UMAP entra?** Recomendación: no.
5. **¿Cómo se sombrea una racha de quiebre de un solo día?** El 44 % de las rachas son así, y a
   ~8 px puede verse como ruido.
6. **¿Modo claro y oscuro desde el arranque, o claro primero?** El plan pide los dos.
