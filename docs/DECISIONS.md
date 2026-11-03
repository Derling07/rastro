# Decisiones

Lenguaje llano. Cada punto dice qué se hizo, por qué, qué otra opción se miró, y hasta dónde llega.

## 1. Libreta de campo, no el visor de noche

**Qué.** La app pasó de fondo verde casi negro a una libreta: papel gris verdoso, texto verde bosque, el video dentro de un marco oscuro con esquinas de visor. Cada módulo tiene un color (trampa ocre, tránsito azul, multitud teja, granja musgo, área protegida umber). Arriba hay tres pasos: elegí un módulo, mirá el video, leé el conteo y las alertas. Sigue en inglés.

**Por qué.** El dueño no quería el estilo anterior. Un juez tiene que entender el producto sin que nadie se lo explique. El marco oscuro es la pieza que se recuerda: parece una cámara, no una tarjeta de un panel genérico. Los números van en monoespaciada (hechos). La nota de Muse Spark va en serif (interpretación).

**Otra opción.** Seguir el diseño “cámara trampa de noche” de `docs/design/DESIGN.md`, o un panel claro tipo SaaS. Se descartó el primero porque ya no gustaba, y el segundo porque se ve igual a cualquier dashboard.

**Límite.** No hay animaciones de relleno. El contraste de texto sobre papel está pensado para AA. No se midió con un auditor automático de toda la página.

## 2. Una sola tarjeta de alerta para los módulos

**Qué.** `AlertCard` muestra, en este orden: lo que vio el detector (la caja, no una foto recortada), el conteo del motor, el contexto, dos o tres líneas de “Muse Spark summary”, la severidad (puede decir `not sure`), y Confirmar / Descartar. En el área protegida el botón es Review.

**Por qué.** Los criterios se puntúan parejo: impacto, uso de Meta, profundidad, y demo. Una sola tarjeta deja ver el sistema (cámara → conteo → nota → persona) en los cuatro módulos, sin convertir Rastro en “analizá esta imagen”.

**Otra opción.** Un texto distinto en cada página. Se descartó porque el juez no compararía los módulos.

**Límite.** La caja es el rectángulo guardado, no un recorte de píxeles del animal. Si no hay foto, la tarjeta lo dice.

## 3. DSCF0112 es el flujo héroe, y no se vuelve a llamar al modelo

**Qué.** La nota de la trampa lee el `result.json` ya guardado: 90 detecciones de un coyote (individuos NOT VERIFIED) y el párrafo que Muse Spark Open escribió en esa corrida (`meta-models/muse-spark-open-1026`). Abrir la página no llama a SAM ni a Baseten. `paid_call` queda en falso.

**Por qué.** Hay que mostrar Meta de verdad, y a la vez no gastar créditos en esta pasada. Esa corrida ya existe y el eval la marca PASS. El número grande sale del motor. Aunque el texto dijera otra cifra, la UI no la usa.

**Otra opción.** Llamar a Muse Spark en vivo al abrir la demo. Se descartó: cuesta créditos y puede fallar delante del juez. Otra opción era inventar un párrafo nuevo y firmarlo como si el modelo lo hubiera escrito ahora. No se hizo.

**Límite.** La nota grabada no se revalidó contra el servicio el 31 oct 2026. El origen dice `baseten-spark` porque así quedó guardado en el archivo, no porque esta página haya hablado con Baseten.

## 4. “Not sure” cuando la confianza es baja

**Qué.** Si la confianza es baja, la severidad es exactamente `not sure`. Pasa en tránsito (el conteo no está verificado), en multitudes de la cámara de ejemplo (no hay metros cuadrados, así que no se calcula gente/m²), y cuando hay una persona en la zona protegida (una persona tiene que mirar). La trampa DSCF0112 queda en `info`, no en `not sure`, porque el eval de ese clip es PASS.

**Por qué.** El criterio pide decir “no estoy seguro” en vez de inventar una alarma segura. En anti-caza, confirmar no puede sonar a “ya identifiqué a alguien”.

