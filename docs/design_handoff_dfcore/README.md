# Handoff: dfcore · frontend de demand-forecasting-core

## Resumen

Interfaz web para un sistema de pronóstico de demanda con corrección de censura por quiebre de stock. El backend ya existe (FastAPI, contrato congelado) y hay un dashboard Streamlit con siete pantallas funcionando. Este frontend no agrega funcionalidad: existe para ser el artefacto que se presenta y para que la tesis del proyecto se vea sin explicarla.

La tesis: la demanda que ve el ERP está censurada por los quiebres de stock, y corregir eso cambia la cantidad a pedir. Todo el diseño está subordinado a que eso se perciba en dos minutos de demo.

Dos audiencias opuestas. Un panel académico que quiere rigor (dispersión entre orígenes, cobertura conformal, comparación contra baselines) y un lector operativo que quiere saber qué pedir hoy. La resolución es jerárquica: la decisión es el titular, la evidencia está embebida en los números que importan, y el rigor vive un nivel más abajo.

## Sobre los archivos de este paquete

Los tres `.dc.html` son **referencias de diseño hechas en HTML**: prototipos que muestran la apariencia y el comportamiento buscados. No son código de producción para copiar.

La tarea es **recrear estos diseños en el entorno del proyecto destino** con sus patrones y librerías establecidos. Si todavía no hay frontend — que es el caso aquí, el plan lo marca como frente H sin código — elegir el stack apropiado e implementarlos ahí. Recomendación razonable dado el backend: React con Vite y una librería de gráficos que permita control fino del orden de capas y de los rellenos del área de dibujo (Visx, D3 directo o SVG a mano). Los gráficos de este diseño son SVG escritos a mano con un `viewBox` fijo; no dependen de ninguna librería.

Los archivos abren directo en el navegador. Requieren `support.js` en la misma carpeta, que ya está incluido.

## Fidelidad

**Alta.** Colores, tipografía, espaciado, alturas de región y estados están definidos al píxel y a la sombra de opacidad. Los valores exactos están en `02 - Tokens y comportamiento.dc.html` y `03 - Planos y medidas.dc.html`, y los esenciales repetidos abajo.

Dos advertencias sobre el contenido:

1. **Los datos de los prototipos son de demostración**, generados en el cliente con semilla fija. Las magnitudes son verosímiles pero no salen de la API.
2. **Lo que el backend no sirve todavía se muestra igual, con sello `sim`.** Esa decisión es de diseño y hay que preservarla: ningún número sin respaldo aparece sin rótulo, y el sello no se puede cerrar. Ver «Dependencias de API» más abajo.

## Pantallas

Diez pantallas, con el id que usan los prototipos.

### 2a · Serie individual (hero)

**Para qué.** Responde «¿por qué le creo a esta cantidad?». Es la imagen que el panel se tiene que llevar: la venta observada contra la demanda recuperada, con los tramos de quiebre sombreados detrás.

**Layout.** Tarjeta de 1180 px. Grid de dos columnas: `minmax(0, 1fr)` y 268 px fijos, sin gap, separadas por una regla de 1 px en tinta 12 %. La columna izquierda lleva encabezado, gráfico principal, franja de horas de quiebre y leyenda. La derecha lleva la cantidad sugerida y su contexto.

**Gráfico principal.** SVG con `viewBox="0 0 1000 300"`, ancho 100 %, alto automático. Rellenos internos: 46 px a la izquierda (etiquetas del eje Y, que terminan a 40), 14 a la derecha, 12 arriba, 22 abajo (fechas). Cuatro guías horizontales en tinta 10 %, eje base en tinta 35 %.

El eje Y es **autoescalado de 0 al máximo × 1,06**. No es opcional: en este panel el p99 sobre la mediana llega a 12×, y con eje fijo una serie con pico promocional queda pegada al piso.

Orden de capas, de atrás hacia adelante:

