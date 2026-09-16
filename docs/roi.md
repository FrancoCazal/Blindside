# Cálculo de ROI

> **Estado:** el simulador está implementado (`src/blindside/decision/policy.py`) y su aritmética
> está cubierta por tests. Los números de la capa 1 se completan al correr el backtest con un
> modelo cuantílico; la capa 2 requiere fijar los cuatro supuestos declarados.

## Restricción que define la forma del cálculo

En FreshRetailNet-50K `sale_amount` y `hours_sale` están multiplicados por un **coeficiente no
divulgado**. Por lo tanto:

- Las métricas de exactitud (MASE, WAPE, pinball, cobertura) son válidas tal cual.
- **El ahorro monetario no se puede derivar directamente del dataset.** Presentar guaraníes
  calculados sobre datos normalizados sería un número sin origen.

**Modalidad elegida: ROI relativo.** Se reporta la mejora en *porcentaje* de costo esperado,
merma y nivel de servicio, y por separado una traducción monetaria **paramétrica** sobre un
perfil de operación declarado. No se atribuye a ninguna empresa concreta.

## Las dos capas

### Capa 1 · Lo que se mide, sin supuestos

Sale del backtest. Son porcentajes, no creencias:

- Reducción del faltante esperado
- Reducción del sobrante esperado
- Aumento del nivel de servicio, en sus **dos** definiciones (ver abajo)
- Reducción de la merma simulada

```
Costo_esperado = Cu × E[faltante] + Co × E[sobrante]

Mejora_relativa = 1 - Costo_esperado(politica_modelo) / Costo_esperado(politica_actual)
```

Ambos términos se estiman **empíricamente sobre las ventanas del backtest**, no con fórmula
cerrada. La diferencia importa y el panel puede preguntarla: la fórmula cerrada del newsvendor
exige conocer la distribución de la demanda, y acá lo que hay son realizaciones. El número sale
de contar, no de suponer una normal.

#### Las cuatro políticas que compara el simulador

`src/blindside/decision/policy.py` no compara dos políticas sino cuatro, y la razón es que un
«ahorro del 12 %» suelto no se puede interpretar.

| Política | Qué repone | Para qué sirve |
|---|---|---|
| **actual** | El promedio móvil reciente, sin margen | Es lo que hace una planilla. La referencia |
| **modelo** | El cuantil `q*` de la demanda latente | La propuesta |
| **mejor estática** | El cuantil `q*` de la distribución de cada serie | Separa el aporte del pronóstico del de la economía |
| **perfecta** | Exactamente la demanda que va a ocurrir | Costo cero. La cota superior real |

La comparación contra la **mejor estática** es la que responde la pregunta que importa: cuánto del
ahorro viene de pronosticar día a día y cuánto viene simplemente de fijar bien el nivel de cada
producto. Si el modelo apenas le gana a la estática, la conclusión honesta es que el valor está en
la economía del cuantil y no en el pronóstico, y hay que decirlo así.

Nota sobre un error fácil de cometer: la política estática **no** es una cota superior del modelo,
aunque use información del futuro para calcular el cuantil. Usa la distribución de cada serie pero
no puede seguir la variación diaria, así que un buen pronóstico le gana sin que haya nada mal en el
cálculo. Confundirlas llevaría a «arreglar» un simulador que funciona.

#### Nivel de servicio: dos definiciones que dan números distintos

Confundirlas es común y cambia la conclusión, así que se reportan las dos.

- **Fill rate**: fracción de las **unidades** demandadas que se satisfacen.
- **Cycle service level**: fracción de los **días** sin ningún quiebre.

Una serie puede tener 50 % de días sin quiebre y 95 % de unidades satisfechas, si los quiebres son
chicos. El anclaje publicado de CADRE (92,9 % → 94,7 %) corresponde al segundo tipo.

### Capa 2 · Traducción a dinero, paramétrica

Se aplica la mejora relativa a un perfil de operación con cuatro supuestos declarados:

| Supuesto | Valor usado | Fuente / justificación |
|---|---|---|
| Facturación anual del perfil | — | declarado, no observado |
| Margen bruto | — | declarado |
| Tasa de merma base | — | ancla publicada (ver abajo) |
| Fracción de la mejora efectivamente capturada | — | nunca 100 % |

