# Blindside · resumen de la defensa

## Slides principales (12:45)

| # | Título | Mensaje principal | Visual | Duración |
|---|---|---|---|---:|
| 1 | Blindside | Cuánto pedir de cada perecedero, en cada tienda, cada día | Portada | 0:15 |
| 2 | El problema: pedir algo que vence | Los dos errores cuestan, la regla actual no estima incertidumbre y la venta engaña | Costo esperado de una orden (`fig_problema.png`, esquema) | 1:00 |
| 3 | La solución planteada | Corregir, pronosticar con incertidumbre y traducir a una orden; dos objetivos medibles | Flujo venta observada → cantidad a pedir (`fig_flujo.png`) | 1:00 |
| 4 | El dataset: FreshRetailNet-50K | Lo elegí porque anota el stock hora por hora | Tabla de campos + un día real con quiebre (`fig_dia_quiebre.png`) | 1:00 |
| 5 | Cuando hay quiebre, la venta miente | Corregir la censura reduce el sesgo 11,57 puntos | Spiral-down + ablación (`fig_spiral.png`, `fig_ablacion.png`) | 1:00 |
| 6 | Qué modelos probé y por qué | Cada modelo responde una pregunta; el servido es el que decide la orden | Tabla modelo, justificación y MASE | 1:15 |
| 7 | Un solo modelo global | SARIMA empata con la media móvil de 21 días | MASE clásico (`fig_clasico.png`) | 0:45 |
| 8 | ¿Funciona? | 25,3 % menos error; objetivo cumplido también en el peor origen | MASE por modelo con objetivo SMART (`fig_resultado.png`) | 0:45 |
| 9 | Cuán seguro está el pronóstico | CQR cubre 88 % con banda 53 % más angosta; sub-cubre dos puntos | Bandas + cobertura por horizonte (`fig_cqr.png`, `fig_cobertura_h.png`) | 1:00 |
| 10 | De pronóstico a cantidad a pedir | La predicción en q* = 0,625 es la orden | Cuantil + toggle medido (`fig_newsvendor.png`, `fig_toggle.png`) | 1:00 |
| 11 | El producto: qué pedir hoy | El toggle cambia la cantidad a pedir, no solo el dibujo | Captura anotada (`reposicion_anotada.png`) | 2:00 |
| 12 | Lo que no funcionó también se publica | Publicar lo que no funcionó es control de sobreajuste | `fig_negativos.png` | 1:00 |
| 13 | Qué falta para producción | Corrige, pronostica y termina en una decisión auditable | Tabla implementado / limitaciones / próxima versión | 0:45 |

## Respaldo

A · Ocho controles antifugas · B · Por qué 7 días y no 28 (con la ventana temporal) · C · SARIMA fijo vs AutoARIMA · D · CQR vs conformal de residuos · E · Recuperación de censura · F · Actualización continua · G · Por qué no ampliar FreshRetailNet · H · Literatura y novedad · I · Pipeline y antifugas

## Imágenes que tienen que estar en `docs/slides/assets/`

- `fig_flujo.png`, `fig_spiral.png`, `fig_ablacion.png`, `fig_ventana.png`
- `fig_pipeline.png`, `fig_features.png`, `fig_clasico.png`, `fig_resultado.png`
- `fig_cqr.png`, `fig_cobertura_h.png`, `fig_newsvendor.png`, `fig_toggle.png`
- `fig_negativos.png`, `fig_problema.png`, `fig_dia_quiebre.png`
- `reposicion_anotada.png` (derivada de `docs/assets/reposicion.png`)

Todas se regeneran con `python docs/slides/figs.py` a partir de números copiados de `reports/`.

## Exportar

```bash
npx --yes @marp-team/marp-cli@4.5.1 docs/slides/blindside_defensa.md --pdf --allow-local-files
```
