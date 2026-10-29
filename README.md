# Rastro

Rastro counts each individual once — and uses that to alert what matters. SAM 3.1 tracks objects through the video, the rules engine stitches a re-entry into the same individual, and Muse Spark writes the report without changing those numbers. The proof is the stored DSCF0112 run: **90 raw detections → 2 unique coyotes**.

A sector is defined by a JSON pack.

Meta Global AI Developer Hackathon 2026 · Indie track. Submission deadline **4 Nov 2026, 8:00 p.m. Costa Rica**.

The code in this repository was written during the event (from 26 Oct 2026). License: MIT. Copyright 2026 Derling Torres Campos. See `LICENSE`.

## Run it

Docker is the path that serves the app and the worker together. With no keys, every run stays in **mock** mode (synthetic tracker, local report). Sample clips never call a paid API. An uploaded video uses SAM when `META_API_KEY` is set, and Muse Spark when `BASETEN_API_KEY` is set.

```bash
docker compose up --build
```

Open [http://127.0.0.1:43123](http://127.0.0.1:43123). Inside Compose the app calls the worker at `http://api:8787`. On the host, that port is published only on `127.0.0.1:8787`.

```bash
cp .env.example .env   # names only; leave values blank for mock
```

In the app: pick a sector, run a sample (or drop an MP4/MOV plus an optional voice note), watch the stages, then read the count. **Camera trap** is the sample where a coyote leaves and returns under a new tracker id. The result says how many sightings were stitched into how many individuals, and the timeline shows the merged bars. Mock runs are labeled **Mock**.

### Without Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=worker RASTRO_STAGE_SLEEP=0 python -m rastro.api

# another shell
cd web && npm install && RASTRO_API_URL=http://127.0.0.1:8787 npm run dev
```

Tests (no network, no keys):

```bash
pytest -q tests eval/tests
```

## What the count means

Naive counting treats every tracker id as a new individual, including an animal that left the frame and came back. Rastro groups detections into sightings, then **stitches a re-entry** when the gap, the edge, and the overlap say it is the same body (`worker/rastro/tracking.py`). The number on screen is that result. It is not typed in by hand.

On the mock camera-trap sample the engine’s own contract (covered by `tests/test_tracking.py` and `tests/test_api.py`) is: the coyote script produces **more sightings than individuals**, and at least one track holds two tracker ids. A person in the same pack is a separate individual. The UI prints those counts, for example “5 sightings, 4 unique individuals”, only after the job finishes.

A separate **stored** clip, DSCF0112, is a previous SAM 3.1 run checked into `web/public/runs/demo-real-coyote-0112`: **90 raw detections, naive_count 2, unique_count 2, is_mock false**. The app replays that file. It does not call SAM again. 90 is `detections_total`, not the naive count.

## Sectors

A sector is defined by a JSON pack.

| Sector | File | What the result shows |
|---|---|---|
| Fauna | `packs/fauna.json` | Unique animals, re-entry stitch, alerts |
| Transit | `packs/transito.json` | Vehicles and a turn matrix. **Not a verified traffic count.** |
| Crowd | `packs/multitudes.json` | People per zone and density. **No re-identification.** One alert: 6 people/m² (high / crush risk). |
| Farm | `packs/farm.json` | A pen the owner draws. Wild animal inside, or farm animal outside, only after it stays that way for 3 seconds. In-app confirm or dismiss. **NOT VERIFIED** — no labeled field clip. |

## Cameras

A camera in this app is not a live stream. It is a clip counted once, cached, and played back on a loop. Alerts are tied to `t_s`. Every camera is labeled **Simulated camera**.

Open [http://127.0.0.1:43123/cameras](http://127.0.0.1:43123/cameras). **North pen** is the farm example. **Ridge gate** is a protected area: the only alert is “Person detected in protected zone at HH:MM”, the face box is blurred, and nothing identifies the person. The ranger presses **Review**. Rastro does not notify authorities. The label is **Possible intrusion — needs review**. **Trap line** replays DSCF0112 (90 → 2). The inbox stays in the app: no SMS and no push. Farm and protected alerts are **NOT VERIFIED** until a labeled field clip exists (`eval/alert_set/`).

## Peak hours

Crowd and traffic counts can be added up by hour and weekday. The chart on the Cameras page is one component for both. Until the server has seen 7 real runs, the chart is labeled **Example data**. After that it switches to **Your data**. Traffic keeps the **Not verified** badge. Only the aggregate row is stored (station, hour, weekday, count) — see `supabase/peak_aggregates.sql`. That table is meant for the Supabase free tier (500 MB). Video stays out of it.

## Open peak-hour feed

`GET /api/open/peak-hours` (through the app: `/engine/api/open/peak-hours`) is a read-only JSON list of peak hours per camera. It is ready to connect to routing apps (for example Waze for Cities). Traffic counts in that feed are not verified. The feed does not push data anywhere; another app would have to read it.

```bash
curl -s http://127.0.0.1:8787/api/open/peak-hours
```

## Meta models

| Model | Role | When |
|---|---|---|
| **SAM 3.1** | Video tracking, one concept per request | Meta Model API (`META_API_KEY`). Mock client if the key is absent, and always for sample clips. |
| **Muse Voice Transcribe 1.0** | Field note → text, speaker per turn | Meta Model API. Mock note if the key is absent. Live notes must be WAV. |
| **Muse Spark Open** | Report and alerts from the counts. The model is not allowed to change the numbers. | Baseten, `meta-models/muse-spark-open-1026` (`BASETEN_API_KEY`). Local report if the key is absent or the run is a mock sample. |

Counts come from the rules engine. The agent writes prose.

## Architecture

```mermaid
flowchart LR
  subgraph Web
    UI[Next.js app]
  end
  subgraph Worker
    API[Python API]
    ENG[Pack plus tracking plus rules]
  end
  subgraph Models
    SAM[SAM 3.1]
    VOICE[Muse Voice Transcribe]
    SPARK[Muse Spark Open on Baseten]
  end
  UI -->|sample or upload| API
  API --> ENG
  ENG -->|real video and key| SAM
  ENG -->|note and key| VOICE
  ENG -->|key and not a mock sample| SPARK
  ENG -->|naive vs unique, report| UI
```

Supabase (`supabase/`) is the schema for a hosted queue. This compose stack does not start a database. `worker/queue_worker.py` still drains that queue when `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set. The demo uses the local API instead.

## Evaluation, only what is in the repo

From `eval/last_score_outputs.json` and `eval/ROUND2_NOTES.md`:

| Clip | Ground truth | Prediction | Status |
|---|---|---|---|
| DSCF0104 | 1 | 1 | PASS. 34 raw detections in the stored run. |
| DSCF0112 | 2 | 2 | PASS. 90 raw detections in the stored run. |
| DSCF0004 | 1 | 1 | PASS |
| DSCF0840 | — | — | SKIPPED. Ground truth not verified. |

**3 scored clips, MAE 0, exact match 3/3.** Small sample. On those scored runs, `naive_count` matches the unique ground truth. The measured gap versus raw boxes is `detections_total` (90 and 34) versus unique individuals (2 and 1).

Wicker Park (`eval/WICKER_COUNT.md`): the engine comparison (car 56, motorcycle 1, bus 1) is **NOT VERIFIED**. No MAE.

## Limits

- No facial recognition. Packs ask for a blur box, not an identity. Crowd does not track people.
- Sample clips are synthetic or stored. They are labeled. They are not a new field survey.
- SAM video, as used by this project: about 15,000 frames per request, at most 16 objects per frame, one concept per request.
- Uploads: MP4 or MOV, up to 50 MB. Product target is also at most 120 seconds at 720p.
- Annotated masks need ffmpeg and a real video. This demo draws the tracker’s boxes from `frames[]` instead.
- Voice transcripts stay hidden unless the upload is marked public.
- No deploy in this repository. No secrets in git.

## Layout

```
packs/             fauna, transito, multitudes
worker/rastro/     tracker, rules, SAM, voice, Spark, local API
worker/queue_worker.py
web/               the app
supabase/          schema only
eval/              scores and fixtures
```

## Data and credits

- **Wicker Park intersection changes** by Steven Vance, [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/), via [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Wicker_Park_intersection_changes.webm).
- **DSCF camera-trap clips:** Seattle(ish) Camera Traps, LILA BC. License: Community Data License Agreement (permissive variant). [Dataset page](https://lila.science/datasets/seattleish-camera-traps/).

Heavy videos were left out of git. See `DATA.md` and `eval/LICENSES.md` before redistributing clips.
