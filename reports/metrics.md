# Metricas de backtest

> Generado por `make backtest`. No editar a mano.

## Configuracion

- Target evaluado: `demand_latent`
- Horizonte: 7 dias
- Estacionalidad (denominador de MASE): 7 dias
- Origenes de backtest: 8
- Series: 3066
- Predicciones evaluadas: 1,545,264

El denominador de MASE se calcula con el **train de cada origen**, nunca
con la serie completa. Las metricas van con su dispersion entre origenes:
un promedio bueno puede esconder un origen catastrofico.

## Resumen por modelo · MASE

| Modelo | MASE medio | Desvio | Peor origen | Mejora vs naive estacional | >= 20 % |
|---|---|---|---|---|---|
| `conformal_lgbm_quantile_adaptive` | 0.8217 | 0.0454 | 0.8790 | +25.3 % | si |
| `cqr_lgbm_quantile` | 0.8217 | 0.0454 | 0.8790 | +25.3 % | si |
| `lgbm_global` | 0.8222 | 0.0457 | 0.8791 | +25.3 % | si |
| `croston_sba` | 0.8952 | 0.0683 | 0.9631 | +18.6 % | no |
| `ridge` | 0.9018 | 0.0626 | 1.0088 | +18.0 % | no |
| `moving_average` | 0.9048 | 0.0654 | 0.9779 | +17.8 % | no |
| `seasonal_moving_average` | 0.9460 | 0.0655 | 1.0189 | +14.0 % | no |
| `seasonal_naive` | 1.1002 | 0.0636 | 1.1579 | +0.0 % | no |
| `naive` | 1.1606 | 0.1099 | 1.3105 | -5.5 % | no |

## Todas las metricas

