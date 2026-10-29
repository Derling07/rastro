# Datos de prueba — Rastro

Todos los clips de este repo se usan **solo para desarrollo y demo** del Meta Global AI Developer Hackathon.
No se redistribuyen los videos en Git (están en `.gitignore`); se documenta cómo bajarlos.

## Seattle(ish) Camera Traps (LILA BC)

- **Fuente:** https://lila.science/datasets/seattleish-camera-traps/
- **Licencia:** Community Data License Agreement — Permissive (CDLA-Permissive)
- **Autor / contacto:** Dan Morris (agentmorris@gmail.com)
- **Base Azure:** `https://lilawildlife.blob.core.windows.net/lila-wildlife/seattleish-camera-traps/`
- **Metadata:** https://storage.googleapis.com/public-datasets-lila/seattleish-camera-traps/seattleish_camera_traps.json.zip

### Clips descargados (26 oct 2026)

| Archivo local | Ruta original en LILA | Contenido (etiqueta) | Duración | Codec | Tamaño |
|---|---|---|---|---|---|
| `data/lila/coyote/DSCF0104.MP4` | `converted_camera_trap_videos/2021.03.21/location-03/coyote/DSCF0104.MP4` | coyote | 10.2 s / 306 frames | H.264 1920×1080 @ 30 fps | 1.9 MB |
| `data/lila/coyote/DSCF0112.MP4` | `converted_camera_trap_videos/2021.03.21/location-03/coyote/DSCF0112.MP4` | coyote | 10.2 s / 306 frames | H.264 1920×1080 @ 30 fps | 2.4 MB |
| `data/lila/coyote/DSCF0840.MP4` | `converted_camera_trap_videos/2021.06.06/location-03/coyote/DSCF0840.MP4` | coyote | 10.2 s / 306 frames | H.264 1920×1080 @ 30 fps | 1.4 MB |
| `data/lila/person/DSCF0004.MP4` | `converted_camera_trap_videos/2021.03.21/location-03/dan/DSCF0004.MP4` | dan (persona, con consentimiento del autor) | 10.2 s / 306 frames | H.264 1920×1080 @ 30 fps | 7.2 MB |

### Cómo volver a bajarlos

```bash
BASE=https://lilawildlife.blob.core.windows.net/lila-wildlife/seattleish-camera-traps
curl -L -o data/lila/coyote/DSCF0104.MP4 \
  "$BASE/converted_camera_trap_videos/2021.03.21/location-03/coyote/DSCF0104.MP4"
```

### Nota sobre pizotes

No hay videos públicos de pizotes (coatis) con licencia clara en LILA.
El paquete `fauna.json` v0.3 usa prompt `coyote` (y `person`); en IR a veces hace falta `animal` como fallback.
Cuando haya video propio de Costa Rica (CC BY), se cambia el prompt a `coati` / `pizote`.


### Derivados a 5 fps (gasto SAM)

Para las corridas reales se generó `data/lila5fps/*.mp4` (~51 frames / clip) con ffmpeg,
porque SAM 3.1 factura mínimo 50 frames/petición a USD 0,20 / 1000 frames.
No se versionan en git (mismo criterio que los MP4 originales).

### Verdad visual vs SAM (corrida real 26 oct 2026)

| Clip | GT visual | Mejor prompt | Conteo Rastro |
|------|-----------|--------------|---------------|
| DSCF0104 | 1 coyote | `coyote` ( `animal` → 0) | 1 |
| DSCF0112 | 2 coyotes | `animal` | 2 |
| DSCF0840 | 1–2 (niebla) | `animal` | 1 |
| DSCF0004 | 1 persona | `person` | 1 |

Detalle y costos: `outputs/real/EVAL.md` (ignorado por git).

## Audio de prueba (Baseten)

- `data/probe_jfk.wav` — clip corto público de Hugging Face (`Xenova/transformers.js-docs`), solo para probar el endpoint de audio. No es dato de fauna.
