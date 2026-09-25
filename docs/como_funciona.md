# Cómo funciona Blindside, de punta a punta

Documento de orientación: qué datos entran, qué se les hace, qué modelos corren y qué sale.
Todos los números de acá están verificados contra el código y los reportes en `reports/`, no
citados de memoria. Si algo cambia en el pipeline, este documento queda viejo — la fuente de
verdad son los reportes generados.

Para las decisiones y sus alternativas descartadas, ver `docs/decisiones.md` (D1–D24). Para el
resumen de resultados, el README.

---

## 1 · El dataset y qué le hacemos

### Qué es

[FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K), de
Dingdong-Inc, un retailer chino de fresco. El original trae 50.000 series; el proyecto
submuestrea a **3.066** eligiendo **tiendas completas** al azar con semilla 42 — completas para no
romper las jerarquías, porque tomar productos sueltos dejaría tiendas a medias y rompería
cualquier agregación por tienda.

| Atributo | Valor |
|---|---|
| Filas | 297.402 |
| Columnas | 25 |
| Series (tienda × producto) | 3.066 |
| Tiendas | 38, en 2 ciudades |
| Productos | 309 |
| Ventana | 2024-03-28 a 2024-07-02 (**97 días**) |
| Series por tienda | 80,7 en promedio |
| Tiendas por producto | 9,9 en promedio |

Una **serie** es un par tienda × producto. Cada fila es un día de una serie. El panel es
**denso**: hay una fila por día por serie, sin huecos.

### Las columnas

| Grupo | Columnas |
|---|---|
| Claves | `series_id`, `dt`, `store_id`, `product_id` |
| Jerarquía | `city_id`, `management_group_id`, `first/second/third_category_id` |
| Objetivo | `sale_amount` (venta observada), `demand_latent` (derivada) |
| **Quiebre** | `is_censored`, `oos_hours_day`, `stock_hour6_22_cnt`, `hours_stock_status` (hora por hora) |
| Comercial | `discount`, `holiday_flag`, `activity_flag` |
| Clima | `precpt`, `avg_temperature`, `avg_humidity`, `avg_wind_level` |

### Imputación: no hay, y es verificable

El panel tiene **cero nulos** en las 25 columnas, y no hay un solo `fillna`, `dropna` ni
`interpolate` en todo `src/blindside/features/`. El dataset viene limpio.

### Pero sí hay una transformación grande, y es el corazón del proyecto

No es imputar valores **faltantes**. Es corregir valores **presentes pero mentirosos**.