| Modelo | Metrica | Media | Desvio | Peor | Mejor |
|---|---|---|---|---|---|
| `croston_sba` | bias | -0.1568 | 0.0773 | -0.0713 | -0.2455 |
| `seasonal_moving_average` | bias | -0.1230 | 0.0919 | 0.0048 | -0.2255 |
| `moving_average` | bias | -0.1158 | 0.0841 | 0.0021 | -0.2175 |
| `conformal_lgbm_quantile_adaptive` | bias | -0.0645 | 0.0917 | 0.0167 | -0.2617 |
| `cqr_lgbm_quantile` | bias | -0.0645 | 0.0917 | 0.0167 | -0.2617 |
| `ridge` | bias | -0.0641 | 0.0876 | 0.0325 | -0.2496 |
| `lgbm_global` | bias | -0.0634 | 0.0926 | 0.0193 | -0.2630 |
| `seasonal_naive` | bias | -0.0617 | 0.0777 | 0.0117 | -0.1756 |
| `naive` | bias | 0.0182 | 0.2308 | 0.3134 | -0.3891 |
| `cqr_lgbm_quantile` | coverage | 0.8802 | 0.0201 | 0.9036 | 0.8384 |
| `conformal_lgbm_quantile_adaptive` | coverage | 0.9869 | 0.0064 | 0.9977 | 0.9783 |
| `cqr_lgbm_quantile` | interval_width | 1.8048 | 0.1533 | 2.0267 | 1.5715 |
| `conformal_lgbm_quantile_adaptive` | interval_width | 3.8336 | 0.5257 | 4.8494 | 3.1692 |
| `conformal_lgbm_quantile_adaptive` | mae | 0.4696 | 0.0244 | 0.5051 | 0.4374 |
| `cqr_lgbm_quantile` | mae | 0.4696 | 0.0244 | 0.5051 | 0.4374 |
| `lgbm_global` | mae | 0.4702 | 0.0245 | 0.5055 | 0.4372 |
| `ridge` | mae | 0.5128 | 0.0345 | 0.5688 | 0.4621 |
| `croston_sba` | mae | 0.5231 | 0.0410 | 0.5660 | 0.4632 |
| `moving_average` | mae | 0.5309 | 0.0392 | 0.5753 | 0.4791 |
| `seasonal_moving_average` | mae | 0.5579 | 0.0363 | 0.6014 | 0.5072 |
| `seasonal_naive` | mae | 0.6315 | 0.0356 | 0.6690 | 0.5801 |
| `naive` | mae | 0.6695 | 0.0759 | 0.7744 | 0.5750 |
| `conformal_lgbm_quantile_adaptive` | mase | 0.8217 | 0.0454 | 0.8790 | 0.7602 |
| `cqr_lgbm_quantile` | mase | 0.8217 | 0.0454 | 0.8790 | 0.7602 |
| `lgbm_global` | mase | 0.8222 | 0.0457 | 0.8791 | 0.7596 |
| `croston_sba` | mase | 0.8952 | 0.0683 | 0.9631 | 0.7957 |
| `ridge` | mase | 0.9018 | 0.0626 | 1.0088 | 0.8048 |
| `moving_average` | mase | 0.9048 | 0.0654 | 0.9779 | 0.8145 |
| `seasonal_moving_average` | mase | 0.9460 | 0.0655 | 1.0189 | 0.8612 |
| `seasonal_naive` | mase | 1.1002 | 0.0636 | 1.1579 | 1.0074 |
| `naive` | mase | 1.1606 | 0.1099 | 1.3105 | 1.0108 |
| `conformal_lgbm_quantile_adaptive` | rmse | 0.7684 | 0.0344 | 0.8147 | 0.7172 |
| `cqr_lgbm_quantile` | rmse | 0.7684 | 0.0344 | 0.8147 | 0.7172 |
| `lgbm_global` | rmse | 0.7690 | 0.0350 | 0.8142 | 0.7172 |
| `ridge` | rmse | 0.8171 | 0.0446 | 0.8718 | 0.7567 |
| `croston_sba` | rmse | 0.8780 | 0.0714 | 0.9573 | 0.7769 |
| `moving_average` | rmse | 0.8884 | 0.0664 | 0.9669 | 0.8019 |
| `seasonal_moving_average` | rmse | 0.9387 | 0.0379 | 0.9806 | 0.8571 |
| `seasonal_naive` | rmse | 1.0172 | 0.0460 | 1.0667 | 0.9527 |
| `naive` | rmse | 1.0852 | 0.1374 | 1.2792 | 0.9241 |
| `conformal_lgbm_quantile_adaptive` | smape | 0.4359 | 0.0116 | 0.4490 | 0.4200 |
| `cqr_lgbm_quantile` | smape | 0.4359 | 0.0116 | 0.4490 | 0.4200 |
| `lgbm_global` | smape | 0.4365 | 0.0125 | 0.4531 | 0.4203 |
| `croston_sba` | smape | 0.4646 | 0.0057 | 0.4761 | 0.4581 |
| `moving_average` | smape | 0.4677 | 0.0067 | 0.4806 | 0.4582 |
| `seasonal_moving_average` | smape | 0.4923 | 0.0080 | 0.5068 | 0.4814 |
| `ridge` | smape | 0.4945 | 0.0259 | 0.5307 | 0.4539 |
| `seasonal_naive` | smape | 0.5833 | 0.0081 | 0.5968 | 0.5717 |
| `naive` | smape | 0.5913 | 0.0239 | 0.6330 | 0.5527 |
| `conformal_lgbm_quantile_adaptive` | wape | 0.3507 | 0.0147 | 0.3707 | 0.3307 |
| `cqr_lgbm_quantile` | wape | 0.3507 | 0.0147 | 0.3707 | 0.3307 |
| `lgbm_global` | wape | 0.3512 | 0.0153 | 0.3728 | 0.3302 |
| `ridge` | wape | 0.3827 | 0.0153 | 0.4022 | 0.3622 |
| `croston_sba` | wape | 0.3898 | 0.0050 | 0.3987 | 0.3815 |
| `moving_average` | wape | 0.3958 | 0.0054 | 0.4026 | 0.3887 |
| `seasonal_moving_average` | wape | 0.4162 | 0.0116 | 0.4343 | 0.4046 |
| `seasonal_naive` | wape | 0.4713 | 0.0131 | 0.4892 | 0.4520 |
| `naive` | wape | 0.4992 | 0.0454 | 0.5630 | 0.4375 |

## Degradacion por horizonte

Responde cuanto dura el modelo antes de necesitar reentrenamiento. El error
debe **crecer** con el horizonte; si baja, hay un desalineamiento de indices.