**Otra opción.** Poner severidad alta en la persona del bosque. Se descartó: el producto dice “posible intrusión, hace falta revisión”, y no avisa a autoridades.

**Límite.** “Confianza baja” aquí es una regla del código (verificado o no, y si el aviso es de una persona). No es un porcentaje que haya devuelto el modelo en esta pasada.

## 5. El área protegida usa Review, no Confirm

**Qué.** En Forest trail el único botón es Review. Confirm está rechazado por el servidor, igual que antes.

**Por qué.** Confirm en esa cámara se leería como “esto es una intrusión verificada” o como permiso para avisar a alguien. Rastro no identifica y no notifica autoridades. La cara queda en una caja difuminada, sin nombre ni id.

**Otra opción.** El mismo par Confirmar / Descartar en los cuatro módulos, incluido este. Choca con la prueba que prohíbe `confirm` en esa cámara. Se dejó Review a propósito.

**Límite.** El difuminado del video publicado ya venía en el clip. El visor tapa la caja de la persona; no es un desenfoque nuevo del archivo de video.

## 6. Exportar en formato compatible con Waze for Cities, sin ser socios

**Qué.** `GET /api/open/events` devuelve JSON con un arreglo `incidents` (id, type, street, polyline, direction, starttime, description), el esquema público CIFS. `GET /api/open/events.xml` es el mismo contenido en XML. Hay un enlace `https://www.waze.com/ul?ll=...` que solo abre el mapa. El texto dice que el formato es compatible con Waze for Cities, que no hay partnership, y que para que Waze ingiera el archivo hay que entrar al programa.

**Por qué.** El dueño quiere que Rastro hable el idioma de un sistema de movilidad, no solo de un video subido. El formato está documentado por Waze. No hace falta una llave de pago para armar el archivo.

**Otra opción.** Prometer integración con Uber, DiDi o Google Maps, o mandar el archivo a Waze desde el servidor. No se hace. Un envío real podría publicar un cierre falso.

**Límite.** No se envió el archivo a Waze. Está **NOT VERIFIED** contra el servicio en vivo. La calle es “Example road” y el punto es un ejemplo en San José (9.928069, -84.090725), no una cámara medida. No hay que subirlo tal cual. El feed de horas pico sigue siendo solo lectura.

## 7. Webhooks apagados

**Qué.** Se puede anotar una URL `https`. Al confirmar o revisar una nota, el servidor guarda el cuerpo que mandaría (incluye el conteo del motor). No abre una conexión. Rechaza localhost y URLs con usuario/clave.

**Por qué.** Cualquier app podría suscribirse más adelante, sin elegir un proveedor de pago. Dejar el envío apagado evita pegarle a un sitio por accidente y evita filtrar secretos.

**Otra opción.** Hacer POST de verdad en la demo. Se descartó en esta pasada.

**Límite.** La entrega real no está probada. **NOT VERIFIED.**

## 8. Cámaras RTSP, HLS y MJPEG, en modo simulado

**Qué.** `POST /api/streams` reconoce `rtsp`/`rtsps`, una lista HLS (`.m3u8`) y MJPEG. Responde `connected: false` y `mode: simulated`. No abre el flujo. La página de cámaras sigue pasando clips con licencia abierta y el sello Simulated camera.

**Por qué.** La idea es un sistema que puede colgarse de una cámara de camino o de finca. Abrir una URL cualquiera en la demo puede violar una licencia o una red privada. El modo simulado es el respaldo honesto.

**Otra opción.** Reproducir una cámara pública en vivo. No hay una URL con licencia revisada para dejarla fija. Quedó para que Derling pegue una si la consigue.

**Límite.** No hay una conexión de prueba contra una cámara real. **NOT VERIFIED.**

## 9. Clima y mapa, no en esta pasada

**Qué.** No se llamó a Open-Meteo ni a Nominatim. El contexto de la nota dice que no se agregó clima ni mapa.

