# Paquete multitudes (propuesta NOVA, 26 oct 2026)

Archivo: `pack_multitudes.propuesta.json`. Está en `docs/design/` porque `packs/` es de ORION; ORION decide si lo copia.

## Qué cuenta
Personas por zona y **densidad en personas/m²** en frames muestreados a 1 fps. No sigue individuos ni hay IDs: el plan ya lo recomienda (modo imagen de SAM devuelve todas las instancias y evita seguir a personas).

## Umbrales (propuesta, Derling decide)
- **≥ 4 personas/m² sostenido 10 s:** alerta media.
- **≥ 6 personas/m² sostenido 10 s:** alerta alta.
- Los números vienen del plan de ORION como propuesta. **No verifiqué una norma que los respalde**; antes de citarlos en el pitch, ECHO o QA deben buscar la fuente.
- "Sostenido 10 s" con media móvil de 5 s evita alertas por un solo frame ruidoso.

## Cómo se mide el área (lo más simple que funciona)
Cada zona trae `area_m2`, que la persona escribe al dibujar la zona (por ejemplo, contando baldosas o midiendo con pasos). Sin `area_m2`, el panel muestra solo **personas por zona** y no calcula densidad ni alertas. La homografía queda para después.
Cada persona se ubica por el **centro inferior de su caja** (los pies), que es lo que está sobre el piso de la zona.

## Lo que el motor necesita y hoy no tiene (para ORION)
1. Modo `image_sample` (SAM imagen cada N s) además de `video_track`.
2. Campo `area_m2` por zona y métricas `persons_per_zone`, `density_per_m2`, `peak_density`.
3. Condición `SUSTAINED` en alertas.
4. Difuminar la caja completa de cada persona antes de guardar.
5. En `result.json`: una serie `density[] = {t_s, zone, persons, density_per_m2}` para el mapa de calor y la gráfica.

## Panel (FRONT)
- Contador grande: **pico de personas/m²** con su zona y `t_s`; debajo, personas en la zona ahora.
- Video difuminado con la zona dibujada y coloreada por densidad (verde < 4, ámbar 4–6, rojo ≥ 6), siempre con el número escrito.
- Gráfica de densidad en el tiempo con líneas en 4 y 6.
- Acento del paquete: cian `#5CC8E0`.

## Guía para el clip de Derling en San José
- Desde arriba y de lejos (segundo piso, puente peatonal), celular fijo, horizontal, 1080p, MP4 H.264 ("Más compatible" en iPhone), 1 a 2 min.
- Elegir un piso con medida fácil (baldosas, una plaza con líneas) y anotar el área aproximada de la zona.
- Sin acercarse a caras; igual se difumina todo.
- Una nota de voz corta al final, con hora y lugar.