Los cuatro son **argumentos obligatorios sin valor por defecto** en `policy.roi_monetary`. Es
deliberado y hay un test que lo verifica: no tiene que haber forma de calcular un ROI monetario
sin nombrar los supuestos que lo sostienen.

Se reporta un **rango con análisis de sensibilidad** sobre la fracción capturada
(`policy.sensitivity_grid`), incluyendo el caso pesimista de 0,3. Es el supuesto más frágil y el
que domina el resultado: entre la mejora del pronóstico y la mejora realizada hay ejecución,
restricciones de proveedor y decisiones humanas.

### Sensibilidad a la economía

`q*` depende **solo** del cociente `Co/Cu`, así que el análisis barre ese cociente y no las dos
magnitudes por separado (`newsvendor.sensitivity_to_economics`). Es la única dimensión que cambia
la decisión.

| `Co/Cu` | `q*` | Lectura |
|---|---|---|
| 0,3 | 0,769 | Producto seco: el sobrante es capital inmovilizado, conviene pedir de más |
| 0,6 | 0,625 | **Perecedero**: el sobrante es pérdida total al vencimiento |
| 1,0 | 0,500 | Los dos errores cuestan igual: el óptimo es la mediana |
| 1,5 | 0,400 | El sobrante duele más que el quiebre: pedir por debajo de la mediana |

Que `q*` baje al subir `Co` es exactamente el efecto de la cadena de frío sobre la decisión, y es
la forma concreta en que el dominio entra al modelo. Aun así, con `Co/Cu = 0,6` el óptimo queda
**por encima** de la mediana: el quiebre sigue doliendo más.

## Anclas publicadas

Estos números provienen de CADRE, medido sobre este mismo dataset
([MDPI Sustainability 18(15):7642](https://www.mdpi.com/2071-1050/18/15/7642)). Sirven para que
los supuestos sean citables y para comparar el orden de magnitud del resultado propio:

| Indicador | Política censurada | Con recuperación de demanda |
|---|---|---|
| Merma | 9,8 % | 6,4 % |
| Nivel de servicio | 92,9 % | 94,7 % |
| Sesgo de demanda re-censurada | −8,1 % | −1,3 % |
| WAPE | 39,42 % | 36,71 % |

**Sanity check.** Se reporta en la industria que ~10 % de mejora en exactitud de pronóstico
equivale a ~1,5 % de mejora en disponibilidad de stock. Si el ROI calculado implica un salto de
disponibilidad mucho mayor, algún supuesto está inflado.

## Limitaciones del cálculo

1. El newsvendor de un solo período subestima el valor en productos con vida útil mayor al
   período de revisión, porque ignora que el sobrante puede venderse al período siguiente.
2. No se costea el lead time ni el capital en tránsito.
3. No se costean las restricciones operativas de la orden (múltiplos de caja, capacidad).
4. La fracción capturada es el supuesto más frágil y el que domina la sensibilidad.
5. **La política actual simulada es probablemente mejor que la real, no peor.** Se modela como
   promedio móvil de 21 días aplicado sin sesgo. Está documentado que los decisores humanos
   además **subestiman** la demanda cuando las ventas perdidas no son observables
   ([Tong, Feiler y Larrick 2018](https://journals.sagepub.com/doi/10.1111/poms.12823)). O sea que
   el ahorro calculado es conservador por este lado, y conviene decirlo antes de que lo pregunten.
6. **La política actual se evalúa contra demanda latente, igual que la del modelo.** Evaluarla
   contra la venta observada la premiaría por pedir de menos: en un día con quiebre la venta ya
   está truncada por la propia falta de stock, así que una orden chica parecería suficiente. Es
   el efecto spiral-down metido en la evaluación.

## Chequeo de coherencia del propio cálculo

Con la mejora de exactitud medida (24,5 % de MASE) y el ancla de la industria (~10 % de mejora en
exactitud ≈ ~1,5 % de mejora en disponibilidad), el salto de disponibilidad esperable es del orden
de **3,7 puntos**. Si el ROI calculado implicara mucho más que eso, algún supuesto está inflado.
La regla está fijada como test en `tests/test_policy.py` para que el chequeo exista en el código y
no como una nota al pie que nadie corre.
