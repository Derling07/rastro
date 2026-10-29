# Revisión de licencias — datos en `data/` (QA, 26 oct 2026)

Solo links reales verificados hoy. Flags en **FLAG**.

## 1. Seattle(ish) Camera Traps (LILA BC) — clips fauna

| Campo | Valor |
|---|---|
| Dataset | Seattle(ish) Camera Traps |
| Página | https://lila.science/datasets/seattleish-camera-traps/ |
| Licencia declarada en la página | Community Data License Agreement (**permissive variant**) |
| Texto CDLA-Permissive 2.0 (referencia SPDX) | https://cdla.dev/permissive-2-0/ · https://spdx.org/licenses/CDLA-Permissive-2.0.html |
| Autor / contacto | Dan Morris (`agentmorris@gmail.com`) |
| Clips locales | `data/lila/coyote/*.MP4`, `data/lila/person/DSCF0004.MP4`, derivados `data/lila5fps/*` |
| Documentado en repo | `DATA.md` |

**FLAG — versión CDLA no numerada en la página LILA.**  
La ficha dice “Community Data License Agreement (permissive variant)” sin “1.0” ni “2.0”. LILA suele usar la variante permisiva; el texto canónico más citado hoy es CDLA-Permissive-2.0. Para el README público conviene citar la página LILA + el texto CDLA-Permissive-2.0, o confirmar con el autor.

**OK para hackathon open source** (permisiva; al compartir datos hay que incluir el texto del acuerdo). Videos no se redistribuyen en git (`.gitignore`); se documenta cómo bajarlos.

Persona en `DSCF0004`: etiqueta LILA `dan` = el dueño del dataset, incluido con su consentimiento (explicado en la ficha LILA).

## 2. `data/probe_jfk.wav`

| Campo | Valor |
|---|---|
| Origen documentado | Hugging Face dataset `Xenova/transformers.js-docs` |
| URL del archivo | https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/jfk.wav |
| Ficha del dataset | https://huggingface.co/datasets/Xenova/transformers.js-docs |

**FLAG — dataset HF sin dataset card / licencia explícita** (la ficha dice “No dataset card yet”).  
El contenido es un extracto del discurso inaugural de JFK (1961). Grabaciones del gobierno federal de EE. UU. de ese discurso se tratan habitualmente como dominio público; ver por ejemplo documentación de muestra que apunta al Public Domain Mark 1.0 vía Wikimedia/NARA: https://instascript.app/assets/demo/SOURCE.md (cita secundaria).  

**Recomendación:** no redistribuir en el repo público sin (a) confirmar PD del extracto o (b) enlazar solo la URL de HF. Hoy el `.wav` está en `.gitignore` (`*.wav`). Uso actual: probe de audio / Voice Transcribe, no fauna.

## 3. `data/probe/nota_campo_es.wav` (+ `.mp3`)

| Campo | Valor |
|---|---|
| Origen | TTS sintético (nota de campo en español) generado para el demo |
| Evidencia | `docs/pitch/x_hook.md` y `outputs/real/EVAL.md` lo describen como TTS ES |

**OK** para demo: audio sintético propio del evento. No hay obra de terceros.  
**FLAG menor:** documentar en `DATA.md` el motor TTS usado (p. ej. gTTS) y que no hay voz de persona real.

## 4. `data/probe_animal.png` y `data/probe/coyote_frame*.png` / `coyote_2s_5fps.mp4`

| Archivo | Hallazgo |
|---|---|
| `probe_animal.png` (320×240) | Usado por `worker/rastro/probe_baseten.py`. Apariencia de frame de cámara trampa. **FLAG — procedencia no documentada en DATA.md.** Si es frame de Seattle(ish), hereda CDLA-Permissive; si no, licencia desconocida. |
| `probe/coyote_frame.png`, `coyote_frame_sm.png`, `coyote_2s_5fps.mp4` | Derivados evidentes de clips LILA coyote → misma licencia CDLA que el set, con atribución. |

## 5. Resumen de flags

| Ítem | Severidad | Acción |
|---|---|---|
| CDLA sin número de versión en ficha LILA | Media | Citar página + CDLA-Permissive-2.0; opcional confirmar con autor |
| `probe_jfk.wav` / dataset HF sin licencia | Media | No publicar el wav; enlazar URL o confirmar PD |
| `probe_animal.png` sin fuente en DATA.md | Media | Añadir línea en DATA.md (origen + licencia) |
| `nota_campo_es` TTS sin detalle de motor | Baja | Una línea en DATA.md |

