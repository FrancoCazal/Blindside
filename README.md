# demand-forecasting-core

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-en%20desarrollo-yellow)

Pronóstico de demanda de productos perecederos por tienda y producto, con **recuperación de
demanda censurada por quiebres de stock** y una **capa de decisión** que convierte el
pronóstico en una cantidad concreta a reponer.

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

> Pendiente: screenshot del dashboard + enlace al despliegue.

## Resultados

> Pendiente: se completa con el reporte de `make backtest`.

| Métrica | Baseline (naive estacional) | Modelo | Δ |
|---|---|---|---|
| MASE | — | — | — |
| WAPE | — | — | — |
| Cobertura empírica (nominal 90 %) | — | — | — |
| Sesgo de demanda re-censurada | — | — | — |

Las métricas se reportan **con su dispersión entre orígenes de backtest**, nunca como número
único: un promedio bueno puede esconder un origen catastrófico.

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

## Instalación

```bash
git clone https://github.com/FrancoCazal/demand-forecasting-core.git
cd demand-forecasting-core

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

make setup       # requirements.txt fijos + paquete en modo editable
make sample      # (opcional) regenera la muestra commiteada
make test        # verifica que todo importa y los tests antifugas pasan
make app         # dashboard en http://127.0.0.1:8501
```

## Estructura del repositorio

```
demand-forecasting-core/
├── data/
│   ├── raw/          # descarga original (no commiteado)
│   ├── interim/      # subconjunto submuestreado (no commiteado)
│   ├── processed/     # demanda latente recuperada + features (no commiteado)
│   └── sample/       # muestra chica (SI commiteada)
├── src/dfcore/       # codigo fuente importable
│   ├── data/         # carga, submuestreo, contrato de esquema
│   ├── features/     # calendario, lags, rolling
│   ├── validation/   # splits de origen movil + asserts antifugas
│   ├── models/       # baselines, GBDT, estadisticos, recurrentes, tuning
│   ├── unsupervised/ # clustering, embeddings, anomalias
│   ├── decision/     # censura, conformal, newsvendor, reconciliacion, politica
│   ├── evaluate/     # metricas, backtest, drift
│   └── explain/      # SHAP
├── notebooks/        # analisis; importan de src/, no contienen logica
├── tests/            # unitarios + antifugas
├── app/              # Streamlit desplegable
├── api/              # FastAPI
├── docs/             # arquitectura, ROI, decisiones tecnicas, model card
├── artifacts/        # modelos serializados (no commiteados)
└── reports/          # metricas y figuras generadas
```

## Decisiones técnicas y limitaciones

Están documentadas en `docs/decisiones.md`. Las cuatro limitaciones que conviene conocer antes
de leer los resultados:

1. El newsvendor es **de un solo período**. Para perecederos con vida útil mayor al período de
   revisión el modelo correcto es de inventario perecedero multi-período con despacho por
   antigüedad. La aproximación vale cuando la vida útil se parece al período de revisión.
2. No se modela **lead time** ni estructura multi-echelon: se asume que lo pedido llega para el
   período siguiente.
3. No se modelan **restricciones operativas de la orden** (cantidad mínima, múltiplos de caja o
   pallet, capacidad de cámara). El modelo emite un número continuo.
4. Hay detección de drift, pero **no loop de reentrenamiento automático**.

## Próximos pasos

Ver `docs/decisiones.md`, sección Roadmap.

## Licencia

MIT. Ver `LICENSE`.

El dataset FreshRetailNet-50K es de Dingdong-Inc y se distribuye bajo CC BY 4.0; no se
redistribuye en este repositorio más allá de la muestra de `data/sample/`.
