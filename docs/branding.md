# Blindside · identidad de marca

**Estado:** especificación para diseñar. Complementa `docs/frontend_design.md`, que define
estructura y comportamiento; esto define lenguaje visual.
**Redactado:** 2026-09-16

---

## 1. La idea en una línea

> Los quiebres de stock te toman del lado ciego: la venta cae a cero y tu ERP no registra que hubo
> demanda. **Blindside recupera esa demanda antes de pronosticar.**

Todo lo visual tiene que servir a esa frase. Si un elemento de diseño no ayuda a que se entienda,
sobra.

## 2. Qué categoría de producto es, y qué no es

Esta es la decisión que ordena todo lo demás, y es también la respuesta a no cruzarse con el resto
del portfolio.

**Blindside es un instrumento, no un asistente.** Es un tablero de lectura densa que un
responsable de compras escanea en dos minutos, decide, y cierra. No conversa, no sugiere en prosa,
no explica. Muestra.

### Arquetipo de interfaz por proyecto

| Proyecto | Arquetipo | Lenguaje de interfaz |
|---|---|---|
| WhisperDocs | Asistente conversacional | Columna centrada, stream de mensajes, texto que aparece |
| SilentOps | Cola de propuestas para aprobar | Evidencia citada, decisión humana por ítem |
| AgroBuy | Copiloto recomendador | Comparación, score explicable |
| Focal Point | SaaS de gestión | App de negocio multi-módulo |
| Urban Attic | Vidriera | Brutalista, «Concrete Gallery» |
| **Blindside** | **Panel de instrumentos** | **Grilla densa, tabla, gráfico primero** |

El arquetipo de instrumento está libre en tu portfolio. Ocuparlo es lo que hace que Blindside se
lea como otra categoría de trabajo antes de que alguien lea una sola palabra de la descripción.

### Prohibiciones que salen de esta tabla

Estas no son preferencias estéticas, son separación de territorio:

- **Cero afordancias de chat.** Ni burbujas, ni input de pregunta, ni texto que se escribe solo, ni
  «preguntale a tus datos». Eso es WhisperDocs, y tu propio sitio ya tiene un widget `ask franco`.
- **Cero cola de aprobación.** Nada de «revisar / aceptar / rechazar» ítem por ítem. Eso es
  SilentOps. Blindside emite cantidades, no propuestas que esperan visto bueno.
- **Cero grilla de tarjetas.** Las tarjetas sirven para navegar catálogos. Acá se escanea una tabla.
- **Cero estética brutalista.** Es Urban Attic.
- **Cero módulos ni menú de ERP.** Es Focal Point.

---

## 3. El concepto visual: la brecha es el sujeto

Hay un hecho de los datos que debería generar toda la identidad.

La venta observada y la demanda recuperada son **idénticas** en todos los días sin quiebre, y se
separan **solo** dentro de los tramos de quiebre. O sea que la información no está en ninguna de
las dos líneas: está en **la brecha entre ellas**.

Eso da un sistema visual con una sola idea, que es lo que hace a una marca memorable: **el vacío se
dibuja como elemento de primera clase.** La cuña entre las dos líneas no es un espacio sobrante,
es el producto.

### La marca

Dos trazos horizontales que corren superpuestos y en un punto se abren, con la cuña entre ellos
rellena.

```
observada  ────────────────╮
                            ╰──────────────
recuperada ─────────────────────────────────
           ↑ coinciden      ↑ acá se abren
                            └── la cuña es la demanda recuperada
```

Por qué funciona como marca:

- Es literalmente un gráfico del producto, no una metáfora decorativa.
- Sobrevive a 16 px de favicon: dos líneas y una forma.
- Funciona en un solo color, en negativo, y grabada.
- Se puede animar: las líneas se abren. Eso es el toggle de censura, que es la interacción central
  del frontend. La marca y la interacción son la misma cosa.

## 4. Paleta · lógica antes que valores

La lógica importa más que los hex, porque es lo que hace que la paleta sea defendible.

**Regla única: el mundo observado es desaturado y la demanda recuperada es lo único con color
saturado en pantalla.** Ninguna otra cosa usa ese acento. Nada.

