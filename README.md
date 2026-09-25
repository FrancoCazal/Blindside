# Blindside

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-en%20desarrollo-yellow)

Pronóstico de demanda de productos perecederos por tienda y producto, con **recuperación de
demanda censurada por quiebres de stock** y una **capa de decisión** que convierte el
pronóstico en una cantidad concreta a reponer.

> Los quiebres de stock te toman del lado ciego: la venta cae a cero y tu ERP no registra que
> hubo demanda. **Blindside recupera esa demanda antes de pronosticar.**

Proyecto final integrador · Diplomado en Machine Learning y Deep Learning Aplicado ·
FIUNA 2026.

---

## El problema

En el retail de perecederos la reposición se decide con reglas manuales basadas en el promedio
de las últimas semanas. Eso genera al mismo tiempo **quiebres** de productos que rotan y
**vencimiento** de lotes que no se vendieron: los dos errores conviven porque nadie estima la
incertidumbre, y el sobre-stock funciona como un seguro caro y ciego.

Hay un problema anterior que la mayoría de los pipelines ignora: cuando hubo quiebre de stock,
la venta registrada es cero pero la demanda real no lo era. Entrenar sobre la venta observada
produce el **efecto spiral-down** — se pide de menos, hay más quiebres, se observa menos
demanda, se pide de menos todavía. Este proyecto corrige eso primero y después pronostica.

## Qué entrega

No termina en una predicción. Termina en una **cantidad a pedir**, derivada de la economía del
negocio: con `Cu` el costo de quedarse corto y `Co` el de quedarse largo — que en perecederos
es pérdida total al vencimiento, no capital inmovilizado — el cuantil óptimo de reposición es
la fracción crítica `q* = Cu / (Cu + Co)`. El modelo se entrena con pérdida cuantílica en ese
`q*`, así que su salida **es** la orden.

## Demo

```bash
make app     # dashboard Streamlit, 7 pantallas
make api     # FastAPI en localhost:8000, /docs para el OpenAPI
make front   # frontend React en localhost:5173 (necesita la API arriba)
```

> **La API no tiene autenticación.** Es deliberado para el alcance del prototipo — bindea en
> `127.0.0.1` y corre detrás de Docker Compose — pero conviene decirlo en vez de dejarlo
> implícito: cualquiera que alcance el puerto puede consultar todos los pronósticos y todas las
> cantidades de reposición, que es información comercial sensible. Tampoco hay límite de tasa, y
> un `/forecast` de 500 series es una consulta costosa. **No exponer a una red pública sin agregar
> autenticación antes.** Para la Fase 2 multi-tenant es bloqueante: hace falta autenticación por
> tenant y aislamiento de datos.

> Pendiente: screenshot del dashboard + enlace al despliegue.

## Frontend

React + Vite + TypeScript en `frontend/`, dos pantallas hero y el cromo completo. La dirección
visual sale de `docs/design_handoff_dfcore/`; los datos, de la API.

```bash
make front-setup    # npm install
make front          # dev server en http://127.0.0.1:5173
make front-test     # vitest: logica pura + render con fetch simulado
make api-schema     # regenera los tipos TS desde el OpenAPI
```

**Los tipos no se escriben a mano**: `frontend/src/api/schema.d.ts` se genera del OpenAPI que
produce FastAPI, así que un rename en `api/schemas.py` rompe la compilación del front en vez de
romper la demo.

**El front llama a la API por HTTP, no por un proxy de Vite.** Un proxy volvería las llamadas
same-origin y esconderían un CORS mal configurado hasta el despliegue. Por eso la API publica un
allowlist explícito de orígenes (`BLINDSIDE_CORS_ORIGINS`, por defecto los puertos 5173 y 4173 de
Vite) y no un comodín: sin autenticación, `allow_origins=["*"]` significaría que cualquier página
abierta en el navegador del usuario puede leer los pronósticos de todas las tiendas.

El control central es el **toggle de censura**, y cambia la decisión y no solo el dibujo: hay
**dos artefactos**, uno entrenado sobre venta observada y otro sobre demanda latente, con la misma
arquitectura y los mismos hiperparámetros para que la comparación sea pareada. Medido sobre 25
series con `q* = 0,625`:

| Base | Pronóstico | Cantidad a pedir | Política actual | Δ de costo esperado |
|---|---|---|---|---|
| Venta observada | 190,229 | 210,958 | 231,960 | −14,09 % |
| Demanda recuperada | 238,413 | **268,478** | 278,596 | −8,64 % |

Corregir la censura sube el pronóstico **+25,3 %** y la orden **+27,3 %**. Con un solo artefacto el
toggle habría movido el gráfico y no la cantidad, que es la mitad del argumento del proyecto.

