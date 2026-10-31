"""The landing ledger may only repeat numbers that already live in the repo."""

from __future__ import annotations

import json
import re
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
    assert "density_per_m2 >= 4" not in blob
    assert "density_medium" not in blob
    assert "density_per_m2 >= 6" in blob
    thresholds = claims["crowd_thresholds_people_per_m2"]
    assert thresholds["high"] == 6
    assert "media" not in thresholds
    assert "4" not in json.dumps(thresholds)

    _assert_seed_density_thresholds_are_six()
    _assert_transit_text_has_no_count_beside_people_or_vehicles()


_COUNT_BESIDE = re.compile(
    r"\b(?:people|person|persons|vehicles|vehicle)\b(?:[^.\n]{0,48}?)\d+"
    r"|\d+(?:[^.\n]{0,48}?)\b(?:people|person|persons|vehicles|vehicle)\b",
    re.IGNORECASE,
)


def _assert_seed_density_thresholds_are_six() -> None:
    """Seed SQL is generated from the packs. Density alerts are 6, not 4."""
    seeds = sorted((REPO / "supabase").glob("seed*.sql"))
    assert seeds
    saw_density = False
    for path in seeds:
        text = path.read_text(encoding="utf-8")
        assert ">= 4" not in text
        assert ">=4" not in text.replace(" ", "")
        for raw in re.findall(r"density_per_m2\s*>=\s*([0-9.]+)", text):
            saw_density = True
            assert float(raw) == 6, f"{path.name} density threshold {raw}"
    assert saw_density


def _assert_transit_text_has_no_count_beside_people_or_vehicles() -> None:
    pack = json.loads((REPO / "packs" / "transito.json").read_text(encoding="utf-8"))
    templates = [str(alert["message"]) for alert in pack["alerts"]]
    for template in templates:
        assert "{unique_count}" not in template
        assert "{count}" not in template
    rendered = [
        template.format(station="corner", unique_count=1, **{"class": "person"})
        for template in templates
    ]
    blob = "\n".join(rendered)
    assert "Person detected in the intersection" in blob
    assert "Heavy car flow detected (NOT VERIFIED)" in blob
    assert "Motorcycles detected (NOT VERIFIED)" in blob
    assert _COUNT_BESIDE.search(blob) is None
