# Brief para Claude · Slides de defensa de Blindside

Quiero que diseñes una presentación académica en **Markdown compatible con Marp** para defender
Blindside, proyecto final del Diplomado en Machine Learning y Deep Learning Aplicado de FIUNA.

La defensa dura **15 minutos**. Prepará:

- **11 slides principales** para unos 13 minutos.
- **Hasta 8 slides de respaldo** para preguntas.
- Notas del presentador debajo de cada slide.
- Tiempo aproximado por slide.
- Un visual concreto recomendado por slide.
- Texto corto y legible: una conclusión principal por slide.

Usá exclusivamente la información de este brief y de los documentos adjuntos. **No inventes
números, capacidades, moneda, despliegues ni resultados.**

## Documentos que tenés que leer

1. `README.md`
2. `docs/como_funciona.md`
3. `docs/model_card.md`
4. `docs/auditoria_final.md`
5. `docs/decisiones.md`
6. `docs/demo_guion.md`
7. `reports/metrics.md`
8. `reports/censoring_ablation.md`
9. `reports/metrics_classical.md`
10. `reports/tuning.md`
11. Imagen: `docs/assets/reposicion.png`

Si dos documentos discrepan, priorizá los reportes generados de `reports/` y después el README.
No cambies un número para que quede más lindo.

---

# 1 · Qué es Blindside

Blindside es un sistema de pronóstico de demanda de productos perecederos por tienda y producto.
Tiene tres diferencias frente a un proyecto de forecasting convencional:

1. **Corrige la demanda censurada por quiebres antes de pronosticar.**
2. **Cuantifica la incertidumbre con CQR.**
3. **Convierte el pronóstico en una cantidad concreta a pedir mediante newsvendor.**

Mensaje central de la presentación:

> Blindside no termina en una predicción. Termina en cuánto pedir.

El flujo conceptual es:

```text
venta observada
    ↓
recuperación de demanda censurada
    ↓
demanda latente estimada
    ↓
pronóstico probabilístico
    ↓
cuantil crítico según costos
    ↓
cantidad a pedir
```

---

# 2 · El problema

Cuando un producto se queda sin stock, la venta registrada cae a cero, pero la demanda no
necesariamente cayó. Si se entrena un modelo directamente sobre esa venta, aprende una demanda
artificialmente baja.

Esto genera el **efecto spiral-down**:

```text
se pide poco
    ↓
hay quiebre
    ↓
se observa menos venta
    ↓
el modelo aprende menor demanda
    ↓
se vuelve a pedir poco
```

FreshRetailNet anota el quiebre **hora por hora**, lo que permite estimar cuánta demanda quedó
oculta.

No decir que se recupera la demanda real perfectamente. La expresión correcta es:

> demanda latente estimada

La recuperación es conservadora:

- Nunca produce demanda menor que la venta observada.
- Limita la inflación a ×3.
- No corrige si queda menos del 15 % de la masa diaria observable.

Resultado de la ablación:

| Entrenado sobre | Sesgo re-censurado |
|---|---:|
| Venta observada | −18,19 % |
| Demanda recuperada | **−6,61 %** |

**Reducción de sesgo: 11,57 puntos porcentuales.**

---

# 3 · Datos

Fuente: **FreshRetailNet-50K**, de Dingdong-Inc.

| Dato | Valor |
|---|---:|
| Series utilizadas | **3.066** tienda × producto |
| Tiendas | 38 |
| Productos | 309 |
| Filas | 297.402 |
| Ventana temporal | **97 días** |
| Fechas | 2024-03-28 a 2024-07-02 |
| Train oficial | 90 días |
| Eval oficial | 7 días |
| Horizonte | 7 días |
| Orígenes de backtest | 8 |

Es un **panel de series temporales**: muchas series cortas y simultáneas, no una sola serie larga.
Cada serie es la combinación tienda × producto y cada fila representa un día.

El panel procesado tiene **cero nulos**. No hay imputación tradicional. La transformación central
es corregir valores presentes pero censurados por quiebre.

