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
