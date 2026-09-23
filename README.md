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

| Base | Pronóstico | Cantidad a pedir |
|---|---|---|
| Venta observada | 261,402 | 345,694 |
| Demanda recuperada | 345,476 | **454,027** |

Corregir la censura sube la orden **+31,3 %**. Con un solo artefacto el toggle habría movido el
gráfico y no la cantidad, que es la mitad del argumento del proyecto.

Todo número que no venga del backend vive en un solo archivo (`frontend/src/domain.ts`), lleva
sello `sim` en pantalla y dice qué endpoint falta.

## Resultados

Medidos sobre **3066 series** tienda-producto (38 tiendas, 97 días), backtesting de origen
móvil con **8 orígenes**, horizonte de **7 días**, target de demanda latente recuperada.
Reporte completo generado en `reports/metrics.md` por `make models`.

| Modelo | MASE | Desvío entre orígenes | Peor origen | Δ vs naive estacional |
|---|---|---|---|---|
| **LightGBM global** | **0,8311** | 0,0462 | 0,8849 | **+24,5 %** |
| Croston SBA | 0,8952 | 0,0683 | 0,9631 | +18,6 % |
| Media móvil 21 d | 0,9048 | 0,0654 | 0,9779 | +17,8 % |
| Media móvil estacional | 0,9460 | 0,0655 | 1,0189 | +14,0 % |
| Naive estacional | 1,1002 | 0,0636 | 1,1579 | — |
| Naive | 1,1606 | 0,1099 | 1,3105 | −5,5 % |

El objetivo SMART era **reducir MASE al menos 20 %** frente al naive estacional. Se cumple con
24,5 %, y el **peor** de los ocho orígenes sigue por debajo de 0,89 — o sea que no depende de
promediar un origen bueno con uno malo.

Todas las métricas van **con su dispersión entre orígenes**, nunca como número único: un
promedio bueno puede esconder un origen catastrófico, y el origen catastrófico es el que pasa en
producción.

### Dos aclaraciones sobre cómo leer la tabla

**El naive estacional da MASE 1,10 y no 1,00.** El denominador de MASE es su error *en muestra*
sobre el train de cada fold, y el numerador es *fuera de muestra*. Que el segundo sea mayor es
lo normal y es la definición estándar.

**Los baselines de media móvil son duros.** Croston y la media móvil de 21 días le ganan al
naive estacional por 18 %, así que el 24,5 % del modelo global no se mide contra un rival
elegido para perder. Un proyecto que solo compara contra el naive simple se regala 6 puntos.

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
pareada.

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
make docker-test    # 146 tests en la imagen del pipeline
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
│   ├── models/        # base.py (CONTRATO 2), baselines, tabular, gbdt, linear
│   ├── unsupervised/  # clustering, embeddings, anomalias  [pendiente]
│   ├── decision/      # censoring, conformal, newsvendor, policy
│   ├── evaluate/      # contracts.py (CONTRATO 3), metrics, backtest, ablation
│   └── explain/       # SHAP  [pendiente]
├── notebooks/         # analisis; importan de src/, no contienen logica
├── tests/             # 150 tests; test_leakage.py son los 8 items del checklist
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
conformal por partición, newsvendor, simulador de política, API y dashboard.

Pendiente del alcance del plan: SARIMA y Prophet (M6), GRU/LSTM y transformer temporal (M5),
clustering y detección de anomalías (M4), SHAP y drift (M9), reconciliación MinT (8.3), Optuna,
frontend React y el generador sintético del caso Focal Point (frente K).

Fuera del alcance de la entrega, en `docs/decisiones.md` sección Roadmap.

## Licencia

MIT. Ver `LICENSE`.

El dataset FreshRetailNet-50K es de Dingdong-Inc y se distribuye bajo CC BY 4.0; no se
redistribuye en este repositorio más allá de la muestra de `data/sample/`.