Jerarquía disponible:

```text
2 ciudades → 38 tiendas

7 grupos → 24 categorías → 61 subcategorías
         → 148 sub-subcategorías → 309 productos
```

El original tiene 50.000 series. El proyecto selecciona tiendas completas con semilla fija para
preservar la jerarquía.

No afirmar que FreshRetailNet puede aportar más tiempo: solo existen 90+7 días. Se pueden agregar
más series, pero no más historia temporal.

---

# 4 · Pipeline y antifugas

Pipeline:

```text
descarga
  ↓
submuestreo reproducible
  ↓
recuperación de censura
  ↓
features ancladas en el origen
  ↓
backtesting de origen móvil
  ↓
calibración CQR
  ↓
newsvendor
  ↓
artefacto + API + interfaces
```

Las **73 features** del artefacto real se distribuyen así:

| Tipo | Cantidad |
|---|---:|
| Rezagos de demanda | 27 |
| Calendario y plan comercial | 18 |
| Estadísticos móviles | 16 |
| Jerarquía categórica | 7 |
| Historia de quiebres | 2 |
| Otras | 3 |

Todas las features se construyen con datos disponibles hasta el origen de pronóstico. No se usa
información posterior.

Existen **8 asserts antifugas**. Cada uno tiene un caso negativo en el que se inyecta la fuga a
propósito y se verifica que falle.

Ejemplos:

- Futuro sin columna de target.
- Lags ordenados y agrupados por serie.
- Escalador ajustado solo con train.
- Test de shuffle.
- Train y test temporalmente disjuntos.
- Alineación temporal del target.

Mensaje recomendado:

> La ausencia de leakage no se declara en el README: se prueba con tests que fallan.

Estos controles encontraron defectos reales, entre ellos:

- `is_censored` del día objetivo entraba como feature.
- `days_since_start` usaba anclas diferentes entre entrenamiento e inferencia.
- Las covariables futuras llegaban como NaN a la API aunque el backtest las poblaba.

---

# 5 · Modelos

El modelo servido es:

> **CQR sobre LightGBM cuantílico global**

Es global porque un solo modelo aprende de todas las series. Con solo 97 días por serie, entrenar
3.066 modelos aislados desperdiciaría la información compartida.

El modelo sigue distinguiendo productos y categorías porque recibe como categóricas:

- Ciudad.
- Tienda.
- Grupo de gestión.
- Tres niveles de categoría.
- Producto.

Modelos usados como contraste:

- Naive.
- Naive estacional.
- Medias móviles.
- Croston SBA.
- Ridge, Lasso y ElasticNet.
- XGBoost.
- LightGBM puntual.
- SARIMA.
- Prophet.

Contraste clásico sobre 400 series y 8 orígenes:

| Modelo | MASE |
|---|---:|
| **LightGBM global** | **0,8386** |
| Croston SBA | 0,9032 |
| SARIMA | 0,9136 |
| Media móvil 21 días | 0,9139 |
| Prophet | 0,9698 |
| Naive estacional | 1,1058 |

Lectura:

> SARIMA queda empatado con la media móvil de 21 días. En series cortas e intermitentes, su
> complejidad no compra precisión adicional.

No ridiculizar SARIMA ni Prophet. Explicar que no están en su escenario ideal: 97 días no permiten
estimar un ciclo anual.

---

# 6 · Resultado principal

Resultados oficiales sobre 3.066 series, 8 orígenes, horizonte de 7 días y 1.545.264 predicciones:

| Modelo | MASE | Desvío | Peor origen | Mejora vs naive estacional |
|---|---:|---:|---:|---:|
| **CQR + LightGBM** | **0,8217** | 0,0454 | **0,8790** | **+25,3 %** |
| LightGBM puntual | 0,8222 | 0,0457 | 0,8791 | +25,3 % |
| Croston SBA | 0,8952 | 0,0683 | 0,9631 | +18,6 % |
| Media móvil 21 días | 0,9048 | 0,0654 | 0,9779 | +17,8 % |
| Naive estacional | 1,1002 | 0,0636 | 1,1579 | referencia |

