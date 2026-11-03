# Guion de demo — 3 minutos (Rastro)

**Audiencia:** jueces Meta Global AI Developer Hackathon 2026 (Indie).  
**Idioma:** inglés hablado + subtítulos ES (o bilingüe).  
**Regla:** solo lo construido del 26 oct–4 nov 2026. Nada de maquetas que pasen por funciones reales.

| Criterio | Peso |
|---|---|
| Impacto | 30 % |
| Uso de Meta | 25 % |
| Demo | 25 % |
| Profundidad técnica | 20 % |

Contrato de datos: **`docs/OUTPUT_SCHEMA.md` v1.1** → `outputs/<run_id>/result.json`.  
Corrida por defecto del panel: **`outputs/demo-real-coyote-0112`** (`is_mock=false`, `source_video_id=DSCF0112`, schema 1.1).  
Mocks (`demo-mock-*`): decir en voz alta **«ejemplo»** (UI también marca `ejemplo`).

**Prohibido decir «11 → 3» o «2 unique coyotes».** Número que sí se puede decir: **90 raw detections of a coyote (individuals NOT VERIFIED)** (`detections_total=90` en `demo-real-coyote-0112`; 90 ≠ `naive_count`). `detections_total` lo escribe el motor desde `586a9a1`.

---

## Pre-flight

```bash
cd web && npm install && npm run sync-runs && npm run dev
```

- [ ] Panel abre en `demo-real-coyote-0112` (SAM real, anotado en `artifacts.annotated_video`).
- [ ] Contador lee `detections_total` / `naive_count` / `unique_count` / `by_class` / `cost_usd`.
- [ ] Pack chips: fauna con corrida; tránsito y multitudes muestran **· sin corrida**.
- [ ] Nota de voz: **solo** si `voice.is_public === true` (nota de Derling con consentimiento + `--voice-public`). Si no hay, no inventar transcript; usar `report` o saltar el bloque.
- [ ] `agent_log` visible; alertas con `t_s`.
- [ ] Sin claves en pantalla.

---

## Guion con tiempos

### 0:00 – 0:20 · Problema (Impacto 30 %)

| | |
|---|---|
| **Pantalla** | Vacío / carpeta de cámara trampa. |
| **Decís** | «Millions of hours of camera-trap video never get reviewed. Frame counts double-count the same animal.» |
| **Fuente** | Problema del plan; datos demo LILA CDLA — `DATA.md` / `eval/LICENSES.md`. |

---

### 0:20 – 0:45 · Subir / abrir corrida + pack fauna (Demo + Meta)

| | |
|---|---|
| **Pantalla** | Abrir run oficial `demo-real-coyote-0112` (o subir MP4). Chip **Fauna** → `packs/fauna.json`. |
| **Decís** | «One engine. The sector is a JSON pack. Default demo run is real SAM — not a mock.» |
| **Campos** | `run_id`, `source_video_id`, `pack.id`, `is_mock=false`. |

---

### 0:45 – 1:25 · Video anotado + contador (Meta 25 % + profundidad 20 %)

| | |
|---|---|
| **Pantalla** | Player de `artifacts.annotated_video` (máscaras solo ahí). Contador desde `detections_total` / `naive_count` / `unique_count`. Hover opcional con `frames[].objects[].bbox`. |
| **Decís** | «SAM 3.1 tracks across frames. On DSCF0112: **90 raw detections of a coyote (individuals NOT VERIFIED)** — real API (`demo-real-coyote-0112`).» |
| **Números** | `detections_total=90` (0112) / `34` (`demo-real-coyote` / DSCF0104); `unique_count=2`, `naive_count=2`, `cost_usd=0.0102`, `is_mock=false`. 90/34 are **not** naive_count. Written by engine since `586a9a1`. Score PASS (`eval/last_score_outputs.json`). |
| **Corrida en panel** | Default = `demo-real-coyote-0112` (DSCF0112). |
| **Eval honesta** | Round 2: **MAE 0**, **3/3 exact** on 3 clips (**small sample**): DSCF0104 1=1 (`demo-real-coyote`), DSCF0112 2=2 (`demo-real-coyote-0112`), DSCF0004 1=1. DSCF0840 SKIPPED. Tests: eval **12/12**, repo **24/24** (`eval/ROUND2_NOTES.md`). |

