"""Offline tests for eval/score.py — fixtures only, no API calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
ROOT = EVAL.parent

# Ensure score module is importable without installing the package
import sys

sys.path.insert(0, str(EVAL))
import score  # noqa: E402

FIXTURES = EVAL / "fixtures"
GT = EVAL / "ground_truth.json"


def test_extract_counts_result_schema_v11():
    payload = json.loads((FIXTURES / "result_DSCF0112_mock.json").read_text())
    assert payload.get("is_mock") is True or payload.get("mock") is True
    assert payload.get("schema_version") == "1.1"
    assert payload.get("unique_count") == 2
    unique, naive = score.extract_counts(payload)
    assert unique == 2
    assert naive == 5


def test_extract_counts_flat_preferred_over_nested():
    """v1.1 flat aliases win when both present (CORE source of truth)."""
    unique, naive = score.extract_counts(
        {
            "unique_count": 1,
            "naive_count": 3,
            "counts": {"unique": 99, "naive": 99},
        }
    )
    assert unique == 1 and naive == 3


def test_extract_counts_legacy_summary():
    unique, naive = score.extract_counts({"unique_count": 1, "naive_count": 4, "mock": True})
    assert unique == 1 and naive == 4


def test_extract_counts_nested_only_v10():
    unique, naive = score.extract_counts({"counts": {"unique": 2, "naive": 7}})
    assert unique == 2 and naive == 7


def test_skip_not_verified():
    gt = score.load_json(GT)
    clip = next(c for c in gt["clips"] if c["id"] == "DSCF0840")
    assert clip["status"] == "NOT VERIFIED"
    s = score.score_clip(clip, {"counts": {"unique": 1, "naive": 1}}, "x", tolerance=0)
    assert s.status == "SKIPPED"
    assert s.abs_error is None


def test_pass_on_mock_fixture():
    gt = score.load_json(GT)
    clip = next(c for c in gt["clips"] if c["id"] == "DSCF0112")
    payload = score.load_json(FIXTURES / "result_DSCF0112_mock.json")
    s = score.score_clip(clip, payload, "fixture", tolerance=0, allow_mock=True)
    assert s.status == "PASS"
    assert s.abs_error == 0
    assert s.pred_naive == 5
    assert s.rastro_better_than_naive is True


def test_fail_on_overcount_fixture():
    gt = score.load_json(GT)
    clip = next(c for c in gt["clips"] if c["id"] == "DSCF0104")
    payload = score.load_json(FIXTURES / "result_DSCF0104_overcount_mock.json")
    s = score.score_clip(clip, payload, "fixture", tolerance=0, allow_mock=True)
    assert s.status == "FAIL"
    assert s.abs_error == 2


def test_skip_mock_payload_without_allow():
    gt = score.load_json(GT)
    clip = next(c for c in gt["clips"] if c["id"] == "DSCF0112")
    payload = score.load_json(FIXTURES / "result_DSCF0112_mock.json")
    s = score.score_clip(clip, payload, "fixture", tolerance=0, allow_mock=False)
    assert s.status == "SKIPPED_MOCK"
    assert s.abs_error is None


def test_find_prefers_real_over_mock(tmp_path: Path):
    """When both mock and real exist for same source_video_id, pick real."""
    out = tmp_path / "outputs"
    mock = out / "demo-mock-coyote"
    real = out / "demo-real-coyote"
    mock.mkdir(parents=True)
    real.mkdir(parents=True)
    (mock / "result.json").write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "run_id": "demo-mock-coyote",
                "source_video_id": "DSCF0104",
                "unique_count": 3,
                "naive_count": 3,
                "counts": {"unique": 3, "naive": 3},
                "is_mock": True,
            }
        )
    )
    (real / "result.json").write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "run_id": "demo-real-coyote",
                "source_video_id": "DSCF0104",
                "unique_count": 1,
                "naive_count": 1,
                "counts": {"unique": 1, "naive": 1},
                "is_mock": False,
                "created_at": "2026-10-27T04:12:23+00:00",
                "pack": {"id": "fauna-camtrap", "version": "0.4.0"},
            }
        )
    )
    payload, src, meta = score.find_run_payload(out, "DSCF0104", allow_mock=False)
    assert payload is not None
    assert payload["unique_count"] == 1
    assert payload["is_mock"] is False
    assert "demo-real" in src
    assert meta["matched_mock_only"] is False


def test_find_flags_mock_only(tmp_path: Path):
    out = tmp_path / "outputs"
    mock = out / "demo-mock-coyote"
    mock.mkdir(parents=True)
    (mock / "result.json").write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "run_id": "demo-mock-coyote",
                "source_video_id": "DSCF0104",
                "unique_count": 3,
                "naive_count": 3,
                "counts": {"unique": 3, "naive": 3},
                "is_mock": True,
            }
        )
    )
    payload, src, meta = score.find_run_payload(out, "DSCF0104", allow_mock=False)
    assert meta["matched_mock_only"] is True
    assert score.payload_is_mock(payload)
    gt = score.load_json(GT)
    clip = next(c for c in gt["clips"] if c["id"] == "DSCF0104")
    s = score.score_clip(clip, payload, src, tolerance=0, mock_only=True, allow_mock=False)
    assert s.status == "SKIPPED_MOCK"


def test_score_run_with_fixture_map(tmp_path: Path):
    """Full score_run using only mock fixtures (no real outputs required)."""
    fixture_map = {
        "DSCF0112": FIXTURES / "result_DSCF0112_mock.json",
        "DSCF0104": FIXTURES / "result_DSCF0004_mock.json",  # unique=1 matches GT0104
        "DSCF0004": FIXTURES / "result_DSCF0004_mock.json",
        # DSCF0840 skipped via GT status; transit clips also NOT VERIFIED
    }
    empty = tmp_path / "outputs"
    empty.mkdir()
    report = score.score_run(GT, empty, tolerance=0, fixture_map=fixture_map)
    agg = report["aggregate"]
    # fauna NOT VERIFIED (DSCF0840) + any transit NOT VERIFIED
    assert agg["n_skipped"] >= 1
    assert agg["n_scored"] == 3
    assert agg["n_pass"] == 3
    assert agg["mae"] == 0.0
    assert agg["exact_match_rate"] == 1.0
    assert "META_API_KEY" not in json.dumps(report)
    assert "BASETEN_API_KEY" not in json.dumps(report)


def test_cli_fixtures_exit_zero(tmp_path: Path):
    """CLI path with crafted real (is_mock=false) result.json files."""
    out = tmp_path / "real"
    for clip, src in [
        ("DSCF0112", "result_DSCF0112_mock.json"),
        ("DSCF0104", "result_DSCF0104_mock.json"),
        ("DSCF0004", "result_DSCF0004_mock.json"),
    ]:
        d = out / clip
        d.mkdir(parents=True)
        payload = json.loads((FIXTURES / src).read_text())
        # Strip mock so CLI scores them as real for this unit test
        payload["is_mock"] = False
        payload["mock"] = False
        payload["source_video_id"] = clip
        (d / "result.json").write_text(json.dumps(payload), encoding="utf-8")
    rc = score.main(["--gt", str(GT), "--outputs", str(out), "--tolerance", "0"])
    assert rc == 0
