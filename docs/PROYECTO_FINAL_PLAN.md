# Proyecto Final Integrador · M7 · Diplomado ML/DL FIUNA 2026

**Autor:** Franco Cazal
**Documento:** plan de ejecución, alcance completo
**Redactado:** 2026-09-08

---

## 0. Ventana real de ejecución

| Hito | Fecha | Estado |
|---|---|---|
| M7.1 Kick-off | lun 2026-09-02 | pasado |
| M7.2 Tutoría grupal | vie 2026-09-04 | pasado |
| M7.3 Tutoría desarrollo | lun 2026-09-07 | pasado |
| M7.4 Tutoría de deploy | mié 2026-09-09 · 18:30 | pasado |
| **M7.5 Defensa ante panel** | **vie 2026-09-11 · 18:30** | **fecha vencida · re-fechar** |

> **Ventana desactualizada (revisado 2026-09-14).** Todas las fechas de esta tabla ya pasaron.
> La ventana real de trabajo y la fecha de defensa están **sin confirmar**: hasta que se fijen,
> el documento usa `[FECHA]` y el cronograma de la sección 14 usa días relativos en vez de
> días de la semana. Lo que sigue vigente de esta sección es la **estrategia**, no el
> calendario.

Tres días y medio de trabajo efectivo. El alcance de este documento es completo y no se
recorta. La estrategia que lo hace viable es **paralelización con agentes de IA sobre
contratos definidos primero**, más un **release etiquetado cada noche** para que la defensa
nunca dependa del último commit.

Eso además juega a favor en la evaluación. La programación asistida por IA es eje
transversal declarado del diplomado, así que ejecutar con agentes en paralelo no es un
atajo que haya que disimular. Es parte de lo que el programa quiere ver, y conviene
contarlo en la defensa.

---

## 0.1 Formulario de aprobación del tema · respuestas oficiales

Redactado 2026-09-14. Estas son las respuestas presentadas al formulario del diplomado y son
la versión canónica del alcance declarado.

> **Estado de consistencia.** Reconciliado 2026-09-14: el documento entero está reescrito
> sobre el dominio de **cadena de frío y perecederos** y sobre la decisión de datos de la
> sección 4 (FreshRetailNet-50K primario, generador Focal Point secundario). Las respuestas
> P1 y P4 de abajo ya reflejan esa decisión.
>
> **Único pendiente real:** la fecha de entrega. Los hitos de la sección 0 fechan la defensa el
> 2026-09-11, ya pasado. Reemplazar `[FECHA]` en este documento (aparece en 0.1 y en 1).

### P1 · Objetivo en una oración

> Construiré un sistema de pronóstico de demanda de productos perecederos por tienda y
> producto que primero recupera la demanda censurada por quiebres de stock y después la
> traduce en una cantidad concreta a reponer, desarrollado sobre FreshRetailNet-50K y
> aplicado a la estructura operativa de Focal Point, midiendo el éxito con una reducción de
> al menos 20 % de MASE frente al baseline estacional ingenuo y una cobertura empírica
> ≥ 90 % del intervalo de predicción, entregado antes del `[FECHA]`.

| Dimensión | Respuesta |
|---|---|
| Qué construyo | Recuperación de demanda censurada + pipeline de forecasting + capa de decisión de reposición, con API y dashboard |
| Con qué datos | FreshRetailNet-50K (primario, real, censura anotada) y generador sintético calibrado a Focal Point (secundario, organización propia) |
| Métrica | MASE contra naive estacional (principal) + cobertura empírica del intervalo + sesgo de demanda re-censurada |
| Para cuándo | `[FECHA]` |

### P2 · Descripción del problema

> En los distribuidores de insumos con cadena de frío la reposición se decide con reglas
> manuales basadas en el promedio de las últimas semanas, y eso genera al mismo tiempo
> quiebres de productos críticos y vencimiento de lotes que nunca se vendieron. El problema
> lo tiene el responsable de compras, que firma la orden sin ninguna estimación de la
> incertidumbre y sin saber si su pedido cubre el 50 % o el 95 % de los escenarios posibles.
> ML/DL es la solución porque son cientos de series producto × depósito con estacionalidad,
> promociones y demanda censurada por quiebres, y porque un modelo entrenado con pérdida
> cuantílica predice directamente el cuantil óptimo de reposición según el costo de cada
> error — algo que ningún promedio ni planilla puede entregar.

### P4 · Datos disponibles

> **Fuente primaria: FreshRetailNet-50K** (Dingdong-Inc, CC BY 4.0), el primer benchmark
> a gran escala de estimación de demanda censurada en retail de perecederos. 50.000 series
> tienda-producto de 90 días con ventas horarias de 898 tiendas en 18 ciudades y 865 SKU
> perecederos, con **≈ 20 % de eventos de quiebre de stock anotados hora por hora**. Doble
> jerarquía (`city_id > store_id` y `management_group_id > … > product_id`) y covariables de
> descuento, feriado, actividad promocional, precipitación, temperatura, humedad y viento.
> Se submuestrea a ~2.000-5.000 series con semilla fija para que el backtesting entre en la
> ventana de trabajo; el submuestreo se declara.
>
> **Fuente secundaria: generador sintético propio** versionado con semilla fija
> (`src/dfcore/data/generator.py`), calibrado a la estructura operativa real de Focal Point —
> jerarquía producto → categoría → sucursal → total, feriados paraguayos, cola de baja
> rotación, vida útil de lote y quiebres que censuran. Es el caso de la organización propia y
> el único donde el ROI se expresa en guaraníes, porque en el dataset primario las ventas
> están normalizadas por un coeficiente no divulgado.
>
> **Target: `sale_amount`** (demanda por tienda-producto-período), en versión puntual y en
> cuantiles, y — como objetivo intermedio — la **demanda latente recuperada** en los tramos
> censurados por quiebre.

### P5 · Módulos del diplomado a utilizar

| Módulo | Uso declarado |
|---|---|
| M2 | Pipeline de scikit-learn con `ColumnTransformer` para imputación, escalado y encoding, ajustado dentro de cada fold para evitar fugas |
| M3 | Modelo supervisado global con LightGBM y XGBoost sobre features de lag, rolling y calendario, con Optuna y explicabilidad SHAP |
| M4 | Clustering de perfiles de demanda (K-Means / DBSCAN) como feature de arranque en frío, y detección de anomalías con Isolation Forest |
| M5 | GRU y LSTM en PyTorch, multi-serie con embeddings de producto y depósito, con early stopping y LR scheduling |
| M6 | Backtesting de origen móvil, SARIMA y Prophet como contraste, y anomalías secuenciales sobre el residuo |

