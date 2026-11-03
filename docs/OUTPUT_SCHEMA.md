# Schema de salida — `result.json`

**Versión del schema:** `1.1`  
**Ruta estable:** `outputs/<run_id>/result.json`  
**Consumidores:** web (`web/`), CORE (`supabase/` + API), QA (`eval/`).

El motor (`worker/rastro/`, `packs/`) escribe este archivo al final de cada
`rastro run`. **Fuente de verdad para FRONT y CORE = `result.json`.**

Las **máscaras** de SAM **no** van en el JSON: solo en el video anotado
(`artifacts.annotated_video`). En el JSON van **cajas (bbox) + IDs por cuadro**.

## `run_id` y `source_video_id`

- **`run_id`**: una corrida por par *(paquete, video)*.  
  Formato: `{pack_id}-{video_stem}-{YYYYMMDDTHHMMSSZ}`  
  Ejemplo: `fauna-camtrap-DSCF0112-20261027T041500Z`
- **`source_video_id`**: id estable del video de origen (stem del archivo, p. ej.
  `DSCF0112`). Sirve para comparar **varios paquetes** sobre el mismo video.

## Campos requeridos (v1.1)

| Campo | Tipo | Notas |
|-------|------|--------|
| `schema_version` | string | `"1.1"` |
| `run_id` | string | Único por pack+video+corrida |
| `source_video_id` | string | Stem del video; comparable entre packs |
| `created_at` | string | ISO-8601 UTC |
| `pack` | object | `{ "id", "version", "path" }` |
| `video` | object | `{ "path", "fps", "native_fps" }` |
| `station` | string | Estación |
| `local_hour` | int \| null | 0–23 |
| `naive_count` | int | **CORE / supabase** |
| `detections_total` | int | Detecciones crudas de SAM sumadas en todos los frames (suma de `sam[].n_detections`); opcional en lectores |
| `unique_count` | int | **CORE / supabase** |
| `by_class` | object | **CORE / supabase** mapa clase→N |
| `cost_usd` | number | **CORE / supabase** total estimado USD |
| `counts` | object | `{ naive, unique, by_class }` (espejo nested) |
| `tracks` | array | Pistas únicas (sin máscaras) |
| `frames` | array | Por cuadro: bboxes + track_id (ver abajo) |
| `events` | array | Individuos, cruces, … |
| `alerts` | array | Cada alerta **incluye `t_s`** |
| `voice` | object \| null | Turnos con `speaker`, `start_s`, `end_s` |
| `agent_log` | array | Pasos/herramientas del agente Spark |
| `report` | object | Reporte redactado |
| `artifacts` | object | Rutas relativas; `annotated_video` tiene las máscaras dibujadas |
| `cost` | object | Desglose `est_usd_sam`, `est_usd_voice`, `est_usd_total` |
| `sam` | array | Meta por llamada SAM |
| `is_mock` | bool | `true` si SAM/voice fueron simulados |


Campos **aditivos opcionales** 1.1: multitudes (`density`, `peak_density`, `persons_per_zone`, `sampling_mode`); tránsito / tope SAM (`partial`, `max_objects_hit`, `events[].movement`, `report.matriz_giros`). Ver secciones abajo.

### `alerts[]` — obligatorio `t_s`

```json
{
  "id": "especie_objetivo",
  "severity": "info",
  "message": "Coyote recorded (individuals NOT VERIFIED)",
  "t_s": 0.2
}
```

`t_s` = segundo del video donde aplica la alerta (primer frame relevante / inicio de pista).

### `voice` — turnos en segundos

```json
{
  "transcript": "…",
  "audio_duration_ms": 11440,
  "station": "norte",
  "local_hour": 21,
  "est_usd": 0.00057,
  "is_mock": false,
  "is_public": false,
  "turns": [
    {
      "turn_id": 0,
      "speaker": "A",
      "start_s": 0.22,
      "end_s": 10.94,
      "transcript": "…"
    }
  ]
}
```

`is_public` (bool, opcional, **default `false`**): si la nota de campo es legible en lecturas públicas. Flag CLI: `--voice-public`.

### `agent_log[]`

Bitácora de lo que hizo el agente (Spark u orquestación local):

```json
[
  { "step": 1, "tool": "sam.segment_video", "detail": "concept=coyote n=100" },
  { "step": 2, "tool": "tracking.count_unique", "detail": "unique=2" },
  { "step": 3, "tool": "spark.chat_json", "detail": "source=baseten-spark" }
]
```


### `events[]` — campo aditivo `movement` (tránsito)

Campo **aditivo** (schema 1.1): no es obligatorio en fauna/multitudes. FRONT
(`web/src/lib/transito.ts`) arma la matriz de giros N/S/E/O desde
`report.matriz_giros` **o**, si falta, desde eventos con `kind: "turn"` y
`movement`.

Formato de `movement` (entrada→salida, brújula española):

```text
^(N|S|E|O)->(N|S|E|O)$
```