| # | Capa | Especificación |
|---|---|---|
| 1 | Guías horizontales | tinta 10 %, cuatro líneas |
| 2 | Tramos de quiebre | sombreado vertical, tinta 7 %, de borde a borde |
| 3 | Eje base y corte del pronóstico | tinta 35 % continuo; tinta 30 % guionado 3/3 |
| 4 | Etiquetas de eje | 11 px en apagada, tabular |
| 5 | Cuña entre observada y recuperada | vermellón 16 % |
| 6 | Demanda recuperada | vermellón, 2,4 px, solo dentro de los tramos |
| 7 | Venta observada | gris observado, 1,4 px, continua en todo el rango |
| 8 | Banda conformal | vermellón 12 %, ensanchándose con el horizonte |
| 9 | Pronóstico | tinta 55 %, 1,8 px, guionado 5/4 |
| 10 | Cantidad sugerida | punto de 4,5 px de radio y plomada de 1 px hasta el eje |

La observada va **encima** de la recuperada a propósito: así la separación se lee como que la recuperada emerge desde abajo, no que tapa el dato original.

La línea recuperada **solo se dibuja dentro de los tramos de quiebre**, con un día de entrada y uno de salida. Fuera de ellos las dos series son idénticas, y dibujarlas superpuestas en todo el rango produce un artefacto visual que sugiere una corrección que no existe.

Las rachas de un solo día se dibujan con **ancho mínimo de 3 px sin borde**, más un marcador en la franja de horas. La mediana de racha en el panel real es de 2 días, así que sin mínimo desaparecen.

**Franja de horas de quiebre.** SVG de `viewBox="0 0 1000 60"`, debajo del gráfico principal, alineada al mismo eje X. Área rellena en tinta 42 %, escala 0 a 16 franjas comerciales. Comparte la fuente de cálculo con la métrica de censura de la franja de contexto: son el mismo número, y tienen que cuadrar.

**Panel derecho.** Cantidad sugerida en 42 px Archivo 600, con su cuantil al lado en 12 px. Debajo, tres bloques separados por regla de 1 px y 14 px de padding superior: comparación contra la política actual (política, delta, Cu/Co), contexto de censura (uplift, horas por día, racha máxima) y la nota de consecuencia de la base activa sobre fondo superficie con borde izquierdo de 2 px.

### 4a · Reposición (hero, landing)

**Para qué.** Responde «¿qué pido hoy, y cuánto?». Es la pantalla de entrada. El sistema no termina en una predicción, termina en una cantidad, así que la landing es la lista de reposición y no un resumen de exactitud.

**Layout.** Tarjeta de 1180 px con el shell arriba (ver abajo) y el cuerpo en grid de dos columnas: `minmax(0, 1fr)` y 300 px, gap 26, `align-items: start`. Padding del cuerpo 20 / 22 / 8.

**Tabla.** Siete columnas: Serie (flexible), Clase (92), Quiebre 14 d (118), Política (96), Sugerido (104), Δ (84), Impacto (110). El resto fijas para que las cifras no salten al alternar la base de cálculo. Cabecera en 10,5 px versalitas con regla inferior en tinta 35 %; filas de 34 px con padding 8 y regla en tinta 10 %; hover al fondo superficie.

Orden: **por impacto esperado descendente**. Ese orden depende de una columna simulada, lo cual está documentado en la nota al pie de la tabla y hay que mantener.

La columna de quiebre lleva un sparkline de 76 × 15 px con 14 barras de 5,4 px y 2,2 de gap en tinta 42 %, más el conteo en texto. La de impacto lleva una barra de 46 × 5 px en vermellón al 75 %, proporcional al máximo de la vista.

**Fila expandida.** Clic o Enter sobre una fila la abre en el lugar, sin navegar. Fondo superficie, padding 4 / 0 / 14, grid de `minmax(0, 1fr)` y 232 px con gap 24. A la izquierda el pronóstico a 7 días: una fila por día con etiqueta, barra proporcional en vermellón 14 % con borde derecho de 2 px en vermellón, rango de la banda conformal y predicción en 600. A la derecha el «por qué difiere»: días con quiebre de los últimos 28, racha máxima y un enlace a la serie completa. Solo una fila abierta a la vez; la primera arranca abierta.

**Control de ratio de costo.** Cuatro botones en una caja de 42 px de alto, con la cifra en 13 px / 600 arriba y el cuantil resultante en 10 px al 72 % abajo. El activo va en tinta plena. Es funcional: cambia las cantidades sugeridas, el total, los deltas y el orden de la tabla.