Cuando un producto se agota, la venta registrada es 0 — pero la demanda no era 0. La gente la
quiso y no había. Entrenar sobre eso produce el **efecto spiral-down**: se pide de menos, hay más
quiebres, se observa menos demanda, se pide de menos todavía. El sesgo equivalente en decisores
humanos está documentado ([Tong, Feiler y Larrick 2018](https://journals.sagepub.com/doi/10.1111/poms.12823)).

**Cómo se corrige.** El dataset anota el quiebre **hora por hora**. `HourlyProfileRecovery` mira
las horas en que sí había stock, estima con eso el perfil de demanda intradiario del día, y calcula
cuánta masa de demanda se perdió en las horas de quiebre. Eso produce `demand_latent`, la columna
contra la que se entrena.

Dos límites que no se negocian:

- La demanda latente **nunca** es menor que la venta observada. La venta ocurrió.
- La inflación se topea en **×3**, y no se corrige nada si queda menos del **15 %** de la masa de
  demanda del día disponible. Sin ese tope, un día con 15 de 16 franjas en quiebre y una venta
  chica implicaría una demanda dieciséis veces mayor apoyada en un único dato. Se prefiere un sesgo
  residual conocido a una varianza inventada (D11).

**Y va antes de las features, no después** (D4). Un promedio móvil calculado sobre la venta
observada ya propagó el sesgo a todo lo que derive de él, y corregir después no lo deshace.

Hay un segundo recuperador, `TobitEWMARecovery`, que trata el día censurado como una observación
censurada por la derecha. Existe como contraste: si los dos métodos dan resultados parecidos, la
conclusión no depende del método.

**Cuánto vale la corrección.** Medido sobre 99.721 días limpios, el mismo modelo entrenado sobre
las dos bases:

| Entrenado sobre | Sesgo re-censurado |
|---|---|
| Venta observada | −18,19 % |
| Demanda latente | **−6,61 %** |

**11,57 puntos de reducción de sesgo.** Detalle en `reports/censoring_ablation.md`.

### El EDA

Está en `notebooks/01_eda.ipynb`, ejecutado y con salidas. Cinco secciones: qué hay en el panel,
cómo se distribuye la demanda, cuánta censura hay y dónde, verificación del supuesto de ventana
comercial, y el perfil intradiario que es el mecanismo de la corrección.

Dos cosas que salieron de ahí: el panel es denso y no ralo, y la ventana comercial de 16 franjas
reproduce el «≈20 % de horas en quiebre» que declara la ficha del dataset — 43,9 % de días con
quiebre × 7,0 horas promedio / 16 franjas = **19,2 %**. El código falla si las horas derivadas de
la máscara horaria no coinciden con la columna, así que el supuesto se verifica en cada corrida.

### El pipeline de entrenamiento

```
descarga → submuestreo con semilla → recuperación de censura → features
→ backtesting de origen móvil → métricas → artefacto serializado
```

```bash
make data       # descarga y submuestrea con semilla fija
make recover    # recupera la demanda censurada
make models     # backtest completo -> reports/metrics.md
make train      # serializa los dos artefactos
```

Las **73 features** del modelo, contadas del artefacto real:

| Tipo | Cuántas |
|---|---|
| Rezagos de la demanda | 27 |
| Calendario y plan comercial | 18 |
| Estadísticos móviles (medias, medianas, ratios) | 16 |
| Jerarquía (categóricas) | 7 |
| Historia de quiebres | 2 |
| Otras | 3 |

Todas **ancladas en el origen**: se calculan con información disponible hasta el día desde el que
se pronostica, nunca después. Ocho asserts antifugas lo verifican, y **cada uno tiene su fuga
inyectada a propósito** para probar que la detecta. Un test antifugas que pasa siempre, incluso con
fuga presente, es peor que no tenerlo.

---

## 2 · Qué modelos, y qué se predice

### Qué se predice

La **demanda latente diaria** de cada serie tienda × producto, para los **próximos 7 días**, con
intervalo de incertidumbre. Y eso se convierte en una **cantidad a pedir**.

| Modelo | Para qué |
|---|---|
| **LightGBM global cuantílico + CQR** | **El que se sirve.** Un solo modelo para las 3.066 series |
| LightGBM puntual | Referencia pareada del anterior |
| XGBoost, Ridge, Lasso, ElasticNet | Contraste de familia |
| Naive, naive estacional, medias móviles, Croston SBA | Baselines. El naive estacional es el denominador de MASE |
| SARIMA, Prophet | Contraste contra la tradición **por serie** |

### Lo distintivo no es el pronóstico, es el paso siguiente

Un pronóstico no dice cuánto pedir. Para eso hace falta la economía del negocio: con `Cu` el costo
de quedarse corto y `Co` el de quedarse largo — en perecederos, **pérdida total al vencimiento**,
no capital inmovilizado — la cantidad óptima es el **cuantil** `q* = Cu / (Cu + Co)` de la
distribución de demanda. Acá `q* = 0,625`.

Entonces el modelo se entrena con pérdida cuantílica **en ese cuantil**, y su salida **es** la
orden. No se predice un promedio para sumarle después un stock de seguridad heurístico.

El **CQR** encima calibra el intervalo para que «90 %» signifique 90 %. Mide **88,0 %**, y los dos
puntos de diferencia están declarados.

### Cómo se evalúa

**Backtesting de origen móvil.** Se para en un día, entrena solo con lo anterior, predice los 7
siguientes, compara. Después mueve el origen y repite — **8 veces**. Eso da 8 mediciones y se
reporta siempre la **dispersión entre ellas**, porque un promedio bueno puede esconder un origen
catastrófico y el catastrófico es el que pasa en producción.

Resultado principal: **MASE 0,8217 ± 0,0454**, peor origen 0,8790, **+25,3 %** contra el naive
estacional. El objetivo declarado era 20 %.

---

## 3 · ¿Todos los productos por igual, o por categoría?

**Un solo modelo para todos, pero que sabe de categorías.** Es la pregunta más fina, y la respuesta
es una decisión de arquitectura que conviene poder justificar rápido.

Se llama **modelo global**. En vez de entrenar 3.066 modelitos (uno por serie), se entrena **uno**
que ve todas. La ventaja es que una serie con poca historia aprende del patrón de las demás; un
modelo por serie con 97 días no aprende gran cosa.

Pero la jerarquía **sí entra**, como siete variables categóricas:

```
2 ciudades  →  38 tiendas
7 grupos  →  24 categorías  →  61 subcategorías  →  148 sub-subcategorías  →  309 productos
```

El modelo puede partir por cualquiera, así que aprende «los lácteos de la tienda 12 se comportan
así» sin que nadie se lo programe. Comparte fuerza estadística entre series y a la vez diferencia.

**Evidencia de que el global es la elección correcta acá.** Se midió contra la tradición por serie
sobre 400 series y los mismos 8 orígenes (`reports/metrics_classical.md`):

| Modelo | MASE |
|---|---|
| **LightGBM global** | **0,8386** |
| Croston SBA | 0,9032 |
| SARIMA `(1,0,1)(1,0,0)[7]` | 0,9136 |
| Media móvil 21 d | 0,9139 |
| Prophet | 0,9698 |

**SARIMA queda empatado con la media móvil de 21 días** y pierde contra Croston. Todo el aparato
ARIMA no compra nada sobre un promedio simple en este panel.

**Y agrupar por comportamiento no ayudó.** Se probó K-Means sobre forma de la demanda como feature:
efecto medio **+0,28 %** de MASE con oscilaciones de **±11 puntos** entre orígenes, o sea ruido. No
está en el modelo servido. La razón probable es que `product_id` y `store_id` ya identifican la
serie exactamente, así que el cluster es un resumen grueso de algo que el modelo ya tiene más
preciso. Detalle en D23.

---

## 4 · Para qué rubros sirve

El encaje natural pide **tres** condiciones:

1. **Demanda diaria por local y producto**, no mensual ni agregada.
2. **El faltante y el sobrante cuestan distinto**, y el sobrante es pérdida total o casi. Es lo que
   hace que el cuantil no sea 0,5.
3. **Se sabe cuándo hubo quiebre.** Sin esto la corrección de censura no se puede medir, aunque el
   resto del pipeline funciona igual.

**Encaja directo:** supermercados y fruterías (frutas, verduras, carnes, lácteos, panadería),
farmacias con cadena de frío, restaurantes y cafeterías con producción diaria, florerías, plantas
de producción de fresco.

**Encaja con ajustes:**

- Retail no perecedero: funciona, pero `Co` pasa a ser capital inmovilizado en vez de pérdida
  total, así que `q*` sube y el argumento económico se debilita.
- Repuestos y farmacia de baja rotación: la demanda es tan intermitente que Croston compite de
  igual a igual.
- E-commerce sin tienda física: no hay quiebre en góndola, así que el diferencial desaparece.

**No encaja:** demanda no diaria; lead times largos con múltiples escalones de depósito (no se
modela ni lead time ni multi-echelon); o donde el precio sea la variable de decisión — el modelo
usa el descuento como covariable pero **no** estima elasticidad, así que usarlo para fijar precios
daría una respuesta con forma correcta y sin fundamento.

---

## 5 · Actualización continua: hoy no, y qué falta

**Es un prototipo de lote.** Verificado en el código:

- El panel se carga **una vez al arrancar** la API (en el `lifespan`) y queda en memoria.
- De los **12 endpoints**, **ninguno escribe**. Son todos de consulta.
- Los volúmenes se montan en Docker como **solo lectura** en los servicios de consulta; solo el
  perfil `pipeline` escribe.
- Para incorporar datos nuevos hoy: regenerar las capas y reiniciar el contenedor.

**Qué falta para que sea continuo:**

- Endpoint de ingesta y recarga en caliente del panel.
- **Detección de drift** (M9). Hoy nada avisa si la distribución de entrada se corrió respecto de
  la del entrenamiento.
- Scheduler de reentrenamiento y versionado de artefactos.

**La arquitectura no se opone.** Los modelos ya se serializan y recargan, y la recuperación de
censura y las features son funciones puras sobre un DataFrame, así que correrlas incrementalmente
es un agregado y no una reescritura. Pero hoy no está.

---

## 6 · Cuánta data, y por qué 97 días importa

**97 días por serie**, del **2024-03-28 al 2024-07-02**: 90 de `train` + 7 de `eval` según el split
oficial del benchmark.

**Es un panel** (datos longitudinales): 3.066 series en paralelo, cada una de 97 puntos diarios,
todas sobre la misma ventana de calendario. No es una serie larga — son muchas cortas y
simultáneas, y eso es precisamente lo que favorece al modelo global.

**97 días es poco, y tiene tres consecuencias medidas:**

- **No hay estacionalidad anual que estimar.** Solo semanal. Es parte de por qué Prophet queda
  último entre los modelos con ajuste: sin ciclo anual se reduce a tendencia más estacionalidad
  semanal, que un rolling ya captura.
- **El horizonte bajó de 4 semanas a 7 días.** Con horizonte 28 caben como máximo 4 orígenes de
  backtest y la metodología exige 8: los dos requisitos eran incompatibles. Documentado en D8.
- **No se puede medir arranque en frío.** Las 3.066 series tienen *exactamente* 97 días, ninguna
  tiene menos de 21, y ninguna empieza a vender después del día 16. No hay una sola serie nueva,
  porque el dataset entrega ventanas completas por construcción. Por eso la feature de cluster,
  cuyo propósito declarado era justamente eso, no se pudo validar.

---

## Lo que el proyecto publica y no le conviene

Tres resultados negativos están reportados a propósito, porque son los que hacen creíble el resto:

| Qué se probó | Resultado | Dónde |
|---|---|---|
| Cluster de perfil como feature | +0,28 % con ±11 de dispersión: ruido. No se adopta | D23 |
| Búsqueda de hiperparámetros con Optuna | +0,49 %, menor que la dispersión. No se adopta | D24 |
| SARIMA como contraste per-serie | Empata con la media móvil de 21 días | D22 |

Y dos limitaciones declaradas: la cobertura del intervalo mide 88,0 % cuando el objetivo declarado
pedía ≥ 90 %, y la garantía conformal es **marginal, no condicional** — el 88 % global esconde
subgrupos peores, y por horizonte el paso 6 baja a 85,4 %.