---

### 1:25 – 1:50 · Momento wow: cambio de pack **honesto** (Demo 25 %)

| | |
|---|---|
| **Pantalla** | Chip **Tránsito** o **Multitudes** → UI muestra **· sin corrida** / «Sin reporte — pack sin corrida». Color de acento cambia; **no** se carga un mock de tránsito/multitudes como si fuera real. |
| **Decís** | «Same engine. Different file. Transit and crowds have **no real runs yet** — the panel says so on purpose.» |
| **Pendientes** | Tránsito: RepOD licenses **vary per file**, not verified — plan is own San José clip (pending Derling). Multitudes: clip to be recorded by Derling in San José; one alert at 6 people/m² (high / crush risk). MOT20 = NC-SA if used later (link only). |
| **Si alguien pregunta por mocks** | `demo-mock-*` y `web/mock/*` son **ejemplo** (`is_mock=true`), no evidencia de pack tránsito/multitudes. |

---

### 1:50 – 2:15 · Nota de voz (Meta 25 %) — solo pública

| | |
|---|---|
| **Condición** | Mostrar turnos **únicamente** si `voice.is_public === true` (nota de Derling con consentimiento; CLI `--voice-public`). |
| **Pantalla** | `voice.turns[]` con `speaker`, `start_s`, `end_s`, `transcript`. |
| **Si no hay nota pública** (estado actual de `demo-real-coyote-0112`: `voice=null`) | Decir: «Voice notes are private by default; we only show Derling’s consented public note.» Pasar al agente/reporte. **No** usar `probe_jfk.wav` ni presentar el mock TTS como voz pública. |
| **Criterio** | Muse Voice Transcribe + privacidad (`is_public` default false). |

---

### 2:15 – 2:40 · Agente, alertas, reporte (Meta + profundidad)

| | |
|---|---|
| **Pantalla** | `agent_log[]` (herramientas); `alerts[]` con **`t_s`**; `report`; `cost_usd`. |
| **Decís** | «The rules engine owns the counts. The agent logs tools, can verify frames, raises alerts, writes the report.» |
| **Ejemplo alerta** | En `demo-real-coyote-0112`: `especie_objetivo` con `t_s: 1.2` («Coyote recorded (individuals NOT VERIFIED)»). |
| **Spark** | Baseten Muse Spark Open probado (`docs/baseten_probe.json`); bitácora en schema. |

---

### 2:40 – 3:00 · Cierre

| | |
|---|---|
| **Pantalla** | Tabla eval + schema 1.1 + «add your pack». |
| **Decís** | «MAE 0 on three verified clips — small sample, honest. Open source. One JSON from your sector. That’s Rastro.» |

---

## Mapa criterio ↔ momento

| Criterio | Momentos |
|---|---|
| **Impacto 30 %** | Problema campo; packs por sector; honestidad «sin corrida» |
| **Meta 25 %** | SAM 3.1 + annotated video; Voice (si pública); Spark / `agent_log` |
| **Demo 25 %** | Flujo panel; 90 raw detections of a coyote (individuals NOT VERIFIED); pack switch honesto |
| **Profundidad 20 %** | Schema v1.1; dedup/fallback; eval MAE; reglas ≠ LLM |

---

## Variante CLI (si web falla)

```bash
# ya cacheado — no hace falta gastar créditos
ls outputs/demo-real-coyote-0112/result.json outputs/demo-real-coyote-0112/annotated.mp4
```

Mostrar `result.json` v1.1 + video anotado. Decir «CLI + artifacts; UI is the same contract.»