| Co/Cu | q* | Lectura |
|---|---|---|
| 0,3 | 0,769 | Producto seco: el sobrante es capital inmovilizado |
| **0,6** | **0,625** | **Perecedero: el sobrante es pérdida total al vencimiento** (por defecto) |
| 1,0 | 0,500 | Los dos errores cuestan igual: el óptimo es la mediana |
| 1,5 | 0,400 | El sobrante duele más que el quiebre |

Debajo del control, la lectura del ratio activo en 11,5 px. La relación entre ratio y cuantil no se explica en un tooltip: se muestra el cuantil resultante en el propio botón.

**Total.** 38 px Archivo 600 con el cuantil al lado, más la nota de que la magnitud es adimensional. Después, tres líneas de contexto (impacto acumulado, series en alerta en ocre, Cu/Co) y la nota de consecuencia de la base activa.

### 4b · Selector

Overlay de 556 px. Campo de búsqueda de 44 px de alto con padding 13 / 16, lupa de 14 px, texto en 15 px y cursor de 1 px en vermellón. A la derecha del campo, el conteo de resultados sobre el total.

Resultados de 36 px con padding 9 / 16: rótulo de tipo en 9,5 px versalitas (ancho fijo 58), código en 13 px / 500 tabular (ancho fijo 96) y descripción en 11,5 px apagada. El seleccionado lleva fondo superficie, sin acento: no es un hallazgo.

Pie con las teclas (↑↓ mover, ↵ abrir, esc cerrar) en 10,5 px.

**Por qué búsqueda y no un desplegable:** 309 productos, 19 tiendas y 3.066 series. Un `<select>` con 309 opciones no es usable. La búsqueda cubre código y descripción.

### 4c · Salud del modelo

Tarjeta de 556 px en tres bloques separados por regla de 1 px.

1. **Artefacto cargado** (`/health`, real): versión, entrenado hasta, series conocidas contra las del panel, origen de los datos.
2. **Cobertura empírica por horizonte** (real): barras desde la línea del nominal de 90 %, que es una línea guionada en tinta 45 %. Las barras que caen por debajo se leen como desvío hacia abajo. Nota fija: la degradación no es monótona y eso es correcto, porque con estacionalidad semanal el objetivo de h7 cae el mismo día de la semana que el origen.
3. **Deriva de features** (simulado): tres barras horizontales con su valor, y una nota que dice que no existe endpoint de deriva y que estos valores son sintéticos.

### 4d · Mapa de productos

Tarjeta de 556 px con un scatter de 309 puntos en `viewBox="0 0 300 170"` sobre fondo superficie. Radio 1,6 a 3,5 px; tres opacidades de tinta según banda de rotación (45 %, 30 %, 16 %). La selección activa lleva un anillo de 6,5 px en vermellón con punto central y una línea de guía hasta su etiqueta.

Leyenda con los tres conteos. Nota al pie: la cola de baja rotación es un tercio del catálogo, no la mayoría. El plan del proyecto asume lo contrario y conviene corregirlo antes de la defensa; esta pantalla lo hace visible.

Proyección simulada: no hay endpoint.

### Shell (en todas las pantallas)

119 px de cromo fijo, que no se desplaza con el scroll, en tres regiones:

| Región | Alto | Contenido |
|---|---|---|
| Franja de estado | 44 px | Logo, selector de serie, toggle de censura. Fondo superficie, padding 11 / 22 |
| Navegación | 42 px | Dos pantallas hero destacadas, resto agrupado. Fondo papel, padding 0 / 22 |
| Franja de contexto | 33 px | Cinco datos de confianza en 11,5 px, gap 26, padding 8 / 22 |

**El estado global y la navegación son dos contenedores visualmente distintos.** El toggle y el selector no son navegación y no pueden compartir contenedor con ella. Los separa el cambio de fondo (superficie contra papel) más la regla de 18 %.

La navegación tiene dos niveles. Primario: Reposición y Serie individual, en Archivo 600 de 15 px, con subrayado de 2 px en tinta en el activo. Secundario: el resto agrupado bajo los rótulos «Evidencia» y «Diagnóstico» en 10,5 px versalitas, con los ítems en 12,5 px apagada. Separados por una regla vertical de 1 px con 8 px de aire. Un sidebar de siete ítems iguales sería la estructura equivocada: repite el error del Streamlit, donde todo pesa lo mismo.