La consecuencia es que accionar el toggle **inunda la interfaz de un color que no estaba**. El
gesto se vuelve físico, y eso es exactamente lo que hay que lograr en los diez segundos de la demo
en que se muestra la corrección de censura.

### Roles de color

| Rol | Qué es | Tratamiento |
|---|---|---|
| Base | Superficies, contenedores | Neutro frío, desaturado |
| **Observado** | Venta que el ERP registró | Gris frío. Es «lo que hay», no «lo que está bien» |
| **Recuperado** | Demanda latente reconstruida | **El único acento saturado del sistema** |
| Quiebre | Los tramos ciegos | Un tratamiento propio, ver la tensión de abajo |
| Pronóstico e intervalo | Futuro | Distinto del pasado, sin competir con el acento |
| Alerta | Series que requieren atención | Reservado, y **no** puede ser el acento de recuperado |

### Dirección recomendada: ámbar sobre pizarra fría

Un acento **cálido de alta croma** — ámbar, ascua — sobre una base de grises fríos.

Tres razones, en orden:

1. La demanda recuperada tiene que leerse como algo que se enciende sobre un fondo apagado. Cálido
   sobre frío hace eso sin trucos.
2. Evita por completo la paleta por defecto de las herramientas de IA, que va a violeta, índigo,
   teal o verde. Ese es el territorio donde probablemente ya está WhisperDocs.
3. Cadena de frío invita a azules y celestes, que es la decisión obvia y por eso mismo la
   equivocada: te deja igual a cualquier dashboard de logística.

**Restricción sobre el ámbar:** no puede ser también el color de alerta. Si «recuperado» y
«atención» comparten hue, se pierde la lectura de los dos. La alerta tiene que resolverse por otro
canal, probablemente forma o posición antes que color.

### Modo claro y oscuro

Los dos, y está en el plan. La consecuencia real no es duplicar tokens: es que **el sombreado de
quiebre tiene que funcionar en ambos**. Un gris translúcido que se lee bien sobre blanco desaparece
sobre fondo oscuro. Ese sombreado hay que resolverlo dos veces, no escalarlo.

---

## 5. La tensión de diseño más difícil, medida

El sombreado de los tramos de quiebre tiene dos requisitos que empujan en direcciones opuestas.
Los números salen del panel real de 3066 series:

| Dato | Valor | Qué implica |
|---|---|---|
| Rachas de quiebre | 53.072 | Hay muchísimas |
| Rachas de **un solo día** | **44 %** | Sobre 97 días en ~800 px, un día son ~8 px |
| Mediana de la racha | 2 días | La mayoría son angostas |
| Racha máxima | **95 días** | Series en quiebre prácticamente todo el período |

**El requisito A:** una banda de 8 px tiene que ser visible. Eso pide contraste y saturación.

**El requisito B:** un gráfico con el fondo entero sombreado tiene que seguir siendo legible. Eso
pide lo contrario.

Tres salidas posibles, y hay que elegir una explícitamente en el draft:

1. **Ancho mínimo.** Las rachas de un día se dibujan con un mínimo de ~3 px de ancho visual, sin
   borde. Honesto en la forma, ligeramente impreciso en la posición.
2. **Dos tratamientos.** Bandas para rachas de dos días o más, marcadores discretos en el eje para
   las de un día. Más preciso, más complejo de leer.
3. **Marcas en el eje en vez de bandas.** Todas las rachas se indican en una franja delgada
   dedicada, bajo el gráfico, y no sobre él. El gráfico queda limpio y la relación visual entre
   quiebre y brecha se debilita.

Mi voto es la 1 para el gráfico hero y la 3 como franja complementaria, porque el panel de horas de
quiebre por día ya existe en la especificación del frontend.

---

## 6. Tipografía · direcciones, no elección

La elección es tuya. Las restricciones no:

- **Cifras tabulares obligatorias** (`font-variant-numeric: tabular-nums`) en toda la tabla de
  reposición y en todas las métricas. Con 21.462 filas de números, si las cifras no alinean
  verticalmente la tabla se vuelve ilegible.
- **Dos decimales de precisión visible.** La mediana de la demanda es 0,80. Redondear a entero
  destruye la información. Y no hay símbolo de moneda: las magnitudes son adimensionales porque el
  dataset está normalizado.
