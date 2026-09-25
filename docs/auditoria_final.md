# Auditoría final y plan de últimas horas

Fecha: 2026-09-25. Contexto: entrega en horas. Criterio de prioridad: **riesgo para la defensa por
minuto invertido**, no cantidad de módulos del roadmap.

## Veredicto ejecutivo

**El software está terminado. La entrega todavía no:** faltan el video y las slides, más dos
ensayos cronometrados. No conviene abrir ahora actualización continua, aumentar el dataset,
calibrar otra vez el intervalo ni agregar modelos.

El audit encontró y corrigió cuatro defectos baratos de demo:

1. El README contaba 7 pantallas de Streamlit y 8 de React; son **8 y 7**, respectivamente.
2. `PantallaSerie` mostraba un sello `sim` afirmando que la política se calculaba en cliente,
   aunque `/reorder` ya devuelve `policy_qty` y `policy_window` y la pantalla los usa.
3. El toggle central no anunciaba la cifra que cambiaba en la landing. Ahora anuncia el modo y,
   cuando termina `/reorder`, el total real de la página; el atajo global `B` también anuncia.
4. El README seguía pidiendo una captura. La captura real de Playwright está publicada en
   `docs/assets/reposicion.png`. El despliegue público no se promete porque la API no tiene auth.

Verificación del lote: TypeScript limpio, 39 tests de Vitest, oxlint con 0 errores, ruff limpio y
12 tests de Playwright en claro/oscuro y cuatro anchos.

---

## P0 · Hacer antes de entregar

### 1. Grabar el video — no escribir más código antes

Guion: `docs/demo_guion.md`. Dos minutos. El video principal usa React; Streamlit es la red de
seguridad. Plano que no se puede omitir: activar el toggle de censura y mostrar que cambia la
**cantidad a pedir**, no solo el gráfico.

Preparación:

```bash
make docker-up
make front-setup
make front
docker compose ps     # api y Streamlit en healthy
```

Esperar a `/health` antes de grabar. Abrir las pestañas antes del primer frame.

### 2. Hacer las slides

Quince minutos, siguiendo la sección 15 del plan:

1. Problema y efecto spiral-down · 2 min.
2. Dataset y recuperación de censura · 2 min.
3. Antifugas y backtesting móvil · 2 min.
4. Resultados contra baselines, con dispersión · 3 min.
5. CQR + newsvendor: de pronóstico a orden · 3 min.
6. Demo · 2 min.
7. Limitaciones y roadmap · 1 min.

Números que tienen que aparecer una sola vez y coincidir:

- MASE **0,8217 ± 0,0454**, peor origen **0,8790**, +**25,3 %** vs naive estacional.
- Cobertura **88,0 %** vs 90 % nominal; declarar la sub-cobertura, no redondearla.
- Sesgo re-censurado −18,19 % → −6,61 %: **11,57 puntos** de reducción.
- `q* = 0,625`: la predicción en ese cuantil **es** la orden.
- SARIMA 0,9136, empatado con media móvil 0,9139.

### 3. Hacer dos ensayos cronometrados

El segundo ensayo tiene que usar el video como fallback, no el vivo. Ensayar también estas tres
respuestas, porque son los lugares donde la medición contradijo una intuición cómoda:

- **Productos nuevos:** el mecanismo de clustering existe, pero no entra al artefacto. La feature
  mueve MASE +0,28 % con ±11 puntos entre orígenes, y FreshRetailNet no tiene una sola serie de
  arranque en frío.
- **Cobertura menor a 90 %:** CQR cubre 88 % con banda 53 % más angosta; el conformal de residuos
  cubre 98,7 % con una banda del doble de ancho. No se movió el objetivo después de mirar el dato.
- **Por qué no moneda:** `sale_amount` está escalado por un coeficiente no divulgado. Inventar
  guaraníes sería peor que reportar porcentajes.

---

## P1 · Limitaciones del frontend que NO conviene arreglar hoy

### Orden global de la tabla de reposición

La tabla ordena las 25 filas visibles, no las 3.066 series. `/series` no conoce el impacto porque
el impacto aparece recién después de `/reorder`. La serie de mayor impacto puede estar en otra
página. Está declarado al pie y no es un bug de presentación: corregirlo exige un endpoint batch
de triage/reposición de catálogo completo, con paginación y orden del lado servidor.

**Respuesta para la defensa:** «La versión operativa pagina primero y ordena dentro de la página;
para producción el backend tiene que materializar la reposición del catálogo y servirla ordenada.
No hago 123 llamadas desde el navegador ni finjo que la página visible es el catálogo.»

### Ancho mínimo de 1024 px

Debajo de 1024 px el React muestra un aviso en vez de esconder columnas de decisión. Es deliberado:
la interfaz está pensada para escritorio/proyector y no para móvil. Probar la máquina y el proyector
antes de la defensa; no rediseñar responsive hoy.

### React y Streamlit abren en cosas distintas

Es correcto y hay que poder decir por qué:

- **React** abre en Reposición: producto operativo, responde cuánto pedir hoy.
- **Streamlit** abre en Qué mirar primero: red de seguridad analítica, responde dónde revisar.

No son dos productos compitiendo: React es la superficie principal; Streamlit puede operar sin el
frontend y sirve como fallback de la defensa.

---

## Actualización continua · recomendación

### Estado actual

Hoy el sistema es **batch**:

