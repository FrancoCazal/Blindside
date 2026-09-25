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

**El video principal usa React.** Es la superficie operativa: abre en «Reposición» y responde
cuánto pedir hoy. Streamlit es la red de seguridad independiente y abre en «Qué mirar primero»,
el triage del catálogo; no conviene saltar entre las dos en un video de 2 minutos. Si React no
levanta, grabar la variante de respaldo en `:8501`: mostrar 15 segundos del triage y después
«Reposición», «Serie individual» y «Validación y antifugas».

Esperar a que `/health` responda: la API carga el panel al arrancar y los primeros segundos
devuelve error. Abrir las tres pestañas y **dejarlas cargadas** antes del primer frame — el video
no debe mostrar un spinner de arranque.

## Los 2 minutos, plano por plano

| Tiempo | Pantalla | Qué se hace | Qué se ve |
|---|---|---|---|
| 0:00–0:20 | Reposición | Nada, dejar quieto | 3.066 series, la tabla con cantidad a pedir, la columna Señal, el paginador «1–25 de 3.066» |
| 0:20–0:50 | Reposición | **Activar el toggle de censura** y esperar | El pronóstico y la **cantidad** cambian: 210,958 → 268,478. Es el momento más importante del video |
| 0:50–1:10 | Serie | Clic en una serie con señal «parcial» | La banda del intervalo, el sparkline, la política de media móvil al lado de la del modelo |
| 1:10–1:35 | Serie | Abrir la atribución | Los aportes por feature con valor y signo, el cuantil 0,625 declarado |
| 1:35–1:50 | Salud | — | El modelo cargado, MASE y cobertura servidos por la API |
| 1:50–2:00 | Terminal | `make test-leakage` | Los asserts antifugas pasando en verde |

## El plano que no se puede saltear

**El toggle de censura (0:20–0:50).** Es el argumento del proyecto en una interacción: hay **dos
artefactos** entrenados con la misma arquitectura, uno sobre venta observada y otro sobre demanda
latente, así que el toggle cambia **la cantidad a pedir** y no el dibujo. Si el video muestra una
sola cosa, es esa.

Al narrarlo: «corregir la censura sube el pronóstico 25,3 % y la orden 27,3 %».

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