Las cuatro columnas salen de la API y ninguna se escribe a mano: el pronóstico es la suma de
`/forecast`, y la orden, la política y el delta vienen de `/reorder` — `qty`, `policy_qty` y
`total_cost_delta_pct`. La política es el promedio móvil de 21 días **de la misma base**, porque
compararla contra venta observada mientras el modelo pronostica demanda latente le regalaría al
modelo justo la diferencia que la tabla mide aparte.

**El delta de costo no necesita saber qué demanda hubo.** Las dos cantidades — la del modelo y la
de la política — se evalúan bajo la **misma** distribución predictiva, así que lo que cambia es la
decisión y no el supuesto. El faltante y el sobrante esperados salen de integrar
`E[(D−q)⁺]` sobre la inversa de la CDF que describen los cuantiles; son esperanzas implicadas por
el modelo, no resultados medidos, y el faltante es una **cota inferior** porque la grilla termina
en el cuantil 0,95 y el 5 % de masa de arriba no está descrito. La respuesta devuelve ese
`tail_mass` para que la interfaz lo pueda decir.

Todo número que no venga del backend vive en un solo archivo (`frontend/src/domain.ts`), lleva
sello `sim` en pantalla y dice qué endpoint falta.

### El plan comercial del horizonte se declara

El modelo usa tres covariables del día objetivo que no son fuga porque se conocen antes:
descuento, feriado y actividad comercial. En el backtest salen del panel, que ya tiene esos días.
En producción el horizonte está **después** del último día del panel, así que no hay de dónde
leerlas: o las aporta quien consulta, que es el que conoce su plan comercial, o hay que asumirlas.

Los tres endpoints aceptan un `plan` opcional, y cuando no viene el servidor asume la mediana de
los últimos 21 días del panel y **lo declara en la respuesta**:

```json
"plan": {"plan": {"discount": 0.967, "holiday_flag": 0, "activity_flag": 0},
         "source": "panel_median", "window_days": 21}
```

Ese default está elegido por medición y no por gusto; las cinco variantes evaluadas están en
`docs/decisiones.md` D19. Antes de esto las tres covariables llegaban en **NaN**, y el costo
medido de eso era grande: ver la sección de antifugas.

## Notebooks

Seis, ejecutados y con salidas commiteadas, en `notebooks/`. Se leen en orden y cada uno cierra
con qué consecuencia tiene lo que muestra sobre el resto del proyecto.

| Notebook | Qué responde |
|---|---|
| `01_eda` | Qué hay en el panel, cómo se distribuye la demanda, cuánta censura hay, y la **verificación** de que la ventana comercial de 16 franjas reproduce el ≈20 % de la ficha |
| `02_features_validacion` | Los ocho asserts antifugas corriendo, **cada uno con su fuga inyectada** para probar que la detecta |
| `03_modelos_backtest` | El backtest de origen móvil, MASE con dispersión entre orígenes, y por qué el naive estacional da 1,10 y no 1,00 |
| `04_no_supervisado` | PCA del catálogo, con la varianza explicada al lado. Y los dos huecos de M4 declarados |
| `05_decision_conformal` | El óptimo del costo esperado cayendo en `q*`, y CQR contra el conformal de residuos |
| `06_roi` | El ahorro en porcentaje, contra cuatro políticas, sin traducir a moneda |

```bash
make notebooks        # ejecuta los seis en orden, en el lugar
```

**La regla del directorio: los notebooks importan de `src/blindside` y no contienen lógica.** Si
un cálculo vive en una celda, no tiene test y no llega a producción; cuando hace falta, va al
paquete y el notebook lo llama. Es la razón por la que las celdas son cortas.

Corren sobre una **submuestra declarada de 400 series** con la semilla del proyecto, salvo `01` y
`04` que usan el panel completo. Los números oficiales salen de `make models` sobre las 3.066
series con 8 orígenes; los notebooks muestran el mecanismo y dicen cuál es su alcance. Cuando el
reporte oficial existe en `reports/`, `03` lo carga y compara las dos corridas.

Dos cosas que aparecieron **al escribirlos**, y que quedaron dentro:

- El test de alineación del target pasa con LightGBM y falla por poco con Ridge. No es un
  desalineamiento —el pipeline es el mismo— sino que correr el target hacia atrás acerca la tarea
  a una autorregresión pura, que para un modelo lineal es *más fácil*. La lección es que la
  sensibilidad de ese test depende del modelo con el que se corre.
- En la comparación de políticas, el stock de seguridad fijo **le gana al modelo** por 6 puntos.
  Usa el cuantil real de cada serie, o sea conocimiento de oráculo, así que no es implementable ni
  es una cota superior — pero acota cuánto del ahorro se puede atribuir al pronóstico diario en
  vez de a haber elegido bien el cuantil.

## Resultados

