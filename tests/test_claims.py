"""The landing ledger may only repeat numbers that already live in the repo."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_claims_match_sources():
    claims = json.loads((REPO / "web" / "src" / "data" / "claims.json").read_text())
    assert "illustration" not in claims

    run = json.loads(
        (REPO / "web" / "public" / "runs" / "demo-real-coyote-0112" / "result.json").read_text()
    )
    measured = claims["measured_0112"]
    assert measured["detections_total"] == run["detections_total"] == 90
    assert measured["unique_count"] == run["unique_count"] == 2
    assert measured["naive_count"] == run["naive_count"] == 2
    assert run["is_mock"] is False
    assert run["cost"]["est_usd_total"] == 0

    run104 = json.loads(
        (REPO / "web" / "public" / "runs" / "demo-real-coyote" / "result.json").read_text()
    )
    assert claims["measured_0104"]["detections_total"] == run104["detections_total"] == 34
    assert claims["measured_0104"]["unique_count"] == run104["unique_count"] == 1

    score = json.loads((REPO / "eval" / "last_score_outputs.json").read_text())
    agg = score["aggregate"]
    assert claims["eval"]["n_scored"] == agg["n_scored"] == 3
    assert claims["eval"]["n_pass"] == agg["n_pass"] == 3
    assert claims["eval"]["mae"] == agg["mae"] == 0
    skipped = {c["clip_id"] for c in score["clips"] if c["status"] == "SKIPPED"}
    for clip in claims["eval"]["skipped_unverified"]:
        assert clip in skipped

    wicker = (REPO / "eval" / "WICKER_COUNT.md").read_text()
    assert "NOT VERIFIED" in wicker
    assert "car 56" in wicker

    pack = json.loads((REPO / "packs" / "multitudes.json").read_text())
    blob = json.dumps(pack)
    assert "density_per_m2 >= 4" in blob
    assert "density_per_m2 >= 6" in blob
    assert claims["crowd_thresholds_people_per_m2"]["validated"] is False