**Por qué.** El orden pedido fue: diseño, nota del agente, export y cámaras. Clima y mapa eran el paso 4, solo si sobraba tiempo. Meterlos a medias habría sido otro número sin verificar.

**Otra opción.** Geocodificar “San José” y mostrar el tiempo de hoy. Es gratis, pero no cambia el conteo y no se alcanzó a probar con calma.

**Límite.** Si Derling lo quiere antes del 4 de noviembre, se puede agregar después, marcado como contexto y no como medición.

## 10. Reglas de la hackathon

**Qué.** `HACKATHON.md` lista los commits. No hay ninguno antes del 26 oct 2026, mediodía del Este de EE. UU. SAM 3.1 y Muse Spark Open están en el flujo que se muestra (corrida guardada de DSCF0112). Sin llaves, todo sigue en mock. No se gastaron créditos en esta pasada.

**Por qué.** Las reglas piden trabajo del evento, uso real de modelos Meta, y que no sea un analizador de una sola imagen. El sistema es módulo + cámara simulada + alerta + revisión humana + export abierto.

**Otra opción.** Volver a llamar a los modelos en la grabación del pitch. Eso lo decide Derling, con sus créditos, no esta rama.

**Límite.** El historial de git de este clon empieza el 29 oct. No prueba qué había en otra carpeta antes de esa fecha.

## 11. Hoja de levantamiento, no la libreta verde

**Qué.** El fondo pasó de papel gris verdoso a hueso cálido (`#f4efe6`), la tinta a hierro (`#1f1a14`) y el visor a carbón (`#1c1814`) con marcas de latón (`#f2d48a`). Cada módulo tiene un color plano: fauna arcilla, tránsito laguna, multitud azafrán oscuro, granja viña, área protegida azul marino. No hay degradado. La disposición de las páginas no cambió.

**Por qué.** Derling pidió colores distintos de la libreta verde. El diseño del repo (`docs/design/DESIGN.md`) pide un visor de campo, no un panel genérico. Se mantuvo la hoja clara para que el texto siga en AA, y se dejó el marco oscuro solo alrededor del video, que es lo que se recuerda. Los acentos se midieron contra el hueso y contra la tarjeta: todos superan 4.5:1.

**Otra opción.** Volver al visor nocturno de todo el fondo, o un dashboard oscuro con violeta. El primero ya se había descartado porque oscurecía la nota. El segundo se ve igual a cualquier herramienta de analítica.

**Límite.** El contraste se revisó con las fórmulas WCAG y con axe en `/` y `/cameras`. No se rediseñó la tipografía ni el orden de la tarjeta.

## 12. El pie en el polígono, y un frame ruidoso no abre la alerta

**Qué.** La zona es un polígono. El punto que se prueba es el centro inferior de la caja (los pies). Para cambiar de adentro a afuera, o al revés, el lado nuevo tiene que sostenerse: en las cámaras, 3 segundos y 3 muestras. Un solo frame del otro lado no voltea un lado ya confirmado y no dispara solo. Cada alerta lleva una confianza de la regla (no del modelo), el segundo, y el punto del disparo dibujado sobre el video. En Goat lane el texto es “Animal left the safe zone”, con el rastro y un recorte. En Forest trail el texto es “Possible person inside the protected area — review needed”: cara tapada, sin nombre, botón Review, y `authorities: false`. La bandeja muestra severidad alta en la granja y “not sure” en el área protegida.

**Por qué.** Un frame suelto del detector no es una salida ni una persona que se quedó. Decir “posible” evita tratar el cuadro como un hecho de caza. La confianza baja cuando el tramo apenas cumple el mínimo, para no exagerar.

**Otra opción.** Alertar en el primer frame que cae afuera, o subir la severidad del bosque a emergencia. La primera se dispara con ruido. La segunda suena a identificación. No se hizo.

**Límite.** Goat lane y person-trail son clips ya contados, no una llamada nueva a SAM. La confianza es una regla sobre cuántas muestras sostuvieron el lado. No es un porcentaje devuelto por un modelo. No se avisa a autoridades.
