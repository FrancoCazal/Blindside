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

### La restricción dura: el registro de terminal está doblemente ocupado

Confirmado con el autor. **WhisperDocs** es consola futurista monocromática: azul oscuro con
blanco y negro, todo muy cuadrado, registro Windows Vista. Y **francocazal.com** también usa el
registro de terminal, con `$ whoami`, `franco@prod:~` y `$ ls ~/work`.

O sea que el lenguaje de consola ya aparece dos veces en el portfolio. Blindside no puede ser la
tercera, y esto elimina un conjunto grande de decisiones que de otro modo eran tentadoras para un
panel denso:

| Prohibido | Por qué |
|---|---|
| Fondo oscuro como expresión canónica | Es WhisperDocs |
| Azul oscuro en cualquier rol protagónico | Es WhisperDocs |
| Paleta monocromática | Es WhisperDocs |
| Monoespaciada como recurso estético | WhisperDocs y el sitio personal |
| Prompt, cursor parpadeante, scanlines, glow | Registro de consola |
| Bordes gruesos y cajas duras estilo Vista | Es WhisperDocs |
| Cromado, vidrio, gradientes lustrosos | Vista |

Queda poco margen por el lado oscuro-técnico, y eso es bueno: fuerza la decisión que sigue.

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

### Dirección recomendada: el registro corregido

**La interfaz es un registro de medición impreso, y la demanda recuperada es la corrección
anotada encima.** Papel cálido, reglas finas, tablas regladas, y un único acento de anotación.

Es la dirección que propongo después de confirmar que WhisperDocs es consola oscura monocromática,
y la elijo por cinco razones que van de la más fuerte a la más débil:

**1. Encoda la tesis, no la decora.** El proyecto sostiene que el registro del ERP está mal y que
esto es la corrección. Dibujar la demanda recuperada como una anotación sobre un registro impreso
*es* el argumento. El rojo de corrección sobre el informe ya significa eso culturalmente, sin que
haya que explicarlo.

**2. Es el contraste máximo contra WhisperDocs.** Consola oscura monocromática contra registro
claro con un acento. No hay forma de confundirlos ni de reojo.

**3. Es la decisión menos obvia y por lo tanto la que se recuerda.** Prácticamente toda herramienta
de datos y de IA en 2026 va oscura. Ir claro es lo diferenciado, y además es lo que hace un
instrumento de medición serio: los papers, los informes de laboratorio y los registros de
calibración son claros.

**4. Resuelve mejor la tensión técnica de la sección 5.** Un lavado de sombra de 8 px es más fácil
de hacer visible sobre papel que sobre fondo oscuro, y un gráfico con el fondo entero sombreado
sigue siendo legible en claro. Sobre negro, un sombreado que se vea a 8 px vuelve ilegible el caso
de 95 días.

**5. Se aleja del reflejo obvio del dominio.** Cadena de frío invita a azules y celestes, que es la
decisión evidente y por eso mismo la equivocada: te deja igual a cualquier dashboard de logística,
y encima cerca del azul de WhisperDocs.

### Paleta de arranque

Valores para empezar el draft, no para cerrarlo. La lógica de los roles es lo que importa.

| Rol | Valor | Nota |
|---|---|---|
| Papel | `#FAF8F5` | Blanco cálido, no puro. El frío llevaría al eje azul |
| Papel hundido | `#F2EEE8` | Insets, encabezados de tabla, franjas alternas |
| Tinta | `#1A1A18` | Casi negro cálido. Texto principal |
| **Observado** | `#8A8A84` | Gris cálido medio. Es «lo que hay», no «lo que está bien» |
| **Recuperado** | `#D6451A` | **Vermellón de anotación. El único saturado del sistema** |
| Quiebre | Tinta al 7 % | Lavado neutro. Sobre papel lee como sombra, que es exacto |
| Pronóstico | Tinta al 55 %, trazo discontinuo | Futuro distinto del pasado |
| Banda conformal | Recuperado al 12 % | Deriva del acento, no compite con él |
| Reglas | Tinta al 12 % | Hairlines. Nunca bordes gruesos |

**Dos restricciones sobre el acento:**

El vermellón **no puede ser también el color de alerta**. Si «recuperado» y «atención» comparten
hue se pierden los dos. La alerta se resuelve por forma y peso — un marcador lleno, la fila en
negrita — antes que por color. Si hace falta un hue, que sea un oro oscuro y sobrio, lejos del
vermellón.

