# Model card · blindside-core

Conecta con el eje de ética y AI Act del programa. La estructura sigue la de Mitchell et al.,
*Model Cards for Model Reporting* (2019).

---

## 1. Detalles del modelo

| Campo | Valor |
|---|---|
| Nombre | `lgbm_global` (LightGBM global, un modelo para todas las series) |
| Versión | 0.1.0 |
| Tipo | Gradient boosting sobre árboles, regresión, estrategia directa multihorizonte |
| Pérdida | `regression_l1` (estima la **mediana**, no la media) |
| Variante de decisión | `lgbm_quantile`, un booster por cuantil con pérdida cuantílica |
| Entradas | 73 features: rezagos, estadísticos móviles, calendario, historia de quiebres, jerarquía |
| Salida | Demanda latente diaria por tienda-producto, horizonte 1 a 7 días |
| Licencia | MIT |
| Autor | Franco Cazal · Diplomado ML/DL FIUNA 2026 |

**Por qué L1 y no L2.** La pérdida absoluta estima la mediana, que en una distribución con cola
derecha larga es lo que se quiere de un pronóstico puntual. L2 estima la media y queda arrastrada
por los picos promocionales. Consecuencia que hay que tener presente al leer las métricas: el
sesgo medido contra promedios sale sistemáticamente negativo por este motivo, no por un problema
del modelo. Ver `docs/decisiones.md` D10.

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

Backtesting de origen móvil, 8 orígenes, horizonte 7 días, target de demanda latente recuperada.

| Métrica | Valor | Referencia |
|---|---|---|
| MASE | **0,8311** ± 0,0462 | naive estacional = 1,1002 → **+24,5 %** |
| MASE peor origen | 0,8849 | sigue por debajo del mejor baseline |
| MAE | 0,4772 ± 0,0234 | adimensional (dataset normalizado) |

**MAPE está excluido a propósito.** Explota con demanda cercana a cero, que es exactamente la
cola de baja rotación — la mayoría del catálogo en perecederos. Se usa MASE, que es libre de
escala y compara directamente contra el método que la operación ya usa. Ver `docs/decisiones.md` D5.

**Todas las métricas van con dispersión entre orígenes.** Un número único esconde el origen
catastrófico, y el origen catastrófico es el que pasa en producción.

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
contra la venta registrada. Ver `reports/censoring_ablation.md`.

**Quién pierde si el modelo se equivoca.** Si subestima, hay quiebre: el cliente no encuentra el
producto y la tienda pierde el margen. Si sobreestima, hay merma: producto perecedero a la basura,
que es pérdida económica y también desperdicio de alimento. La asimetría entre los dos errores es
explícita en el parámetro `Co/Cu` y **se declara**, en vez de quedar implícita en un stock de
seguridad heurístico. Que la decisión sea auditable es parte del punto.

**Datos personales: ninguno.** El dataset es agregado a nivel tienda-producto-día. No hay
identificadores de cliente, ni transacciones individuales, ni nada que permita reidentificar a
una persona.

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
7. **Hay detección de drift pero no loop de reentrenamiento automático.**
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
```

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
