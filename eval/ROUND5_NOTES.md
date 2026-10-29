# Round 5 QA notes (2026-10-26 America/Chicago)

FRONT under test: `3dc9380` (multitudes density view + R2-03 chip cargando).
Rules: eval/ only; no push/deploy; no API/Supabase; no lasting web/ edits.

## Method (crowds mock)

- Permanent fixture: `eval/fixtures/multitudes_density_mock.json` (derived from `web/mock/multitudes-demo/result.json`, enriched with `zona_sin_area` without `area_m2`, boundary dens 4.0/6.0, `partial=true`, `max_objects_hit=[10.5,22.0]`).
- **Did not** copy into `web/public/runs/` (view only reads public runs for live packs; multitudes still `has_run=false` in index).
- Unit-rendered `PackSwitcher`, `MultitudesPanel`, `DensityChart`, `PartialBanner`, `EventTimeline` via temporary `web/_r5_render.mts` + `tsx` (script **removed** after; no web/ commit).
- Live SSR: `next start` `/` for PackSwitcher first HTML.

## 1. R2-03 / BUG-R4-01 PackSwitcher chip — **RESOLVED**

| state | evidence |
|-------|----------|
| SSR before index | `curl /`: 3× `· cargando` (Fauna/Tránsito/Multitudes); **0×** `· sin corrida` |
| Unit `packStatus=null` | 3× cargando, 0× sin corrida |
| Unit after index (fauna has_run, others `_sin_corrida`) | Fauna chip clean (no suffix); Tránsito+Multitudes `· sin corrida`; 0× cargando |

`PackSwitcher` now takes `packStatus: … \| null`; `DemoPanel` passes `index ? index.packs : null`.

## 2. Crowds / Multitudes view — **PASS** (unit-render + empty path)

- Empty (`empty=true`): «Multitudes · sin corrida»; no density numbers / no «propuesta».
- Filled (eval fixture): chart labels **«4 propuesta»** and **«6 propuesta»**; peak `6.20` pers/m² color `#ef4444`; «área supuesta: 25 m²» + badge «ejemplo»; `persons_per_zone` list visible; `zona_sin_area` shows «sin área → solo personas» (count only).
- Thresholds (`densityLevel` / `densityColor`): green `<4` (`3.99→#22c55e`), amber `≥4` (`4.0→#f59e0b`), red `≥6` (`6.0→#ef4444`). Numbers shown next to colors (peak + zone dens).

## 3. Partial warning — **PASS**

- `partial=true` → banner «Conteo parcial: más de 16 objetos por frame».
- `partial=false` / absent → render `null`.
- `max_objects_hit` → EventTimeline «Tope de objetos» marks `0:10` and `0:22`; absent → no Tope section.
- DemoPanel wires `PartialBanner` only when `result.partial === true`; passes `result.max_objects_hit` into `EventTimeline`.

## 4. Quick a11y — **PASS with residual**

- Color not sole signal: dens numbers + «4/6 propuesta» labels + zone counts (**PASS**).
- Amber/red on dark panel (~`#0b1220`): amber `#f59e0b` ≈8.7:1, red `#ef4444` ≈5.0:1, green ≈8.2:1 (AA for normal text) (**PASS** approximate).
- Residual: `DensityChart` SVG `<title>` uses multi-child JSX → React warning «children of title tags … Array»; see **BUG-R5-01**.

## 5. Regression — **PASS**

| check | result |
|-------|--------|
| tsc --noEmit | PASS |
| lint | PASS |
| build | PASS |
| pages 200 | `/`, `/runs/index.json`, `/runs/demo-real-coyote-0112/result.json` |
| medido/ejemplo | 0112+0104 medido; mocks ejemplo |
| voice gate | `demo-mock-voice` `is_public: false`; normalizeVoice default false |
| client secrets | none in `.next/static` |
| pytest | **58 passed** |
| score.py `--outputs outputs` | 3 PASS (0104/0112/0004), mae=0; 5 SKIPPED |

## New bugs

### BUG-R5-01 — DensityChart `<title>` multi-child React warning
- **severity:** low
- **area:** `web/src/components/DensityChart.tsx` (circle `<title>`)
- **steps:** unit-render DensityChart / MultitudesPanel with density samples; observe React DOM server warnings
- **expected:** `<title>{`t=… · … pers · …/m²`}</title>` single string (also better a11y tooltip text)
- **actual:** JSX array children → React warns; tooltip content may not serialize cleanly in SSR

## Out of scope
No API/Supabase/push/deploy. Servers stopped after QA.