Y el vermellón **no se usa en ningún otro lugar**: ni en botones, ni en links, ni en el logo en
contexto de interfaz. Reservarlo por completo es lo que hace que accionar el toggle inunde la
pantalla de un color que no estaba.

> Los ratios de contraste hay que verificarlos en el draft. `#8A8A84` sobre `#FAF8F5` no llega a
> 4.5:1, así que sirve para trazos de gráfico pero **no** para texto. El texto secundario necesita
> bajar a algo del orden de `#5F5F59`.

### Lenguaje de forma

Contra las cajas duras de Vista, el registro impreso pide lo contrario:

- **Reglas finas en vez de bordes.** Una tabla se estructura con hairlines horizontales, no con
  cajas cerradas.
- **Radio de esquina mínimo o nulo, pero sin peso.** Lo cuadrado no es el problema; el problema es
  lo cuadrado *grueso*. Un borde de 1 px al 12 % de opacidad es cuadrado y no es Vista.
- **Nada de sombras de elevación, glow, vidrio ni gradientes.** Un instrumento es plano.
- **La densidad se logra con alineación, no con líneas.** Si todo alinea a una grilla, hacen falta
  muchas menos reglas.

### Modo claro y oscuro

El claro es la **expresión canónica**: es el que va a las capturas, al case study y a las slides.
El oscuro existe porque el plan lo pide y porque un operador que mira el panel todo el día lo va a
querer, pero no es la cara de la marca.

Consecuencia real, y no es duplicar tokens: **el lavado de quiebre hay que resolverlo dos veces.**
Un translúcido neutro que funciona sobre papel desaparece sobre fondo oscuro. Y en oscuro el
vermellón necesita subir en luminosidad para no apagarse.

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
- **Sin monoespaciada como recurso estético, y esto es firme.** El registro de terminal ya aparece
  dos veces en el portfolio: WhisperDocs es consola monocromática y francocazal.com usa `$ whoami`
  y `franco@prod:~`. Una tercera vez deja de ser una firma y pasa a ser un tic.

  La distinción que importa: **monoespaciada para código sí, monoespaciada como estética no.** Un
  bloque de `make backtest` en el README va en mono porque es código. Los números de la tabla de
  reposición van en cifras tabulares de una proporcional, no en mono.
- **Dirección que acompaña al registro impreso:** una proporcional con buenas cifras tabulares para
  los datos, y si se usan dos caras, una con algo de personalidad editorial para los títulos. Serif
  o sans es decisión tuya; lo que no va es la estética de consola.

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

## 10. Contraste contra el portfolio, resumido

La tabla que conviene tener al lado mientras se diseña:

| Eje | WhisperDocs | Blindside |
|---|---|---|
| Fondo canónico | Azul oscuro, casi negro | Papel cálido |
| Croma | Monocromático | Neutro + **un** acento reservado |
| Registro | Consola futurista | Registro de medición impreso |
| Forma | Cuadrado grueso, Vista | Reglas finas, plano |
| Tipografía | Monoespaciada estética | Proporcional con cifras tabulares |
| Interacción central | Conversar | Accionar un toggle y ver cambiar todo |
| Densidad | Columna de lectura | Grilla a todo el ancho |

Si el draft cumple esa tabla, no hay forma de confundirlos.

## 11. Decisiones abiertas para el draft

1. ¿Cuál de las tres salidas del sombreado de quiebre de la sección 5? Mi voto: ancho mínimo en el
   gráfico hero, más la franja de horas de quiebre debajo.
2. ¿Una cara tipográfica o dos?
3. ¿El vermellón `#D6451A` o rotar el acento? Lo que no se negocia es que sea uno solo, cálido y
   exclusivo de la demanda recuperada.
4. ¿La marca se anima en el toggle, o queda estática?
5. ¿El oscuro entra en la primera versión o queda para después? El claro es el canónico de todos
   modos.

## 12. Riesgo de esta dirección, dicho de entrada

Un panel claro para uso operativo diario tiene un contra real: mucha gente de operaciones prefiere
oscuro, y hay quien lee «claro» como menos técnico. La mitigación es que el oscuro exista, y el
argumento de fondo es que la marca no se elige por preferencia de uso sino por legibilidad en el
portfolio: la expresión canónica tiene que distinguirse de WhisperDocs a primera vista, y ahí el
claro gana sin discusión.

Si en el draft el claro no cierra, la alternativa **no** es volver a oscuro-azul. Es oscuro cálido,
tinta casi negra con matiz cálido y el mismo vermellón, que mantiene la separación por temperatura
aunque pierda el contraste de valor.
