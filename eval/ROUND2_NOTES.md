# Round 2 QA notes (2026-10-26 America/Chicago)

## Score (outputs/ preferred real over mock)

| clip | status | gt | pred | source |
|------|--------|----|------|--------|
| DSCF0104 | PASS | 1 | 1 | outputs/demo-real-coyote/result.json (v1.1, is_mock=false) |
| DSCF0112 | PASS | 2 | 2 | outputs/demo-real-coyote-0112/result.json (v1.1, is_mock=false) |
| DSCF0004 | PASS | 1 | 1 | outputs/real/DSCF0004/summary.json (legacy) |
| DSCF0840 | SKIPPED | — | — | NOT VERIFIED GT |
| repod-* | SKIPPED | — | — | NOT VERIFIED / not downloaded |

Aggregate (`--outputs outputs`): n_scored=3, n_pass=3, mae=0, exact_match_rate=1.0. Mocks never scored as real.

### DSCF0104 retest
**VERIFIED PASS** against existing `outputs/demo-real-coyote` (pack fauna-camtrap 0.4.0, unique=1, agent_log concept=coyote n=34). No API call. Legacy `outputs/real/DSCF0104` still unique=0 (superseded).

### DSCF0112 100 vs 90
- **100** = `sam[].n_detections` in legacy `outputs/real/DSCF0112/run.json` (and `cost.json`) — concept=`animal`, n_detections=100. Tracks n_dets 50+50.
- **90** = `sam[].n_detections` in `outputs/demo-real-coyote-0112/run.json` (and result/cost) — concept=`coyote`, n_detections=90. Tracks n_dets 45+45.
- Both runs: unique_count=2, naive_count=2. 100/90 are raw SAM detections, **not** naive_count.

## RepOD
See LICENSES.md §7. Quote: "Different licenses for individual files"; example MP4 "License: CC BY - Creative Commons Attribution 4.0"; "Video available only upon request". Not downloaded (3.5 GB).

## Pytest
- eval/tests: 12 passed
- tests/test_queue_worker.py: 4 passed
- full repo pytest: 24 passed