| Modelo | h | MASE | WAPE |
|---|---|---|---|
| `conformal_lgbm_quantile_adaptive` | 1 | 0.7536 | 0.3279 |
| `conformal_lgbm_quantile_adaptive` | 2 | 0.7759 | 0.3515 |
| `conformal_lgbm_quantile_adaptive` | 3 | 0.8334 | 0.3498 |
| `conformal_lgbm_quantile_adaptive` | 4 | 0.8089 | 0.3433 |
| `conformal_lgbm_quantile_adaptive` | 5 | 0.8753 | 0.3622 |
| `conformal_lgbm_quantile_adaptive` | 6 | 0.8711 | 0.3585 |
| `conformal_lgbm_quantile_adaptive` | 7 | 0.8337 | 0.3545 |
| `cqr_lgbm_quantile` | 1 | 0.7536 | 0.3279 |
| `cqr_lgbm_quantile` | 2 | 0.7759 | 0.3515 |
| `cqr_lgbm_quantile` | 3 | 0.8334 | 0.3498 |
| `cqr_lgbm_quantile` | 4 | 0.8089 | 0.3433 |
| `cqr_lgbm_quantile` | 5 | 0.8753 | 0.3622 |
| `cqr_lgbm_quantile` | 6 | 0.8711 | 0.3585 |
| `cqr_lgbm_quantile` | 7 | 0.8337 | 0.3545 |
| `croston_sba` | 1 | 0.8263 | 0.3699 |
| `croston_sba` | 2 | 0.8135 | 0.3778 |
| `croston_sba` | 3 | 0.9234 | 0.3981 |
| `croston_sba` | 4 | 0.8904 | 0.3839 |
| `croston_sba` | 5 | 0.9543 | 0.4018 |
| `croston_sba` | 6 | 0.9490 | 0.3999 |
| `croston_sba` | 7 | 0.9099 | 0.3943 |
| `lgbm_global` | 1 | 0.7535 | 0.3278 |
| `lgbm_global` | 2 | 0.7761 | 0.3518 |
| `lgbm_global` | 3 | 0.8338 | 0.3504 |
| `lgbm_global` | 4 | 0.8095 | 0.3434 |
| `lgbm_global` | 5 | 0.8751 | 0.3624 |
| `lgbm_global` | 6 | 0.8733 | 0.3599 |
| `lgbm_global` | 7 | 0.8340 | 0.3549 |
| `moving_average` | 1 | 0.8388 | 0.3777 |
| `moving_average` | 2 | 0.8245 | 0.3844 |
| `moving_average` | 3 | 0.9254 | 0.3993 |
| `moving_average` | 4 | 0.9007 | 0.3900 |
| `moving_average` | 5 | 0.9651 | 0.4083 |
| `moving_average` | 6 | 0.9569 | 0.4055 |
| `moving_average` | 7 | 0.9218 | 0.4013 |
| `naive` | 1 | 1.0934 | 0.4815 |
| `naive` | 2 | 1.1482 | 0.5310 |
| `naive` | 3 | 1.2161 | 0.5200 |
| `naive` | 4 | 1.1668 | 0.5005 |
| `naive` | 5 | 1.1982 | 0.4956 |
| `naive` | 6 | 1.1798 | 0.4864 |
| `naive` | 7 | 1.1216 | 0.4781 |
| `ridge` | 1 | 0.8244 | 0.3596 |
| `ridge` | 2 | 0.8569 | 0.3843 |
| `ridge` | 3 | 0.8993 | 0.3768 |
| `ridge` | 4 | 0.8922 | 0.3757 |
| `ridge` | 5 | 0.9638 | 0.3954 |
| `ridge` | 6 | 0.9515 | 0.3899 |
| `ridge` | 7 | 0.9246 | 0.3913 |
| `seasonal_moving_average` | 1 | 0.8995 | 0.4089 |
| `seasonal_moving_average` | 2 | 0.8954 | 0.4235 |
| `seasonal_moving_average` | 3 | 0.9663 | 0.4171 |
| `seasonal_moving_average` | 4 | 0.9357 | 0.4094 |
| `seasonal_moving_average` | 5 | 1.0021 | 0.4290 |
| `seasonal_moving_average` | 6 | 0.9846 | 0.4156 |
| `seasonal_moving_average` | 7 | 0.9387 | 0.4056 |
| `seasonal_naive` | 1 | 1.0622 | 0.4729 |
| `seasonal_naive` | 2 | 1.0296 | 0.4683 |
| `seasonal_naive` | 3 | 1.1233 | 0.4722 |
| `seasonal_naive` | 4 | 1.1120 | 0.4768 |
| `seasonal_naive` | 5 | 1.1205 | 0.4607 |
| `seasonal_naive` | 6 | 1.1319 | 0.4647 |
| `seasonal_naive` | 7 | 1.1216 | 0.4781 |

## Sesgo de censura

**Sesgo re-censurado** es la metrica de referencia: se le vuelve a aplicar a la
prediccion de demanda latente el patron real de quiebres y se compara contra la
venta registrada. Un cero significa que el modelo recupero la demanda latente.
Un valor negativo es el efecto spiral-down medido. Referencia publicada sobre
este mismo dataset (CADRE): -8,1 % sin correccion, -1,3 % con correccion.

