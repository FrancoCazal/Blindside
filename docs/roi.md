# Cálculo de ROI

> **Estado:** estructura definida, números pendientes. Se completa cuando el backtest produzca
> las mejoras de decisión (`make backtest`).

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
- Aumento del nivel de servicio
- Reducción de la merma simulada

La política actual se modela como reposición según promedio reciente, que es lo que hace la
mayoría de las operaciones sin sistema.

```
Costo_esperado = Cu × E[faltante] + Co × E[sobrante]

Mejora_relativa = 1 - Costo_esperado(politica_modelo) / Costo_esperado(politica_actual)
```

Ambos términos se estiman **empíricamente sobre las ventanas del backtest**, no con fórmula
cerrada.

### Capa 2 · Traducción a dinero, paramétrica

Se aplica la mejora relativa a un perfil de operación con cuatro supuestos declarados:

| Supuesto | Valor usado | Fuente / justificación |
|---|---|---|
| Facturación anual del perfil | — | declarado, no observado |
| Número de SKU activos | — | declarado |
| Margen bruto por categoría | — | declarado |
| Tasa de merma base | — | ancla publicada (ver abajo) |
| Fracción de la mejora efectivamente capturada | — | nunca 100 % |

Se reporta un **rango con análisis de sensibilidad** sobre los cuatro, más el caso pesimista.

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