Medidos sobre **3066 series** tienda-producto (38 tiendas, 97 días), backtesting de origen
móvil con **8 orígenes**, horizonte de **7 días**, target de demanda latente recuperada.
1.545.264 predicciones evaluadas. Reporte completo en `reports/metrics.md`, generado por
`make models`.

| Modelo | MASE | Desvío entre orígenes | Peor origen | Δ vs naive estacional |
|---|---|---|---|---|
| **CQR sobre LightGBM cuantílico** · el artefacto servido | **0,8217** | 0,0454 | 0,8790 | **+25,3 %** |
| Conformal de residuos sobre el mismo base | 0,8217 | 0,0454 | 0,8790 | +25,3 % |
| LightGBM global (puntual) | 0,8222 | 0,0457 | 0,8791 | +25,3 % |
| Croston SBA | 0,8952 | 0,0683 | 0,9631 | +18,6 % |
| Ridge | 0,9018 | 0,0626 | 1,0088 | +18,0 % |
| Media móvil 21 d | 0,9048 | 0,0654 | 0,9779 | +17,8 % |
| Media móvil estacional | 0,9460 | 0,0655 | 1,0189 | +14,0 % |
| Naive estacional | 1,1002 | 0,0636 | 1,1579 | — |
| Naive | 1,1606 | 0,1099 | 1,3105 | −5,5 % |

El objetivo SMART era **reducir MASE al menos 20 %** frente al naive estacional. Se cumple con
25,3 %, y el **peor** de los ocho orígenes sigue por debajo de 0,88 — o sea que no depende de
promediar un origen bueno con uno malo.

Las dos primeras filas dan el mismo MASE hasta el cuarto decimal, y eso es correcto: son el
mismo modelo base con dos envoltorios conformales distintos, y **ninguno de los dos toca la
predicción central**. Lo que cambia entre ellas es el intervalo, y ahí la diferencia es grande.

Todas las métricas van **con su dispersión entre orígenes**, nunca como número único: un
promedio bueno puede esconder un origen catastrófico, y el origen catastrófico es el que pasa en
producción.

### Cobertura del intervalo, que es la segunda métrica de éxito

| Modelo | Nominal | Empírica | Brecha | Ancho medio | Desvío del ancho |
|---|---|---|---|---|---|
| **CQR** | 90 % | **88,0 %** | **−2,0 pts** | **1,805** | 0,153 |
| Conformal de residuos, adaptativo | 90 % | 98,7 % | +8,7 pts | 3,834 | 0,526 |

El conformal de residuos absolutos cubre casi nueve puntos **por encima** de lo que promete, y
eso no es prudencia: lo paga con un intervalo del doble de ancho. El caso degenerado de esa
lógica es `[0, ∞)`, que cubre el 100 % y no informa nada.

CQR queda dos puntos por debajo del nominal con un intervalo **53 % más angosto**. Dos puntos de
sub-cobertura son una desviación real y conviene decirla: la garantía del split-conformal supone
intercambiabilidad, y en una serie temporal con partición temporal eso se cumple de forma
aproximada. La alternativa era seguir cubriendo 98,7 % con una banda inútil.

**Por qué el otro no se podía arreglar ajustando un parámetro.** Su score de conformidad es un
residuo **absoluto**, así que el cuantil sale siempre positivo y la mecánica solo sabe ensanchar.
El score de CQR es `max(q_lo − y, y − q_hi)`, que es negativo cuando el punto cayó dentro del
intervalo, así que la corrección puede **apretar**. Detalle y medición en `docs/decisiones.md` D21.

### El contraste contra los clásicos per-serie

El modelo que el proyecto defiende es **global**: un solo LightGBM que ve las 3066 series a la
vez. La objeción obvia es que el pronóstico de series temporales tiene una tradición de modelos
**por serie**, y que un global podría estar ganando solo porque se comparó contra baselines
simples. SARIMA y Prophet son la respuesta.

Medido sobre una submuestra declarada de **400 series** con los mismos 8 orígenes —son por serie
y cuestan ~650 ms y ~300 ms cada una, así que las 3066 serían horas. Reporte en
`reports/metrics_classical.md`, generado por `make classical`:

| Modelo | MASE | Desvío | Peor origen | Δ vs naive estacional |
|---|---|---|---|---|
| **LightGBM global** | **0,8386** | 0,0549 | 0,9029 | **+24,2 %** |
| Croston SBA | 0,9032 | 0,0707 | 0,9873 | +18,3 % |
| SARIMA `(1,0,1)(1,0,0)[7]` | 0,9136 | 0,0599 | 0,9832 | +17,4 % |
| Media móvil 21 d | 0,9139 | 0,0652 | 0,9927 | +17,4 % |
| Prophet | 0,9698 | 0,0704 | 1,0502 | +12,3 % |
| Naive estacional | 1,1058 | 0,0674 | 1,1761 | — |

