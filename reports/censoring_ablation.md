# Ablacion de censura

> Generado por `make ablation`. No editar a mano.

El **mismo** modelo entrenado dos veces, cambiando unicamente el target.
Las dos ramas se evaluan contra la misma verdad de terreno: la venta observada
de los dias **sin ninguna hora de quiebre**, que es el unico terreno donde la
demanda real se conoce.

- Modelo: `lgbm_global`
- Series: 3066
- Dias limpios evaluados: 99,721

## Resultado

| Entrenado sobre | Sesgo re-censurado | Sesgo dias limpios | MASE dias limpios | WAPE dias limpios |
|---|---|---|---|---|
| venta observada (`sale_amount`) | -18.19 % | -2.03 % | 0.8117 | 0.3015 |
| demanda latente (`demand_latent`) | -6.61 % | +10.25 % | 0.8958 | 0.3252 |

**Reduccion de sesgo re-censurado: 11.57 puntos porcentuales.**

## Lectura

El **sesgo re-censurado** es la metrica de referencia. Se le vuelve a aplicar a la
prediccion de demanda latente el patron real de quiebres y se compara contra la
venta registrada: si el modelo recupero la demanda latente, re-censurarla da
exactamente lo que se vendio, y el sesgo es cero.

El signo negativo en la rama de venta observada es el **efecto spiral-down**: el
modelo aprendio de una demanda deprimida por los quiebres, asi que su prediccion
re-censurada queda por debajo de la venta real. Es el sesgo que en la operacion se
realimenta — se pide de menos, hay mas quiebres, se observa menos demanda, se pide
de menos todavia.

El **sesgo en dias limpios** va al lado como diagnostico y no como resultado. Los
dias sin quiebre no son una muestra aleatoria: el stock se agota cuando la gente
compra mucho, asi que ese subconjunto tiende a dias de demanda baja y un modelo que
predice bien la demanda latente esperada sobrepredice ahi sin estar equivocado.
Leer esa columna como si midiera la censura invierte la conclusion.

El MASE de las dos ramas usa el **mismo denominador**, el de la rama de venta
observada. Cada rama calculando su propia escala regalaria una mejora aparente
de ~30 % que solo refleja que la serie corregida varia mas.

## Contra la literatura

Numeros publicados de CADRE, medidos sobre este mismo dataset
([MDPI Sustainability 18(15):7642](https://www.mdpi.com/2071-1050/18/15/7642)):

| Indicador | CADRE sin corregir | CADRE corregido | Este proyecto sin corregir | Este proyecto corregido |
|---|---|---|---|---|
| Sesgo re-censurado | -8.1 % | -1.3 % | -18.19 % | -6.61 % |
| WAPE | 0.3942 | 0.3671 | 0.3015 | 0.3252 |

El sesgo **sin corregir** de este panel (-18.19 %) es 2.2 veces el publicado por CADRE (-8.1 %), asi que las dos cifras **no** son directamente comparables y conviene no presentarlas como si lo fueran. La diferencia mas probable es el submuestreo: 3066 series elegidas por tienda completa no son las 50.000 del dataset, y la tasa de quiebre de este subconjunto define cuanto sesgo hay para corregir. Lo que si es comparable es la **reduccion**: +11.57 puntos aca contra +6.8 de CADRE.

La correccion propia es mas conservadora que la de CADRE, y eso es una
consecuencia declarada de los dos limites del recuperador: tope de inflacion en
x3 y nada de correccion cuando queda menos del 15 % de la masa de demanda diaria
disponible. Se prefiere un sesgo residual conocido a una varianza inventada a
partir de una sola venta en un dia casi entero en quiebre. Ver docs/decisiones.md
D11.