**Mínimo defendible si el reloj aprieta:** M2 + M3 + M6. M4 y M5 se agregan si el tiempo
alcanza. Prometer cinco y entregar tres es peor que prometer tres y entregar cinco.

### P6 · Métrica de éxito

> **MASE** como métrica principal, complementada con **cobertura empírica del intervalo** y
> **pinball loss** para los cuantiles.
>
> Elijo MASE y no MAPE deliberadamente. MAPE explota cuando la demanda se acerca a cero, y
> eso es exactamente lo que pasa en la cola de productos de baja rotación, que es la mayoría
> del catálogo en cadena de frío. MASE es libre de escala y compara directamente contra el
> baseline estacional ingenuo, así que un MASE menor a 1 significa literalmente "el modelo
> le gana al método que la empresa ya usa"; eso es interpretable para el negocio sin
> traducción.
>
> Agrego cobertura empírica porque el sistema no entrega solo una predicción, sino un
> intervalo que alimenta la decisión de cuánto pedir: un intervalo nominal del 90 % que en la
> práctica cubre el 60 % haría que el modelo prometa un nivel de servicio que no cumple. Y
> reporto WAPE como lectura de negocio ponderada por volumen. La métrica se informa con su
> dispersión entre orígenes de backtest, no como número único, porque un promedio bueno puede
> esconder un origen catastrófico.

**Riesgo de evaluación:** el formulario lista MAPE, RMSE y MAE para forecasting, y la
respuesta se desvía hacia MASE. La justificación de arriba es obligatoria, no opcional: sin
ella la desviación se lee como error en vez de criterio propio.

---

## 0.2 Investigación de respaldo · hallazgos y fuentes

Investigado 2026-09-14. Esta sección existe para que ningún número del proyecto sea
autoevaluación: cada afirmación de meta, calibración o novedad tiene una fuente citable.
Las fuentes fueron leídas a nivel de abstract y ficha, salvo la ficha de HuggingFace, que se
verificó campo por campo.

### 0.2.1 · Hallazgo principal: FreshRetailNet-50K

Dataset público que reproduce casi exactamente la estructura del problema de este proyecto.