> La fila de Prophet exige la instalación opcional; sin ella `make classical` corre igual y el
> reporte sale con los otros cinco. SARIMA **no** es opcional: sale de `statsforecast`, que ya
> está fijado en `requirements.txt`.

El global le gana a SARIMA por 8,2 % y a Prophet por 13,5 %. Pero el dato que más dice es otro:
**SARIMA queda empatado con la media móvil de 21 días** — 0,9136 contra 0,9139 — y pierde contra
Croston. Todo el aparato ARIMA no compra nada sobre un promedio simple en este panel, y eso es
consistente con series cortas, intermitentes y con una estacionalidad semanal que un rolling ya
captura.

Prophet queda último de los modelos con ajuste y su peor origen pasa de 1,05, o sea peor que la
escala del naive estacional. Con 97 días no hay ciclo anual que estimar, así que queda reducido a
tendencia más estacionalidad semanal; el contraste es legítimo y conviene decir que no está en su
terreno.

**El orden de SARIMA está declarado, no buscado, y eso no lo perjudica.** `AutoARIMA` cuesta 2,3 s
por serie contra 85 ms de la orden fija —27 veces más—, lo que haría la comparación imposible
dentro del presupuesto. Para descartar que fijarlo fuera un handicap se midieron las dos sobre 60
series: la orden fija da MASE **0,9566** y la búsqueda **0,9657**, o sea que la versión barata es
*mejor*. Se puede reproducir con `--models sarima_auto`.

**Prophet es opcional y el arnés lo saltea si no está.** Está comentado en `requirements.txt`
porque arrastra un backend de Stan; el import es perezoso y `ProphetForecaster.disponible()`
permite correr el contraste sin él. Si se instala, hacen falta las dos líneas:
`pip install prophet==1.1.6 cmdstanpy==1.2.4` — con la cmdstanpy que pip resuelve por defecto el
bundle de Stan queda sin makefile y Prophet falla con un `AttributeError` que no dice nada sobre
la causa.

### Dos aclaraciones sobre cómo leer la tabla

**El naive estacional da MASE 1,10 y no 1,00.** El denominador de MASE es su error *en muestra*
sobre el train de cada fold, y el numerador es *fuera de muestra*. Que el segundo sea mayor es
lo normal y es la definición estándar.

**Los baselines de media móvil son duros.** Croston y la media móvil de 21 días le ganan al
naive estacional por 18 %, así que el 25,3 % del modelo no se mide contra un rival elegido para
perder. Un proyecto que solo compara contra el naive simple se regala 7 puntos.

### Recuperación de demanda censurada

| Grupo | Demanda observada | Demanda latente | Uplift |
|---|---|---|---|
| Todos los días | 1,0087 | 1,2218 | +21,1 % |
| Días **sin** quiebre | 0,9793 | 0,9793 | **0,00 %** |
| Días con quiebre | 1,0463 | 1,5318 | +46,4 % |

El uplift de exactamente 0 % en los días limpios es por diseño, no casualidad: esos días son la
verdad de terreno con la que se mide el sesgo, así que corregirlos destruiría la medición.

**Comprobación de que la ventana comercial asumida es la correcta:** 43,9 % de días con quiebre
× 7,0 horas de quiebre promedio / 16 franjas comerciales = **19,2 % de horas comerciales en
quiebre**, que reproduce el «≈20 %» que declara la ficha del dataset. El código además falla si
las horas derivadas de la máscara horaria no coinciden con la columna `stock_hour6_22_cnt`, así
que el supuesto se verifica en cada corrida.

Ver `reports/censoring_ablation.md` para la comparación pareada del mismo modelo entrenado sobre
venta observada contra demanda latente, y `docs/decisiones.md` D10 para por qué tiene que ser
pareada. El resultado, medido sobre 99.721 días limpios:

| Entrenado sobre | Sesgo re-censurado | MASE días limpios |
|---|---|---|
| Venta observada | **−18,19 %** | 0,8117 |
| Demanda latente | **−6,61 %** | 0,8958 |

**11,57 puntos porcentuales de reducción de sesgo**, y es el número que el proyecto defiende
porque las dos ramas son el mismo modelo con el mismo denominador de MASE.

Dos cosas que hay que leer con cuidado en esa tabla, y las dos están explicadas en el reporte:

- **El MASE empeora en la rama corregida** (0,8958 contra 0,8117). No es una contradicción: las
  dos se evalúan contra la venta observada de los días limpios, y un modelo que aprendió a
  predecir demanda **latente** sobrepredice ahí por construcción. Es el precio de corregir el
  sesgo, y el sesgo es lo que importa para decidir cuánto pedir.