- **Separar la cara de interfaz de la cara de datos** ayuda mucho en un panel denso, pero no es
  obligatorio. Si se usa una sola, tiene que tener cifras tabulares buenas.
- **Sin monoespaciada como recurso estético.** Tu sitio ya usa el registro de terminal (`$ whoami`,
  `franco@prod:~`). Repetirlo acá diluye los dos.

---

## 7. Voz y microcopy

El registro es de **instrumento**: afirmativo, sin adjetivos, sin entusiasmo.

| En vez de | Escribir |
|---|---|
| «¡Ahorrás un 24 %!» | «−24,5 % de MASE vs naive estacional» |
| «Nuestra IA predice…» | «Cantidad sugerida en q\* = 0,625» |
| «Datos insuficientes» | «60 de 3066 series conocidas por el modelo» |
| «Alta confianza» | «Cobertura empírica 91 % · nominal 90 %» |

Dos reglas que salen del proyecto y no del gusto:

1. **Nunca un número sin su dispersión.** Si aparece un MASE, aparece su desvío entre orígenes o su
   peor origen. La metodología prohíbe el número único y la interfaz tiene que respetarlo.
2. **Nunca símbolo de moneda.** El dataset primario está normalizado por un coeficiente no
   divulgado. Todo impacto va en porcentaje o en unidades adimensionales.

El toggle necesita una etiqueta de **consecuencia**, no de estado:

> `Venta observada` — es lo que ve el ERP. Subestima la demanda en los días con quiebre.
> `Demanda recuperada` — censura corregida. Es la base de la cantidad sugerida.

---

## 8. Accesibilidad, que acá tiene consecuencia de diseño

Dos requisitos que no se pueden retrofitear:

**El par observado/recuperado no puede distinguirse solo por color.** No es solo una regla de
accesibilidad: en el gráfico hero las dos líneas se **superponen exactamente** fuera de los tramos
de quiebre, así que sin diferencia de trazo o grosor no se sabe cuál está arriba. Es un requisito
funcional que además cumple la regla.

**El toggle es el control más importante de la app.** Operable por teclado, con estado anunciado
por lector de pantalla, y con una etiqueta que diga qué cambia y no solo cómo se llama.

Lo difícil son los gráficos. Un `<canvas>` es opaco para un lector de pantalla, así que si se usa
canvas hay que ofrecer la tabla equivalente.

> Verificar cumplimiento WCAG completo requiere testing manual con tecnologías asistivas y revisión
> de un especialista. Este documento fija las decisiones que lo hacen posible, no certifica
> cumplimiento.

---

## 9. Aplicaciones

| Superficie | Qué necesita |
|---|---|
| Favicon | La marca de dos líneas y cuña, a 16 px |
| README del repo | Un solo gráfico hero, no capturas de las siete pantallas |
| Case study | La secuencia del toggle, antes y después |
| Slides de defensa | La marca en la portada; el gráfico hero como única imagen de la sección de resultados |
| Streamlit | **No se rebrandea.** Es la red de seguridad y tiene que verse como lo que es |

Sobre lo último: el dashboard Streamlit no debería intentar parecerse a Blindside. Si las dos
superficies se parecen, la de React deja de justificar su existencia.

---

## 10. Lo que falta para cerrar

**Necesito un dato tuyo.** WhisperDocs no tiene homepage ni notas de diseño en el README, así que
no puedo ver su identidad. Para poner una lista dura de «no usar», decime su paleta y su tipografía,
o mandame una captura. Mi sospecha es que va a violeta, índigo o teal sobre casi negro, que es el
default de las apps de LLM; si es así, la dirección de ámbar sobre pizarra fría ya resuelve el
cruce. Si WhisperDocs usa ámbar o naranja, hay que rotar el acento.

**Decisiones abiertas para el draft:**

1. ¿Cuál de las tres salidas del sombreado de quiebre (sección 5)?
2. ¿Una cara tipográfica o dos?
3. ¿Modo claro y oscuro desde el arranque, o claro primero?
4. ¿La marca se anima en el toggle, o queda estática?
