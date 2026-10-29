# Protocolo de etiquetado — Rastro `eval/`

Fecha: 26 oct 2026 (America/Chicago). Autor: QA.

## Qué se etiqueta

Para fauna (y tránsito cuando exista):

| Campo | Significado |
|---|---|
| `true_unique_count` | Individuos **distintos** a lo largo del clip completo |
| `class` | Clase esperada del paquete (`coyote`, `person`, …) |
| `status` | `VERIFIED` o `NOT VERIFIED` |
| `confidence` | `high` / `medium` / `low` |

**Nunca** se inventa un conteo. Si niebla, eyeshine dudoso o oclusión impiden afirmar el número, se pone `true_unique_count: null` y `status: "NOT VERIFIED"`.

## Cómo se etiqueta (pasos)

1. Extraer frames con ffmpeg (sin tocar `src/` / `packs/` / `worker/`):

```bash
# 1 fps overview
ffmpeg -y -i data/lila/coyote/CLIP.MP4 -vf fps=1 -q:v 2 eval/frames/CLIP/f%02d.jpg
# denser sample for ambiguous clips
ffmpeg -y -i data/lila/coyote/CLIP.MP4 -vf fps=3 -q:v 2 eval/frames/CLIP_dense/f%02d.jpg
```

2. Abrir cada frame con la herramienta de lectura de imágenes y anotar:
   - cuántos cuerpos/eyeshine claros hay **en ese frame**;
   - si es el mismo individuo que frames previos (posición / trayectoria).
3. El GT del clip = número de individuos distintos a lo largo de **todos** los frames revisados.
4. Guardar en `ground_truth.json` con `frames_checked`, `how_labeled` y `naive_notes`.
5. Los frames viven en `eval/frames/` (gitignored). No se versionan.

## Qué no cuenta como GT

- Etiquetas de categoría LILA (solo dicen “coyote”, no “2 coyotes”).
- Salidas de SAM / `summary.json` / `result.json` (eso es lo que se evalúa).
- Conteo ingenuo (apariciones / IDs de SAM sin stitch): se reporta aparte en métricas.

## Tolerancia al scorings

Ver `score.py`: por defecto `abs(pred - gt) <= tolerance` (default `0`) → PASS.
Clips `NOT VERIFIED` se omiten de MAE / exact-match y salen como `SKIPPED`.

## Set actual (fauna)

| Clip | GT unique | Status |
|---|---|---|
| DSCF0104 | 1 | VERIFIED |
| DSCF0112 | 2 | VERIFIED |
| DSCF0840 | — | NOT VERIFIED (niebla IR) |
| DSCF0004 | 1 | VERIFIED |

Tránsito y multitudes: sin clips locales — `GAPS.md`.

## Tránsito (Round 3)

### Líneas de conteo (definir antes de etiquetar)

Para cada clip se documentan líneas en coordenadas normalizadas (0–1) sobre el frame:

| Línea | Uso |
|---|---|
| `stop_N` / `stop_S` / `stop_E` / `stop_W` | Barra de alto del approach (entrada a la intersección) |
| `cross_EW` / `cross_NS` | Cruce peatonal / eje que el vehículo atraviesa al completar el movimiento |
| `turn_right_*` / `turn_left_*` | Arco aproximado del giro (opcional) |

Un vehículo **cuenta** cuando su caja/centro cruza una línea de entrada → sale por otra (straight / left / right). Vehículos solo en cola detrás del semáforo **no** cuentan hasta cruzar `stop_*`.

### Campos GT adicionales (pack `transito`)

| Campo | Significado |
|---|---|
| `true_unique_count` | Vehículos distintos que completan un cruce/giro en el clip (todas las clases) |
| `by_class` | Conteos por clase si VERIFIED: `car`, `motorcycle`, `truck`, `bus`, `van`, `bicycle`, … |
| `counting_lines` | Lista de líneas usadas (ids + puntos) |
| `status` | `VERIFIED` solo si el conteo es inequívoco tras inspeccionar frames |

**Regla:** densidades altas, oclusión por tren elevado, o cola profunda → `true_unique_count: null`, `status: "NOT VERIFIED"`. Nunca inventar.

### Set tránsito actual

| Clip | GT unique | Status |
|---|---|---|
| chiang-mai-jak-krok-siwilai | — | NOT VERIFIED (cola + muchos motos; frames 1 fps / 2 fps insuficientes para IDs únicos) |
| wicker-park-milwaukee-north-damen | — | NOT VERIFIED (vista aérea densa ~25–40 vehículos/frame; oclusión por CTA "L") |
| repod-* | — | NOT VERIFIED / no descargados |
