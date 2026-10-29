# Round 3 QA notes (2026-10-26 America/Costa_Rica)

## Transit clips

| id | license | local mp4 | GT |
|---|---|---|---|
| chiang-mai-jak-krok-siwilai | CC BY-SA 4.0 (Amada44) | data/transit/chiang_mai_intersection.mp4 (~3.9 MB, 14.5 s) | NOT VERIFIED |
| wicker-park-milwaukee-north-damen | CC BY 3.0 (Steven Vance) | data/transit/wicker_park_intersection.mp4 (~8.2 MB, 30.4 s) | NOT VERIFIED |

Binaries not git-added (see DATA_TRANSIT.md). Attribution: `data/transit/ATTRIBUTION.md`.

## Score (`--outputs outputs`, no API)

Fauna PASSes unchanged (DSCF0104/0112/0004). All transit + DSCF0840 + RepOD → SKIPPED (no ORION transit pack run / NOT VERIFIED).

## BUG-R2-01 (CORE a9e3d14)

**RESOLVED.** Without Supabase env: bad type / >50MB / >120s / bad packId → **400** with message; valid body → **503** "Subida no configurada."; bad JSON → 400. `tsc --noEmit` clean. Dev server stopped after test.

## CORE 06bd0d7 READY_FOR_QA

- `pytest tests/test_queue_worker.py`: **5 passed**
- `python worker/queue_worker.py --check` without env: exit **2**, stderr `Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY.` — no keys printed (META/BASETEN values not in output)
- `worker/.env` gitignored (`.gitignore` lines `.env` + `worker/.env`); file absent on disk
- Migrations order: `…000_core` (packs/runs/events/alerts/reports/voice_notes + RLS + ingest_run) → `…100_jobs` (jobs 50MB mp4/mov, claim/finish/stage, RLS read) → `…200_storage` (private `videos` bucket 50MB mp4/mov). Seed: `seed_packs.sql` fauna-only until regenerated.

### Risks
1. Public SELECT on packs/runs/events/alerts/reports (intentional demo) — all demo rows world-readable via anon.
2. `seed_packs.sql` only `fauna-camtrap`; no transit/multitudes pack rows yet (`packs/` only has fauna.json).
3. `ingest_run` can insert pack with `config='{}'` if unknown pack_id — incomplete pack metadata.
4. Bucket insert assumes `storage.buckets` exists (Supabase Storage enabled); no anon storage policies (good) but upload route still needs service_role.
5. Migrations note they are not applied until Derling authorizes — `--check` against empty project will fail bucket/jobs until applied + seed.
6. `finish_job` re-queues on failure if attempts < 3 without clearing `stage` — minor UX noise.
