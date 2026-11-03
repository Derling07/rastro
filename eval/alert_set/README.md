# Alert test set

Each file is one alert the rules engine must be able to raise. `status` is about the **clip**, not the rule.

| Id | What it checks | Clip |
|---|---|---|
| `wild_enters` | Gray fox stays in the bait area for 3 s | **PASS** — Andy, CC BY 3.0 |
| `farm_leaves` | Goats leave the yard | **PASS** — Thamizhpparithi Maari, CC BY-SA 3.0 |
| `person_in_zone` | One person on the trail at 12:47, face and body blurred, no identity | **PASS** — LILA DSCF0004, daytime |
| `crowd_plaza` | Peak people in Plaza Mayor | **PASS** — hand 16, detector 19 |
| `traffic_wicker` | Wicker Park flyover | **NOT VERIFIED** — unique vehicles not established |

`manifest.json` is the score list. Pytest checks those statuses and the synthetic points in `tests/test_zones.py`. Do not treat a passing rule test as a verified field count.