La franja de contexto lleva MASE con su dispersión y peor origen, cobertura empírica contra nominal, fecha de entrenamiento y **cuántas series conoce el modelo cargado contra cuántas hay en el panel**. Ese último dato es una línea de texto que evita una demo fallida: durante el desarrollo se sirvió un artefacto entrenado sobre 60 series contra el panel completo.

Los KPIs de exactitud viven acá, en 11,5 px. Son estado, no titular.

### 5a · Estado: usando la muestra

El error que arruina una defensa es presentar 60 series como 3.066. Se marca en tres lugares a la vez:

1. **Sello fijo** en la franja de estado, junto al logo: 10 px / 700 versalitas, texto papel sobre ocre, padding 3 / 7. **No se puede cerrar.**
2. **Banda explicativa** debajo, sobre ocre al 10 % con borde inferior en ocre 35 %: triángulo de advertencia de 18 px, título en Archivo 600 de 14 px en ocre oscuro, y el detalle en 12,5 px con los conteos reales (60 de 3.066 series, 2 de 19 tiendas, 31 de 309 productos) más la aclaración de que las métricas no son comparables. A la derecha, la acción para cargar el panel.
3. **Conteo en ocre** en la franja de contexto.

### 5b · Estado: serie sin quiebres

El gráfico hero pierde su elemento central y tiene que verse bien igual.

La línea observada sube a 1,8 px y pasa a **tinta plena**: sin una segunda línea que la contraste, el gris de observado se lee como desactivado. No hay sombreado, no hay cuña, no hay línea recuperada. El acento queda solo en la banda conformal y la cantidad sugerida, que es donde sigue habiendo una decisión.

Etiqueta «serie limpia» en 11 px versalitas con borde de 1 px, más una línea que dice que la venta observada es la demanda. El toggle sigue operable y se rotula «sin efecto en series limpias»: deshabilitarlo rompería la persistencia del estado global.

### 5c · Estado: API caída

Hay que distinguirlo de «sin datos», porque se arregla distinto. El cromo se muestra al 50 % de opacidad con la nota de controles deshabilitados.

Cuerpo: marca de desconexión de 34 px, título en Archivo 600 de 21 px, explicación que nombra el puerto, tabla de tres filas con último intento y próximo reintento, endpoint y código de error, el comando de uvicorn sobre fondo superficie con borde izquierdo de 2 px, y un botón primario de reintento.

### 5d · Estado: carga

El esqueleto **reserva la geometría exacta** de la pantalla final: nada se mueve al llegar los datos.

Bloques en tinta 7 a 12 % con las alturas y anchos del contenido real. Las filas se desvanecen hacia abajo (opacidad 1, 0,6, 0,3) para que el esqueleto no compita con el header, que ya tiene contenido real. **Sin brillo animado:** el único elemento en movimiento es una regla de progreso de 2 px en vermellón en el borde superior.

### 5e · Modo oscuro

La misma serie individual con el mapeo de tokens aplicado, más la tabla de equivalencias.

La única decisión que no es una inversión mecánica es el sombreado de quiebre. No invierte su valor sino su **referencia**: en claro es tinta al 7 % sobre papel, en oscuro es papel al 7 % sobre tinta. En los dos casos es más claro que su fondo por la misma cantidad, así que pesa igual. Un gris translúcido fijo desaparecería en uno de los dos modos.

El vermellón sube de `D6451A` a `F0602E` (unos 10 puntos de luminosidad) para mantener 4,5:1 contra el fondo oscuro. El gris de observado no cambia: a `8A8A84` pasa 3:1 contra los dos fondos, y el grosor ya lo distingue.

## Interacciones y comportamiento

### Toggle de censura

El control más importante de la app. Cambia todo a la vez: series, cantidades sugeridas, métricas de error y costo esperado.

- **Estado en la URL:** `?basis=observed|recovered`. Arranca en `observed`, para que la demo empiece en el modo incorrecto y se corrija en vivo, y para que el video de respaldo sea reproducible.
- **Persiste al navegar.** Cambiar de pantalla no lo resetea. Es independiente del selector de serie.
- **Etiqueta de consecuencia, no de estado.** En observada: «Es lo que ve el ERP. Subestima la demanda en los días con quiebre». En recuperada: «Censura corregida. Es la base de la cantidad sugerida». Va en el panel lateral, no en un tooltip.
- **Advertencia sutil en observada.** La regla de 2 px en vermellón bajo el control está en opacidad 0 y sube a 1 al pasar a recuperada. En observada el acento no aparece en ninguna parte de la pantalla: la ausencia de color es la advertencia, y es lo que hace que el cambio se perciba como una inundación de color.

