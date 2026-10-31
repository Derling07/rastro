# Hackathon window

Meta Global AI Developer Hackathon 2026. Kickoff is **26 Oct 2026, 12:00 noon US Eastern** (16:00 UTC). Submission deadline is **4 Nov 2026, 8:00 p.m. Costa Rica**.

Rule used here: work shown in the demo should be built during the event. Any commit dated before kickoff must be called out. This file lists the git history of this repository.

## Commits before kickoff

**None.** `git log --until=2026-10-26T16:00:00Z` is empty.

The earliest commit in this clone is `402d089` on **29 Oct 2026, 02:21 UTC**. There is no earlier history to separate. If a file existed before the event, it is not in this git history.

## Commits during the event

All 19 commits on `main` before this redesign landed on 29 Oct 2026.

| Commit | Date (UTC) | What it added |
|---|---|---|
| `402d089` | 2026-10-29 02:21 | Initialize project |
| `2ea5568` | 2026-10-29 02:26 | Add Rastro source as the project home |
| `0757d68` | 2026-10-29 02:44 | Working app and re-identification |
| `2b782e6` | 2026-10-29 02:56 | Upload checks and mock / live / unverified labels |
| `42be20d` | 2026-10-29 02:59 | English copy and cited data |
| `35975d2` | 2026-10-29 03:05 | Crowd density-only results, fail and empty runs |
| `f8e06fd` | 2026-10-29 03:11 | Mock uploads no longer look like a real count |
| `c10fb4e` | 2026-10-29 03:15 | DSCF0112 headline uses measured detections |
| `09cf7a9` | 2026-10-29 03:43 | Traffic and fauna numbers stay consistent |
| `e9c6fed` | 2026-10-29 03:54 | Leftover Spanish copy translated |
| `91f365d` | 2026-10-29 04:06 | MIT license and one crowd alert |
| `ac81cb2` | 2026-10-29 14:08 | Simulated cameras and a farm pen |
| `02643b5` | 2026-10-29 14:11 | Protected-area alert a person reviews |
| `c99790a` | 2026-10-29 14:15 | Peak-hour charts stay on example data |
| `dd3953d` | 2026-10-29 14:18 | Read-only peak-hour feed |
| `99a738d` | 2026-10-29 14:39 | Open-licensed clips on the cameras |
| `a92b4d6` | 2026-10-29 14:39 | Alert fixtures marked PASS where the local detector matched |
| `9362d78` | 2026-10-29 14:43 | Gray fox camera opens first |
| `8e30f6e` | 2026-10-29 14:48 | Each camera keeps its own clip while the next loads |

The field-notebook redesign, the Muse Spark field note, and the open export land in the pull request that adds this file. Those commits are also after kickoff.

## In-memory demo state

Field-note statuses, webhook subscriptions, and the webhook outbox live in process memory only. Each list is capped at 50 entries. They disappear when the process stops. They are not written to Supabase or to disk. Webhook delivery stays off: a confirm records a payload and does not POST it. `RASTRO_WRITE_TOKEN` may be unset. Those write routes then accept localhost or a matching token.

## Meta models in this repo

- **SAM 3.1** produced the stored DSCF0112 run (90 raw detections → 2 unique coyotes, `is_mock` false). The app replays that file. It does not call SAM again on page load.
- **Muse Spark Open** (`meta-models/muse-spark-open-1026`) wrote the stored report in that same run. The field note shows that recorded reply. Page load does not call Baseten.
- With no API keys, new samples use the mock tracker and a local report. That is the no-cost path for local development.