Objetivo SMART de precisión:

> Mejorar al menos 20 % frente al naive estacional.

Resultado:

> **25,3 % de mejora. Objetivo cumplido.**

Explicar MASE en una frase:

> MASE divide el error del modelo por el error en muestra del naive estacional y permite comparar
> productos de escalas distintas.

No afirmar que un naive estacional debe dar MASE 1 fuera de muestra. En este proyecto da 1,1002
porque el denominador se calcula en train y el numerador fuera de muestra.

---

# 7 · Incertidumbre y CQR

Comparación:

| Método | Cobertura empírica | Ancho medio |
|---|---:|---:|
| **CQR** | **88,0 %** | **1,805** |
| Conformal de residuos | 98,7 % | 3,834 |
| Nominal | 90 % | — |

Lectura correcta:

- CQR queda 2 puntos por debajo del nominal.
- Produce una banda **53 % más angosta**.
- El conformal de residuos cubre demasiado y produce una banda del doble de ancho.
- Una banda infinita cubriría 100 % y no informaría nada.

No afirmar que se cumple el objetivo de cobertura de 90 %. La expresión correcta es:

> CQR sub-cubre dos puntos; es una limitación real y declarada.

La garantía conformal es **marginal, no condicional**. La cobertura por horizonte baja hasta
0,854 en el paso 6.

La cantidad a pedir **no sale del intervalo**. Sale del booster entrenado en el cuantil crítico.
La sub-cobertura afecta la banda de incertidumbre, no directamente la orden.

---

# 8 · Newsvendor: de pronóstico a cantidad

Fórmula principal:

\[
q^* = \frac{C_u}{C_u + C_o}
\]

Donde:

- `Cu`: costo de quedarse corto.
- `Co`: costo de quedarse largo.
- En perecederos, quedarse largo puede significar pérdida total al vencimiento.

Valor usado:

\[
q^* = 0,625
\]

Flujo:

```text
distribución predictiva
        ↓
costos Cu y Co
        ↓
cuantil crítico q* = 0,625
        ↓
cantidad sugerida
```

Mensaje central:

> El modelo se entrena directamente en `q*`. La predicción en ese cuantil es la orden.

Ejemplo medido:

| Base | Pronóstico | Cantidad a pedir | Política actual |
|---|---:|---:|---:|
| Venta observada | 190,229 | 210,958 | 231,960 |
| Demanda recuperada | 238,413 | **268,478** | 278,596 |

La recuperación de censura:

- Sube el pronóstico **25,3 %**.
- Sube la orden **27,3 %**.

No afirmar que conformal + newsvendor es una contribución teórica original. Decir:

> Apliqué un resultado reciente de la literatura en una implementación end-to-end.

---

# 9 · Producto y demo

Usar en la slide la imagen:

```text
docs/assets/reposicion.png
```

La slide debe señalar visualmente:

1. Cantidad sugerida.
2. Política de comparación.
3. Estado de señal.
4. Faltante y sobrante esperados.
5. Toggle entre venta observada y demanda recuperada.
6. MASE y cobertura visibles.
7. Explicación TreeSHAP.

La demo principal usa **React**, que abre en Reposición y responde cuánto pedir hoy.

Streamlit es la red de seguridad independiente y abre en **Qué mirar primero**, un triage del
catálogo. No saltar entre ambas superficies durante una demo de dos minutos.

Secuencia de demo:

1. Abrir Reposición.
2. Activar recuperación de censura.
3. Mostrar que cambia la **cantidad a pedir**, no solo el dibujo.
4. Abrir una serie.
5. Mostrar intervalo y política.
6. Mostrar explicación por features.
7. Si queda tiempo, mostrar Salud del modelo.

---

# 10 · Resultados negativos que se publican