## 6. Sets aún no bajados (ver `GAPS.md`)

Solo referencia; **no se descargaron** archivos grandes en esta tarea:

- MOT20 — CC BY-NC-SA 3.0: https://motchallenge.net/data/MOT20  
- Politechnika Bydgoska (RepOD) — CC BY 4.0 (video ejemplo): https://repod.icm.edu.pl/dataset.xhtml?persistentId=doi:10.18150/BAI5PS  
- Bellevue Traffic Video Dataset — **FLAG sin licencia clara**: https://github.com/City-of-Bellevue/TrafficVideoDataset

## 7. RepOD — Politechnika Bydgoska traffic (Round 2)

| Campo | Valor |
|---|---|
| Dataset | Baza danych… skrzyżowaniach z sygnalizacją świetlną |
| Página | https://repod.icm.edu.pl/dataset.xhtml?persistentId=doi:10.18150/BAI5PS |
| DOI | https://doi.org/10.18150/BAI5PS |
| Licencia (página) | **Different licenses for individual files** |
| Video ejemplo | `04_09_Example of Rondo Fordońskie (HEVC 3840x2160).MP4` — **License: CC BY - Creative Commons Attribution 4.0** (3.5 GB) |
| Acceso video completo | Cita en ficha: *"Video available only upon request"* / *"Materiał wideo dostępny wyłącznie na prośbę osoby zainteresowanej."* |

**Confirmado 2026-10-26 (America/Chicago):** CC BY 4.0 en el MP4 de ejemplo permite redistribución con atribución, pero el archivo supera el tope QA de 200 MB → **no se descargó** a `data/transit/`. Segundo clip (Kamienna–Wyszyńskiego) solo tiene `.sql` públicos; video bajo petición → listado en `ground_truth.json` con status NOT VERIFIED.


## 8. Wikimedia Commons — traffic intersections (Round 3)

Descargados a `data/transit/` (binarios locales; ver `eval/DATA_TRANSIT.md` + `data/transit/ATTRIBUTION.md`).

### 8.1 Chiang Mai — Jak-Krok Siwilai

| Campo | Valor |
|---|---|
| Archivo Commons | [File:A intersection with traffic in Chiang Mai, Thailand.ogv](https://commons.wikimedia.org/wiki/File:A_intersection_with_traffic_in_Chiang_Mai,_Thailand.ogv) |
| Autor | Amada44 |
| Licencia (ficha) | **CC BY-SA 4.0** — https://creativecommons.org/licenses/by-sa/4.0/ |
| Redistribución / comercial | Permitida con atribución + ShareAlike |
| Local | `data/transit/chiang_mai_intersection.{ogv,mp4}` (~33 MB original → ~3.9 MB H.264 720p) |
| Duración | ~14 s |

**Atribución:** "A intersection with traffic in Chiang Mai, Thailand" by Amada44, Wikimedia Commons, CC BY-SA 4.0. Converted to H.264 720p (audio removed) for Rastro QA.

### 8.2 Wicker Park — Milwaukee / North / Damen (Chicago)

| Campo | Valor |
|---|---|
| Archivo Commons | [File:Wicker Park intersection changes.webm](https://commons.wikimedia.org/wiki/File:Wicker_Park_intersection_changes.webm) |
| Autor | Steven Vance (importado desde Vimeo; reviewer Roy17 2019-06-13 confirmó CC BY en origen) |
| Licencia (ficha) | **CC BY 3.0** — https://creativecommons.org/licenses/by/3.0/ |
| Redistribución / comercial | Permitida con atribución |
| Local | `data/transit/wicker_park_intersection.{webm,mp4}` (~22 MB original → ~8.2 MB H.264 720p) |
| Duración | ~30 s |

**Atribución:** "Wicker Park intersection changes" by Steven Vance, Wikimedia Commons (from Vimeo), CC BY 3.0. Converted to H.264 720p (audio removed) for Rastro QA.

**Confirmado 2026-10-26 (America/Costa_Rica):** licencias leídas en la ficha de cada archivo Commons (no en la categoría). Ambos ≪ 500 MB (tope ORION Round 3) y ≪ 50 MB post-convert.