- **El sesgo sin corregir de este panel es 2,2 veces el que publica CADRE** (−18,19 % contra
  −8,1 %), así que las dos cifras no son directamente comparables y el reporte ya no finge que lo
  sean. La causa más probable es el submuestreo: 3066 series elegidas por tienda completa no son
  las 50.000 del dataset. Lo que sí se compara es la **reducción**: 11,57 puntos acá contra 6,8
  de CADRE.

## Datos

**Fuente primaria:** [FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K)
(Dingdong-Inc, CC BY 4.0) — 50.000 series tienda-producto de 90 días, 898 tiendas, 18 ciudades,
865 SKU perecederos, con **≈ 20 % de eventos de quiebre anotados hora por hora**. Paper:
[arXiv 2505.16319](https://arxiv.org/abs/2505.16319).

El dataset **no se carga completo nunca** (ver `docs/decisiones.md`): se submuestrea durante la
lectura del parquet con semilla fija y se persiste el subconjunto. `data/sample/` contiene una
muestra pequeña y commiteada para que el repo se pueda correr sin descargar nada.

> **Nota sobre magnitudes.** En el dataset `sale_amount` y `hours_sale` están multiplicados por
> un coeficiente no divulgado. Las métricas de exactitud son válidas tal cual; el ROI **no** se
> expresa en moneda a partir de estos datos. Ver `docs/roi.md`.

## Docker

Dos superficies orquestadas con Compose, y una imagen aparte para el pipeline.

```bash
make docker-up      # api en :8000, app en :8501
make docker-ps      # estado y salud
make docker-logs    # logs de los dos servicios
make docker-down
```

Los datos y el artefacto se **montan como volúmenes**, no se copian a la imagen: `data/` pesa
cientos de MB y `artifacts/` cambia en cada entrenamiento, así que meterlos en una capa haría que
reentrenar exigiera un rebuild. Para preparar todo sin depender del entorno local:

```bash
make docker-data                                            # descarga + recupera censura
docker compose --profile pipeline run --rm pipeline train    # serializa el artefacto
make docker-up
```

### Dos imágenes, y por qué

| Target | Tamaño | Para qué | Incluye |
|---|---|---|---|
| `serve` | **1,17 GB** | API + dashboard | numpy, pandas, pyarrow, sklearn, lightgbm, fastapi, streamlit |
| `full` | **3,57 GB** | Pipeline, entrenamiento, tests | todo `requirements.txt` |

La imagen de servicio deja afuera torch, jupyter, shap, optuna, umap-learn y xgboost. Nada de eso
se ejecuta para responder `/forecast` ni para levantar el dashboard: el artefacto servido es un
LightGBM y la app lee parquet.

**La imagen es de CPU por diseño, y el build lo verifica.** En Linux el `torch==2.4.1` de PyPI es la
build CUDA y arrastra los paquetes `nvidia-*`, del orden de 2,5 GB de wheels que este proyecto no
usa. El Dockerfile instala `torch==2.4.1+cpu` desde el índice CPU de PyTorch; la variante `+cpu`
satisface el pin, así que no hay divergencia de versiones. Aparte, **xgboost 2.1.1 declara
`nvidia-nccl-cu12` como dependencia dura en Linux** (454 MB medidos) para comunicación multi-GPU
que acá no se usa: se desinstala, y está verificado que xgboost sigue entrenando con
`tree_method="hist"`. Entre las dos cosas la imagen del pipeline baja de ~6 GB a 3,57 GB.

Hay un paso de build que **falla** si aparece cualquier paquete `nvidia-*` o `triton`, para que una
dependencia futura no agregue gigabytes en silencio.

El target `serve` tampoco tiene su propio archivo de dependencias: instala una lista corta de
paquetes de primer nivel con `--constraint requirements.txt`, así que las versiones salen del
**mismo archivo** que el entorno completo. Un `requirements-serve.txt` separado habría sido más
obvio de leer y habría abierto la puerta a que los pines se desincronicen en silencio.

### Verificado

```
blindside-api   Up (healthy)   127.0.0.1:8000->8000/tcp
blindside-app   Up (healthy)   127.0.0.1:8501->8501/tcp
```

`/health` responde con el modelo cargado, `/series` devuelve el catálogo, Streamlit responde en
`/_stcore/health`, y la suite corre dentro del contenedor:

```bash
make docker-test    # 213 tests en la imagen del pipeline
```

### Seguridad del despliegue

Los puertos se publican atados a `127.0.0.1`, no a `0.0.0.0`. Con `- "8000:8000"` Docker abriría el
puerto en todas las interfaces de la máquina, y **la API no tiene autenticación**: en una red
compartida cualquiera podría consultar los pronósticos y las cantidades de reposición. Los
contenedores corren como usuario sin privilegios (`uid 1000`), y `data/`, `artifacts/` y `reports/`
se montan **de solo lectura** en los servicios de consulta — solo el perfil `pipeline` escribe.

Cambiar el binding a `0.0.0.0` exige agregar autenticación antes.

## Instalación

Requiere **Python 3.11 o 3.12**. Los pines de `requirements.txt` (numpy 2.0.2, torch 2.4.1,
numba vía umap-learn) no publican wheels para 3.13 ni 3.14, y desfijarlos para que instale
rompería la reproducibilidad que ese archivo está protegiendo.

```bash
git clone https://github.com/FrancoCazal/blindside-core.git
cd blindside-core

python3.11 -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

make setup          # requirements.txt fijos + paquete en modo editable
make test           # la suite entera; no necesita descargar nada
make test-leakage   # solo los tests antifugas, los de la defensa
make app            # dashboard en http://127.0.0.1:8501
```

Eso ya corre: `data/sample/` viene commiteado. Para reproducir los resultados de arriba hay que
bajar el dataset (115 MB) y regenerar las capas:

```bash
make data       # descarga y submuestrea a data/interim/ con semilla fija
make recover    # recupera la demanda censurada -> data/processed/
make models     # backtest de baselines + LightGBM + Ridge -> reports/metrics.md
make ablation   # ablación de censura -> reports/censoring_ablation.md
```

`make data` y `make recover` tardan pocos minutos. `make models` entrena LightGBM y Ridge en
ocho folds sobre 400.000 filas cada uno, así que son decenas de minutos.

## Estructura del repositorio

```
blindside-core/
├── data/
│   ├── raw/          # descarga original (no commiteado)
│   ├── interim/      # subconjunto submuestreado (no commiteado)
│   ├── processed/     # demanda latente recuperada + features (no commiteado)
│   └── sample/       # muestra chica (SI commiteada)
├── src/blindside/
│   ├── config.py      # rutas, semilla, economia, parametros de pronostico
│   ├── data/          # schema.py (CONTRATO 1), freshretail.py, loaders.py
│   ├── features/      # calendar.py, lags.py, build.py (anclado en el origen)
│   ├── validation/    # splits.py (origen movil), leakage.py (los 8 asserts)
│   ├── models/        # base.py (CONTRATO 2), baselines, tabular, gbdt, linear, classical
│   ├── unsupervised/  # clustering, embeddings, anomalias  [pendiente]
│   ├── decision/      # censoring, conformal, newsvendor, policy
│   ├── evaluate/      # contracts.py (CONTRATO 3), metrics, backtest, ablation
│   └── explain/       # SHAP  [pendiente]
├── notebooks/         # 6 notebooks ejecutados; importan de src/, no contienen logica
├── tests/             # 213 tests; test_leakage.py son los 8 items del checklist
├── app/               # streamlit_app.py, 7 pantallas
├── api/               # schemas.py (CONTRATO 4), main.py
├── frontend/          # React + Vite + TS; schema.d.ts generado del OpenAPI
│   ├── src/api/       # cliente tipado contra el contrato
│   ├── src/charts/    # SVG a mano: viewBox fijo y orden de capas
│   ├── src/screens/   # reposicion (landing), serie individual, salud
│   └── src/domain.ts  # UNICO lugar con numeros que no vienen del backend
├── docs/              # decisiones tecnicas, ROI, plan del proyecto
├── artifacts/         # modelos serializados (no commiteados)
└── reports/           # metrics.md, censoring_ablation.md (generados)
```

### Los cuatro contratos

Están congelados a propósito antes que el resto (sección 13 del plan): sin ellos los frentes
paralelos producen piezas que no encajan.

| Contrato | Archivo | Qué fija |
|---|---|---|
| Esquema de datos | `src/blindside/data/schema.py` | Columnas, tipos, granularidad, jerarquías |
| Interfaz de modelo | `src/blindside/models/base.py` | `fit(history)` / `predict(future)`, artefacto |
| Resultado de backtest | `src/blindside/evaluate/contracts.py` | Forma única que consumen métricas y dashboard |
| API | `api/schemas.py` | Request y response Pydantic |

El segundo es el que hace estructural el diseño antifugas: un modelo recibe `history` (hasta el
origen) y un `future` **sin columna de target**. No tiene desde dónde mirar el futuro ni por
accidente. La fuga deja de ser algo que hay que recordar no hacer y pasa a ser algo que no se
puede expresar.

## Validación y antifugas

El checklist de la metodología está implementado como **tests que fallan si hay fuga**. Un README
que dice «evité leakage» no prueba nada.

```bash
make test-leakage
```

| Item | Cómo se verifica |
|---|---|
| Sin features posteriores a `t` | Toda feature es constante dentro de cada `(serie, origen)` |
| Lags por grupo y ordenados | El lag de la primera fila de cada serie es nulo |
| Sin agregados globales | Ninguna feature iguala un promedio del panel completo |
| Sin target encoding del futuro | Ninguna feature correlaciona ≥ 0,999 con el target |
| Escalador ajustado en el fold | Su media se parece a la del train, no a la del panel |
| Test de shuffle | Al permutar el target, el modelo no le gana al mejor constante |
| Alineación del target | Correr el target un día **empeora** la métrica en las dos direcciones |
| Test de fold | Train y test disjuntos, y el gap es igual al horizonte |

Cada uno lleva su **caso negativo**: se inyecta la fuga a propósito y se verifica que el assert la
detecte. Un test antifugas que pasa siempre, incluso con fuga presente, es peor que no tenerlo.

Dos de estos tests encontraron fugas y bugs reales en este código, no hipotéticos:

- `is_censored` del **día objetivo** entraba a la matriz como feature, porque el `merge` la
  desambiguaba con el sufijo `_target`. Eso es predecir demanda sabiendo si va a haber quiebre.
- `days_since_start` se anclaba al mínimo de cada DataFrame, así que valía 0..18 en entrenamiento
  y 0..6 en inferencia. Ridge daba MASE 3,75 con desvío 5,26; con el ancla fija da 0,91. LightGBM
  apenas se movía, que es lo que hacía al bug difícil de ver.

Detalle del segundo en `docs/decisiones.md` D12.

### El desajuste train/serve que ninguna métrica detectaba

Los asserts antifugas cubren el camino de **validación**. Hubo un tercer defecto que vivía solo en
**inferencia**, y por eso ningún backtest lo veía: de las 73 features que recibe el modelo, las
tres covariables conocidas de antemano — descuento, feriado y actividad — llegaban en **NaN**.

El mecanismo es limpio de explicar. El estado congelado del origen las descarta a propósito,
porque son del día objetivo y tienen que venir del índice de futuro. El arnés de backtesting las
pone, porque el fold cae dentro del panel y esos días ya existen. La API no las ponía, porque su
horizonte empieza después del último día del panel y no hay de dónde leerlas.

Medido sobre un fold real (train hasta 2024-06-25, test del 26 de junio al 2 de julio, 21.462
filas):

| Covariables del horizonte | MASE | vs. reales | Cantidad a pedir | vs. reales |
|---|---|---|---|---|
| Reales, del panel | **0,8790** | — | 35.011 | — |
| Mediana de 21 días, global · **el default** | 0,9437 | +7,4 % | 32.787 | −6,4 % |
| Mediana de 21 días, por serie | 0,9513 | +8,2 % | 33.692 | −3,8 % |
| Precio de lista, sin campaña | 0,9571 | +8,9 % | 30.390 | −13,2 % |
| Persistir el último día conocido | 0,9573 | +8,9 % | 33.406 | −4,6 % |
| **Las tres en NaN** · lo que servía la API | **1,6392** | **+86,5 %** | 53.391 | **+52,5 %** |

La última fila es la que importa: **1,64 es peor que el naive estacional**, que da 1,10. La API
publicaba pronósticos peores que el baseline que el proyecto dice superar, con órdenes 52 % más
altas de lo que corresponde, y contestaba 200 sin una sola advertencia — LightGBM trata el NaN
como una rama más, así que la salida era un número plausible.

Por columna, asumiendo una sola por vez: `discount` +4,2 %, `holiday_flag` +2,6 %,
`activity_flag` +0,02 %. El descuento pesa el doble que el feriado, y la bandera de actividad
casi no mueve la aguja.

Hay ahora un test que falla si cualquiera de las tres vuelve a llegar nula. La elección del
default está en `docs/decisiones.md` D19.

### Un segundo defecto de inferencia, en la capa de decisión

El artefacto servido es un conformal envolviendo un LightGBM cuantílico. Su `predict_quantile`
**descartaba los boosters entrenados con pérdida cuantílica** e interpolaba entre los límites del
intervalo, así que la cantidad a pedir salía de la forma de la banda conformal y no del cuantil
`q*`. Medido sobre 25 series: la banda daba `q0,625 = 1,93` donde el booster entrenado da 1,52,
o sea una orden **21,5 % más alta**. Y como la banda está sobre-inflada, el error iba siempre en
la misma dirección.

Importa porque el README afirma que «el modelo se entrena con pérdida cuantílica en ese `q*`, así
que su salida **es** la orden». Para el artefacto servido eso no era cierto. Ahora, cuando el
modelo base sabe dar cuantiles, manda el base; el conformal sigue siendo dueño del intervalo, que
es para lo que tiene garantía de cobertura. Detalle en `docs/decisiones.md` D20.

## Decisiones técnicas y limitaciones

Están documentadas en `docs/decisiones.md`, cada una con qué se decidió, por qué, y qué
alternativa se descartó. Las que conviene conocer antes de leer los resultados:

1. **Horizonte de 7 días, no de 4 semanas.** El dataset trae 90 + 7 días por serie. Con horizonte
   28 caben como máximo 4 orígenes de backtest y la metodología declara 8, así que las dos cosas
   son incompatibles. Además, el split `eval` oficial del benchmark son exactamente 7 días, lo que
   permite compararse contra el baseline publicado. Detalle en D8.
2. **Submuestreo declarado.** 3066 de las 50.000 series, elegidas por tienda completa con semilla
   fija para no romper las jerarquías. El manifiesto queda en `data/interim/`.
3. El newsvendor es **de un solo período**. Para perecederos con vida útil mayor al período de
   revisión el modelo correcto es de inventario perecedero multi-período con despacho por
   antigüedad. La aproximación vale cuando la vida útil se parece al período de revisión.
4. No se modela **lead time** ni estructura multi-echelon: se asume que lo pedido llega para el
   período siguiente.
5. No se modelan **restricciones operativas de la orden** (cantidad mínima, múltiplos de caja o
   pallet, capacidad de cámara). El modelo emite un número continuo.
6. **La corrección de censura es conservadora a propósito.** Tope de inflación en ×3 y nada de
   corrección cuando queda menos del 15 % de la masa de demanda diaria disponible. Sin esos
   límites, un día con 15 de 16 franjas en quiebre y una sola venta chica implicaría una demanda
   latente dieciséis veces mayor apoyada en un único dato. Se prefiere un sesgo residual conocido
   a una varianza inventada, y eso hace que la corrección quede por debajo de la publicada por
   CADRE. Detalle en D11.

### Encuadre del diferencial, sin inflar

El cruce entre predicción conformal y newsvendor **no es un aporte original**. Que los pronósticos
cuantílicos calibrados sean equivalentes a la solución óptima del newsvendor es un resultado
publicado ([MDPI JRFM](https://www.mdpi.com/1911-8074/19/3/173)), y conformalizar el cuantil
crítico también está hecho ([Cao 2024](https://arxiv.org/abs/2412.13159)). Lo que se reivindica
es la **aplicación**: la implementación corriendo de punta a punta, que es lo raro, porque la
mayoría de las implementaciones reales usan stock de seguridad heurístico en vez de un cuantil
con cobertura verificada.

Existe además [un pipeline publicado](https://www.mdpi.com/2411-5134/11/5/89) muy parecido a este
proyecto sobre este mismo dataset. Se cita a propósito: es plantilla y competencia a la vez, y
conviene haberlo citado primero.

## Estado y próximos pasos

Implementado y verificado: contratos, carga y submuestreo, recuperación de censura, features
ancladas en el origen, validación de origen móvil con asserts antifugas, métricas, arnés de
backtesting, baselines, LightGBM (puntual y cuantílico), XGBoost, regresión regularizada,
**SARIMA y Prophet como contraste per-serie (M6)**, CQR con cobertura verificada, newsvendor con
esperanzas derivadas de la distribución predictiva, simulador de política, API, dashboard
Streamlit, frontend React de 8 pantallas, TreeSHAP por predicción y PCA del catálogo.

Con eso queda cubierto el **mínimo defendible que el plan declara: M2 + M3 + M6.**

Pendiente del alcance del plan: GRU/LSTM y transformer temporal (M5), clustering y detección de
anomalías (M4), drift (M9), reconciliación MinT (8.3), Optuna, y el generador sintético del caso
Focal Point (frente K).

**La limitación que queda del lado del intervalo**, ahora que CQR está medido: cubre 88,0 %
cuando promete 90 %, o sea dos puntos **por debajo**. La garantía del split-conformal supone
intercambiabilidad y una partición temporal la cumple de forma aproximada, así que la brecha es
esperable y está declarada. La orden no depende de eso — sale del booster entrenado en `q*` —
pero la banda que se dibuja en la interfaz sí.

La otra limitación, más de fondo: la cobertura garantizada es **marginal, no condicional**. El
88 % global puede esconder subgrupos peores, y el desglose por horizonte del notebook `05` muestra
que los pasos intermedios bajan a 0,85. Desagregar es lo que la hace visible; corregirla exigiría
conformal condicional o por grupo, y eso está en el Roadmap.

Fuera del alcance de la entrega, en `docs/decisiones.md` sección Roadmap.

## Licencia

MIT. Ver `LICENSE`.

El dataset FreshRetailNet-50K es de Dingdong-Inc y se distribuye bajo CC BY 4.0; no se
redistribuye en este repositorio más allá de la muestra de `data/sample/`.