**Secuencia de la transición, 740 ms en total**, curva `cubic-bezier(.4, 0, .2, 1)`:

| Qué | Desde | Hasta |
|---|---|---|
| Relleno del botón | 0 ms | 120 ms |
| Regla de acento | 60 ms | 180 ms |
| Cuña y línea recuperada | 120 ms | 720 ms |
| Cifras, con conteo | 200 ms | 700 ms |
| Columna Δ y barras de impacto | 240 ms | 740 ms |

El orden importa: primero responde el control, después aparece la evidencia, al final se mueven los números. Invertirlo hace que los números parezcan la causa. Sin `layout shift`: cifras tabulares y anchos de columna fijos.

Con `prefers-reduced-motion` todo pasa a 0 ms y los valores se reemplazan en seco, sin conteo.

### Accesibilidad del toggle

- Un `role="group"` con `aria-label="Base de cálculo"` y dos botones con `aria-pressed`. No es un checkbox: son dos estados con nombre propio.
- Tab entra al grupo, ← → mueven entre los dos, Enter o Espacio confirman. Atajo global `B`, anunciado en la ayuda.
- Al cambiar, una región `aria-live="polite"` anuncia el cambio de valor, no el nombre del modo: «Demanda recuperada. La cantidad sugerida pasa de 1,12 a 1,35».
- Contraste de texto 4,5:1 mínimo. El vermellón sobre papel da 4,6:1.
- El par de líneas del gráfico se distingue por grosor además de color, así que funciona en escala de grises y con daltonismo. Esto es un requisito, no una mejora: el par observado / recuperado es la información central del diseño.
- Contorno de foco de 2 px en tinta con 2 px de separación. Nunca se suprime.

### Otras interacciones

- **Fila de la tabla:** clic o Enter la abre en el lugar. Hover solo cambia el fondo a superficie. Ninguna información se descubre solo con hover: la app se proyecta, y en proyección no hay puntero visible.
- **Selector:** ⌘K lo abre, búsqueda incremental sobre código y descripción, ↑↓ para moverse, ↵ para abrir, esc para cerrar.
- **Ratio de costo:** recalcula cantidades, deltas, total, barras de impacto y el orden de la tabla. Las barras y los anchos transicionan en 500 ms.

### Reflow

Diseñado a 1180 px, soportado hasta 1024 px.

| Ancho | Panel lateral | Tabla | Navegación |
|---|---|---|---|
| ≥ 1180 | Columna fija de 300 px | Siete columnas | Dos niveles en una fila |
| 1024–1179 | Pasa arriba de la tabla, en tira de tres bloques | Se ocultan Clase y Quiebre 14 d; la evidencia queda solo en la fila abierta | Los dos niveles se apilan |
| < 1024 | — | — | Aviso de ancho mínimo |

La demo va a proyector: ningún texto baja de 11,5 px y las cifras de decisión no bajan de 19 px.

## Estado de la aplicación

| Variable | Valores | Alcance |
|---|---|---|
| `basis` | `observed` \| `recovered` | Global, en la URL. Por defecto `observed` |
| `series` | tienda + producto | Global, en la URL. Sobrevive a la navegación |
| `costRatio` | 0,3 \| 0,6 \| 1,0 \| 1,5 | Por pantalla de reposición. Por defecto 0,6 |
| `openRow` | índice o −1 | Local a la tabla. Una sola fila abierta |
| `theme` | claro \| oscuro | Preferencia del sistema, con override manual |
| `dataSource` | panel \| muestra | Derivado de `/health`. Dispara el estado 5a |
| `apiStatus` | ok \| caída \| sin artefacto \| cargando | Derivado de `/health`. Dispara 5c, 5d |

`basis` y `series` son los dos estados globales, y son independientes entre sí: cambiar de serie no cambia la base de cálculo.

## Tokens de diseño

Una sola regla gobierna la paleta: **el mundo observado es desaturado y solo lo recuperado lleva acento.** Si algo nuevo necesita color, la respuesta por defecto es un gris de la escala.

