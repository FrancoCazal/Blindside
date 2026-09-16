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

**Consecuencia de diseño.** `dfcore.data.freshretail` tiene un contrato explícito: **nunca
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
permite que los notebooks y la app importen `dfcore` sin manipular `sys.path`. Los pines viven
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
