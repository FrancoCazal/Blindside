# Guion del video del demo

El plan llama al video "el único riesgo que puede arruinar la defensa", porque un demo en vivo
que falla no se recupera. Esto es un **respaldo grabado**: dura 2 minutos, es el punto 6 de la
defensa, y si el vivo falla se proyecta esto.

Grabar en **1440×900 o 1920×1080**, tema claro, sin audio (se narra en vivo). Cursor visible.

## Antes de grabar

```bash
make docker-up                      # api en :8000, Streamlit en :8501
make front-setup                    # una vez; evita descubrir que falta node_modules al grabar
make front                          # React en http://127.0.0.1:5173
docker compose ps                   # api y Streamlit en (healthy) ANTES de empezar
```

**El video principal usa React.** Es la superficie operativa. La app abre en el Panel y en inglés,
pero el video entra directo a Reposición y en español con
`http://127.0.0.1:5173/?screen=reorder&basis=observed&lang=es`, que responde cuánto pedir hoy.
`lang=es` queda guardado en el navegador, así que las pestañas siguientes ya abren en español; si
no, se cambia en Preferencias, arriba a la derecha, que es también donde se fija el tema claro.
Streamlit es la red de seguridad independiente y abre en «Qué mirar primero»,
el triage del catálogo; no conviene saltar entre las dos en un video de 2 minutos. Si React no
levanta, grabar la variante de respaldo en `:8501`: mostrar 15 segundos del triage y después
«Reposición», «Serie individual» y «Validación y antifugas».

Esperar a que `/health` responda: la API carga el panel al arrancar y los primeros segundos
devuelve error. Abrir las tres pestañas y **dejarlas cargadas** antes del primer frame — el video
no debe mostrar un spinner de arranque.

## Los 2 minutos, plano por plano

| Tiempo | Pantalla | Qué se hace | Qué se ve |
|---|---|---|---|
| 0:00–0:20 | Reposición | Nada, dejar quieto | 3.066 series ordenadas por ahorro esperado sobre todo el catálogo, los motivos de cada fila, los cuatro KPI contra la política |
| 0:20–0:50 | Reposición | **Activar el toggle de censura** y esperar | Las **cantidades** cambian fila por fila y el orden del catálogo se rehace. La orden total pasa de 3.601 a 4.218. Es el momento más importante del video |
| 0:50–1:15 | Serie | Clic en la primera fila | El gráfico con la brecha observada contra recuperada, la cantidad sugerida, los motivos de alerta y los próximos 7 días |
| 1:15–1:35 | Serie | Bajar a «Por qué este número» | Los aportes por variable con valor y signo, que suman **exactamente** la cantidad sugerida |
| 1:35–1:50 | Modelos | — | MASE 0,822 ± 0,045, 25,3 % menos error que el naive estacional, y la cobertura CQR contra la del conformal de residuos |
| 1:50–2:00 | Terminal | `make test-leakage` | Los asserts antifugas pasando en verde |

## El plano que no se puede saltear

**El toggle de censura (0:20–0:50).** Es el argumento del proyecto en una interacción: hay **dos
artefactos** entrenados con la misma arquitectura, uno sobre venta observada y otro sobre demanda
latente, así que el toggle cambia **la cantidad a pedir** y no el dibujo. Si el video muestra una
sola cosa, es esa.

Al narrarlo: «corregir la censura sube la orden total del catálogo un 17 %, de 3.601 a 4.218».
El atajo `B` alterna la base sin tocar el mouse.

## Errores a evitar

- **No** improvisar navegación. Cada clic está en la tabla de arriba.
- **No** mostrar el `/docs` de FastAPI. Es tentador y no dice nada del proyecto.
- **No** grabar con la API recién levantada. El primer `/forecast` de 500 series tarda.
- **No** dejar la consola del navegador abierta.
- Si algo sale mal, **cortar y regrabar**. Son 2 minutos.

## Si el vivo falla durante la defensa

Poner el video y narrar encima. Los números que hay que poder decir de memoria:

- MASE **0,8217**, peor origen **0,8790**, **+25,3 %** contra el naive estacional. El objetivo
  SMART era 20 %.
- Cobertura **88,0 %** contra 90 % nominal, y está declarado que sub-cubre dos puntos.
- Reducción del sesgo de censura: **11,57 puntos** (−18,19 % → −6,61 %).
- Cuantil crítico **q\* = 0,625**, y la predicción en ese cuantil **es** la orden.
