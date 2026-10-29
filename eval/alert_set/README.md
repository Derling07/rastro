# Alert test set

Each file is one alert the rules engine must be able to raise. `status` is about the **clip**, not the rule.

| Id | What it checks | Clip |
|---|---|---|
| `wild_enters` | Wild animal stays inside the drawn pen for `sustain_s` (default 3 s) | **NOT VERIFIED** — no labeled field clip |
| `farm_leaves` | Farm animal stays outside the pen for `sustain_s` after being inside | **NOT VERIFIED** — no labeled field clip |

`manifest.json` is the score list. Pytest checks those statuses and the synthetic points in `tests/test_zones.py`. Do not treat a passing rule test as a verified field count.