Esta slide es importante porque demuestra control de sobreajuste y criterio experimental.

## Clustering

Feature de cluster sobre perfiles de demanda:

- Efecto medio sobre MASE: **+0,28 %**.
- Oscilación entre orígenes: aproximadamente **±11 puntos**.
- No entra al artefacto servido.

Además, FreshRetailNet no permite medir arranque en frío:

- Todas las series tienen exactamente 97 días.
- Ninguna tiene menos de 21 días.
- Ninguna empieza a vender después del día 16.

## Optuna

| | MASE | Desvío entre orígenes |
|---|---:|---:|
| Parámetros actuales | 0,8672 | 0,0134 |
| Mejor trial | 0,8630 | 0,0153 |

- Mejora: **0,49 %**.
- Menor que la dispersión entre orígenes.
- El mejor conjunto tiene más dispersión.
- No se adopta.

## Rendimiento por serie

- **404 series —13,2 %— tienen MASE > 1.**
- Para esas series, el modelo pierde contra el naive estacional.
- No son series pequeñas: su nivel medio es 2,120 frente a 1,344 del panel.
- La portada de Streamlit las identifica como “Modelo no confiable”.

Mensaje:

> Publicar lo que no funcionó es parte del control de sobreajuste, no una debilidad del proyecto.

---

# 11 · Limitaciones y cierre

## Implementado

- Recuperación de demanda censurada.
- Features ancladas en el origen.
- Backtesting móvil y pruebas antifugas.
- LightGBM puntual y cuantílico.
- CQR.
- Newsvendor.
- SARIMA y Prophet como contraste.
- Clustering e Isolation Forest.
- Optuna.
- TreeSHAP local y global.
- API FastAPI.
- Frontend React de 7 pantallas.
- Streamlit de 8 pantallas.
- **290 tests Python, 39 tests frontend y 12 tests Playwright.**

## Limitaciones

- Solo 97 días de historia.
- Horizonte de 7 días.
- Cobertura 88 % frente a 90 % nominal.
- Garantía conformal marginal, no condicional.
- Sin lead time ni multi-echelon.
- Sin mínimos de compra ni múltiplos de caja.
- Sin actualización continua.
- Sin detección de drift.
- Sin autenticación: no exponer públicamente.
- ROI relativo, no monetario, porque la escala del dataset no está divulgada.

## Próxima versión

1. Ingesta diaria idempotente.
2. Modelo candidato, promoción atómica y rollback.
3. Frescura visible en `/health`.
4. Drift y política de reentrenamiento.
5. Datos propios con 12–24 meses.
6. Restricciones operativas de inventario.

Cierre recomendado:

> Blindside corrige primero lo que la venta oculta, pronostica después y termina en una decisión
económica auditable.

---

# Estructura obligatoria de slides principales

| Slide | Tema | Tiempo aproximado |
|---|---|---:|
| 1 | Problema y propuesta | 0:45 |
| 2 | Demanda censurada y spiral-down | 1:15 |
| 3 | Dataset y alcance | 1:00 |
| 4 | Pipeline y antifugas | 1:15 |
| 5 | Modelos y estrategia global | 1:15 |
| 6 | Resultado principal | 1:15 |
| 7 | Incertidumbre y CQR | 1:15 |
| 8 | Newsvendor: de pronóstico a orden | 1:30 |
| 9 | Producto y demo | 2:00 |
| 10 | Resultados negativos | 1:15 |
| 11 | Limitaciones y cierre | 1:00 |

---

# Slides de respaldo

Preparar después del cierre y no incluirlas dentro de los 15 minutos normales.

## Backup A · Ocho controles antifugas

Tabla con cada assert, qué fuga detecta y un ejemplo del caso negativo.

## Backup B · Por qué 7 días y no 28

- FreshRetailNet tiene 97 días.
- Horizonte 28 deja como máximo cuatro orígenes.
- La metodología exige ocho.
- El split oficial de evaluación tiene siete días.

