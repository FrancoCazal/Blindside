# Metricas de backtest

> Generado por `make classical`. No editar a mano.

## Configuracion

- Target evaluado: `demand_latent`
- Horizonte: 7 dias
- Estacionalidad (denominador de MASE): 7 dias
- Origenes de backtest: 8
- Series: 400
- Predicciones evaluadas: 134,400

El denominador de MASE se calcula con el **train de cada origen**, nunca
con la serie completa. Las metricas van con su dispersion entre origenes:
un promedio bueno puede esconder un origen catastrofico.

## Resumen por modelo · MASE

| Modelo | MASE medio | Desvio | Peor origen | Mejora vs naive estacional | >= 20 % |
|---|---|---|---|---|---|
| `lgbm_global` | 0.8386 | 0.0549 | 0.9029 | +24.2 % | si |
| `croston_sba` | 0.9032 | 0.0707 | 0.9873 | +18.3 % | no |
| `sarima` | 0.9136 | 0.0599 | 0.9832 | +17.4 % | no |
| `moving_average` | 0.9139 | 0.0652 | 0.9927 | +17.4 % | no |
| `prophet` | 0.9698 | 0.0704 | 1.0502 | +12.3 % | no |
| `seasonal_naive` | 1.1058 | 0.0674 | 1.1761 | +0.0 % | no |

## Todas las metricas

| Modelo | Metrica | Media | Desvio | Peor | Mejor |
|---|---|---|---|---|---|
| `prophet` | bias | -0.1590 | 0.0951 | -0.0374 | -0.2669 |
| `croston_sba` | bias | -0.1504 | 0.0775 | -0.0694 | -0.2530 |
| `moving_average` | bias | -0.1147 | 0.0811 | -0.0196 | -0.2340 |
| `sarima` | bias | -0.0851 | 0.0854 | -0.0069 | -0.1966 |
| `lgbm_global` | bias | -0.0636 | 0.1097 | 0.0904 | -0.2460 |
| `seasonal_naive` | bias | -0.0545 | 0.0881 | 0.0492 | -0.1659 |
| `lgbm_global` | mae | 0.4599 | 0.0324 | 0.5010 | 0.4159 |
| `croston_sba` | mae | 0.5018 | 0.0440 | 0.5569 | 0.4469 |
| `sarima` | mae | 0.5091 | 0.0365 | 0.5540 | 0.4603 |
| `moving_average` | mae | 0.5096 | 0.0408 | 0.5617 | 0.4619 |
| `prophet` | mae | 0.5484 | 0.0431 | 0.5980 | 0.4898 |
| `seasonal_naive` | mae | 0.6055 | 0.0381 | 0.6416 | 0.5486 |
| `lgbm_global` | mase | 0.8386 | 0.0549 | 0.9029 | 0.7651 |
| `croston_sba` | mase | 0.9032 | 0.0707 | 0.9873 | 0.8161 |
| `sarima` | mase | 0.9136 | 0.0599 | 0.9832 | 0.8387 |
| `moving_average` | mase | 0.9139 | 0.0652 | 0.9927 | 0.8378 |
| `prophet` | mase | 0.9698 | 0.0704 | 1.0502 | 0.8697 |
| `seasonal_naive` | mase | 1.1058 | 0.0674 | 1.1761 | 1.0027 |
| `lgbm_global` | rmse | 0.7191 | 0.0570 | 0.8012 | 0.6410 |
| `croston_sba` | rmse | 0.8085 | 0.0877 | 0.9338 | 0.7085 |
| `moving_average` | rmse | 0.8158 | 0.0840 | 0.9359 | 0.7228 |
| `sarima` | rmse | 0.8178 | 0.0692 | 0.9076 | 0.7086 |
| `prophet` | rmse | 0.8794 | 0.0793 | 0.9744 | 0.7691 |
| `seasonal_naive` | rmse | 0.9364 | 0.0575 | 0.9961 | 0.8605 |
| `lgbm_global` | smape | 0.4559 | 0.0123 | 0.4723 | 0.4366 |
| `croston_sba` | smape | 0.4775 | 0.0079 | 0.4937 | 0.4657 |
| `sarima` | smape | 0.4797 | 0.0095 | 0.4956 | 0.4661 |
| `moving_average` | smape | 0.4811 | 0.0082 | 0.4977 | 0.4710 |
| `prophet` | smape | 0.5035 | 0.0118 | 0.5219 | 0.4881 |
| `seasonal_naive` | smape | 0.5975 | 0.0093 | 0.6127 | 0.5832 |
| `lgbm_global` | wape | 0.3634 | 0.0103 | 0.3824 | 0.3502 |
| `croston_sba` | wape | 0.3960 | 0.0078 | 0.4059 | 0.3803 |
| `sarima` | wape | 0.4022 | 0.0107 | 0.4191 | 0.3828 |
| `moving_average` | wape | 0.4023 | 0.0060 | 0.4082 | 0.3926 |
| `prophet` | wape | 0.4331 | 0.0121 | 0.4496 | 0.4192 |
| `seasonal_naive` | wape | 0.4786 | 0.0100 | 0.4916 | 0.4660 |

## Degradacion por horizonte

Responde cuanto dura el modelo antes de necesitar reentrenamiento. El error
debe **crecer** con el horizonte; si baja, hay un desalineamiento de indices.

