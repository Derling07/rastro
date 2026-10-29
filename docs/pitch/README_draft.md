# Rastro

**One engine** that tracks things in video without double-counting, merges consented field voice notes, and lets an agent write the report and raise alerts.

Swap the **JSON pack** → the engine counts something else. No code change.

> Meta Global AI Developer Hackathon 2026 — Indie track (solo).  
> Code written during the event window (from 26 Oct 2026).  
> Submission: **4 Nov 2026, 8:00 p.m. Costa Rica** ([event](https://dev.meta.ai/events/global-hackathon)).

<!-- [PENDIENTE: GIF/MP4 — annotated fauna + honest pack switch showing «sin corrida»] -->

**Demo hook (verified):** **90 detecciones → 2 coyotes** on LILA DSCF0112 — run `outputs/demo-real-coyote-0112` (schema 1.1, `is_mock=false`, `cost_usd=0.0102`). Counter field: **`detections_total`** (90 on 0112; **34** on `demo-real-coyote` / DSCF0104). Not a naive count (`naive_count` is 2 / 1). Values written by the engine (regenerated at `586a9a1`).  
Do **not** claim “11 → 3” — that contrast is not in `eval/`.

---

## What it is

1. **Tracks over time** — IDs across frames via SAM 3.1 video (masks live in `artifacts.annotated_video`, not in JSON).
2. **Sector rules as data** — packs define targets, geometry, dedup, alerts, privacy.
3. **Agent that acts** — Muse Spark Open (Baseten); tool steps in `agent_log`. **Counts come from a deterministic rules engine**, not the LLM.

| Pack | Counts | Real runs (26 Oct 2026) |
|---|---|---|
| `packs/fauna.json` | Coyotes / person on camera traps | Yes — default `outputs/demo-real-coyote-0112` |
| Transit (`transito`) | Turning movements | Public demo clip: [Wicker Park intersection](https://commons.wikimedia.org/wiki/File:Wicker_Park_intersection_changes.webm) by Steven Vance, CC BY 3.0. Real run in progress; counts **NOT VERIFIED** yet |
| Crowds (`multitudes`) | Density (blur faces, no facial recognition) | **No real run** — pack **pending**. Proposed thresholds **4** and **6** people/m² (to validate). Clip to be recorded by Derling in San José; MOT20 NC-SA if used later (link only) |

Official web default: **`demo-real-coyote-0112`** (`is_mock=false`). Mock runs are labeled **ejemplo**.

---

## Why it matters

Camera-trap programs accumulate more video than people can review. Frame-level detections re-count the same animal. Rastro reports **unique individuals** (and pack metrics), plus an optional **public** field note (`voice.is_public`).

Pilot framing: global problem; Costa Rica as natural field pilot. Current fauna demo clips are public LILA Seattle(ish) coyotes until CR-licensed trap video exists.

---

## Output contract (schema 1.1)

Stable path: `outputs/<run_id>/result.json` — see **`docs/OUTPUT_SCHEMA.md`** (v1.1).

Key fields consumers (web / Supabase / eval) rely on:

| Field | Role |
|---|---|
| `source_video_id` | Stable video stem (compare packs on same clip) |
| `naive_count`, `unique_count`, `by_class` | Flat counts for UI / DB |
| `detections_total` | Raw SAM detections across frames (schema 1.1 additive; written by engine since `586a9a1`) |
| `cost_usd` | Estimated USD for the run |
| `alerts[].t_s` | Alert timestamp in video seconds |
| `voice.turns[]` | `speaker`, `start_s`, `end_s`, `transcript` |
| `voice.is_public` | Default `false`; only Derling’s consented notes set `true` (`--voice-public`) |
| `agent_log[]` | Agent / pipeline tool steps |
| `artifacts.annotated_video` | MP4 with masks drawn |

Example shape: `docs/result.example.json`.

---

## How it works

```text
Video → worker (chunks + overlap) → SAM 3.1 (per concept, multi-prompt fallback)
      → stitch tracks → rules (unique_count, alerts, …)
Voice (optional) → Voice Transcribe → voice.* (public only if is_public)
Counts + events + notes → agent_log / report
Privacy blur per pack → aggregates (+ blurred clip if allowed)
```

---

## Meta models

| Model | Role | Today |
|---|---|---|
| **SAM 3.1** | Video tracking / masks | Meta Model API (`META_API_KEY`) — verified |
| **Muse Voice Transcribe 1.0** | Notes → text + turns | Meta Model API |
| **Muse Spark Open** | Agent / verify_frame / report | Baseten (`BASETEN_API_KEY`, `meta-models/muse-spark-open-1026`) |
| **Muse Wonder 1.0** | Optional long tasks | [PENDIENTE] |

Never print or commit API keys.

---

## Evaluation (QA)

Protocol + labels: **`eval/`** (`ground_truth.json`, `score.py`, `LABELING.md`, `ROUND2_NOTES.md`).

Round 2 score (`eval/last_score_outputs.json`, prefers real demo runs over legacy/mock):

| Clip | GT unique | Pred | Status | Source |
|---|---|---|---|---|
| DSCF0104 | 1 | 1 | **PASS** (prompt fallback) | `outputs/demo-real-coyote` (`detections_total=34`) |
| DSCF0112 | 2 | 2 | **PASS** | `outputs/demo-real-coyote-0112` (`detections_total=90`) |
| DSCF0004 | 1 | 1 | **PASS** | `outputs/real/DSCF0004` |
| DSCF0840 | — | — | SKIPPED (GT not verified) | — |

**Aggregate (3 scored):** **MAE 0**, **exact match 3/3**. **Small sample** (3 clips) — say so when pitching.  
Tests: **eval 12/12**, full repo **24/24** (`eval/ROUND2_NOTES.md`).  
Legacy `outputs/real/DSCF0104` (unique=0) is superseded by `demo-real-coyote`.

Transit / crowds: **0** labeled clips (`eval/GAPS.md`).

---

## Quickstart

### Worker

```bash
cd rastro
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

rastro probe-baseten          # needs BASETEN_API_KEY
rastro run --pack fauna --video data/lila5fps/DSCF0104.mp4 --mock-sam   # no Meta spend
# Real SAM spends credits — ask before running
pytest -q
```

### Web panel

```bash
cd web
npm install
npm run sync-runs    # copies official outputs → public/runs
npm run dev
```

Default run id: `demo-real-coyote-0112`. Mocks show as **ejemplo**. Pack chips for transit/crowds: **sin corrida**.

LILA downloads: **`DATA.md`** (MP4s gitignored).

---

## Privacy

- No facial recognition.
- Pack declares blur (`face`, `license plate`).
- Voice notes private by default; UI shows literal turns only when `voice.is_public === true` (Derling consented).
- Crowds (when shipped): density without individual tracking.

---

## Limits

- SAM video: ~15 000 frames/request; ≤ 16 objects/frame; one concept/request (Meta docs).
- Voice: WAV mono ≤ 10 min / 32 MB; speaker labels **per turn**.
- IR prompts unstable → fallbacks in pack; score must be re-run after changes.
- Upload limits: **MP4/MOV ≤ 50 MB ≤ 120 s**, target **720p**.
- Supabase free: 50 MB/file. Vercel Hobby: 300 s function cap — heavy work stays in worker (`queue_worker.py`).
- Transit/crowds demos: **no real `result.json` yet**. Crowd pack thresholds (4 / 6 people/m²) are **proposed**, not validated.

---

## Architecture (CORE)

Supabase project created by **ORION** (no deploy/push from pitch docs):

| Piece | Notes |
|---|---|
| Tables | `runs`, `events`, `alerts`, `reports`, `voice_notes`, `jobs` (+ `packs`) |
| Security | RLS on public tables |
| Upload | Signed URL → private Storage bucket **`videos`** |
| Worker | `supabase/queue_worker.py` drains `jobs` (stage pipeline) |
| Limits | MP4/MOV ≤ 50 MB ≤ 120 s · 720p |

Videos stay private; DB stores aggregates / metadata only (`supabase/README.md`).

---

## Licenses

Aligned with **`eval/LICENSES.md`** (QA, 26 Oct 2026):

| Asset | License / note |
|---|---|
| **Code** | Apache-2.0 proposed (`LICENSE`; Derling still confirms) |
| **Seattle(ish) Camera Traps (LILA)** | Page says Community Data License Agreement (**permissive variant**) — **CDLA version number not stated on the LILA page** (FLAG). Cite https://lila.science/datasets/seattleish-camera-traps/ + CDLA-Permissive-2.0 text as reference; do not redistribute MP4s in git (`DATA.md`) |
| **`probe_jfk.wav`** | HF dataset without clear license card — **do not use publicly** |
| **`probe_animal.png`** | Provenance undocumented in `DATA.md` — **do not use publicly** |
| **TTS `nota_campo_es`** | Synthetic OK for internal probes; not a Derling public voice note unless `is_public` |
| **Wicker Park (public demo)** | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Wicker_Park_intersection_changes.webm), Steven Vance, **CC BY 3.0**, converted to MP4 720p |
| **Chiang Mai (internal eval only)** | Amada44, CC BY-SA 4.0. Nothing derived from it is published |
| **RepOD traffic (dropped)** | Page: licenses **vary per file**; example MP4 CC BY 4.0 — **not verified for all files / not downloaded**. Plan: own San José clip (pending Derling) |
| **MOT20 (candidate)** | CC BY-NC-SA 3.0 — link, don’t redistribute |
| **Bellevue traffic** | No clear license — avoid in public demo |
| **Models** | Via Meta / Baseten APIs — weights not redistributed |

---

## Cost note

Usage-based Meta API (plan figures: SAM video ≈ \$0.20 / 1000 frames, min 50 frames/request; Voice ≈ \$0.18 / hour). Earlier real fauna session estimate ≈ **\$0.082** (`outputs/real/cost_summary.json`). Prefer cached runs. Credit balance: **[PENDIENTE: dashboard]**.

---

## Español (resumen)

**Rastro** sigue objetos en video sin contarlos dos veces, une notas de voz **públicas solo con consentimiento** (`voice.is_public`) y deja que un agente arme reporte y alertas. Cada sector es un **paquete JSON**.

Corrida demo por defecto: `outputs/demo-real-coyote-0112` (SAM real). Gancho: **90 detecciones → 2 coyotes** (`detections_total`; 90 ≠ conteo ingenuo; `naive_count=2`). `detections_total` lo escribe el motor desde `586a9a1`. Tránsito: clip público Wicker Park (Steven Vance, CC BY 3.0); conteo aún no verificado. Multitudes: pack pendiente (umbrales propuestos 4 y 6 pers/m²); clip a grabar por Derling en San José. Eval fauna Round 2: **MAE 0**, **3/3 exactos** (muestra chica: 3 clips); tests eval 12/12, repo 24/24. Arquitectura: Supabase (ORION) + `queue_worker.py`, bucket privado `videos`.

No publiques claves ni uses `probe_jfk.wav` / `probe_animal.png` en materiales públicos. Licencias: ver `eval/LICENSES.md`.

```bash
cd web && npm install && npm run sync-runs && npm run dev
```

---

Indie · Derling Torres Campos · Command Center (ORION / NOVA / FRONT / CORE / QA / ECHO).
