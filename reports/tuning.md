# Busqueda de hiperparametros

> Generado por `make tune`. No editar a mano.

## Alcance, que esta reducido y se declara

- Trials: 25
- Series: 400 (la corrida oficial usa 3066)
- Origenes: 4 (la oficial usa 8)
- Arboles por modelo: 300
- Objetivo: MASE medio + 0.5 x desvio entre origenes

Cada trial corre el **mismo** `run_backtest` que produce las metricas
oficiales, con origenes moviles. No hay validacion cruzada aleatoria: sobre
datos de panel produciria un numero mejor y falso.

## Resultado

| | MASE | Desvio entre origenes | Objetivo |
|---|---|---|---|
| Parametros actuales | 0.8672 | 0.0134 | 0.8739 |
| Mejor encontrado | 0.8630 | 0.0153 | 0.8707 |

Diferencia de MASE: **+0.49 %**.

**La mejora (0.0042 de MASE) es menor que la dispersion entre origenes (0.0134), asi que no se adopta.** Adoptarla seria confundir una realizacion afortunada del azar sobre los origenes elegidos con una mejora real. El criterio esta declarado en el codigo (`Resultado.vale_la_pena`) y no se decide despues de ver el numero.

## Mejores parametros

```json
{
  "objective": "regression_l1",
  "metric": "mae",
  "learning_rate": 0.03744479677742343,
  "num_leaves": 54,
  "min_child_samples": 40,
  "feature_fraction": 0.6263282355704631,
  "bagging_fraction": 0.609246376924976,
  "bagging_freq": 1,
  "lambda_l2": 0.05303564016913495,
  "seed": 42
}
```

## Los 10 mejores trials

| trial | objetivo | mase | desvio | learning_rate | num_leaves | min_child_samples | feature_fraction | bagging_fraction | bagging_freq | lambda_l2 |
|---|---|---|---|---|---|---|---|---|---|---|
| 23 | 0.87065 | 0.86299 | 0.015334 | 0.037445 | 54 | 40 | 0.62633 | 0.60925 | 1 | 0.053036 |
| 3 | 0.87071 | 0.86436 | 0.012696 | 0.047754 | 57 | 45 | 0.56975 | 0.64607 | 1 | 0.037647 |
| 22 | 0.8711 | 0.86269 | 0.016817 | 0.034238 | 67 | 41 | 0.55257 | 0.7514 | 1 | 0.046006 |
| 12 | 0.87158 | 0.86212 | 0.018925 | 0.033466 | 74 | 32 | 0.66927 | 0.72692 | 1 | 0.028295 |
| 24 | 0.87212 | 0.8637 | 0.016843 | 0.024584 | 57 | 42 | 0.56368 | 0.60803 | 1 | 0.074826 |
| 13 | 0.87244 | 0.86378 | 0.017325 | 0.029501 | 70 | 29 | 0.51318 | 0.73435 | 1 | 0.015155 |
| 15 | 0.87291 | 0.86523 | 0.015358 | 0.046359 | 63 | 23 | 0.60771 | 0.7462 | 1 | 0.5926 |
| 6 | 0.87297 | 0.86446 | 0.017019 | 0.036948 | 38 | 54 | 0.72008 | 0.56102 | 1 | 0.13483 |
| 19 | 0.8733 | 0.86507 | 0.016461 | 0.028766 | 84 | 21 | 0.72385 | 0.88187 | 1 | 0.0056406 |
| 18 | 0.87335 | 0.86508 | 0.016543 | 0.04119 | 100 | 46 | 0.65003 | 0.60792 | 1 | 0.047008 |