| Modelo | h | MASE | WAPE |
|---|---|---|---|
| `croston_sba` | 1 | 0.8422 | 0.3778 |
| `croston_sba` | 2 | 0.7923 | 0.3823 |
| `croston_sba` | 3 | 0.9521 | 0.4086 |
| `croston_sba` | 4 | 0.9051 | 0.3931 |
| `croston_sba` | 5 | 0.9291 | 0.4023 |
| `croston_sba` | 6 | 0.9751 | 0.4062 |
| `croston_sba` | 7 | 0.9263 | 0.3997 |
| `lgbm_global` | 1 | 0.7813 | 0.3453 |
| `lgbm_global` | 2 | 0.7518 | 0.3551 |
| `lgbm_global` | 3 | 0.8636 | 0.3631 |
| `lgbm_global` | 4 | 0.8283 | 0.3600 |
| `lgbm_global` | 5 | 0.8806 | 0.3743 |
| `lgbm_global` | 6 | 0.9117 | 0.3731 |
| `lgbm_global` | 7 | 0.8529 | 0.3679 |
| `moving_average` | 1 | 0.8606 | 0.3886 |
| `moving_average` | 2 | 0.8039 | 0.3884 |
| `moving_average` | 3 | 0.9508 | 0.4085 |
| `moving_average` | 4 | 0.9170 | 0.3993 |
| `moving_average` | 5 | 0.9432 | 0.4101 |
| `moving_average` | 6 | 0.9827 | 0.4114 |
| `moving_average` | 7 | 0.9392 | 0.4073 |
| `prophet` | 1 | 0.9271 | 0.4267 |
| `prophet` | 2 | 0.8778 | 0.4303 |
| `prophet` | 3 | 1.0162 | 0.4415 |
| `prophet` | 4 | 0.9623 | 0.4269 |
| `prophet` | 5 | 0.9904 | 0.4369 |
| `prophet` | 6 | 1.0426 | 0.4399 |
| `prophet` | 7 | 0.9721 | 0.4267 |
| `sarima` | 1 | 0.8549 | 0.3844 |
| `sarima` | 2 | 0.8128 | 0.3927 |
| `sarima` | 3 | 0.9678 | 0.4168 |
| `sarima` | 4 | 0.9110 | 0.3972 |
| `sarima` | 5 | 0.9230 | 0.4003 |
| `sarima` | 6 | 0.9868 | 0.4116 |
| `sarima` | 7 | 0.9389 | 0.4075 |
| `seasonal_naive` | 1 | 1.0766 | 0.4806 |
| `seasonal_naive` | 2 | 1.0038 | 0.4698 |
| `seasonal_naive` | 3 | 1.1422 | 0.4832 |
| `seasonal_naive` | 4 | 1.1346 | 0.4911 |
| `seasonal_naive` | 5 | 1.1029 | 0.4629 |
| `seasonal_naive` | 6 | 1.1316 | 0.4658 |
| `seasonal_naive` | 7 | 1.1488 | 0.4923 |

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
| `croston_sba` | -13.39 % | +3.33 % | 0.6725 | 1.2281 |
| `lgbm_global` | -7.30 % | +9.18 % | 0.6477 | 1.1075 |
| `moving_average` | -10.57 % | +6.70 % | 0.7013 | 1.2135 |
| `prophet` | -15.11 % | -0.35 % | 0.7543 | 1.2734 |
| `sarima` | -8.72 % | +8.26 % | 0.7127 | 1.1966 |
| `seasonal_naive` | -5.93 % | +12.26 % | 0.9256 | 1.3596 |

## Por banda de rotacion

Que el modelo complejo no le gane al ingenuo en baja rotacion es un
resultado esperado y publicado, no un fracaso. Se reporta igual.

| Modelo | Banda | MASE | WAPE | n |
|---|---|---|---|---|
| `croston_sba` | alta | 0.9510 | 0.3239 | 3,360 |
| `croston_sba` | baja | 0.9001 | 0.4973 | 11,200 |
| `croston_sba` | media | 0.8871 | 0.3943 | 7,840 |
| `lgbm_global` | alta | 0.8476 | 0.2854 | 3,360 |
| `lgbm_global` | baja | 0.8344 | 0.4550 | 11,200 |
| `lgbm_global` | media | 0.8407 | 0.3744 | 7,840 |
| `moving_average` | alta | 0.9646 | 0.3296 | 3,360 |
| `moving_average` | baja | 0.9091 | 0.5027 | 11,200 |
| `moving_average` | media | 0.8992 | 0.4015 | 7,840 |
| `prophet` | alta | 1.0990 | 0.3752 | 3,360 |
| `prophet` | baja | 0.9054 | 0.4968 | 11,200 |
| `prophet` | media | 1.0064 | 0.4448 | 7,840 |
| `sarima` | alta | 0.9637 | 0.3287 | 3,360 |
| `sarima` | baja | 0.8950 | 0.4913 | 11,200 |
| `sarima` | media | 0.9187 | 0.4104 | 7,840 |
| `seasonal_naive` | alta | 1.0862 | 0.3647 | 3,360 |
| `seasonal_naive` | baja | 1.1162 | 0.6115 | 11,200 |
| `seasonal_naive` | media | 1.0993 | 0.4950 | 7,840 |