- La API carga panel y artefactos una sola vez en `lifespan` y los guarda en `STATE`.
- No hay endpoint de ingesta, append, upsert ni reload.
- Los servicios de consulta montan datos y artefactos como volúmenes de solo lectura.
- Regenerar `demand.parquet` o `model.joblib` no cambia lo que la API sirve hasta reiniciarla.
- `Forecaster.save` hace `joblib.dump` directamente sobre el archivo final: no hay swap atómico,
  candidato, rollback ni versión anterior.
- No hay drift ni scheduler de reentrenamiento.

**Conclusión:** es viable, porque recuperación/features/modelos ya están separados y serializados,
pero no es un cambio de horas. Implementar «un endpoint que reciba CSV» no sería actualización
continua; sería abrir una ruta de escritura sin idempotencia, atomicidad, auth, drift ni rollback.

### Orden correcto de implementación después de la entrega

#### Fase A · Observabilidad y swap seguro

1. Guardar el modelo a `candidate.joblib`; cargarlo y hacer smoke forecast.
2. Promover con `os.replace()` en el mismo filesystem; conservar `model.prev.joblib`.
3. Exponer en `/health`: `data_max_date`, `artifact_trained_until`, mtime/versión y estado de
   frescura. No llamar «drift» a una fecha vieja: es **staleness**, no cambio de distribución.
4. Recargar por mtime o con endpoint administrativo **autenticado**. Sin auth no se agrega un
   endpoint que cambie el modelo servido.

#### Fase B · Ingesta idempotente

1. Contrato diario por tienda×producto con clave única `(series_id, dt)`.
2. Validación de esquema y rangos antes de escribir.
3. Upsert en staging, detección de duplicados y conflicto explícito; nunca append ciego.
4. Particionar parquet por fecha o usar una base; el parquet único actual exige reescribir todo.
5. Recalcular recuperación/features solo para series tocadas, con suficiente cola histórica para
   lags/rolling.

#### Fase C · Política de reentrenamiento

1. Trigger por calendario **y** por cantidad de días nuevos, no por cada archivo.
2. Backtest del candidato contra el vigente en orígenes recientes.
3. Puerta de promoción y rollback. El criterio de tuning (`vale_la_pena`) es una plantilla, no la
   regla final.
4. Drift de features/errores con alertas; nunca reentrenar automáticamente solo porque PSI pasó un
   umbral.
5. Registro de versiones: datos, código, parámetros, métricas y artefacto promovido.

### Qué implementar hoy

**Nada de estas fases.** El cambio mínimo útil (swap atómico + frescura visible) puede hacerse en
unas horas, pero no compra puntos comparables con tener video/slides y abre una nueva superficie a
verificar. Está documentado como siguiente versión.

---

## ¿Se puede entrenar con más tiempo de FreshRetailNet?

### Más días: no

Evidencia local y de la fuente:

- `data/raw/` contiene únicamente `train.parquet` y `eval.parquet`.
- `REMOTE_FILES` del loader define solo esos dos splits.
- El manifiesto real declara 97 días, del 2024-03-28 al 2024-07-02.
- `train` aporta 90 días y `eval` los 7 siguientes. No hay un tercer tramo escondido.
- La fuente pública describe 50.000 series de 90 días con vectores horarios; el `eval` agrega los 7
  días del benchmark.

Las columnas horarias no agregan historia: son 24 observaciones **dentro de cada uno de esos días**.
Por tanto, ampliar la ventana temporal exige **otra fuente** o datos propios con el mismo contrato.
No hay workaround honesto dentro de FreshRetailNet.

### Más series: sí, pero no hoy

La fuente tiene 50.000 series, 898 tiendas y 18 ciudades; el proyecto usa 3.066, 38 tiendas y 309
productos. Subir `n_series` o abrir más ciudades es un cambio de configuración, y el submuestreo
por tienda completa preserva jerarquías.

Pero más series **no corrige** lo que falta por tiempo: no crea estacionalidad anual, no habilita
horizonte de 28 días y no produce series de arranque en frío. Solo aumenta variedad y volumen.
Además invalida todos los números publicados: exige regenerar `interim`, `processed`, artefactos,
backtests, ablación, tuning, README y model card. A horas de entregar no se toca.

### Si se quiere más tiempo de verdad

Buscar una segunda fuente o datos propios con, como mínimo:

- 12 meses diarios para aprender anualidad básica; ideal 18–24 meses.
- Las mismas claves tienda/producto/categoría.
- Stock disponible o etiqueta de quiebre; sin eso se pierde el diferencial de censura.
- Precio/descuento, feriado y actividad planificada.
- Altas reales de productos para medir arranque en frío.

No conviene concatenar datasets de retailers/geografías distintos como si fueran una sola serie. Se
puede preentrenar/contrastar o usar como dominio separado, pero calendario, escala, categorías y
mecanismo de quiebre no son directamente compatibles.

---

## Decisión final

### Implementado ahora

- Correcciones bloqueantes del frontend y documentación.
- Captura real en el README.
- Auditoría guardada en este documento.

### Hacer manualmente ahora

1. Video.
2. Slides.
3. Dos ensayos.
4. Entregar el tag final y no volver a abrir código.

### Primera versión posterior a la entrega

1. Frescura en `/health`.
2. Guardado/promoción atómica de artefactos con rollback.
3. Recarga segura.
4. Ingesta idempotente.
5. Drift y política de reentrenamiento.
6. Evaluar una fuente con 12–24 meses; FreshRetailNet no puede aportar más días.