## Backup C · SARIMA fijo vs AutoARIMA

- Orden fija: MASE 0,9566.
- AutoARIMA: MASE 0,9657.
- Costo: 85 ms contra 2,3 s por serie.
- La orden fija no perjudicó al contraste.

## Backup D · CQR vs conformal de residuos

Mostrar los scores:

\[
s_{residuo}=|y-\hat y|
\]

\[
s_{CQR}=\max(\hat q_{lo}-y,\ y-\hat q_{hi})
\]

El score CQR puede ser negativo y por eso puede apretar el intervalo. El de residuos absolutos
solo puede ensanchar.

## Backup E · Recuperación de censura

Mostrar el perfil horario, peso disponible, factor de inflación y topes conservadores.

## Backup F · Actualización continua

Estado actual:

- Batch.
- Panel y artefactos cargados al arrancar.
- Sin ingesta, recarga, drift ni rollback.

Roadmap:

```text
ingesta idempotente
→ candidato
→ backtest
→ promoción atómica
→ observabilidad
→ drift
→ rollback
```

## Backup G · Por qué no ampliar FreshRetailNet

- La fuente tiene 90+7 días.
- Más series sí; más días no.
- Más series no agrega anualidad ni arranque en frío.
- Para más tiempo hace falta otra fuente con 12–24 meses.

## Backup H · Literatura y novedad

- FreshRetailNet-50K.
- CADRE.
- Cao 2024 sobre conformalización del cuantil crítico.
- Resultado de equivalencia entre pronóstico cuantílico calibrado y newsvendor.

Mensaje:

> La contribución no es inventar conformal + newsvendor. Es implementar y evaluar el pipeline
> completo, con recuperación de censura y decisión operativa.

---

# Reglas visuales

- Fondo claro y cálido, coherente con `docs/assets/reposicion.png`.
- Texto negro o gris oscuro.
- Rojo coral/naranja solo para quiebre, advertencias y cantidades clave.
- Verde con moderación para objetivos cumplidos.
- Títulos de 32–40 px.
- Texto principal de 22–26 px.
- Notas y fuentes de al menos 15–16 px.
- Máximo seis líneas visibles por bloque.
- Una conclusión principal por slide.
- Sin gráficos 3D ni pie charts.
- Preferir barras horizontales, diagramas de flujo e intervalos comparados.
- Tablas de máximo cinco o seis filas en slides principales.
- Mostrar dispersión junto a promedios.
- Usar coma decimal: `0,8217`, no `0.8217`.
- Sin animaciones complejas; debe funcionar igual exportada a PDF.

---

# Prohibiciones

No hacer ninguna de estas afirmaciones:

- No inventar moneda, kilos, unidades ni facturación.
- No afirmar que existe despliegue público.
- No afirmar que existe actualización continua.
- No afirmar que existe drift.
- No afirmar que hay más de 97 días.
- No afirmar que el clustering mejora el modelo.
- No afirmar que Optuna mejoró el modelo servido.
- No afirmar que la cobertura cumple 90 %: mide 88 %.
- No afirmar que conformal + newsvendor es una invención propia.
- No presentar el ROI como monetario.
- No llamar “demanda real” a `demand_latent`; decir “demanda latente estimada”.
- No usar MAPE como métrica principal.
- No mostrar un promedio sin su dispersión o peor origen.
- No afirmar que el frontend React tiene 8 pantallas: tiene 7.
- No afirmar que Streamlit tiene 7 pantallas: tiene 8.

---

# Formato de salida requerido

Entregá en este orden:

1. Una tabla resumen con número, título, mensaje principal, visual y duración de cada slide.
2. El archivo Markdown completo compatible con Marp.
3. Notas del presentador para cada slide.
4. Las slides de respaldo separadas por un encabezado claro.
5. Una lista final de los archivos de imagen que tengo que tener disponibles.

No vuelvas a explicar el proyecto antes de producir las slides. Empezá directamente por la tabla
resumen y luego generá el Markdown de Marp.