| Rol | Claro | Oscuro | Dónde |
|---|---|---|---|
| papel | `#FAF8F5` | `#141310` | Fondo de la app y de las tarjetas |
| superficie | `#F2EEE8` | `#1E1C18` | Franja de estado, filas abiertas, notas al pie |
| tinta | `#1A1A18` | `#F2EEE8` | Títulos, cifras, línea observada en series limpias |
| secundaria | `#44443E` | `#C9C4BB` | Cuerpo de texto y celdas de dato |
| apagada | `#5F5F59` | `#9A958C` | Notas, ejes, etiquetas secundarias |
| rótulo | `#6B6B64` | `#86817A` | Versalitas de 10,5 px |
| observado | `#8A8A84` | `#8A8A84` | Línea de venta observada. No cambia entre modos |
| recuperado | `#D6451A` | `#F0602E` | Solo lo recuperado: línea, cuña, banda, cantidad |
| advertencia | `#7A5C10` | `#D9A93A` | Muestra, sello sim, series en alerta |
| regla fina | tinta 12 % | papel 14 % | Divisiones internas de tarjeta |
| regla de sección | tinta 18 % | papel 16 % | Borde de tarjeta y separador de sección |
| regla de cabecera | tinta 35 % | papel 30 % | Solo bajo el thead y en el eje base |
| quiebre | tinta 7 % | papel 7 % | Sombreado vertical de los tramos |

**Semántica reservada.** Cuatro significados no se reasignan, y cada uno lleva redundancia no cromática:

| Significado | Color | Redundancia |
|---|---|---|
| Observado | `#8A8A84` | 1,4 px, la mitad de grosor que la recuperada |
| Recuperado | `#D6451A` | 2,4 px y cuña rellena |
| Pronóstico | tinta 55 % | guionado 5/4. Nunca lleva acento: el futuro no es un hallazgo |
| Advertencia | `#7A5C10` | triángulo o sello con borde, nunca solo color |

**Tipografía.** Archivo para títulos y cifras de decisión, IBM Plex Sans para todo lo demás. Sin fuente monoespaciada: el registro de consola está reservado a otro proyecto de la misma marca.

| Nivel | Familia y peso | px | Tracking |
|---|---|---|---|
| Título de página | Archivo 600 | 34–36 | −0,018 em |
| Título de pantalla | Archivo 600 | 21 | −0,018 em |
| Título de sección | Archivo 600 versalitas | 16–17 | −0,010 em |
| Cifra de decisión | Archivo 600 tabular | 38–42 | −0,020 em |
| Cifra de KPI | Plex Sans 500 tabular | 20 | 0 |
| Cuerpo | Plex Sans 400 | 13–14 | 0 |
| Celda de dato | Plex Sans 400 tabular | 12,5 | 0 |
| Nota | Plex Sans 400 | 11,5 | 0 |
| Rótulo | Plex Sans 600 versalitas | 10,5 | 0,14 em |

Toda cifra usa `font-variant-numeric: tabular-nums`. No es estético: evita el salto al alternar la base de cálculo.

**Espaciado.** Múltiplos de 2 en una escala de seis pasos: 4 (rótulo a cifra), 8 (interno de fila), 12 (vertical de celda), 18 (entre bloques del panel), 22 (horizontal de tarjeta), 44 (entre pantallas).

**Radio de esquina: 0 px, sin excepciones. Sin sombras.** La jerarquía la llevan las reglas y el peso tipográfico.

**Formato de cifras.** Locale es-PY: coma decimal, punto de miles.

| Tipo | Ejemplo | Regla |
|---|---|---|
| Magnitud | 1,35 | Dos decimales. **Sin símbolo ni unidad, nunca** |
| Error | 0,743 ± 0,061 | Tres decimales, siempre con su dispersión |
| Porcentaje | +21,1 % | Un decimal, espacio antes del signo, signo explícito |
| Negativo | −24,5 % | Menos tipográfico U+2212, no guion |
| Conteo | 3.066 series | Siempre contra su total: «60 de 3.066» |
| Fecha | 2026-09-18 | ISO en datos; «15 sep» solo en etiquetas de eje |

`sale_amount` viene multiplicado por un coeficiente no divulgado. No hay guaraníes, no hay kilos: **cualquier símbolo de moneda o unidad en la interfaz es un error factual**, y los ejes tampoco los llevan.

## Restricciones de los datos

