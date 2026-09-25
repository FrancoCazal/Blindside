# Model card · blindside-core

Conecta con el eje de ética y AI Act del programa. La estructura sigue la de Mitchell et al.,
*Model Cards for Model Reporting* (2019).

---

## 1. Detalles del modelo

| Campo | Valor |
|---|---|
| Nombre | `cqr_lgbm_quantile` — CQR sobre un LightGBM cuantílico global, un modelo para todas las series |
| Versión | 0.2.0 |
| Tipo | Gradient boosting sobre árboles, regresión, estrategia directa multihorizonte |
| Pérdida | Cuantílica en `(0,05 · 0,5 · 0,625 · 0,9 · 0,95)`; el `0,625` es la fracción crítica `q*` |
| Envoltorio | Regresión cuantílica conformalizada, que calibra el intervalo y **no** la predicción central |
| Base de comparación | `lgbm_global` con `regression_l1` (estima la mediana), misma matriz de features |
| Entradas | 73 features: rezagos, estadísticos móviles, calendario, historia de quiebres, jerarquía |
| Salida | Demanda latente diaria por tienda-producto, horizonte 1 a 7 días, con intervalo al 90 % |
| Artefactos servidos | **Dos**, con misma arquitectura e hiperparámetros: uno sobre venta observada y otro sobre demanda latente. Ver D17 |
| Licencia | MIT |
| Autor | Franco Cazal · Diplomado ML/DL FIUNA 2026 |

**La salida del cuantílico en `q*` es la orden, sin post-proceso.** Con `Cu` el costo de quedarse
corto y `Co` el de quedarse largo, el newsvendor de un período tiene óptimo en el cuantil
`q* = Cu / (Cu + Co)`, así que entrenar con pérdida cuantílica en ese nivel hace que la predicción
**sea** la cantidad a pedir. El intervalo lo aporta el envoltorio conformal, que es lo que tiene
garantía de cobertura; los dos roles están separados a propósito. Ver D20 y D21.

**Por qué la comparación usa L1 y no L2.** La pérdida absoluta estima la mediana, que en una
distribución con cola derecha larga es lo que se quiere de un pronóstico puntual. L2 estima la
media y queda arrastrada por los picos promocionales. Consecuencia que hay que tener presente al
leer las métricas: el sesgo medido contra promedios sale sistemáticamente negativo por este
motivo, no por un problema del modelo. Ver `docs/decisiones.md` D10.

---

## 2. Uso previsto

**Para qué sirve.** Sugerir cantidades de reposición de productos perecederos por tienda y
producto, con un horizonte de una semana, en una operación donde hoy se decide por promedio
móvil manual.

**Quién lo usa.** El responsable de compras o reposición. La salida es una cantidad, no un
informe: la predicción del modelo cuantílico en `q*` **es** la orden.

**Para qué NO sirve, y esto importa más que lo anterior:**

- **No es un sistema de decisión autónomo.** Emite una sugerencia. La orden la firma una persona.
- **No opina sobre aptitud de la mercadería** ni monitorea equipos de refrigeración. La cadena de
  frío entra como restricción que deforma la economía, no como sistema a controlar.
- **No sirve para productos nuevos** sin historia. El arranque en frío está en el roadmap.
- **No sirve para decisiones de personal.** No se usó ni se debe usar para evaluar desempeño de
  empleados de tienda a partir de desviaciones entre pronóstico y venta: la desviación mide el
  error del modelo, no el trabajo de nadie.
- **No sirve para fijar precios.** El descuento entra como covariable, pero el modelo no estima
  elasticidad y usarlo para eso daría una respuesta con forma correcta y sin fundamento.

---

## 3. Datos