**Sesgo en dias limpios** es un diagnostico, no un resultado. Los dias sin quiebre
no son una muestra aleatoria: el stock se agota cuando la gente compra mucho, asi
que ese subconjunto tiende a dias de demanda baja y un modelo correcto sobrepredice
ahi sin estar equivocado.

| Modelo | Sesgo re-censurado | Sesgo dias limpios | MASE dias limpios | MASE dias censurados |
|---|---|---|---|---|
| `conformal_lgbm_quantile_adaptive` | -6.68 % | +10.22 % | 0.6265 | 1.0922 |
| `cqr_lgbm_quantile` | -6.68 % | +10.22 % | 0.6265 | 1.0922 |
| `croston_sba` | -13.01 % | +4.04 % | 0.6517 | 1.2326 |
| `lgbm_global` | -6.61 % | +10.25 % | 0.6281 | 1.0911 |
| `moving_average` | -9.95 % | +7.76 % | 0.6807 | 1.2152 |
| `naive` | -0.36 % | +18.02 % | 0.9951 | 1.3899 |
| `ridge` | -6.81 % | +10.26 % | 0.7343 | 1.1339 |
| `seasonal_moving_average` | -10.70 % | +6.50 % | 0.7282 | 1.2478 |
| `seasonal_naive` | -5.78 % | +13.02 % | 0.9167 | 1.3543 |

## Por banda de rotacion

Que el modelo complejo no le gane al ingenuo en baja rotacion es un
resultado esperado y publicado, no un fracaso. Se reporta igual.

| Modelo | Banda | MASE | WAPE | n |
|---|---|---|---|---|
| `conformal_lgbm_quantile_adaptive` | alta | 0.8418 | 0.2816 | 25,760 |
| `conformal_lgbm_quantile_adaptive` | baja | 0.8221 | 0.4355 | 85,848 |
| `conformal_lgbm_quantile_adaptive` | media | 0.8125 | 0.3578 | 60,088 |
| `cqr_lgbm_quantile` | alta | 0.8418 | 0.2816 | 25,760 |
| `cqr_lgbm_quantile` | baja | 0.8221 | 0.4355 | 85,848 |
| `cqr_lgbm_quantile` | media | 0.8125 | 0.3578 | 60,088 |
| `croston_sba` | alta | 0.9595 | 0.3299 | 25,760 |
| `croston_sba` | baja | 0.8842 | 0.4723 | 85,848 |
| `croston_sba` | media | 0.8834 | 0.3907 | 60,088 |
| `lgbm_global` | alta | 0.8443 | 0.2824 | 25,760 |
| `lgbm_global` | baja | 0.8221 | 0.4355 | 85,848 |
| `lgbm_global` | media | 0.8128 | 0.3581 | 60,088 |
| `moving_average` | alta | 0.9721 | 0.3362 | 25,760 |
| `moving_average` | baja | 0.8907 | 0.4764 | 85,848 |
| `moving_average` | media | 0.8960 | 0.3973 | 60,088 |
| `naive` | alta | 1.1800 | 0.4020 | 25,760 |
| `naive` | baja | 1.1810 | 0.6343 | 85,848 |
| `naive` | media | 1.1232 | 0.4987 | 60,088 |
| `ridge` | alta | 0.8978 | 0.3044 | 25,760 |
| `ridge` | baja | 0.9297 | 0.4928 | 85,848 |
| `ridge` | media | 0.8636 | 0.3804 | 60,088 |
| `seasonal_moving_average` | alta | 1.0202 | 0.3570 | 25,760 |
| `seasonal_moving_average` | baja | 0.9266 | 0.4950 | 85,848 |
| `seasonal_moving_average` | media | 0.9420 | 0.4178 | 60,088 |
| `seasonal_naive` | alta | 1.1025 | 0.3736 | 25,760 |
| `seasonal_naive` | baja | 1.1211 | 0.6009 | 85,848 |
| `seasonal_naive` | media | 1.0693 | 0.4746 | 60,088 |

## Calibracion de intervalos

| Modelo | Nominal | Empirica | Gap | Ancho medio | Cumple |
|---|---|---|---|---|---|
| `conformal_lgbm_quantile_adaptive` | 90% | 98.7% | +8.7% | 3.834 | si |
| `cqr_lgbm_quantile` | 90% | 88.0% | -2.0% | 1.805 | si |
