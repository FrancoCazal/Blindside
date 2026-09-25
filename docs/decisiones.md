# Decisiones técnicas

Cada entrada dice **qué** se decidió, **por qué**, y qué **alternativa** se descartó. El orden es
de mayor a menor impacto en el resultado.

---

## D1 · Fuente de datos: benchmark público en vez de dataset propio

**Decisión.** FreshRetailNet-50K como fuente primaria.

**Por qué.** Tres razones. Trae la **censura de demanda etiquetada hora por hora**, así que la
corrección se puede *medir* y no solo afirmar. Trae **dos jerarquías reales**
(`city_id > store_id` y `management_group_id > … > product_id`), así que la reconciliación no
opera sobre una jerarquía inventada. Y trae un **baseline oficial publicado**
([frn-50k-baseline](https://github.com/Dingdong-Inc/frn-50k-baseline)), lo que convierte la
mejora reportada en un resultado comparable con un tercero en vez de en autoevaluación.

**Alternativa descartada.** Generador sintético como fuente única. Era la pieza más costosa y
más riesgosa del camino crítico, y su métrica de éxito habría sido autoevaluada. Sigue siendo
útil como complemento porque en un generador el proceso generador es conocido y se puede
verificar que el modelo recupera lo que se inyectó.

---

## D2 · El dataset nunca se carga completo

**Decisión.** El submuestreo pasa **durante** la lectura del parquet, filtrando por `city_id` o
por grupo de categorías, con semilla fija, y el subconjunto se persiste una sola vez en
`data/interim/`.

**Por qué.** El parquet pesa 115 MB comprimido, pero `hours_sale` y `hours_stock_status` son
secuencias de 24 elementos. Expandido son ~4,85 M filas × 48 valores ≈ 233 millones de números,
del orden de 1,9 GB en `float64` solo para esas dos columnas. Un `load_dataset(...).to_pandas()`
no entra en una máquina de trabajo normal.

**Consecuencia de diseño.** `blindside.data.freshretail` tiene un contrato explícito: **nunca
materializa el dataset completo**. Cualquier función que lo haga es un bug, no una optimización
pendiente.

---

## D3 · Estructura del repo: checklist del módulo 7, no `cookiecutter-data-science` literal

**Decisión.** Se construyó la estructura que el checklist de M7 enumera, y se tomó de
Cookiecutter Data Science lo conceptual: la higiene de `data/` (crudo inmutable, capas
intermedias separadas) y la convención de nombres de notebooks.

**Por qué.** El checklist pide cosas que `ccds` no genera o genera con otro nombre: módulo bajo
`src/` (ccds v2 lo pone en la raíz), `data/sample/` **commiteado** (ccds no lo tiene),
`app/streamlit_app.py`, `artifacts/` en vez de `models/`, y `requirements.txt` con versiones
fijas. Adoptar `ccds` literal habría implicado renombrar y mover media estructura.

**Nota.** `pyproject.toml` existe igual, porque el src-layout con paquete instalable es lo que
permite que los notebooks y la app importen `blindside` sin manipular `sys.path`. Los pines viven
en `requirements.txt` para no duplicar la fuente de verdad.

---

## D4 · Recuperación de censura antes de construir features

**Decisión.** La corrección de demanda censurada corre **antes** de los lags y los rolling.

**Por qué.** Un lag calculado sobre la venta observada arrastra el sesgo de censura a todas las
features derivadas. Corregir después no lo deshace. El orden es una dependencia real del
pipeline, no una preferencia de estilo.

**Referencia.** Tobit Exponential Smoothing con agregación temporal
([arXiv 2409.05412](https://arxiv.org/html/2409.05412v1)), que trata la censura con niveles
conocidos y variables y nombra el efecto spiral-down. El sesgo de censura en decisores humanos
está documentado en [Tong, Feiler y Larrick (2018)](https://journals.sagepub.com/doi/10.1111/poms.12823).

---

## D5 · MASE como métrica principal, MAPE excluido

**Decisión.** MASE contra naive estacional, más cobertura empírica del intervalo y pinball loss
para los cuantiles. WAPE como lectura de negocio ponderada por volumen.

**Por qué.** MAPE explota con demanda cercana a cero, que es exactamente la cola de productos de
baja rotación — la mayoría del catálogo en perecederos. MASE es libre de escala y un MASE menor
a 1 significa literalmente "le gana al método que la operación ya usa".

**Alternativa descartada.** MAPE, que es lo que la plantilla del curso sugiere para forecasting.
La desviación es deliberada y se justifica arriba.

---

## D6 · Conformal + newsvendor: aplicación, no invención

**Decisión.** El cruce entre predicción conformal y newsvendor se presenta como **aplicación de
literatura reciente**, con citas, no como aporte original.

**Por qué.** El cruce ya existe: Cao (dic-2024) conformaliza el cuantil crítico con garantías
independientes de la especificación del modelo
([arXiv 2412.13159](https://arxiv.org/abs/2412.13159)), y hay un resultado que prueba que los
pronósticos cuantílicos calibrados son *equivalentes* a la solución óptima del newsvendor
([MDPI JRFM](https://www.mdpi.com/1911-8074/19/3/173)). Reivindicar novedad frente a un panel que
conozca la literatura sería un error evitable.

**Lo que sí es aporte.** La implementación corriendo de punta a punta, que es lo raro: la mayoría
de las implementaciones reales usan stock de seguridad heurístico en vez de intervalos con
cobertura verificada.

---

## D7 · Conformal desde `statsforecast`, no desde cero

**Decisión.** Usar la implementación de conformal de Nixtla `statsforecast`.

**Por qué.** El valor defendible no está en escribir el algoritmo, está en **verificar la
cobertura**: el gráfico de cobertura nominal contra empírica. El tiempo ahorrado va ahí.

---

## D8 · Horizonte de 7 días, no de 4 semanas

**Decisión.** `horizon = 7`, `season_length = 7`, 8 orígenes separados por 3 días, con
42 días mínimos de entrenamiento antes del primer origen.

**Por qué.** El plan original fijaba un horizonte de 4 semanas. No entra en este dataset, y
la aritmética es simple: FreshRetailNet-50K trae **90 días** de historia por serie en `train`
más **7 días** en `eval`, o sea 97 días en total. El número de orígenes que caben es

```
n_max = (n_días − min_train_days − horizonte) // paso + 1
```

Con horizonte 28 y 42 días de calentamiento quedan `(97 − 42 − 28) // 7 + 1 = 4` orígenes
como máximo, y si el paso fuera igual al horizonte para que no se solapen, 2. La metodología
declara **mínimo 8**, así que 28 días de horizonte y 8 orígenes son incompatibles: hay que
soltar uno de los dos. Con horizonte 7 caben 17, y se usan 8.

Hay un segundo motivo, y es el que decide entre las dos opciones: el split `eval` oficial del
dataset son exactamente **7 días** (350.000 filas / 50.000 series). Adoptar el horizonte
oficial es lo que permite comparar contra el baseline publicado del benchmark, que es
justamente lo que convierte el "20 % de MASE" de autoevaluación en resultado comparable con
un tercero.

**Alternativa descartada.** Mantener las 4 semanas y reportar 2 o 3 orígenes. Un promedio de
dos orígenes no tiene dispersión que reportar, y la metodología del proyecto prohíbe el número
único justamente porque esconde el origen catastrófico.

**Consecuencia.** El objetivo SMART del plan dice "horizonte de 4 semanas". Hay que corregirlo
a 7 días antes de la defensa, o el panel encuentra la discrepancia entre el documento y el
código. `RollingOriginSplitter` falla con un mensaje explícito cuando el panel no admite los
orígenes pedidos, en vez de correr con menos en silencio.

---

## D9 · La ventana comercial son 16 franjas, no 17

**Decisión.** `CensoringConfig.open_hours = range(6, 22)`, o sea los índices 6..21 de
`hours_stock_status`.

**Por qué.** El campo se llama `stock_hour6_22_cnt` y la ficha lo describe como las horas de
quiebre "entre 6:00 y 22:00", lo que se lee naturalmente como 17 franjas (6 a 22 inclusive).
No es eso. Verificado contra las filas de ejemplo de la ficha: una fila con máscara
`[0]*11 + [1]*13` trae `stock_hour6_22_cnt = 11`, que es la cuenta en 6..21; en 6..22 serían
12. Se comprobó con cuatro filas distintas, incluida una con la máscara entera en 1, que trae
16.

`build_panel` deriva las horas de quiebre de la máscara y **falla** si no coinciden con la
columna del dataset, así que el supuesto queda verificado en cada corrida y no solo una vez.
Sobre las 3066 series submuestreadas coincide en las 297.402 filas.

**Por qué importa.** Una hora de corrimiento desplaza el denominador del factor de inflación
de la recuperación de censura en 1/16 ≈ 6 %, y ninguna métrica del proyecto lo delataría:
la demanda latente saldría sistemáticamente sesgada y todo lo demás seguiría siendo coherente.

**Comprobación cruzada.** Con la ventana correcta, el panel da 43,9 % de días con al menos una
hora de quiebre y 7,0 horas de quiebre promedio en los días censurados. Eso es
`0,439 × 7,0 / 16 = 19,2 %` de horas comerciales en quiebre, que reproduce el "aproximadamente
20 % de datos de quiebre" que declara la ficha del dataset.

---

## D10 · El sesgo de censura se mide con una ablación pareada, no en absoluto

**Decisión.** El resultado que se defiende es `evaluate.backtest.run_censoring_ablation`: el
**mismo modelo** entrenado dos veces, cambiando únicamente el target entre venta observada y
demanda latente, evaluado contra la **misma** verdad de terreno.

**Por qué.** El sesgo absoluto de un solo modelo mezcla dos efectos. El de la censura, que es
el que interesa, y el de la función de pérdida: LightGBM con `regression_l1` estima la
**mediana**, y en una distribución con cola derecha la mediana está por debajo de la media, así
que el sesgo medido contra promedios sale negativo aunque la censura esté perfectamente
corregida. Medido sobre el panel, la mediana de la demanda es 1,00 y la media 1,51: la brecha
es grande y contamina la lectura.

En la comparación pareada el efecto de la pérdida es idéntico en las dos ramas y se cancela.
Lo que queda es atribuible a la censura.

**Detalle que costó un bug.** Cada rama calcula su propio denominador de MASE a partir de su
propio target, y el de la demanda latente es mayor porque la serie corregida varía más.
Comparar los MASE crudos entre ramas medía esa diferencia de denominador y regalaba ~30 % de
mejora inexistente. La ablación usa la **escala de la rama de venta observada** para las dos.

**Verdad de terreno.** Las dos ramas se evalúan contra la venta observada de los **días sin
ninguna hora de quiebre**, que es el único terreno donde la demanda real se conoce. Evaluar la
rama latente contra demanda latente y la observada contra venta observada compararía cosas
distintas.

---

## D11 · La censura se corrige antes de las features, y el orden está testeado

Complementa D4. La dependencia no es solo documental: `HourlyProfileRecovery` deja los días
limpios **exactamente** como estaban (`uplift = 0,0000 %` medido), porque son la verdad de
terreno contra la que se mide el sesgo. Corregirlos destruiría la medición, así que hay un test
que falla si alguna vez se tocan.

Los dos límites del recuperador — tope de inflación en ×3 y no corregir cuando queda menos del
15 % de la masa de demanda diaria disponible — son deliberados. Un día con 15 de 16 franjas en
quiebre y una sola venta chica implicaría, sin tope, una demanda latente dieciséis veces mayor
apoyada en un único dato. Se prefiere un sesgo residual conocido a una varianza inventada, y
por eso la corrección propia (−8,4 % → −6,5 %) es más conservadora que la publicada por CADRE
(−8,1 % → −1,3 %). Se declara así en vez de aflojar los límites hasta igualar el número
publicado.

---

## D12 · La tendencia lineal se ancla en una época fija

**Decisión.** `days_since_start` se calcula contra `TREND_EPOCH = 2020-01-01`, no contra la
fecha mínima del DataFrame que recibe la función.

**Por qué.** Anclar en `df[dt].min()` parece inofensivo y es un bug silencioso. El frame de
entrenamiento abarca decenas de días y el de inferencia solo el horizonte, así que la misma
fecha recibe un valor distinto según quién la calcule. Medido sobre la muestra: en
entrenamiento la feature valía 0..18 y en inferencia 0..6 — la misma columna significando dos
cosas a cada lado del `fit`.

**Cómo se encontró, que es la parte interesante.** No lo encontró una revisión de código, lo
encontró el reporte de métricas. Ridge daba MASE 3,75 con desvío 5,26 entre orígenes y sesgo de
+5,98 en el peor, sobre una demanda de media 1,2. Ese perfil — error enorme, varianza entre
folds enorme, sesgo positivo — no es "los modelos lineales son peores en esta tarea", es un
modelo extrapolando sobre una escala equivocada.

**Por qué era difícil de ver.** LightGBM apenas se movía. Un árbol solo particiona, así que un
valor fuera del rango de entrenamiento cae en el bin extremo y la predicción sigue siendo
razonable. Un modelo lineal multiplica por el coeficiente y se va. Si el proyecto tuviera solo
modelos de árbol, el bug habría quedado adentro sin dar señales.

**Resultado del fix.** Ridge pasó de MASE 3,75 (±5,26, peor origen 12,49) a 0,9102 (±0,0736,
peor origen 1,0593). Hay dos tests que lo cubren: uno verifica que la misma fecha dé el mismo
valor en frames distintos, y otro que el rango de la tendencia en inferencia continúe el del
entrenamiento en vez de reiniciarse.

**Lectura para la defensa.** Es el argumento concreto de por qué el proyecto corre familias de
modelos distintas contra el mismo arnés y no solo la que gana. Un modelo lineal es un detector
de errores de escala que el boosting no tiene.

---

## D13 · Dos imágenes Docker, y una sola fuente de versiones

**Decisión.** Un `Dockerfile` multi-stage con dos targets: `serve` (1,17 GB) para la API y el
dashboard, y `full` (3,57 GB) para el pipeline, el entrenamiento y los tests.

**Por qué.** `requirements.txt` tiene torch, jupyter, shap, optuna, umap-learn y xgboost. Nada de
eso se ejecuta para responder `/forecast` ni para levantar el dashboard: el artefacto servido es un
LightGBM y la app lee parquet. Instalar todo en la imagen de servicio la triplica y alarga cada
build sin que nada de eso corra nunca.

**El detalle que evita la divergencia.** El target `serve` **no tiene su propio archivo de
dependencias**. Instala una lista corta de paquetes de primer nivel con
`--constraint requirements.txt`, así que las versiones salen del mismo archivo que el entorno
completo. Un `requirements-serve.txt` separado habría sido más obvio de leer y habría abierto la
puerta a que los pines se desincronicen en silencio, que es peor que una línea menos legible.

**Alternativa descartada.** Una sola imagen con todo. Habría sido más simple y son 2,4 GB de
diferencia en el artefacto que se despliega.

---

## D14 · La imagen es de CPU por diseño, y el build lo verifica

**Decisión.** `torch==2.4.1+cpu` desde el índice CPU de PyTorch, `nvidia-nccl-cu12` desinstalado, y
un paso de build que **falla** si aparece cualquier paquete `nvidia-*` o `triton`.

**Por qué.** En Linux el `torch==2.4.1` de PyPI es la build CUDA y arrastra los paquetes `nvidia-*`,
del orden de 2,5 GB de wheels. No hay GPU en el host de la defensa y los modelos servidos son
LightGBM. La variante `+cpu` satisface el pin de `requirements.txt` porque PEP 440 permite el
sufijo local, así que no hay que tocar el archivo de dependencias.

Esto no se nota en Windows: ahí `pip install torch==2.4.1` ya trae CPU por defecto, que es por qué
el entorno local dice `2.4.1+cpu` sin haber hecho nada especial. El problema aparece solo al
construir la imagen.

**Un segundo hallazgo, que costó un build fallido.** Después de sacar torch del camino, la imagen
seguía trayendo `nvidia-nccl-cu12`: son 454 MB medidos y los declara **xgboost 2.1.1** como
dependencia dura en Linux, para comunicación multi-GPU que este proyecto no usa.

El primer intento fue `pip install --no-deps xgboost==2.1.1` antes de `requirements.txt`. **No
funciona**, y el guard lo detectó: pip completa las dependencias faltantes de un paquete que ya
está instalado, así que el `-r requirements.txt` posterior vuelve a traer nccl. La solución es
desinstalarlo **después**. Verificado en el contenedor que sin nccl xgboost importa, entrena con
`tree_method="hist"` y predice.

**Por qué el guard y no solo el fix.** Una dependencia futura puede volver a arrastrar el stack
CUDA, y 2,5 GB extra en una imagen no se notan hasta que alguien intenta subirla a un registry.
Con el guard el build falla y dice qué paquete lo trajo. Ya disparó una vez de verdad, que es la
única forma de saber que un chequeo sirve.

---

## D15 · Los datos son volúmenes, no capas de la imagen

**Decisión.** `data/`, `artifacts/` y `reports/` se montan como volúmenes. El `.dockerignore` los
excluye del contexto de build.

**Por qué.** `data/` pesa cientos de MB y `artifacts/` cambia en cada entrenamiento. Metidos en una
capa, la imagen quedaría inmutable respecto de los datos: reentrenar exigiría un rebuild de 3,5 GB.
Montados, se entrena en el host o con el perfil `pipeline` y los dos servicios ven el resultado sin
reconstruir nada.

**Detalle de permisos.** En los servicios de consulta los tres se montan **de solo lectura**.
Ningún servicio que responde consultas tiene por qué escribir en la capa de datos, y que no pueda
es una garantía y no una molestia. Solo el perfil `pipeline` monta con escritura.

**Consecuencia operativa que el frontend debería exponer.** Un artefacto entrenado sobre una capa
de datos distinta de la servida devuelve predicciones plausibles e idénticas para todas las series
(ver D12 y la sección de validación del README). Hay un chequeo al arrancar la API que lo loguea;
verificado dentro del contenedor, avisa «el modelo conoce 60 de las 3066 series del panel servido».

---

## D16 · El proyecto se llama Blindside

**Decisión.** El nombre es **Blindside**. El paquete Python pasa de `blindside` a `blindside`, y el
repo de `blindside-core` a `blindside-core`.

**Por qué ese nombre.** Los quiebres de stock te toman del lado ciego: la venta cae a cero y el
ERP no registra que hubo demanda. El nombre apunta al punto ciego de los datos, que es el
diferencial del proyecto, y no al pronóstico, que es la parte commodity donde ya compiten Prophet,
Chronos, Nixtla y Darts.

Frase de defensa, que sale sola y es el test que el nombre tiene que pasar:

> «Los quiebres de stock te toman del lado ciego: la venta cae a cero y tu ERP no registra que
> hubo demanda. Blindside recupera esa demanda antes de pronosticar.»

**Alternativas descartadas, y por qué.**

| Nombre | Motivo del descarte |
|---|---|
| `trAIl` | El infijo `AI` no sobrevive en minúsculas, o sea que desaparece en imports, URLs, pip y al pronunciarlo. Y grita AI en un proyecto sin un solo LLM ni agente, lo que lee como sobreventa |
| Vestige | Colisión triple: `samvallad33/vestige` tiene 624 estrellas, está activo, y vive en agentic AI y MCP, que es la audiencia declarada del portfolio |
| Blindsight | Mejor metáfora que Blindside (el fenómeno neurológico real), pero el paquete está tomado por un proyecto activo de MCP e incident response. Misma trampa que Vestige |
| Sonar | La mejor metáfora de todas y el nombre más inusable: SonarQube y SonarSource dominan el término en software. Un revisor asume análisis estático antes de leer la descripción |
| Tobit | Es *el* modelo econométrico para datos censurados, pero atrae justo a quien va a notar que `TobitEWMARecovery` es una heurística con EWMA y no una verosimilitud censurada. Prometer precisión técnica que el código no entrega |
| Penumbra | Buena metáfora, PyPI squatteado desde 2019 y ruido de marca con penumbra.zone |
| Occlude | El paquete está activo con una herramienta de blur de video por recato religioso. Adyacencia incómoda |

**Un patrón que apareció en la búsqueda y conviene registrar.** La escena de observabilidad
agéntica está consumiendo rápido todo el territorio semántico de «conocimiento oculto»: Vestige y
Blindsight cayeron por lo mismo, los dos tomados por proyectos de MCP que razonan sobre lo que no
se puede ver. Si en el futuro hace falta otro nombre de esa familia, hay que verificar antes.

### La consecuencia del rename que no era obvia

`joblib` graba la **ruta del módulo dentro del pickle**. Al renombrar el paquete, todo artefacto
serializado antes del cambio quedó inservible con `ModuleNotFoundError: No module named 'dfcore'`.

Y ahí apareció un bug de resiliencia que el rename solo expuso: **la API explotaba en el arranque**
y el contenedor entraba en bucle de reinicio. Manejaba bien el caso «no hay artefacto» — arrancaba
con `model_loaded: false` — pero no el caso «hay uno y está roto».

Eso no es una excepción excepcional. La misma falla aparece con cualquier desfasaje entre artefacto
y código: una clase renombrada, un módulo movido, una versión de scikit-learn distinta de la que
serializó. Es una condición esperable en operación, así que ahora degrada a `model_loaded: false`
con el motivo visible en `/health`, y los endpoints que dependen del modelo responden 503
distinguiendo los dos casos, porque se arreglan distinto: uno pide entrenar, el otro reentrenar.

El dashboard no se ve afectado porque lee los parquet directamente, que es exactamente para lo que
se diseñó así.

Cubierto por `tests/test_api.py`, que simula un artefacto ilegible y verifica que la API arranque
igual.

**Nota sobre PyPI, que no fue un filtro.** Publicar en PyPI es Fase 2, después de la defensa
(sección 16 del plan, bajo «no empezar antes»). Lo que sí hace falta y ya está es `pyproject.toml`
más `pip install -e .`, que es instalación editable local y nunca toca internet: es lo que permite
que tests, notebooks, API, app y contenedor importen el paquete sin manipular `sys.path` (ver D3).
Casi toda palabra inglesa común está squatteada en PyPI por algo muerto de 2010-2014, así que el
filtro real nunca fue el paquete sino la existencia de un proyecto activo y prominente en la misma
audiencia. `blindside` está libre en PyPI de todos modos.

---

## D17 · Dos artefactos, uno por base de cálculo

**Decisión.** `make train` serializa **dos** modelos con la misma arquitectura y los mismos
hiperparámetros: `model.joblib` entrenado sobre demanda latente recuperada y `model_observed.joblib`
sobre venta observada. La API elige según `recover_censoring` y **declara en la respuesta** con cuál
contestó.

**Por qué.** El toggle de censura es el control central de la interfaz y tenía que cambiar la
**decisión**, no solo el dibujo. Con un solo artefacto lo único que se podía hacer era mostrar dos
series históricas distintas y una única cantidad a pedir, y eso vacía el argumento del proyecto:
si corregir la censura no mueve la orden, corregirla no sirve para nada operativo.

Medido sobre 25 series con `q* = 0,625`: el pronóstico sube 25,3 % y la orden 27,3 %.

**Por qué no un solo modelo con un ajuste a la salida.** Porque el sesgo de la censura se aprende
**durante** el entrenamiento: el modelo sobre venta observada aprende que los días con quiebre
tienen venta baja y lo propaga a sus lags y rollings. Escalar su salida después reproduciría el
efecto que se quiere medir, en vez de medirlo. Es la misma razón que da D10 para que la ablación sea
pareada.

**Lo que costó.** Dos artefactos abren una falla nueva: servir el equivocado. Un artefacto cruzado
—el de demanda latente servido como base observada— haría que las dos posiciones del toggle
devuelvan el mismo número, y la interfaz mostraría una comparación que no existe **sin fallar**. Por
eso al cargar se compara el target con el que se entrenó el artefacto contra el que la base declara
y se **rechaza** si no coinciden. Hay un test que serializa un artefacto cruzado a propósito.

---

## D18 · CORS con allowlist explícito, nunca comodín

**Decisión.** La API publica `BLINDSIDE_CORS_ORIGINS` con una lista explícita de orígenes; por
defecto los puertos 5173 y 4173 de Vite. No usa `allow_origins=["*"]`.

**Por qué.** La API **no tiene autenticación** — está declarado en el README y es deliberado para el
alcance del prototipo. Con esas dos cosas juntas, el comodín significa que cualquier página abierta
en el navegador de un usuario puede leer los pronósticos y las cantidades de reposición de todas las
tiendas, que es información comercial sensible. El comodín es el default cómodo justamente en el
caso en que es más peligroso.

**Por qué el front no usa un proxy de Vite.** Sería más fácil y es lo que hace la mayoría de los
tutoriales, pero volvería todas las llamadas same-origin y esconderían un CORS mal configurado
**hasta el despliegue**, que es el peor momento para descubrirlo. Llamando por HTTP desde el
principio, un origen faltante falla en desarrollo.

---

## D19 · El plan comercial del horizonte se declara, y su default está medido

**Decisión.** Los tres endpoints que arman un índice de futuro aceptan un `plan` opcional con las
tres covariables conocidas de antemano — descuento, feriado y actividad comercial. Cuando no viene,
el servidor asume la **mediana de los últimos 21 días del panel** y lo declara en la respuesta con
`source: "panel_median"`.

**El problema que resuelve.** Esas tres covariables no son fuga porque se conocen antes del día
objetivo, así que el modelo las usa. El estado congelado del origen las descarta a propósito: son
del día objetivo y tienen que venir del índice de futuro. El arnés de backtesting las pone, porque
el fold cae dentro del panel y esos días ya existen. **La API no las ponía**, porque su horizonte
empieza después del último día del panel y no hay de dónde leerlas. Llegaban en NaN.

De las 73 features del modelo eran exactamente esas tres las únicas nulas. Y no fallaba: LightGBM
trata el NaN como una rama más, así que la API contestaba 200 con un número plausible.

**Cuánto costaba.** Medido sobre un fold real (train hasta 2024-06-25, test del 26 de junio al 2 de
julio, 21.462 filas):

| Covariables del horizonte | MASE | vs. reales | Cantidad a pedir | vs. reales |
|---|---|---|---|---|
| Reales, del panel (oráculo) | **0,8790** | — | 35.011 | — |
| **Mediana de 21 días, global** · el default | **0,9437** | **+7,4 %** | 32.787 | −6,4 % |
| Mediana de 21 días, por serie | 0,9513 | +8,2 % | 33.692 | **−3,8 %** |
| Precio de lista, sin campaña | 0,9571 | +8,9 % | 30.390 | −13,2 % |
| Persistir el último día conocido | 0,9573 | +8,9 % | 33.406 | −4,6 % |
| Las tres en NaN · lo que servía la API | **1,6392** | **+86,5 %** | 53.391 | **+52,5 %** |

**1,64 es peor que el naive estacional**, que da 1,10. La API publicaba pronósticos peores que el
baseline que el proyecto dice superar.

**Por qué la mediana global y no las otras.** Gana en MASE y, sobre todo, **es un escalar**: entra
en el contrato como tres números y no obliga a que el request o la respuesta lleven un plan por
serie. La mediana por serie da una orden más cercana al oráculo (−3,8 % contra −6,4 %) y es la
mejora natural siguiente, pero convierte `CommercialPlan` en una estructura por serie y eso cambia
el contrato de la API para ganar 2,6 puntos en una sola métrica.

Precio de lista se descartó aunque es el default más "obvio": subestima la orden **13,2 %**, porque
el 45,9 % de las filas del panel tiene descuento y el descuento sube la demanda. Un default que
parece neutro y sesga sistemáticamente hacia abajo es peor que uno que se ve raro y no sesga.

**Por qué se declara en la respuesta y no solo en la documentación.** Porque el default se resuelve
del lado del servidor. Una respuesta que no dice qué descuento asumió no se puede auditar, y el plan
mueve la orden de verdad: con descuento 0,8 y campaña activa, la orden sube 12,4 % sobre el default.

**Lo que sigue faltando.** Nada de esto es tan bueno como que quien consulta aporte su plan
comercial, que es quien lo conoce. El campo existe para eso; el default es para que la demo no
mienta mientras nadie lo aporta.

---

## D20 · El conformal no descarta los cuantiles del modelo que envuelve

**Decisión.** `ConformalForecaster.predict_quantile` delega en el modelo base cuando el base sabe
dar cuantiles. Solo interpola entre los límites del intervalo cuando envuelve un modelo puntual.

**Por qué.** El artefacto servido es un conformal envolviendo un LightGBM cuantílico. Su
`predict_quantile` interpolaba **siempre**, así que la cantidad a pedir salía de la forma de la
banda conformal y no del cuantil `q*` entrenado con pérdida cuantílica. Medido sobre 25 series, la
banda daba `q0,625 = 1,93` donde el booster entrenado da 1,52: una orden **21,5 % más alta**. Y como
la banda está sobre-inflada —cubre 99,5 % cuando promete 90 %— el error iba siempre hacia arriba.

Los niveles, para ver de dónde viene la diferencia:

| Nivel | Booster entrenado | Derivado de la banda |
|---|---|---|
| q0,05 | 0,5967 | 0,0032 |
| q0,50 | 1,3120 | 1,3136 |
| **q0,625** | **1,5190** | **1,9339** |
| q0,90 | 2,0573 | 3,2985 |
| q0,95 | 2,3001 | 3,5466 |

La mediana coincide, que es lo que hacía al defecto difícil de ver: un gráfico de pronóstico central
se veía bien.

**Por qué importa más que el 21,5 %.** El README afirma que «el modelo se entrena con pérdida
cuantílica en ese `q*`, así que su salida **es** la orden». Para el artefacto servido eso no era
cierto, y es la frase que sostiene el diferencial del proyecto.

**Un segundo bug en el mismo camino.** La API pedía los cuantiles con
`getattr(model, "quantiles", cfg.FORECAST.quantiles)`, y `ConformalForecaster` no exponía
`quantiles`: `hasattr` daba `False` y caía al default del config, que **no incluye** `q* = 0,625`.
O sea que incluso con los cuantiles del base, `q*` se habría interpolado entre 0,5 y 0,9 teniendo
un booster entrenado exactamente en 0,625. Se agregó la propiedad que delega al base.

**Lo que no se arregla acá.** La banda sigue sobre-inflada; lo que cambia es que la orden ya no
depende de ella. La corrección de la banda es CQR y está en el Roadmap.

---


## D21 · CQR en vez del conformal de residuos absolutos

**Decisión.** El artefacto servido es **CQR** — Conformalized Quantile Regression, Romano,
Patterson y Candès, NeurIPS 2019 — envolviendo el LightGBM cuantílico. El conformal de residuos
absolutos queda en el registro del backtest como contrafactual, no como modelo servido.

**El problema, medido.** La cobertura empírica del intervalo es una de las **tres métricas de
éxito** que el proyecto declara en su formulario de aprobación, y era la única que no se cumplía.
Sobre las 3066 series con 8 orígenes:

| Modelo | Nominal | Empírica | Brecha | Ancho medio | Desvío del ancho |
|---|---|---|---|---|---|
| Conformal de residuos, adaptativo | 90 % | 98,7 % | +8,7 pts | 3,834 | 0,526 |
| **CQR** | 90 % | **88,0 %** | **−2,0 pts** | **1,805** | 0,153 |

Cubrir 98,7 % cuando se promete 90 % no es prudencia. Se paga con un intervalo del **doble** de
ancho, y un intervalo ancho no sirve para decidir: el caso degenerado de esa lógica es
`[0, ∞)`, que cubre el 100 % y no informa nada.

**El MASE es idéntico en los dos: 0,8217.** CQR no toca la predicción central, solo el intervalo.
Es lo que hace la comparación limpia — no hay que descontar ninguna mejora de exactitud.

**Por qué el otro no se podía arreglar ajustando un parámetro.** Y esta es la parte que importa,
porque el primer instinto es subir o bajar un cuantil. Su score de conformidad es un residuo
**absoluto**, así que el cuantil sale siempre positivo y la mecánica **solo sabe ensanchar**. No
tiene forma de expresar «esto está demasiado ancho». El score de CQR es

    E_i = max(q_lo(x_i) − y_i,  y_i − q_hi(x_i))

que es **negativo cuando el punto cayó dentro** del intervalo, así que la corrección puede
apretar. Esa es la diferencia estructural, no un ajuste de calibración.

**De dónde venía la inflación.** Del notebook `01`: el p99 de la demanda diaria es doce veces la
mediana. Un cuantil de residuos agrupado sobre ese panel queda dominado por la cola y le pega una
semiamplitud enorme a la serie típica. Medido sobre un fold, las semiamplitudes del conformal de
residuos van de 6,44 a 7,05 mientras las correcciones de CQR van de +0,11 a +0,59: **dos órdenes
de magnitud**. La variante `adaptive` intentaba lo mismo escalando por una dispersión *por serie*,
que es una aproximación mucho más gruesa — no ve el día, ni la promoción, ni el quiebre. Los
cuantiles del base sí.

**Lo que CQR no hace.** No toca la cantidad a pedir. Esa sale del booster entrenado en `q*`, que
es lo que arregla D20, y `predict_quantile` delega en el base sin tocar. Mezclar el intervalo con
la decisión fue el defecto anterior y hay un test que lo fija.

**Los dos puntos de sub-cobertura, declarados.** 88,0 % contra un nominal de 90 % es una
desviación real. La garantía del split-conformal supone intercambiabilidad, y una partición
temporal la cumple de forma aproximada: el tramo de calibración son los últimos días del train y
el test es el futuro inmediato, que no es lo mismo que dos muestras intercambiables. La
alternativa era seguir cubriendo 98,7 % con una banda inútil.

**Y una limitación más de fondo, que no es de esta decisión sino del método.** La garantía es
**marginal, no condicional**: el 88 % global puede esconder subgrupos peores. El desglose por
horizonte del notebook `05` muestra pasos intermedios en 0,85. Corregirlo exige conformal
condicional o por grupo, y está en el Roadmap.

**Un bug que apareció en la primera corrida y quedó con test.** `1 - cfg.FORECAST.coverage` da
`0.09999999999999998`, así que `alpha / 2` sale `0.04999999999999999` y el LightGBM cuantílico
rechaza el nivel porque entrenó en 0,05 exacto. El nivel es una cantidad **nominal** que viene de
la configuración, no el resultado de un cálculo, así que se canoniza con `round`.

---

## D22 · El contraste clasico va con orden declarada, y Prophet queda opcional

**Decision.** M6 se cierra con **SARIMA de orden fija** `(1,0,1)(1,0,0)[7]` desde
`statsforecast`, y **Prophet** como dependencia opcional que el arnes saltea si no esta. Los dos
se miden sobre una submuestra declarada de 400 series con los mismos 8 origenes.

**Por que hacen falta.** El proyecto defiende un modelo **global** y la objecion natural es que
podria estar ganando solo porque se comparo contra baselines simples. El pronostico de series
temporales tiene una tradicion de modelos **por serie**; si el global no les gana, no hay nada que
defender. Es la comparacion que un panel pregunta primero.

**Resultado, sobre 400 series y 8 origenes:**

| Modelo | MASE | Desvio | Peor origen |
|---|---|---|---|
| LightGBM global | **0,8386** | 0,0549 | 0,9029 |
| Croston SBA | 0,9032 | 0,0707 | 0,9873 |
| SARIMA | 0,9136 | 0,0599 | 0,9832 |
| Media movil 21 d | 0,9139 | 0,0652 | 0,9927 |
| Prophet | 0,9698 | 0,0704 | 1,0502 |
| Naive estacional | 1,1058 | 0,0674 | 1,1761 |

Lo que mas dice no es que el global gane por 8,2 % contra SARIMA, sino que **SARIMA queda empatado
con la media movil de 21 dias** — 0,9136 contra 0,9139 — y pierde contra Croston. Todo el aparato
ARIMA no compra nada sobre un promedio simple en este panel. Es consistente con series cortas (97
dias), intermitentes, y con una estacionalidad semanal que un rolling ya captura.

**Por que el orden es declarado y no buscado.** `AutoARIMA` busca el orden por serie y cuesta
**2,3 s por serie** medido sobre este panel; la orden fija cuesta **85 ms**. Son 27 veces, o sea
la diferencia entre 2 horas y 4,6 minutos para 400 series por 8 origenes.

Fijar el orden podria parecer una forma de hacer perder al contraste, asi que se midio: sobre 60
series, la orden fija da MASE **0,9566** y `AutoARIMA` **0,9657**. La version barata es *mejor*,
asi que no hay handicap que descontar. La variante queda registrada como `sarima_auto` para que la
comparacion sea reproducible.

El orden elegido sale de lo que el panel muestra en el notebook `01`: serie diaria con
estacionalidad semanal clara y sin tendencia marcada en 97 dias, o sea `d = 0` con un AR y un MA
estacionales.

**Por que Prophet queda opcional.** Su instalacion arrastra un backend de Stan, y el plan lo
declara aislado del camino critico. El import es perezoso, `ProphetForecaster.disponible()` deja
que el arnes lo saltee, y el `ImportError` trae las instrucciones. Con 97 dias Prophet queda
reducido a tendencia a tramos mas estacionalidad semanal — no hay ciclo anual que estimar y los
feriados ya viajan como covariable en el global —, asi que el contraste es legitimo pero conviene
decir que no esta en su terreno. Su peor origen pasa de 1,05, o sea peor que la escala del naive
estacional.

Dos detalles de la implementacion que costaron tiempo y quedan escritos para que no se repitan:

- `growth="flat"` y no `linear`. Con 97 dias, una tendencia lineal ajustada por serie extrapola
  con mucha confianza a 7 dias, y es la forma tipica en que Prophet falla en series cortas.
- El pin **`cmdstanpy==1.2.4`** no es decorativo. prophet 1.1.6 resuelve `cmdstanpy>=1.0.4`, asi
  que pip instala la 1.3.0, y con esa el bundle de cmdstan del wheel queda sin makefile: el
  backend no carga y Prophet falla con `AttributeError: 'Prophet' object has no attribute
  'stan_backend'`, que no dice nada sobre la causa real.

**Un agujero de reproducibilidad que esto destapo, y que no tenia nada que ver con M6.** `scipy`
no estaba fijado, aunque numpy, pandas y scikit-learn si. Entraba como dependencia transitiva, asi
que `make setup` resolvia la ultima version — y scipy 1.15 removio `scipy._lib._util._lazywhere`,
que `statsmodels 0.14.4` importa al arrancar.

El efecto: `statsforecast` estaba **fijado en `requirements.txt` y era ininstalable de hecho** en
un entorno nuevo. No se noto durante semanas porque ningun modulo del proyecto lo importaba
todavia. Ahora `scipy==1.17.1` esta fijado y `statsmodels` subio a 0.14.6, que es la ultima de su
serie y no cambia ninguna API que este proyecto use.

La leccion general: en un proyecto que fija versiones, **una dependencia transitiva sin pin es un
pin que falta**, no una decision de dejarla libre.

---

## D23 · El cluster de perfiles no entra al modelo servido, y la razon esta medida

**Decision.** M4 queda implementado — `DemandProfileClusters` (K-Means), `dbscan_profiles`
y `WindowAnomalyDetector` (Isolation Forest) en `src/blindside/unsupervised/` — pero la feature
de cluster **no se agrega al pipeline por defecto**. Se puede activar con `add_feature`, y la
decision de no activarla sale de dos mediciones.

### Medicion 1 · el efecto sobre el modelo es indistinguible del ruido

Comparacion pareada sobre 600 series, tres origenes, el mismo LightGBM con y sin la columna:

| Origen | Sin cluster | Con cluster | Delta |
|---|---|---|---|
| 2024-06-11 | 1,5461 | 1,3952 | **−9,76 %** |
| 2024-06-18 | 1,1271 | 1,1215 | −0,49 % |
| 2024-06-25 | 1,1123 | 1,2356 | **+11,08 %** |
| **Media** | 1,2618 | 1,2508 | **+0,28 %** |

El efecto medio es **tres decimas de punto** y la oscilacion entre origenes es de **±11 puntos**.
La dispersion aplasta al efecto, asi que lo honesto es decir que la feature no aporta senal
medible, no que ayuda ni que perjudica.

**Con un solo fold habria escrito lo contrario.** El primer origen que mire fue el 25 de junio,
donde la feature empeora 11 %, y la conclusion escrita habria sido "el cluster perjudica al
modelo". El origen anterior dice lo opuesto con casi la misma magnitud. Es el argumento de la
metodologia del proyecto — nunca una metrica sin su dispersion entre origenes — aplicandose a una
decision de diseno y no solo a un reporte.

**Por que es plausible que no aporte.** El modelo ya recibe `store_id` y `product_id` como
categoricas, que **identifican la serie exactamente**, mas 70 features de rezagos y estadisticos
moviles. El cluster es un resumen grueso y con perdida de informacion que el modelo ya tiene de
forma mas precisa. Lo unico que agrega es una particion de baja cardinalidad que al arbol le
resulta comoda para partir y que generaliza peor.

### Medicion 2 · el arranque en frio no se puede medir en este panel

Es la razon de fondo, y es una limitacion del dataset y no del metodo. El proposito declarado del
clustering en M4 es mejorar el **arranque en frio**. Medido sobre las 3066 series:

- Dias por serie: minimo **97**, mediana 97, maximo 97. Todas completas.
- Series con menos de 21 dias de historia: **0**.
- Series que empiezan a vender despues del dia 30: **0** (el maximo es el dia 16).

**No hay una sola serie de arranque en frio.** FreshRetailNet entrega ventanas completas por
construccion, asi que la condicion que la feature ataca no ocurre nunca en los datos disponibles.
Se puede mostrar el mecanismo — `assign` le da el grupo modal a una serie nueva — pero **no se
puede medir el beneficio**, y una feature cuyo beneficio no se puede medir no entra al artefacto
que se sirve.

### Lo que si quedo medido, y es informativo

**La silueta es baja: 0,21 con `k = 6`**, que es el mejor de los candidatos (3 → 0,198; 4 → 0,210;
5 → 0,204; 6 → **0,212**; 8 → 0,211; 10 → 0,195). Un 0,21 dice que los grupos existen pero estan
pegados: el espacio de formas de demanda es mas un **continuo** que un conjunto de nichos. DBSCAN
lo confirma desde el otro lado: con los parametros por defecto deja el **19,6 %** de las series
(600 de 3066) en la clase de ruido y encuentra solo 2 grupos densos.

Eso no invalida los grupos, que **si** son interpretables:

| Cluster | Series | Demanda media | Tasa de ceros | Tasa de quiebre |
|---|---|---|---|---|
| 5 | 655 | 1,907 | 0,012 | 0,594 |
| 4 | 158 | 1,530 | 0,030 | 0,454 |
| 1 | 697 | 1,253 | 0,000 | 0,417 |
| 2 | 1382 | 0,865 | 0,032 | 0,380 |
| 0 | 152 | 0,778 | 0,209 | 0,421 |
| 3 | 22 | 0,647 | 0,251 | 0,385 |

Se lee sin esfuerzo: los grupos 0 y 3 son los intermitentes de baja rotacion, y el 5 es el de alta
rotacion con mas quiebres — coherente, porque lo que rota es lo que se agota.

**La particion es estable entre origenes**, que es el requisito minimo para que sirva de feature:
el indice de Rand ajustado entre el ajuste del 18 y el del 25 de junio es **0,832** sobre las 3066
series comunes. Si hubiera salido cerca de 0, la feature habria cambiado de significado cada
semana.

### La deteccion de anomalias apunta a lo que NO esta anotado

El plan la pide "para marcar cargas erroneas **y quiebres**". La mitad de eso ya esta resuelta:
el dataset **anota el quiebre hora por hora**, asi que estimarlo con un modelo no supervisado
seria reemplazar una etiqueta por una inferencia peor. Lo que no viene etiquetado es el resto, y
ahi apunta el detector.

Sobre 236.082 ventanas de 14 dias, marcando el 1 % mas raro:

| | Valor |
|---|---|
| Ventanas marcadas | 2.361 |
| De esas, ya eran quiebre | **49,9 %** |
| Tasa de quiebre del panel | 42,4 % |
| Hallazgos que **no** eran quiebre | **1.182** |

El 49,9 % contra una tasa base del 42,4 % es la cifra que importa: el detector **no** es un
redescubridor de quiebres, porque apenas se corre siete puntos del azar en esa dimension. Su
aporte son las 1.182 ventanas raras que ninguna columna marcaba, que es exactamente el material
que contamina un entrenamiento en silencio.

### Un bug que la medicion destapo, y que sin medir no se habria visto

La primera version de `add_feature` devolvia la columna como `category` de pandas. Las dos ramas
dieron MAE **0,6098 identico a cuatro decimales**, y eso es lo que delato el problema:
`features.build.feature_columns` filtra la matriz a dtypes **numericos**, asi que la columna
categorica se descartaba en silencio y el modelo entrenaba sin ella.

La convencion correcta del proyecto es la que ya usan `store_id` y `product_id`: viajan como
enteros y se declaran en `categorical_features`, y es LightGBM el que las trata sin orden. Hay un
test de regresion que verifica que `CLUSTER_COL` sobreviva a `feature_columns`.

Vale la pena registrar la forma del error: **una feature que no llega no da una excepcion, da el
mismo resultado**. Sin la comparacion pareada, "no cambio nada" se habria leido como "no aporta".

---

## D24 · La busqueda de hiperparametros optimiza el backtest, y su resultado no se adopta

**Decision.** La busqueda con Optuna (`src/blindside/models/tuning.py`, `make tune`) usa como
objetivo el **mismo `run_backtest`** que produce las metricas oficiales, con origenes moviles. Y
su resultado **no se adopta**, porque la mejora que encontro es menor que la dispersion entre
origenes.

### Por que no una validacion cruzada

Un `GridSearchCV` con K-Fold aleatorio es la forma mas rapida de conseguir un numero excelente y
falso. Sobre datos de panel, cada fold aleatorio contiene dias **posteriores** a los de su propio
train, asi que la busqueda optimiza contra un problema mas facil que el real y elige parametros
para ese problema. El proyecto tiene ocho asserts antifugas para el camino de entrenamiento; abrir
la fuga en la seleccion de hiperparametros la dejaria entrar por la puerta de al lado.

El costo de la decision es que **cada trial vale un backtest completo**, y por eso el alcance esta
reducido: 400 series y 4 origenes contra las 3066 y 8 de la corrida oficial. Eso se declara en el
reporte en vez de presentarse como si se hubiera buscado sobre todo.

### El objetivo penaliza la dispersion

No es el MASE medio pelado sino `media + 0,5 x desvio entre origenes`. Un conjunto que promedia
0,82 oscilando entre 0,70 y 0,95 es **peor en produccion** que uno que promedia 0,84 con desvio
0,02, porque lo que se sufre es el origen malo y no el promedio. Es el mismo criterio con el que
el README reporta todas las metricas, aplicado a la funcion que se optimiza.

### `objective` no esta en el espacio de busqueda

La eleccion de `regression_l1` sobre `regression_l2` es una decision documentada (D10: con cola
derecha larga se quiere la mediana, no la media), no un hiperparametro. Si estuviera en el espacio,
la busqueda podria revertirla por unas milesimas de MASE y **cambiar el significado de la salida**
sin que nada avise. Hay un test que falla si `objective` o `metric` aparecen en el espacio.

Los rangos estan centrados en los valores actuales y no en los de la libreria, con un test que
verifica que cada default caiga **dentro** de su rango: un espacio que excluye el punto de partida
no puede responder la pregunta "se puede mejorar lo que ya hay".

### El resultado, y por que no se adopta

25 trials con TPE sobre 400 series y 4 origenes:

| | MASE | Desvio entre origenes | Objetivo |
|---|---|---|---|
| Parametros actuales | 0,8672 | 0,0134 | 0,8739 |
| Mejor encontrado | 0,8630 | 0,0153 | 0,8707 |

La mejora es de **0,0042 de MASE (+0,49 %)** y la dispersion entre origenes de los parametros
actuales es de **0,0134** — tres veces mas grande. Adoptar esos valores seria confundir una
realizacion afortunada del azar sobre los cuatro origenes elegidos con una mejora real.

Notar ademas que el mejor conjunto tiene **mas** dispersion que el actual (0,0153 contra 0,0134),
que es la forma tipica en que una busqueda sobreajusta a los folds que vio.

**El criterio estaba en el codigo antes de ver el numero.** `Resultado.vale_la_pena` compara la
mejora contra el desvio de la referencia, y `escribir_reporte` **deriva** la conclusion de los
numeros en vez de llevar un texto fijo. Es el mismo arreglo que se le hizo al generador de la
ablacion, donde una frase fija afirmaba que el resultado "reproduce el valor publicado" mientras
la tabla de arriba mostraba un factor de 2,2. Un reporte que puede contradecir su propia tabla es
un reporte que en algun momento lo va a hacer.

### Lo que el resultado dice del proyecto

Que los parametros elegidos a mano ya estaban en una zona razonable, y — mas util — que **el
margen que queda en hiperparametros es chico comparado con el que queda en otras partes**. Para
contrastar, en este mismo proyecto: corregir el desajuste train/serve de las tres covariables del
horizonte valia **86 % de MASE** (D19), y separar el cuantil del booster del de la banda conformal
movia la orden **21 %** (D20). Medio punto de hiperparametros no esta en esa escala.

La referencia siempre se evalua primero, con los parametros actuales. Sin esa fila, cualquier
busqueda "encuentra una mejora" por construccion, porque se compara contra su peor trial.

---

## D25 · El triage de cartera da grupos con motivo, no un ranking ni un score

**Decision.** La portada del dashboard responde «de las 3.066 series, cuales miro primero», y lo
hace con **cuatro grupos por motivo** en vez de un top N o un indice de criticidad. Las dos
alternativas se descartaron por medicion, no por gusto.

### Por que no un «top 10 productos criticos»

Porque el costo esta **repartido**. Medido sobre el panel con el costo de newsvendor realizado por
serie:

| Corte | Share del costo |
|---|---|
| Top 1 % de series (30) | 4,8 % |
| Top 5 % (153) | 16,6 % |
| Top 10 % (306) | 26,5 % |
| Top 20 % (613) | 41,4 % |
| Top 50 % (1.533) | 70,2 % |

Un Pareto fuerte pondria 70-80 % en el top 20 %; acá el top 20 % junta 41 %, o sea apenas el doble
de lo proporcional. Con esa forma, **un corte en la posicion 10 es arbitrario**: la serie 11 se
parece a la 10 y la 50 no es cualitativamente distinta. Un «top 10» daria la impresion de que hay
un puñado de culpables cuando no los hay.

### Por que no un score compuesto de criticidad

Porque **los ejes son ortogonales**, y promediarlos destruye la unica informacion accionable.
Medido por correlacion de Spearman y por solapamiento de los top 50:

| Par de ejes | Spearman | Top 50 en comun |
|---|---|---|
| Volumen vs error normalizado (MASE) | +0,36 | **0 de 50** |
| Volumen vs fraccion estimada | −0,06 | **0 de 50** |
| Volumen vs racha vigente | +0,08 | 0 de 50 |
| Fraccion estimada vs tasa de quiebre | +0,70 | 20 de 50 |

Cero series en comun entre el top 50 por volumen y el top 50 por error significa que son
**preguntas distintas sobre el catalogo**. Un indice que los promedie produce un numero que no
contesta ninguna, y pierde lo que sirve: el remedio para «el modelo no le acierta a esta serie» no
es el mismo que para «viene quebrada tres dias». Por eso la salida es un grupo con **motivo** y
cada motivo trae **que hacer**.

### Un eje que se descarto por redundante

El **MAE por serie** parecia el candidato natural para «donde el modelo falla», y **no sirve**:
correlaciona **0,861** con el nivel de demanda, con 23 de 50 series compartidas en el top 50. Es
obvio en retrospectiva — el MAE esta en unidades de demanda, asi que rankear por MAE es rankear por
volumen con otro nombre.

Dividido por el denominador de MASE de cada serie, la correlacion con el nivel baja a **0,364** y el
solapamiento del top 50 cae a **0**. La leccion general: **una metrica de error sin normalizar no es
un eje propio**, es la variable de escala disfrazada.

Lo mismo le pasa al costo de newsvendor realizado: correlaciona 0,985 con el MAE y 0,856 con el
nivel, asi que un «top por plata perdida» seria otra vez un top por volumen. Es la razon de que el
grupo de volumen se llame «Alto volumen» y no «Mayor impacto economico»: es lo que realmente mide.

### Los cuatro grupos y sus cortes

| Grupo | Corte | Series | % catalogo | % volumen |
|---|---|---|---|---|
| Alto volumen | nivel ≥ p90 | 307 | 10,0 % | 32,5 % |
| Modelo no confiable | MASE de la serie > 1 | 404 | 13,2 % | 20,8 % |
| Senal escasa | fraccion estimada > 0,30 | 201 | 6,6 % | 7,4 % |
| Quebrado ahora | racha vigente ≥ 5 dias | 108 | 3,5 % | 3,7 % |

Los cuatro juntos aislan el **26,0 %** del catalogo (798 series), y solo 186 caen en dos o mas
grupos. Que el 74 % no tenga motivo es el resultado buscado: el antecedente es la primera alerta de
la interfaz, que usaba `censored_days_last_28 >= 14` cuando la mediana del panel es 12 de 28, y
marcaba el **35,6 %** del catalogo. Una alerta que marca un tercio del catalogo es un color de
fondo. Hay un test que falla si cualquier grupo pasa la mitad.

**Dos cortes son naturales y dos son cuantiles, y conviene distinguirlos.** `MASE > 1` no es
arbitrario: es el punto exacto donde el modelo deja de justificar su existencia para esa serie,
porque le pierde al naive estacional. La `racha vigente ≥ 5` tampoco, porque la variable es discreta
y con 3 dias marcaria el 21,9 % por empates. En cambio el volumen no tiene corte natural, asi que se
usa el p90 y **se declara que es un cuantil**.

### El hallazgo que esto destapo

**404 series (13,2 %) tienen MASE > 1**, o sea que el modelo servido les pierde al naive estacional.
Y **no son las chicas**: su nivel medio de demanda es **2,120** contra 1,344 del panel, asi que son
mas grandes que el promedio, y concentran **20,8 %** del volumen.

El MASE global de 0,8217 es cierto y esconde eso. No es una contradiccion — es la diferencia entre
un promedio y su distribucion — pero es informacion que la interfaz operativa no mostraba y que
cambia como se usa el numero: en esas 404 series conviene mirar la media movil antes de aceptar la
cantidad sugerida.

### Un bug que solo aparecia en Docker

La primera version de la tabla usaba `Styler.background_gradient` de pandas, que exige
**matplotlib**. Matplotlib **no esta en la imagen `serve`**, que deja afuera a proposito todo lo que
no hace falta para responder `/forecast`. En local funcionaba y en el contenedor habria tumbado la
pagina — o sea durante el demo y no durante el desarrollo.

Ahora la tabla usa `st.column_config.ProgressColumn`, que es nativo de Streamlit, y hay tests de
render con `AppTest` que corren la app de verdad. Un `import` no atrapa esto: la pagina compila y
falla al dibujar.

---

## Roadmap

Fuera del alcance de la entrega, en orden de valor:

1. **Inventario perecedero multi-período** con despacho FIFO y decisión dependiente de la edad
   del lote, que reemplaza la aproximación de un solo período (limitación 1 del README).
2. **Lead time y multi-echelon**: depósito central además de tienda, con tiempo de tránsito.
3. **Restricciones operativas de la orden**: cantidad mínima, múltiplos de caja y pallet,
   capacidad de cámara.
4. **Loop de reentrenamiento** disparado por la detección de drift ya existente, con promoción
   de modelo.
5. **Caso secundario con generador sintético**, para verificar que el modelo recupera una
   estructura conocida inyectada a mano.