**Fuente primaria.** [FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K)
(Dingdong-Inc, CC BY 4.0). Paper: [arXiv 2505.16319](https://arxiv.org/abs/2505.16319).

| Atributo | Valor |
|---|---|
| Universo | 50.000 series tienda-producto, 898 tiendas, 18 ciudades, 865 SKU perecederos |
| **Subconjunto usado** | **3066 series de 38 tiendas, ciudades 0-2, semilla 42** |
| Ventana | 2024-03-28 a 2024-07-02 (97 días: 90 de `train` + 7 de `eval`) |
| Filas | 297.402 |
| Censura | 43,9 % de días con al menos una hora de quiebre; 19,2 % de horas comerciales |
| Granularidad | Diaria, con anotación de quiebre hora por hora |

**El submuestreo se declara y es una decisión de alcance, no un recorte oculto.** 4,85 M filas con
dos columnas de secuencias de 24 elementos no entran en la máquina de trabajo disponible. Se eligen
**tiendas completas** al azar con semilla fija, conservando todos sus productos, para no romper las
dos jerarquías del dataset. El manifiesto queda en `data/interim/subsample_manifest.json`.

**Datos de terceros: ninguno.** El dataset es público con licencia comercial. El caso de la
organización propia (Focal Point) es **sintético** por confidencialidad de clientes. No se expone
ningún dato de ninguna empresa.

**Representatividad, y sus límites.** El dataset es de retail de fresco chino. La estacionalidad
semanal, la estructura de quiebres y la cola de baja rotación son transferibles conceptualmente;
el nivel, el calendario de feriados y la elasticidad al descuento **no**. Aplicar este modelo
entrenado a otra geografía sin reentrenar sería un error.

---

## 4. Métricas y resultados

Backtesting de origen móvil, **8 orígenes**, horizonte 7 días, target de demanda latente
recuperada, **3066 series** y 1.545.264 predicciones evaluadas. Reporte completo en
`reports/metrics.md`.

| Métrica | Valor | Referencia |
|---|---|---|
| MASE · artefacto servido (CQR) | **0,8217** ± 0,0454 | naive estacional = 1,1002 → **+25,3 %** |
| MASE · LightGBM puntual | 0,8222 ± 0,0457 | el envoltorio conformal no toca el punto |
| MASE peor origen | 0,8790 | sigue por debajo del mejor baseline (0,8952) |
| MAE | 0,4696 ± 0,0244 | adimensional (dataset normalizado) |
| **Cobertura del intervalo** | **88,0 %** ± 2,0 | nominal 90 % → **−2,0 pts** |
| Ancho medio del intervalo | 1,805 ± 0,153 | contra 3,834 del conformal de residuos |

El objetivo SMART era reducir MASE al menos **20 %** contra el naive estacional. Se cumple con
25,3 %, y el peor de los ocho orígenes queda en 0,8790, o sea que el resultado no depende de
promediar un origen bueno con uno malo.

**MAPE está excluido a propósito.** Explota con demanda cercana a cero, que es exactamente la
cola de baja rotación — la mayoría del catálogo en perecederos. Se usa MASE, que es libre de
escala y compara directamente contra el método que la operación ya usa. Ver `docs/decisiones.md` D5.

**Todas las métricas van con dispersión entre orígenes.** Un número único esconde el origen
catastrófico, y el origen catastrófico es el que pasa en producción.

### La cobertura sub-cubre dos puntos, y se declara

El intervalo promete 90 % y entrega 88,0 %. Dos puntos es una desviación real y conviene decirla
en vez de redondear: la garantía del split-conformal supone **intercambiabilidad**, y una serie
temporal con partición temporal la cumple de forma aproximada y no exacta.

La alternativa medida era peor. El conformal de residuos absolutos sobre el mismo modelo base
cubre **98,7 %** — ocho puntos y medio por encima de lo prometido — y lo paga con un intervalo del
doble de ancho. Su caso degenerado es `[0, ∞)`: cubre el 100 % y no informa nada. Detalle en D21.

**La cobertura garantizada es marginal, no condicional.** El 88 % global puede esconder subgrupos
peores, y desagregando por horizonte se ve: 0,893 0,893 0,867 0,887 0,883 **0,854** 0,885. El paso
6 baja a 85,4 %. Corregirlo exige conformal condicional o por grupo, y está en el Roadmap.

**Qué depende y qué no depende de esto.** La cantidad a pedir sale del booster entrenado en `q*`,
no del intervalo, así que la decisión no se degrada por los dos puntos. Lo que sí se degrada es la
banda que la interfaz dibuja como incertidumbre.

### El contraste contra modelos por serie

El modelo es **global**, y la objeción natural es que podría estar ganando solo porque se comparó
contra baselines simples. Medido sobre una submuestra declarada de 400 series con los mismos 8
orígenes (`reports/metrics_classical.md`): LightGBM global 0,8386 · Croston SBA 0,9032 · SARIMA
`(1,0,1)(1,0,0)[7]` 0,9136 · media móvil 21 d 0,9139 · Prophet 0,9698.

El dato que más dice no es que el global gane, sino que **SARIMA queda empatado con la media móvil
de 21 días** y pierde contra Croston. El aparato ARIMA no compra nada sobre un promedio simple en
este panel, algo consistente con series cortas, intermitentes y con estacionalidad semanal que un
rolling ya captura. Ver D22.

### Desagregación

Se reporta por **banda de rotación** (baja, media, alta), calculada con el train del primer
origen y nunca con la serie completa. Que el modelo complejo no le gane al ingenuo en baja
rotación es un resultado esperado y publicado, no un fracaso. Ver `reports/metrics.md`.

---

## 5. Consideraciones éticas

**Sesgo de censura, que es el sesgo central de este dominio.** Cuando hubo quiebre de stock la
venta registrada es cero pero la demanda no lo era. Entrenar sobre la venta observada produce el
**efecto spiral-down**: se pide de menos, hay más quiebres, se observa menos demanda, se pide de
menos todavía. El sesgo equivalente en decisores humanos está documentado
([Tong, Feiler y Larrick 2018](https://journals.sagepub.com/doi/10.1111/poms.12823)).

Este proyecto lo corrige **antes** de construir cualquier feature, y lo mide en vez de solo
afirmarlo, porque el dataset anota el quiebre hora por hora. La métrica es el sesgo de demanda
re-censurada: se le vuelve a aplicar a la predicción el patrón real de quiebres y se compara
contra la venta registrada. Medido sobre 99.721 días limpios, con el **mismo** modelo entrenado
sobre las dos bases:

| Entrenado sobre | Sesgo re-censurado |
|---|---|
| Venta observada | −18,19 % |
| Demanda latente | **−6,61 %** |

**11,57 puntos porcentuales de reducción de sesgo.** Las dos ramas son el mismo modelo con el
mismo denominador, que es lo que hace la comparación válida. Ver `reports/censoring_ablation.md`
y D10 para por qué tiene que ser pareada.

Dos cosas que hay que leer con honestidad en ese resultado. El **MASE empeora** en la rama
corregida (0,8958 contra 0,8117), porque las dos se evalúan contra la venta observada de los días
limpios y un modelo que aprendió demanda **latente** sobrepredice ahí por construcción: es el
precio de corregir el sesgo. Y el sesgo sin corregir de este panel es **2,2 veces** el que publica
CADRE (−18,19 % contra −8,1 %), así que las dos cifras no son directamente comparables; lo que se
compara es la reducción, 11,57 puntos acá contra 6,8 de CADRE.

**Quién pierde si el modelo se equivoca.** Si subestima, hay quiebre: el cliente no encuentra el
producto y la tienda pierde el margen. Si sobreestima, hay merma: producto perecedero a la basura,
que es pérdida económica y también desperdicio de alimento. La asimetría entre los dos errores es
explícita en el parámetro `Co/Cu` y **se declara**, en vez de quedar implícita en un stock de
seguridad heurístico. Que la decisión sea auditable es parte del punto.

**Datos personales: ninguno.** El dataset es agregado a nivel tienda-producto-día. No hay
identificadores de cliente, ni transacciones individuales, ni nada que permita reidentificar a
una persona.

**Transparencia de cada sugerencia.** El endpoint `/explain` devuelve la atribución **TreeSHAP por
predicción**, así que la persona que firma la orden puede ver qué features la empujaron y en qué
dirección, en vez de recibir un número sin origen. Es el requisito mínimo para que una sugerencia
sea discutible: si el modelo pide el doble que la semana pasada, tiene que poder decir por qué.

Dos límites que conviene declarar. SHAP atribuye sobre el modelo, **no** sobre el mundo: una
atribución alta en `discount` no prueba que el descuento cause la demanda, solo que el modelo se
apoya en esa columna. Y la atribución explica el **pronóstico**, no la cantidad pedida — la orden
sale del cuantil `q*`, así que la economía (`Cu`, `Co`) mueve la decisión sin aparecer en el SHAP.

**Riesgo de uso indebido.** El principal es el de la sección 2: usar desviaciones entre pronóstico
y venta para evaluar personal de tienda. La desviación mide el error del modelo. Un segundo riesgo
es presentar el ROI como una promesa: los supuestos monetarios son declarados y no observados, y
la fracción de la mejora efectivamente capturada nunca es 100 %.

---

## 6. Limitaciones técnicas

1. **Newsvendor de un solo período.** Para vida útil mayor al período de revisión el modelo
   correcto es de inventario perecedero multiperíodo con despacho por antigüedad.
2. **Sin lead time ni multi-echelon.** Se asume que lo pedido llega para el período siguiente.
3. **Sin restricciones operativas de la orden.** Emite un número continuo, no múltiplos de caja.
4. **Horizonte de 7 días.** No 4 semanas: el dataset tiene 97 días por serie y un horizonte de 28
   dejaría 4 orígenes de backtest contra los 8 que exige la metodología. Ver D8.
5. **Corrección de censura conservadora.** Tope de inflación ×3 y nada de corrección por debajo
   del 15 % de masa disponible. Queda por debajo de la corrección publicada por CADRE, y es una
   decisión declarada: sesgo residual conocido antes que varianza inventada. Ver D11.
6. **El ROI no se expresa en moneda a partir del dataset primario.** `sale_amount` viene
   multiplicado por un coeficiente no divulgado. Ver `docs/roi.md`.
7. **No hay detección de drift, ni loop de reentrenamiento automático.** Es la limitación
   operativa más grande de esta versión: nada avisa si la distribución de entrada se corre
   respecto de la del entrenamiento, así que el modelo seguiría respondiendo con confianza sobre
   un régimen que ya cambió. En una operación real esto se cubre monitoreando PSI o un test de
   dos muestras sobre las features y la salida, con un umbral que dispare revisión. Está en el
   Roadmap (M9) y **no** implementado.
8. **El clima no se usa como regresor futuro.** A 7 días no se conoce, así que entra solo rezagado
   y anclado en el origen. Usar el valor real del día objetivo sería fuga.

---

## 7. Reproducibilidad

| Elemento | Cómo se fija |
|---|---|
| Semilla | `BLINDSIDE_SEED`, por defecto 42, en `src/blindside/config.py` |
| Dependencias | `requirements.txt` con versiones exactas |
| Python | 3.11 o 3.12 (los pines no tienen wheels en 3.13+) |
| Submuestreo | Semilla fija + manifiesto en `data/interim/` |
| Splits | `RollingOriginSplitter`, determinista, falla si no caben los orígenes pedidos |
| Antifugas | 8 asserts como tests, cada uno con su caso negativo |

```bash
make setup && make data && make recover && make models && make ablation
make classical          # el contraste per-serie; Prophet es opcional y se saltea si falta
```

**Una dependencia transitiva sin pin es un pin que falta.** `scipy` no estaba fijado aunque numpy,
pandas y scikit-learn sí, y eso volvió a `statsforecast` ininstalable de hecho en un entorno nuevo
durante semanas, sin que nada fallara: ningún módulo lo importaba todavía. Ver D22.

La CI corre la suite completa **sin descargar el dataset**: `data/sample/` va commiteado y los
tests generan su propio panel sintético, donde el proceso generador es conocido y se puede
verificar que el código recupera lo que se inyectó.

---

## 8. Contacto y mantenimiento

Franco Cazal. Issues en el repositorio.

**Cuándo reentrenar.** La curva de degradación por horizonte está en `reports/metrics.md`. Con
97 días de historia no alcanza para estimar una vida útil del modelo con seriedad; la respuesta
honesta es que hace falta más historia para responder esa pregunta, y decirlo es mejor que dar un
número inventado.