Ejemplo (compatible con `web/mock/transito-demo/events.json`):

```json
{
  "kind": "turn",
  "t_s": 6.0,
  "track_id": "auto-3",
  "class": "auto",
  "movement": "N->E",
  "label": "izquierda",
  "entry": "N",
  "exit": "E"
}
```

| Campo | Tipo | Notas |
|-------|------|--------|
| `kind` | string | `"turn"` para giros; `"line_cross"` / `"individual"` siguen existiendo |
| `movement` | string | Origen→destino (`N->S`). Aditivo; solo packs de tránsito |
| `label` | string | Opcional: `recto` / `izquierda` / `derecha` (pack `turning_rules`) |
| `entry` / `exit` | string | Opcional: cardinales de acceso (`N`/`S`/`E`/`O`) |

`report.matriz_giros` (también aditivo) agrega conteos:

```json
{ "N->S": 2, "N->E": 1, "O->E": 3 }
```

El motor calcula ambos de forma determinista a partir de cruces de
`geometry.lines` / `geometry.approaches` con ids `acceso_N`…`acceso_O` (o
`N`/`S`/`E`/`O`). **No** los inventa el LLM.

### `frames[]` — cajas e IDs (sin máscaras)

```json
{
  "frame": 12,
  "t_s": 2.4,
  "objects": [
    {
      "track_id": "coyote-1",
      "class": "coyote",
      "bbox": [100.0, 200.0, 340.0, 480.0]
    }
  ]
}
```

`bbox` = `[x1, y1, x2, y2]` en píxeles del frame de trabajo.  
**Las máscaras solo existen en** `artifacts.annotated_video` (MP4).

### `artifacts`

```json
{
  "annotated_video": "annotated.mp4",
  "blurred_video": "blurred.mp4",
  "voice_json": "voice.json",
  "cost_json": "cost.json",
  "tracks_json": "tracks.json"
}
```


### `density[]` — serie de densidad (aditivo 1.1, multitudes)

Opcional. Presente cuando el paquete declara métricas de densidad o
`sampling.mode = "image_sample"`. Cada fila es un muestreo por zona:

```json
{
  "t_s": 3.0,
  "zone": "zona_1",
  "persons": 42,
  "density_per_m2": 1.68
}
```

- `persons`: personas cuyo **centro inferior de caja** cae en el polígono de la zona.
- `density_per_m2`: `persons / area_m2` de la zona; `null` si la zona no tiene `area_m2`.
- Relacionados (también opcionales):
  - `peak_density`: `{ "zone", "t_s", "persons", "density_per_m2" }` — pico de la serie.
  - `persons_per_zone`: mapa zona → máximo de personas en cualquier `t_s`.
  - `sampling_mode`: `"video_track"` | `"image_sample"`.

Las alertas de densidad usan media móvil (`smoothing_window_s`, default 5) y
condición sostenida (`SUSTAINED sustain_s`, default 10). Cada alerta sigue
llevando `t_s` (inicio del tramo sostenido) y puede incluir `zone`.


### `partial` / `max_objects_hit` — tope SAM 16 (aditivo 1.1, tránsito)

Opcionales. Presentes cuando el motor corre **recortes por acceso** N/S/E/O
(packs con `turning_movements` / id `transito*` / `access_crops: true`) o cuando
alguna petición video saturó el límite de 16 objetos/frame de SAM 3.1.

```json
{
  "partial": true,
  "max_objects_hit": [
    {
      "t_s": 12.4,
      "frame": 62,
      "n_objects": 16,
      "access": "N",
      "concept": "car"
    }
  ]
}
```

- `partial` (bool): `true` si el resultado es incompleto — porque una petición
  llegó a 16 objetos/frame **o** se omitieron peticiones al alcanzar
  `budget_usd` (default **0.50** USD por corrida, override en el pack).
- `max_objects_hit` (array): instantes (`t_s` y `frame`) donde esa petición
  alcanzó el tope. Puede incluir `access` y `concept` cuando aplica.
- En tránsito el motor **no** manda el frame entero a SAM: recorta una zona
  por acceso (N/S/E/O), pide por recorte y remapea las cajas al frame completo.
  Así cada petición ve menos objetos y cabe bajo el tope de 16.

## Compatibilidad CORE (`supabase/`)

Campos planos listos para upsert:

- `run_id`, `source_video_id`, `pack.id`, `naive_count`, `unique_count`,
  `by_class`, `cost_usd`, `is_mock`, `created_at`, `station`, `local_hour`

## Compatibilidad

- v1.0 → v1.1 es **aditivo** (más campos requeridos para CORE).
- `events[].movement` / `report.matriz_giros` / `partial` / `max_objects_hit` son **aditivos** (tránsito); lectores antiguos los ignoran.
- No se eliminan `counts` ni `cost`; se agregan aliases planos.
- Bump a `2.0` solo si se renombra o quita un campo requerido de 1.1.

## Ejemplo

Ver `docs/result.example.json`.