Medidas sobre el panel real de 3.066 series y 297.402 filas. Un diseño que las ignore no funciona con estos datos.

- **Cola derecha larga.** El p99 sobre la mediana llega a 12×. De ahí el eje autoescalado.
- **Censura.** 43,9 % de días con quiebre, 7,0 horas promedio sobre 16 franjas comerciales. Eso da 19,2 % de horas comerciales en quiebre, que reproduce el ≈20 % declarado en la ficha del dataset. Esa comprobación se muestra en Vista general.
- **Rachas.** Mediana de 2 días, máximo de 95. De ahí el ancho mínimo de 3 px y el estado de quiebre continuo.
- **Escala de la interfaz.** 19 tiendas, 309 productos, 3.066 series, 97 días de historia, horizonte de 7 días, 8 orígenes de validación.
- **Baja rotación.** Un tercio del catálogo, no la mayoría. El plan del proyecto asume lo contrario.

## Dependencias de API

| Pantalla | Endpoint | Estado | Qué hace el frontend |
|---|---|---|---|
| Reposición | `POST /reorder` | parcial | Cantidades reales. `expected_shortfall`, `expected_overage` y `cost_delta_pct` vuelven en cero: el impacto se calcula en el cliente con la banda conformal y el ratio, y va rotulado `sim` |
| Serie individual | **falta** | **bloqueante** | No hay endpoint que devuelva la serie observada contra la latente día por día. Es el hueco que bloquea la pantalla hero |
| Vista general | `GET /censoring` | verificado | Directo, incluida la comprobación de la ventana comercial |
| Comparativa | `GET /backtest` | parcial | El agregado con dispersión es real. Las ocho líneas por origen son sintéticas; los datos existen en `reports/backtest_models.parquet`, así que es exponer algo que ya está |
| Explicabilidad | `POST /explain` | no implementado | Contribuciones sintéticas con sello `sim` |
| Salud | `GET /health` | mixto | Artefacto y cobertura reales; la deriva de features es sintética |
| Mapa | **falta** | no existe | Proyección sintética de los 309 productos |

También verificados y en uso: `GET /series` para poblar el selector.

**Regla de los datos simulados.** Se muestran, no se ocultan, porque las pantallas comunican el diseño completo. Pero: el sello `sim` (9 px, ocre, con borde de 1 px) va en la cabecera de la columna o en el título del bloque, y toda pantalla con datos sintéticos lleva una nota que dice qué endpoint falta. El sello no se puede cerrar. En la defensa esas pantallas se presentan como diseño, no como medición.

## Assets

Ninguno externo. El logotipo es un SVG inline de 120 × 44 en el `viewBox`, dibujado con tres trazos: dos líneas que coinciden y en un punto se abren, más la cuña rellena entre ellas en vermellón. Escala a 30 × 11 px en el shell. No hay iconos de librería: los pocos que hay (lupa, triángulo de advertencia, marca de desconexión) son SVG inline de 12 a 34 px con trazo de 1,4 a 2 px.

Tipografías desde Google Fonts: Archivo (500, 600, 700) e IBM Plex Sans (400, 500, 600).

## Archivos

| Archivo | Contenido |
|---|---|
| `01 - Pantallas finales.dc.html` | Las diez pantallas. Ids `2a`, `4a`–`4d`, `5a`–`5e` |
| `02 - Tokens y comportamiento.dc.html` | Paleta clara y oscura, semántica reservada, escala tipográfica, formato de cifras, secuencia del toggle, accesibilidad, reflow, dependencias de API |
| `03 - Planos y medidas.dc.html` | Retícula, planos de shell / reposición / serie individual con alturas y columnas, orden de capas del gráfico, inventario de controles con sus estados |
| `support.js` | Runtime que necesitan los tres archivos para abrir en el navegador |

Abrir `01` primero. Los tres son navegables y están enlazados entre sí.

## Pendientes de diseño

Dos estados quedaron especificados en texto pero sin dibujar, y están anotados como pendientes en el archivo `02`:

- **Sin artefacto** (`/health` responde `model_loaded: false`): pantalla completa con el comando a correr. Es el estado inicial de un clon del repo.
- **Quiebre continuo** (rachas de hasta 95 días): el fondo entero sombreado. La cuña cubre casi todo el gráfico, así que hay que agregar el conteo de días en el encabezado para que el sombreado no se lea como un error de render.