- Ficha: [huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K)
- Paper: [arXiv 2505.16319](https://arxiv.org/abs/2505.16319)
- Baseline oficial: [Dingdong-Inc/frn-50k-baseline](https://github.com/Dingdong-Inc/frn-50k-baseline)

| Atributo | Valor |
|---|---|
| Volumen | 4,85 M filas · 115 MB · splits `train` 4,5 M / `eval` 350 k |
| Series | 50.000 series tienda-producto de 90 días |
| Cobertura | 898 tiendas · 18 ciudades · 865 SKU perecederos |
| Censura | ≈ 20 % de eventos de quiebre, anotados **hora por hora** (`hours_stock_status`, `stock_hour6_22_cnt`) |
| Jerarquía A | `city_id > store_id` |
| Jerarquía B | `management_group_id > first_category_id > second_category_id > third_category_id > product_id` |
| Covariables | `discount`, `holiday_flag`, `activity_flag`, `precpt`, `avg_temperature`, `avg_humidity`, `avg_wind_level` |
| Licencia | CC BY 4.0 · uso comercial permitido |

Por qué encaja: es perecedero (vencimiento y merma reales), tiene la **censura de demanda
etiquetada** — o sea que la corrección se puede *medir*, no solo afirmar —, tiene **dos
jerarquías reales** donde la reconciliación MinT vive sin ser inventada, trae clima como
regresor externo, y **no es contenido del diplomado**.

**Dos trampas verificadas, que hay que resolver antes de comprometer alcance:**

1. `sale_amount` y `hours_sale` están **normalizados por un coeficiente no divulgado**. Las
   métricas de exactitud salen perfectas, pero el **ROI en guaraníes NO se puede calcular
   directo** desde el dataset: exige reescalar con supuestos declarados. Afecta a la
   sección 11 de este documento.
2. 4,85 M filas es demasiado para la ventana de trabajo y para el host disponible.
   Submuestrear por ciudad o por grupo de categorías a ~2.000-5.000 series, y **declarar el
   submuestreo** en README y defensa.

### 0.2.2 · El objetivo de 20 % de MASE está bien calibrado

Referencia directa: transformers temporales en demanda retail reportan **26 % a 29 % de
mejora de MASE y hasta 34 % de reducción de WQL frente al naive estacional**
([MDPI Mathematics 12(17):2728](https://www.mdpi.com/2227-7390/12/17/2728?type=check_update&version=3)).
Prometer 20 % deja margen sin sonar trivial.

Dos matices para la defensa:

- En la **cola intermitente** la ventaja se achica o se invierte: un benchmark de demanda de
  repuestos halló LightGBM y MLP superiores en intermitencia extrema *por desempeño de
  inventario* pero flojos en exactitud pura
  ([tesis EUR](https://thesis.eur.nl/pub/60771/Master-thesis-final-version-Daniel-de-Haan.pdf)).
  Respalda la decisión de reportar por banda de rotación: "el modelo complejo no gana en baja
  rotación" es resultado esperado y publicado, no fracaso propio.
- La superioridad de **modelos globales sobre datos muy dispersos es debate abierto**, y la
  evidencia viene sobre todo de datos jerárquicos con estructura cruzada fuerte
  ([tesis LIACS](https://theses.liacs.nl/pdf/2025-2026-MciszKPKamil.pdf)). El argumento
  "el modelo global comparte estructura entre series" es correcto **con condiciones**;
  FreshRetailNet las cumple.

### 0.2.3 · El diferencial conformal + newsvendor ya existe en la literatura

Corrección importante al encuadre de la sección 8: el cruce **no es inédito**.

- [A Conformal Approach to Feature-based Newsvendor under Model Misspecification](https://arxiv.org/abs/2412.13159)
  (Cao, dic-2024) conformaliza el cuantil crítico con garantías independientes de que el
  modelo esté bien especificado.
- [A Decision-Theoretic Framework for Probabilistic Forecasting and Constrained Optimization](https://www.mdpi.com/1911-8074/19/3/173)
  demuestra que **los pronósticos cuantílicos calibrados son matemáticamente equivalentes a
  la solución óptima del newsvendor**.

Consecuencia práctica: **no reivindicar invención, reivindicar aplicación.** El discurso pasa
de "inventé algo" a "apliqué un resultado reciente de la literatura que casi nadie implementa
en producción, y acá está corriendo". Citar ambos papers convierte la posición de ingenua en
bien leída. El diferencial **frente a la cohorte** sigue intacto: no está en ningún notebook
del material.

### 0.2.4 · Corrección de demanda censurada · métodos citables

- **Tobit Exponential Smoothing con agregación temporal**
  ([arXiv 2409.05412](https://arxiv.org/html/2409.05412v1)): maneja censura conocida y
  variable, produce bandas comparables a modelos no censurados incluso bajo censura severa, y
  nombra explícitamente el **efecto spiral-down** (pedir de menos → más quiebres → observar
  menos demanda → pedir de menos todavía). Frase de alto valor para la defensa.
- **CADRE** ([MDPI Sustainability 18(15):7642](https://www.mdpi.com/2071-1050/18/15/7642)),
  medido sobre FreshRetailNet-50K. Números directamente reutilizables para calibrar el ROI de
  la sección 11 con supuestos citables:

  | Indicador | Antes | Después |
  |---|---|---|
  | WAPE (backbone TimeXer) | 39,42 % | 36,71 % |
  | Sesgo de demanda re-censurada | −8,1 % | −1,3 % |
  | Merma (simulación de reposición) | 9,8 % | 6,4 % |
  | Nivel de servicio | 92,9 % | 94,7 % |

- **Sesgo de censura en decisores humanos**
  ([POMS, Tong-Feiler-Larrick 2018](https://journals.sagepub.com/doi/10.1111/poms.12823?icid=int.sj-abstract.citing-articles.91)):
  los gerentes subestiman sistemáticamente la demanda cuando las ventas perdidas no son
  observables. Es el respaldo académico del párrafo "hoy se decide por promedio móvil mental".

### 0.2.5 · Riesgo competitivo · leer antes de fijar alcance

Existe [A Reproducible, Leakage-Free Pipeline for Censored Demand Forecasting and Inventory Optimization on FreshRetailNet-50K](https://www.mdpi.com/2411-5134/11/5/89).
Es **plantilla y competencia a la vez**: alguien ya publicó aproximadamente este proyecto
sobre este dataset, incluida la parte antifugas y la optimización de inventario. No invalida
el entregable (esto es un diplomado, no un paper), pero **si el panel lo conoce, conviene
haberlo citado primero**. Leerlo antes de congelar el alcance.

### 0.2.6 · Recursos que ahorran trabajo

- [frn-50k-baseline](https://github.com/Dingdong-Inc/frn-50k-baseline) — pipeline oficial de
  entrenamiento y evaluación. Da un número de comparación **externo**, no autoevaluado.
- [Conformal prediction en statsforecast (Nixtla)](https://nixtlaverse.nixtla.io/statsforecast/docs/tutorials/conformalprediction.html)
  — implementación lista, evita escribir el conformal desde cero.
- [Forecasting retail demand under stockouts (NumPyro)](https://juanitorduz.github.io/numpyro_forecast/docs/examples/fresh_retail_stockout.html)
  — ejemplo trabajado sobre este mismo dataset; útil como referencia de tratamiento aunque el
  stack sea otro.
- Dataset Kaggle de ~600.000 registros de ventas de farmacia, usado en
  [MDPI Forecasting 6(1):10](https://www.mdpi.com/2571-9394/6/1/10). **Descartado como caso
  primario:** una sola farmacia, sin jerarquía ni anotación de quiebres.

### 0.2.7 · Decisión de datos revisada

Reemplaza la recomendación de la sección 4 (que proponía generador sintético como opción
primaria).

**FreshRetailNet-50K como caso primario; generador sintético como complemento.** Fundamento:

1. Saca del camino crítico la pieza más costosa y riesgosa: construir y calibrar el generador.
2. Aporta datos **reales** de perecederos con censura etiquetada, que es la tesis del proyecto.
3. Aporta **baselines publicados**, así el "20 % de MASE" deja de ser autoevaluación.
4. Sigue siendo cadena de frío conceptualmente: fresh retail *es* cadena de frío, con
   vencimiento, merma y quiebres.

El generador **no se descarta**: queda para el **caso Focal Point** (jerarquía propia y
feriados paraguayos), que es lo que satisface el requisito de "caso real de la organización
del participante" y lo que conecta con la Fase 2. Método validado en benchmark público,
aplicado a la estructura de la organización propia — más fuerte que cualquiera de los dos por
separado.

> **Reconciliado 2026-09-14.** Las secciones 1, 4, 5.4, 8, 10, 11, 12, 15 y 17, y las
> respuestas P1 y P4 del formulario (0.1), ya reflejan esta decisión. No queda ninguna
> contradicción de dominio ni de fuente de datos en el documento.

---

## 1. Tema y objetivo

**Sistema de pronóstico de demanda de productos perecederos por tienda y producto, con
corrección de demanda censurada, capa de decisión de reposición, detección de anomalías y
explicabilidad.**

No termina en una predicción. Termina en una **cantidad a pedir** derivada de la economía del
negocio, con intervalos de cobertura garantizada, sobre una demanda que primero hay que
**recuperar**, porque los quiebres de stock la censuran y entrenar sobre la venta observada
enseña al modelo a pedir de menos.

Dominio: cadena de frío y perecederos. La cadena de frío entra como **restricción que deforma
la economía**, no como sistema a controlar: el proyecto no monitorea equipos de refrigeración
ni opina sobre aptitud de la mercadería. Lo que hace el vencimiento es volver el costo de
sobre-stock una **pérdida total** en vez de capital inmovilizado, y eso empuja el cuantil
óptimo de reposición.

### Objetivo SMART

> Reducir el error de pronóstico de demanda semanal por tienda y producto en al menos
> **20 % de MASE** frente al baseline estacional ingenuo, sobre un horizonte de 4 semanas,
> validado con backtesting de origen móvil sobre al menos 8 orígenes de FreshRetailNet-50K, y
> entregar un prototipo desplegado que traduzca el pronóstico en cantidad de reposición con
> cobertura empírica ≥ 90 % del intervalo nominal, antes del `[FECHA]`.

Meta secundaria, habilitada por la anotación horaria de quiebres del dataset: **reducir el
sesgo de demanda re-censurada** respecto de entrenar directamente sobre la venta observada.
Es medible porque la censura viene etiquetada, y es la parte que casi ningún proyecto de
forecasting hace (ver 0.2.4).

---

## 2. Cobertura de módulos

El proyecto integra los siete módulos. Esta tabla va en la presentación, porque responde
por adelantado la pregunta de si el trabajo es integrador o parcial.

| Módulo | Componente del proyecto |
|---|---|
| M1 · Fundamentos y entorno | Repo reproducible, entorno versionado, desarrollo asistido por IA, CI |
| M2 · Datos y pipelines | EDA, imputación, escalado, encoding, feature engineering, `Pipeline` de sklearn |
| M3 · ML supervisado | LightGBM, XGBoost, regresión regularizada, CV temporal, Optuna, SHAP |
| M4 · No supervisado | Clustering de perfiles de demanda, PCA y UMAP, Isolation Forest y autoencoder |
| M5 · Deep learning | GRU y LSTM en PyTorch, regularización, LR scheduling, early stopping |
| M6 · Series temporales | SARIMA, Prophet, transformer temporal, backtesting, anomalías secuenciales |
| M7 · Integrador | API, frontend, Docker, ROI, documentación, defensa |

---

## 3. Estructura de entrega

Definido en la conversación previa. El corte entre público y privado **no** es básico
contra avanzado. Es **método contra producto**.

### 3.1 Repo público · `demand-forecasting-core`

Entregable del diplomado y prueba pública de rigor de modelado. Se hace completo. No se lo
llama "lite" ni interna ni externamente. Se lo llama **core** o **implementación de
referencia**. Licencia MIT o Apache 2.0.

### 3.2 Repo privado · Fase 2, después de la defensa

Depende del core como **paquete instalable**, no lo copia. Las mejoras del core fluyen al
producto y se demuestra diseño de librería, que es señal adicional de currículum.

Contiene lo que sí tiene valor comercial: abstracción multi-tenant, arranque en frío con
embeddings por tenant, adaptadores al esquema real del ERP, features de dominio surgidas
de feedback real, loop de reentrenamiento con drift, API que consume Focal Point,
calibración de costo de quiebre por cliente.

### 3.3 Case study

Enlaza el repo público y describe el privado. Dos reglas innegociables:

1. Solo se describe lo que existe y funciona. Lo planeado va bajo el encabezado **Roadmap**.
2. Cada feature privada mencionada lleva una métrica o resultado concreto. Sin número, es
   marketing.

---

## 4. Decisión de datos · RESUELTA

Decidido 2026-09-14 sobre la investigación de la sección 0.2. Esta sección reemplaza la tabla
de opciones A/B/C que contenía antes, donde el generador sintético figuraba como fuente
primaria.

El programa exige un caso real de la organización del participante. La resolución usa **dos
fuentes con roles distintos**, lo que satisface el requisito y además aporta algo que una sola
fuente no puede dar.

| Fuente | Rol | Qué aporta |
|---|---|---|
| **FreshRetailNet-50K** | Caso **primario** · desarrollo y validación del método | Datos reales de perecederos, censura de quiebres etiquetada hora por hora, doble jerarquía, clima, y **baselines publicados** contra los que compararse |
| **Generador sintético calibrado a Focal Point** | Caso **secundario** · aplicación a la organización propia | Jerarquía y feriados paraguayos, requisito de "caso real de la organización", puente a la Fase 2 |

**Por qué en ese orden.** El generador era la pieza más costosa y más riesgosa del camino
crítico; moverlo fuera de él libera la ventana de trabajo. Y un "20 % de MASE" medido contra
un baseline propio es autoevaluación, mientras que medido sobre un benchmark público con
baseline oficial publicado es un resultado comparable. La secuencia a defender es: **método
validado en benchmark público, aplicado después a la estructura de la organización propia.**

Nada de esto expone datos de terceros: FreshRetailNet es CC BY 4.0 y el caso Focal Point es
sintético. Eso se declara explícitamente en README y presentación — es fortaleza metodológica,
no excusa, y el panel valora que no expongas datos de terceros.

### 4.1 Dos condiciones que hay que resolver, no ignorar

1. **Normalización.** `sale_amount` y `hours_sale` vienen multiplicados por un coeficiente no
   divulgado. Las métricas de exactitud (MASE, WAPE, pinball, cobertura) son válidas tal cual;
   el **ROI monetario no**. Ver la nota de la sección 11.
2. **Volumen.** 4,85 M filas exceden la ventana de trabajo y el host disponible. Submuestrear a
   ~2.000-5.000 series por ciudad o por grupo de categorías, con **semilla fija**, y declarar
   el submuestreo. Es una decisión de alcance declarada, no un recorte oculto.

### 4.2 Calibración del generador · caso Focal Point secundario

Se versiona con semilla fija. Es lo que hace reproducible el caso propio por cualquiera, que
es justamente lo que tiene que probar. Debe reproducir lo que hace difícil el problema real,
no una serie limpia:

- Jerarquía producto → categoría → sucursal → total
- Estacionalidad semanal y mensual, más efecto de fin de mes por cobro de sueldos
- Feriados paraguayos
- Cola larga de baja rotación con muchos ceros
- Quiebres de stock que censuran la demanda observada
- Vida útil del lote, que vuelve el sobre-stock pérdida total y no capital inmovilizado
- Promociones con elasticidad
- Altas y bajas de productos, lo que genera arranque en frío
- Ruido y outliers de carga, para que el subsistema de anomalías tenga qué detectar

**Ventaja metodológica que el dataset real no da:** en el generador el proceso generador es
conocido, así que se puede verificar que el modelo recupera lo que se inyectó — por ejemplo,
que SHAP encuentra la estacionalidad semanal cuya amplitud se fijó a mano. Eso es
verificación, no fe, y es un argumento de defensa distinto del que aporta el benchmark
público.

---

## 5. Metodología · el corazón de la defensa

### 5.1 Validación

- Split **estrictamente temporal**, nunca aleatorio
- **Backtesting de origen móvil**, ventana expansiva, mínimo 8 orígenes
- **Gap** entre fin de train y comienzo de test igual al horizonte
- Escalado, imputación y encoding **dentro** del `Pipeline`, ajustados solo con el train de
  cada fold
- Métricas reportadas con dispersión entre orígenes, no como número único

### 5.2 Checklist antifugas · implementado como tests

Esto es lo que vuelve verificable la afirmación de rigor. Un README que dice "evité
leakage" no prueba nada. Un test que falla si hay fuga, sí.

- [ ] Ningún feature usa información posterior a `t`
- [ ] Lags y rolling calculados por grupo, ordenados por fecha
- [ ] Sin agregados calculados sobre el dataset completo
- [ ] Sin target encoding con datos del futuro
- [ ] El escalador se ajusta solo en train de cada fold
- [ ] **Test de shuffle:** al permutar el target, la métrica colapsa al nivel del baseline
- [ ] **Test de futuro:** desplazar el horizonte no mejora la métrica
- [ ] **Test de fold:** ningún índice de test aparece en el train de su propio fold

### 5.3 Métricas

| Métrica | Para qué |
|---|---|
| MASE | Principal. Libre de escala, compara contra el ingenuo estacional |
| WAPE | Lectura de negocio, ponderada por volumen |
| Pinball loss | Evalúa los cuantiles, no solo la media |
| Cobertura empírica | Valida el intervalo conformal contra su nivel nominal |
| Ancho medio del intervalo | Un intervalo que cubre por ser enorme no sirve |

MAPE queda excluido a propósito, porque explota con demanda cercana a cero, que es
exactamente la cola de productos. Decirlo en la defensa suma.

### 5.4 Baselines

Sin baseline honesto cualquier número es decorativo.

1. Naive, último valor observado
2. Naive estacional, mismo día de semana anterior
3. Media móvil de k semanas
4. Croston para series intermitentes de la cola

El denominador de MASE usa el naive estacional. Si el modelo no gana en algún segmento, se
reporta igual, con análisis por banda de rotación. Un proyecto que dice "el modelo complejo
no supera al ingenuo en baja rotación" es más creíble que uno con mejoras uniformes — y en
este caso además está **publicado** que eso pasa en intermitencia extrema (ver 0.2.2), así que
es un resultado esperado y no un fracaso.

**Baseline externo, además de los cuatro propios.** FreshRetailNet trae un pipeline oficial de
entrenamiento y evaluación ([frn-50k-baseline](https://github.com/Dingdong-Inc/frn-50k-baseline)).
Compararse contra él convierte el "20 % de MASE" de autoevaluación en resultado comparable con
un tercero, que es la diferencia que más pesa en la defensa.

---

## 6. Modelos

Todos entran. Se entrenan en paralelo contra el mismo arnés de backtesting, así la
comparación es directa.

### Clásicos y estadísticos

- **Baselines** los cuatro
- **Regresión regularizada** Ridge, Lasso, ElasticNet sobre features de calendario, como
  puente con M3
- **SARIMA** sobre series agregadas por sucursal y total
- **Prophet** como alternativa con estacionalidad múltiple y feriados

### Gradient boosting

- **LightGBM global**, un modelo para todas las series, con lags, rolling stats, calendario,
  jerarquía como categóricas nativas. Es el que gana en la práctica y el que escala.
- **XGBoost** como contraste
- **LightGBM cuantílico** para los cuantiles de la capa de decisión
- **Optuna** para optimización de hiperparámetros, con el search dentro de la validación
  temporal, nunca sobre el test

### Deep learning

- **GRU y LSTM** en PyTorch, multi-serie con embedding de producto y sucursal
- **Transformer temporal** ligero, tipo encoder con atención sobre la ventana
- Regularización, LR scheduling y early stopping, que cubre M5 explícitamente

Si el deep learning pierde contra LightGBM, ese es el resultado y se reporta con
explicación. Con series cortas y muchas de ellas es el desenlace esperable, y explicarlo
bien vale más que forzar una victoria.

---

## 7. Aprendizaje no supervisado

Cubre M4 y aporta valor real al sistema, no es relleno.

- **Clustering de perfiles de demanda** con K-Means y DBSCAN sobre features de forma de la
  serie. Los clusters entran como feature al modelo global y mejoran el arranque en frío.
- **PCA y UMAP** para visualizar el espacio de productos en el dashboard
- **Detección de anomalías** con Isolation Forest y autoencoder en PyTorch sobre ventanas de
  demanda, para marcar cargas erróneas y quiebres antes de que contaminen el entrenamiento
- **Anomalías secuenciales** sobre el residuo del pronóstico, que es lo que detecta el
  evento que el modelo no vio venir

---

## 8. Capa de decisión · el diferencial

Nada de esto aparece en los notebooks del diplomado. Lo verifiqué buscando en todo el
material. Es donde el proyecto se despega del promedio de la cohorte.

> **Encuadre corregido 2026-09-14 (ver 0.2.3).** El cruce conformal + newsvendor **sí existe
> en la literatura reciente** — Cao (dic-2024) conformaliza el cuantil crítico, y hay un
> resultado que prueba que los pronósticos cuantílicos calibrados son *equivalentes* a la
> solución óptima del newsvendor. Por lo tanto: **no reivindicar invención, reivindicar
> aplicación.** El discurso correcto es "apliqué un resultado reciente de la literatura que
> casi nadie implementa en producción, y acá está corriendo", citando ambos papers. El
> diferencial **frente a la cohorte** sigue intacto; la afirmación de novedad absoluta no.

### 8.0 Recuperación de demanda censurada · el paso previo

Va primero porque contamina todo lo que sigue. Cuando hubo quiebre de stock, la venta
registrada es cero pero la demanda real no lo era; entrenar sobre la venta observada produce
el **efecto spiral-down**: se pide de menos → hay más quiebres → se observa menos demanda →
se pide de menos todavía. FreshRetailNet anota el quiebre hora por hora, así que la
corrección se puede **medir** en vez de solo afirmar.

Enfoque: tratar las horas en quiebre como observaciones censuradas por la derecha y estimar
la demanda latente antes de construir features de lag y rolling. Referencia citable: Tobit
Exponential Smoothing con agregación temporal (0.2.4). Métrica de esta pieza: **sesgo de
demanda re-censurada**, comparado contra el modelo entrenado sobre venta observada cruda.

### 8.1 Conformal por partición

Intervalos con cobertura garantizada sin supuestos distribucionales.

1. Partir train en entrenamiento y calibración
2. Residuos absolutos sobre calibración
3. Cuantil `1 - alpha` de esos residuos
4. Intervalo igual a predicción más y menos ese cuantil
5. Verificar cobertura empírica en test contra el nivel nominal

Variante **conformal adaptativo** normalizando el residuo por una estimación de dispersión,
para que series volátiles reciban intervalos más anchos que series estables. Es barato y se
nota en el gráfico.

Implementación: Nixtla `statsforecast` ya trae conformal (0.2.6), así que no hace falta
escribirlo desde cero — el tiempo ahorrado va a la validación de cobertura, que es lo que
realmente se defiende.

### 8.2 Newsvendor · del pronóstico a la orden de compra

El pronóstico puntual no dice cuánto pedir. La economía sí. Con `Cu` el costo de quedarse
corto, o sea margen perdido, y `Co` el de quedarse largo, que en perecederos es **pérdida
total al vencimiento y no solo capital inmovilizado**, el cuantil óptimo es la fracción
crítica:

```
q* = Cu / (Cu + Co)
```

Se entrena LightGBM con pérdida cuantílica en `q*` y esa predicción **es** la cantidad a
reponer. El modelo deja de emitir un número abstracto y emite una orden.

### 8.3 Reconciliación jerárquica

Pronósticos coherentes con **MinT**. FreshRetailNet trae **dos jerarquías reales**, así que la
reconciliación no es un adorno sobre una jerarquía inventada:

- Geográfica: `city_id > store_id`
- De catálogo: `management_group_id > first_category_id > second_category_id > third_category_id > product_id`

Resuelve un conflicto que existe en toda empresa, donde finanzas proyecta el agregado y
operaciones el detalle, y los números no cierran. Se compara contra bottom-up y top-down.

### 8.4 Política y simulación

Simulador de política de reposición sobre las ventanas del backtest, que compara la política
actual contra la del modelo y produce el costo esperado de cada una. Es la base del ROI y
alimenta el dashboard.

---

## 9. Explicabilidad y confianza

- **SHAP** sobre el LightGBM global: importancia global, dependencia parcial de las
  variables dominantes, waterfall de una predicción concreta elegida para contar una
  historia de negocio
- **Calibración de intervalos** graficada, cobertura nominal contra empírica
- **Detección de drift** con PSI y Kolmogorov-Smirnov entre ventanas, más una vista de
  degradación de métrica por origen de backtest, que responde cuánto dura el modelo antes
  de necesitar reentrenamiento
- **Model card** en `docs/`, con datos, supuestos, limitaciones y uso previsto. Conecta con
  el eje de ética y AI Act del programa.

---

## 10. Arquitectura de despliegue

Se entregan dos superficies. La de Streamlit satisface el requisito literal del programa y
es la red de seguridad. La de React es la que se muestra en la defensa.

```
┌──────────────────────┐     ┌─────────────────────┐
│  Frontend React/TS   │────▶│   FastAPI           │
│  Vite + Tailwind     │     │   /forecast         │
│  Recharts            │     │   /reorder          │
└──────────────────────┘     │   /anomalies        │
                             │   /explain          │
┌──────────────────────┐     │   /backtest         │
│  Streamlit fallback  │────▶│   /health           │
└──────────────────────┘     └─────────────────────┘
                                       │
                             ┌─────────▼───────────┐
                             │ Artefactos joblib   │
                             │ + checkpoints torch │
                             └─────────────────────┘

Todo orquestado con Docker Compose.
```

### Pantallas del dashboard

1. **Vista general.** KPI de error contra baseline, cobertura, ahorro proyectado, número de
   series en alerta
2. **Serie individual.** Histórico, pronóstico, banda conformal, marcas de anomalía,
   **tramos de quiebre sombreados con la demanda latente recuperada superpuesta**, selector
   de ciudad, tienda y producto
3. **Reposición.** Tabla de cantidades sugeridas ordenada por impacto, con filtro por tienda
   y por banda de rotación. El impacto se expresa en **unidades y en porcentaje de costo
   esperado**, no en guaraníes, salvo en la vista del caso Focal Point (ver sección 11)
4. **Comparativa de modelos.** Métricas por origen de backtest, con dispersión, y ranking.
   Incluye la fila del **baseline oficial del dataset** como referencia externa
5. **Explicabilidad.** SHAP global y waterfall de la predicción seleccionada
6. **Mapa de productos.** Proyección UMAP coloreada por cluster de perfil de demanda
7. **Salud del modelo.** Drift, degradación por horizonte, fecha sugerida de reentrenamiento

### Diseño

El frontend se hace con criterio visual, no con componentes por defecto. Paleta propia,
tipografía elegida, densidad de información alta pero legible, modo claro y oscuro. Es el
artefacto que el panel recuerda y el que va al case study.

---

## 11. ROI

> **Condición bloqueante (ver 0.2.1).** En FreshRetailNet-50K `sale_amount` y `hours_sale`
> están multiplicados por un **coeficiente no divulgado**, así que del dataset primario NO se
> puede derivar ahorro monetario directo. Dos salidas válidas, y hay que elegir una
> explícitamente:
>
> 1. **ROI relativo sobre el caso primario:** reportar la mejora en **porcentaje** de costo
>    esperado, merma y nivel de servicio, sin convertir a guaraníes. Honesto y suficiente.
> 2. **ROI monetario sobre el caso secundario:** calcular guaraníes solo sobre el generador
>    calibrado a Focal Point, donde las magnitudes las fijás vos y son declarables.
>
> Lo que **no** es válido es presentar guaraníes derivados del dataset normalizado. Sería un
> número sin origen, y es exactamente lo que el panel pregunta.

La cuenta sale de la misma economía que define el cuantil, así que no es un número inventado
al final.

```
Ahorro anual = Σ_sku [ Costo_esperado(política_actual) - Costo_esperado(política_modelo) ]

Costo_esperado = Cu × E[faltante] + Co × E[sobrante]
```

Ambos términos se estiman empíricamente sobre las ventanas del backtest, no con fórmula
cerrada. La política actual se modela como reposición según promedio reciente, que es lo que
hace la mayoría de las pymes.

**Supuestos declarados explícitamente**, porque el panel los va a pedir:

- Margen unitario promedio por categoría
- Costo de capital y tasa de merma
- Volumen anual y número de SKU activos
- Fracción de la mejora efectivamente capturada, que nunca es 100 %

Se reporta un **rango** con análisis de sensibilidad sobre esos cuatro supuestos, más el
caso pesimista. Un rango con supuestos visibles convence más que un número único sin origen.

### 11.1 Anclas publicadas para los supuestos

Estos números vienen de CADRE medido sobre el mismo dataset (0.2.4) y sirven para que los
supuestos sean **citables en vez de inventados** — que es la diferencia entre un ROI defendible
y uno decorativo:

| Indicador | Política censurada | Con recuperación de demanda |
|---|---|---|
| Merma | 9,8 % | 6,4 % |
| Nivel de servicio | 92,9 % | 94,7 % |
| Sesgo de demanda re-censurada | −8,1 % | −1,3 % |
| WAPE | 39,42 % | 36,71 % |

Referencia adicional de orden de magnitud para el puente accuracy → negocio: se reporta que
**10 % de mejora en exactitud de pronóstico ≈ 1,5 % de mejora en disponibilidad de stock**.
Útil como sanity check: si tu ROI implica un salto de disponibilidad mucho mayor que eso, algún
supuesto está inflado.

---

## 12. Estructura del repo

```
demand-forecasting-core/
├── README.md
├── LICENSE
├── pyproject.toml
├── docker-compose.yml
├── Makefile
├── .github/workflows/ci.yml
├── data/
│   ├── raw/                      # gitignored
│   └── synthetic/                # generador versionado, semilla fija
├── src/dfcore/
│   ├── data/
│   │   ├── generator.py          # caso secundario Focal Point
│   │   ├── freshretail.py        # caso primario: carga + submuestreo con semilla
│   │   ├── loaders.py
│   │   └── schema.py             # contrato de datos, común a ambas fuentes
│   ├── features/
│   │   ├── calendar.py
│   │   ├── lags.py
│   │   └── build.py
│   ├── validation/
│   │   ├── splits.py             # origen móvil
│   │   └── leakage.py            # asserts antifugas
│   ├── models/
│   │   ├── base.py               # interfaz común
│   │   ├── baselines.py
│   │   ├── linear.py
│   │   ├── gbdt.py               # LightGBM, XGBoost, cuantílico
│   │   ├── statistical.py        # SARIMA, Prophet
│   │   ├── recurrent.py          # GRU, LSTM
│   │   ├── transformer.py
│   │   └── tuning.py             # Optuna
│   ├── unsupervised/
│   │   ├── clustering.py
│   │   ├── embedding.py          # PCA, UMAP
│   │   └── anomaly.py            # IsolationForest, autoencoder
│   ├── decision/
│   │   ├── censoring.py          # recuperación de demanda latente (8.0)
│   │   ├── conformal.py
│   │   ├── newsvendor.py
│   │   ├── reconciliation.py     # MinT, dos jerarquías
│   │   └── policy.py             # simulador
│   ├── evaluate/
│   │   ├── metrics.py
│   │   ├── backtest.py
│   │   └── drift.py
│   └── explain/shap_report.py
├── api/
│   ├── main.py                   # FastAPI
│   └── schemas.py                # contrato Pydantic
├── frontend/                     # React + TS + Vite + Tailwind
│   ├── src/
│   └── package.json
├── app/streamlit_app.py          # fallback
├── notebooks/
│   ├── 01_eda.ipynb
│   ├── 02_features_validacion.ipynb
│   ├── 03_modelos_backtest.ipynb
│   ├── 04_no_supervisado.ipynb
│   ├── 05_decision_conformal.ipynb
│   └── 06_roi.ipynb
├── tests/
├── docs/
│   ├── model_card.md
│   └── arquitectura.md
└── reports/
    ├── metrics.md
    └── roi.md
```

---

## 13. Estrategia de ejecución paralela

La clave para que el alcance completo entre en la ventana es **definir contratos primero y
recién después abrir frentes en paralelo**. Sin contratos, los agentes producen piezas que
no encajan y se pierde más tiempo integrando del que se ganó paralelizando.

### Contratos a congelar en la primera hora

1. **Esquema de datos**, en `src/dfcore/data/schema.py`. Columnas, tipos, granularidad,
   claves de jerarquía.
2. **Interfaz de modelo**, en `src/dfcore/models/base.py`. Métodos `fit`, `predict`,
   `predict_quantile`, y formato del artefacto serializado.
3. **Contrato de backtest.** Forma exacta del DataFrame de resultados que todo modelo
   devuelve, para que las métricas y el dashboard consuman lo mismo.
4. **Contrato de API**, en `api/schemas.py`. Los modelos Pydantic de request y response.
   Con esto el frontend arranca contra datos simulados sin esperar al backend.

### Frentes paralelizables

| Frente | Depende de | Puede correr en paralelo con |
|---|---|---|
| A · Carga y submuestreo de FreshRetailNet + EDA | Esquema | Todos |
| A2 · Recuperación de demanda censurada | Esquema + A | C, G, H, I |
| B · Features y validación | Esquema + **A2** | C, G, H, I |
| C · Modelos | Interfaz de modelo | B, E, G, H, I |
| D · Capa de decisión | Contrato de backtest | E, F, H, I |
| E · No supervisado | Esquema | C, D, G, H |
| F · SHAP y drift | Un modelo entrenado | D, H, I |
| G · API FastAPI | Contrato de API | H, I |
| H · Frontend React | Contrato de API | Todos |
| I · Docker, CI, tests | Nada | Todos |
| J · Docs, ROI, slides | Resultados | Todos |
| K · Generador sintético Focal Point (caso secundario) | Esquema | Todos — **fuera del camino crítico** |

**Camino crítico:** esquema → carga y submuestreo → **recuperación de censura** → features →
LightGBM → backtest → decisión → ROI. Todo lo demás es paralelo. El frontend, que suele ser el
que preocupa, no está en el camino crítico porque arranca contra el contrato con datos
simulados. El generador sintético tampoco: pasó a ser el frente K, opcional en el sentido de
que su retraso no bloquea nada, aunque sí es necesario para el requisito de organización
propia y para el ROI monetario.

**Dependencia nueva que es fácil de romper:** B depende de A2, no de A. Construir lags y
rolling sobre la venta observada cruda y recién después corregir la censura invalida las
features. El orden importa.

### Red de seguridad

- **Tag cada noche.** `v0.1-datos`, `v0.2-modelos`, `v0.3-decision`, `v1.0-defensa`. Si algo
  se rompe el viernes, se defiende el tag anterior.
- **Video del demo grabado el jueves.** Si el deploy falla en vivo, se muestra el video y se
  sigue. Esto elimina el único riesgo que puede arruinar la defensa.
- **Streamlit siempre funcionando.** Es la superficie mínima que satisface el requisito
  literal, y no depende del frontend.

---

## 14. Cronograma

> **OBSOLETO — re-fechar.** Este cronograma fue escrito para la ventana 8-11 de septiembre de
> 2026, ya pasada. La **secuencia** de trabajo sigue siendo válida y es lo que hay que
> conservar; las fechas no. Dos cambios de fondo respecto de la versión original:
>
> 1. El **generador ya no está en el camino crítico** (ver 4). La primera noche pasa a ser
>    carga y submuestreo de FreshRetailNet, EDA, baselines y arnés de backtesting.
> 2. Se agrega un paso que antes no existía: **recuperación de demanda censurada** (8.0), que
>    va ANTES de construir features de lag y rolling, porque si no se entrena sobre demanda
>    sesgada.
>
> Camino crítico actualizado: esquema → carga y submuestreo → **recuperación de censura** →
> features → LightGBM → backtest → decisión → ROI.

### Día 1 · noche

- Cerrar la decisión de datos (ya resuelta, ver 4)
- Repo, `pyproject.toml`, CI mínima, estructura de directorios
- **Congelar los cuatro contratos**
- Carga de FreshRetailNet, submuestreo con semilla fija, EDA
- Baselines y módulo de métricas
- Arnés de backtesting de punta a punta

Cierre: un MASE de baseline impreso. Tag `v0.1-datos`.

### Día 2 · tutoría de deploy

Antes de la tutoría:

- **Recuperación de demanda censurada** (8.0) — va primero, antes de las features
- Features completas: lags, rolling, calendario, feriados, jerarquía
- Tests antifugas, incluido shuffle
- LightGBM global entrenado y backtesteado
- Serializar artefacto, porque la tutoría es de deploy y conviene llegar con modelo listo

En paralelo, frentes independientes:

- API FastAPI contra el contrato
- Scaffold del frontend con datos simulados
- Docker Compose

Después de la tutoría: XGBoost, lineales, Optuna. Tag `v0.2-modelos`.

### Día 3 · día completo

- SARIMA, Prophet
- GRU, LSTM, transformer temporal
- Conformal, newsvendor, reconciliación MinT sobre las dos jerarquías, simulador de política
- Clustering, UMAP, anomalías
- SHAP y drift
- Comparación contra el baseline oficial del dataset
- Frontend conectado al backend real, las siete pantallas
- **Grabar el video del demo**

Tag `v0.3-decision`.

### Día 4 · hasta la defensa

- Integración final y revisión de números
- Reporte de ROI con sensibilidad, en la modalidad elegida (relativo o monetario, ver 11)
- Generador Focal Point si no se hizo antes (frente K)
- README, model card, documentación de arquitectura
- Slides
- Dos ensayos cronometrados
- **Congelar el repo al mediodía.** Nada de commits después. Tag `v1.0-defensa`.

---

## 15. Defensa

### Estructura, quince minutos

1. Problema de negocio y costo actual · 2 min
2. Datos: benchmark público de perecederos con censura anotada, más el caso propio sintético
   y por qué esa combinación · 1 min
3. Validación y antifugas · 3 min, es el corazón técnico
4. Resultados contra baselines, con dispersión entre orígenes · 3 min
5. De predicción a decisión: conformal, newsvendor, reconciliación · 3 min
6. Demo en vivo · 2 min
7. ROI, limitaciones y roadmap · 1 min

### Preguntas esperadas, con la respuesta lista

- ¿Cómo evitaste fugas? → mostrar el test de shuffle corriendo
- ¿Por qué ese baseline? → naive estacional es el estándar en demanda, y además se compara
  contra el baseline oficial publicado del dataset
- ¿Por qué MASE y no MAPE? → MAPE explota con demanda cercana a cero
- **¿Por qué no usaste datos de tu propia empresa?** → los uso: el caso Focal Point es el
  secundario y es sintético por confidencialidad de clientes. El primario es un benchmark
  público porque permite comparar contra baselines publicados en vez de autoevaluarme
- **¿Los quiebres de stock no te sesgan la demanda?** → sí, y es la primera cosa que corrijo;
  el dataset anota el quiebre hora por hora, así que la corrección se mide. Nombrar el efecto
  spiral-down
- **¿Esto de conformal + newsvendor es tuyo?** → no, es literatura reciente (Cao 2024, y el
  resultado de equivalencia entre cuantiles calibrados y newsvendor óptimo). Lo que aporto es
  la implementación corriendo end-to-end, que es lo raro
- **¿Por qué el ROI no está en guaraníes?** → porque el dataset primario está normalizado por
  un coeficiente no divulgado; los guaraníes salen del caso Focal Point, con supuestos
  declarados
- ¿Qué hacés con productos nuevos? → cluster de perfil como prior, y arranque en frío por
  embeddings en el roadmap
- ¿Cómo elegiste el cuantil de reposición? → fracción crítica del newsvendor, con `Co` de
  pérdida total por vencimiento y no de capital inmovilizado
- ¿Qué supuestos tiene el ROI? → los cuatro de la sección 11, anclados en números publicados,
  con rango y caso pesimista
- ¿Cuánto dura el modelo? → curva de degradación por origen de backtest
- ¿Los pronósticos de tienda suman el total? → sí, por reconciliación MinT, sobre las dos
  jerarquías del dataset
- ¿Por qué el deep learning no ganó? → series cortas y numerosas, el modelo global comparte
  estructura entre ellas
- ¿Usaste IA para programar? → sí, es eje del programa; explicar la estrategia de contratos
  y frentes paralelos

Declarar las limitaciones antes de que las encuentre el panel. Cambia el tono de la sesión
entera.

---

## 16. Fase 2 · después de la defensa

No empezar antes. En orden:

1. Publicar el core como paquete instalable
2. Repo privado que lo consume como dependencia
3. Adaptadores al esquema real de Focal Point
4. Multi-tenant y arranque en frío por embeddings
5. Reentrenamiento automático con drift
6. Case study en francocazal.com enlazando el core y describiendo el privado con métricas

---

## 17. Riesgos

| Riesgo | Mitigación |
|---|---|
| ~~No hay datos reales disponibles~~ | **RESUELTO 2026-09-14.** FreshRetailNet-50K como caso primario (ver 4) |
| El ROI no se puede expresar en dinero por la normalización del dataset | Elegir explícitamente ROI relativo en el caso primario o ROI monetario solo en el caso Focal Point (ver 11) |
| Existe un paper publicado con casi este mismo proyecto sobre el mismo dataset | Leerlo antes de congelar alcance y **citarlo primero**; el entregable es un diplomado, no una reivindicación de novedad (ver 0.2.5) |
| El volumen del dataset (4,85 M filas) no entra en la ventana ni en el host | Submuestreo declarado con semilla fija a ~2.000-5.000 series (ver 4.1) |
| Reivindicar novedad de conformal + newsvendor y que el panel conozca la literatura | Encuadre corregido: aplicación, no invención, con ambas citas (ver 0.2.3 y 8) |
| El modelo no supera al baseline | Se reporta igual, con análisis por banda de rotación; en intermitencia extrema está publicado que pasa (ver 0.2.2) |
| El deploy falla en la defensa | Video grabado con anticipación, más Streamlit como fallback |
| Integración tardía entre frentes | Contratos congelados en la primera hora |
| Algo se rompe el último día | Tag por noche, se defiende el último estable |
| Prophet o pmdarima fallan al instalar | Aislados en módulo opcional, no bloquean el camino crítico |
| Sobrecarga la noche previa a la tutoría de deploy | Llegar con el artefacto ya serializado |
