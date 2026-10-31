# Rastro — lo que depende SOLO de vos (Derling)

Entrega: **martes 4 nov 2026, 8:00 p.m. hora de Costa Rica**.

La libreta de campo, la nota de campo y el export ya están en una rama (no en un deploy). Nadie gasta créditos ni publica la app sin tu ok.

## Lo que tenés que hacer vos

1. **Grabar el clip de multitudes en San José** (feria, parada o salida de un evento, desde arriba y de lejos). Unos 30 a 60 s, sin caras de cerca.
2. **Calcular más o menos cuántos m² se ven en el clip.** Sin ese número la densidad por m² no se puede verificar. Hoy la cámara de ejemplo no inventa gente/m².
3. **(Opcional) Grabar una intersección de San José** para tránsito. Hoy el tránsito dice que no está verificado.
4. **Decidir si hay demo pública** (ver decisiones). Esta rama no hace deploy.
5. **Grabar el video del pitch y la demo** (guion en `docs/pitch/demo_script.md`). El flujo más claro para abrir es la trampa: 90 detecciones → 2 coyotes, nota grabada de Muse Spark, y vos confirmás en pantalla.
6. **Subir la entrega** en la plataforma de la hackathon. Es con tu cuenta.
7. **(Opcional) Reclamar los $150 de créditos de Meta** en Discord. No se gastan sin tu permiso. Esta pasada no llamó a SAM ni a Baseten.

## Decisiones que tenés que tomar

1. **¿Demo pública o solo video?**
   - A) Solo video + repo. **Sigue siendo la opción mientras no digas nada.**
   - B) Deploy gratis en Vercel con datos de ejemplo, sin llaves.
   - C) Deploy con llaves reales. Gasta créditos. No recomendado.
2. **¿Repo público o privado para la entrega?** Hoy el remoto es privado. Si piden un link público: espejo público, o seguir privado y dar acceso.
3. **¿Qué módulo abre el pitch?** Recomendación: cámara trampa (DSCF0112). Es el único conteo medido con SAM en la tarjeta héroe. Granja y multitudes se pueden mostrar después como el mismo sistema con otra regla.
4. **Estilo.** Ya se aplicó la libreta de campo (papel gris verdoso, texto verde bosque, video en marco oscuro, un color por módulo, tres pasos arriba). Si no te cierra, decilo antes del martes.
5. **Waze.** El servidor arma un archivo en el formato público de incidentes (compatible con Waze for Cities) y un link que abre el mapa. **No somos socios y no se lo mandamos a Waze.** Para que ellos lo ingieran tenés que entrar vos a Waze for Cities. No subas el archivo de ejemplo: la calle y el punto son de muestra, en San José, y están marcados como no verificados.
6. **Webhooks.** Se pueden anotar, pero no se envían. Si querés que salgan de verdad, pasá una URL https y decilo.
7. **Cámara en vivo.** Se acepta una dirección RTSP, HLS o MJPEG, y la demo sigue en cámara simulada. Si tenés una cámara pública con licencia clara, pasá el link. Si no, el pitch usa los clips que ya están.
8. **Clima y mapa.** No se agregaron (Open-Meteo / Nominatim). Si los querés antes del martes, son contexto, no un conteo nuevo.

## Qué no está verificado

- El archivo para Waze no se probó dentro de Waze.
- Los webhooks no se probaron contra un servidor de afuera.
- Ninguna URL RTSP/HLS/MJPEG se abrió de verdad.
- Tránsito (Wicker Park) sigue sin conteo verificado.
- La nota de DSCF0112 es la respuesta guardada de Muse Spark, no una llamada nueva.
- Granja y área protegida: el detector local coincidió con una etiqueta a mano (PASS en `eval/alert_set/`). No es una corrida nueva de SAM. En el pitch decilo así.
