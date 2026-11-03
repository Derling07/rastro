# Round 4 QA notes (2026-10-26 America/Chicago)

FRONT under test: `018fe0b` (JobProgress + detections_total + sync 0112) + `fb0238f` (vista tránsito).
Rules: eval/ only; no push/deploy; no API/Supabase; no web/ edits.

## Per-bug retest (FRONT 018fe0b)

### R2-02 UploadDrop packId — **RESOLVED**
- `UploadDrop` props require `packId`; calls `uploadClip({…, packId})`.
- `uploadClip` → `requestSignedUpload` POSTs `JSON.stringify({filename, contentType, size, duration_s, packId})` (`web/src/lib/upload.ts`).
- `npx tsc --noEmit`: clean (exit 0).

### R2-03 SSR «Cargando corrida» vs «sin corrida» — **REOPENED**
- **CountHero (fixed):** first HTML shows `Cargando corrida` (not «Sin corrida para este video»). Evidence: `curl /` SSR contains 1× `Cargando corrida`, 0× `Sin corrida para este video`.
- **PackSwitcher (still broken):** same SSR still paints `Fauna · sin corrida` (and Tránsito/Multitudes) because `has_run ?? false` while `packStatus={}` before index hydrates (`PackSwitcher.tsx`). «sin corrida» on fauna before index contradicts «only for packs truly without run after index».
- Residual tracked as **BUG-R4-01** below (same root cause).

### R2-04 sync-runs 0112 default — **RESOLVED**
- `npm run sync-runs` copied 5 runs incl. `demo-real-coyote-0112`; log: `listo: 5 default demo-real-coyote-0112`.
- `DEMOS` lists 0112 first; `default_run_id: "demo-real-coyote-0112"` in `sync-runs.mjs` and `public/runs/index.json`.
- `DemoPanel` `DEFAULT_RUN = "demo-real-coyote-0112"`.

## detections_total (engine-written)

| run | detections_total | Σ sam[].n_detections (run.json) | unique | is_mock | sam[].mock | agent_log |
|-----|------------------|----------------------------------|--------|---------|------------|-----------|
| demo-real-coyote | 34 | 34 (1 SAM) | 1 | false | false | sam.segment_video + tracking.count_unique |
| demo-real-coyote-0112 | 90 | 90 (1 SAM) | 2 | false | false | same |

UI counter data from `result.json`: **90 raw detections of a coyote (individuals NOT VERIFIED)** and **34→1**. Match run.json SAM sums; not mock. The stored unique_count is not a verified individual count.

## Transit view (fb0238f)

- Index: `packs.transito.has_run=false`, `_sin_corrida=true`.
- `TurnMatrix` with `empty`: badge «sin corrida», copy «Sin corrida para este video…», cells/access totals render `—` (no invented numbers). No crash path in component.
- DemoPanel: `pack==="transito"` + `empty` → `TurnMatrix matrix={} empty`.

## Regression

| check | result |
|-------|--------|
| `npm run build` | PASS |
| `npm run lint` | PASS (0 warnings) |
| `tsc --noEmit` | PASS |
| pages HTTP | `/` `/runs/index.json` `/runs/demo-real-coyote{-0112}/result.json` → **200** (after clean rebuild; concurrent `next build` while `next dev` briefly 500 MODULE_NOT_FOUND — env flake, not product) |
| mock/real labels | index: 0112/0104 **medido**; mocks **ejemplo** |
| private voice gate | `normalizeVoice`: `is_public = v.is_public === true`; VoiceNote hides literals unless true; `demo-mock-voice` has `is_public: false` |
| secrets in client `.next/static` | none (META/BASETEN values + SERVICE_ROLE names absent) |
| JobProgress mock states | queued→«En cola»; processing + stages Descargando/Motor/Guardando; done «Listo»; failed «Falló»; retry «Reintentando (n de 3)»; badge «simulado» (`jobs.ts` mock adapter) |

**Regression: PASS** (with R2-03 PackSwitcher residual noted).

## Score + pytest

```
python3 eval/score.py --outputs outputs --json-out eval/last_score_outputs.json
```
- DSCF0104 PASS (1/1), DSCF0112 PASS (2/2), DSCF0004 PASS (1/1); 5 SKIPPED (NOT VERIFIED).
- Aggregate: n_scored=3 n_pass=3 mae=0 exact_match_rate=1.0.

```
python -m pytest tests/ eval/tests/ -q  → 48 passed
```

## New bugs

### BUG-R4-01 — PackSwitcher SSR flash «Fauna · sin corrida»
- **severity:** medium
- **area:** `web/src/components/PackSwitcher.tsx` (+ DemoPanel passes `packStatus={}` until index)
- **steps:** open `/` (SSR or hard refresh); inspect first HTML before `/runs/index.json` returns
- **expected:** fauna chip has no «· sin corrida» until index says otherwise; CountHero already shows «Cargando corrida»
- **actual:** all three chips include «· sin corrida» because `has_run ?? false` on empty status
- **fix:** treat missing status as unknown (omit chip) or default fauna `has_run` from SSR props / loading flag

## Out of scope / not done
- No API, Supabase, push, or deploy.
- Dev/prod server stopped after QA.
