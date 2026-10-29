"""Peak-hour aggregates stay small, and example data yields to real runs."""

from __future__ import annotations

from rastro.peaks import NEEDED_REAL_RUNS, note_finished_run, peak_view, reset_peaks


def setup_function():
    reset_peaks()


def test_example_badge_until_enough_real_runs():
    crowd = peak_view("crowd")
    assert crowd["badge"] == "Example data"
    assert crowd["real_runs"] == 0
    assert crowd["not_verified"] is False
    assert len(crowd["heatmap"]) == 7
    assert len(crowd["heatmap"][0]) == 24
    assert len(crowd["series"]) == 24
    traffic = peak_view("traffic")
    assert traffic["badge"] == "Example data"
    assert traffic["not_verified"] is True
    assert traffic["unit"] == "vehicles"


def test_your_data_replaces_the_example_after_seven_real_runs():
    for index in range(NEEDED_REAL_RUNS):
        note_finished_run(
            "transito",
            {
                "is_mock": False,
                "local_hour": 8,
                "naive_count": 3,
                "station": "wicker",
                "created_at": "2026-10-27T14:00:00+00:00",
            },
        )
        if index < NEEDED_REAL_RUNS - 1:
            assert peak_view("traffic")["badge"] == "Example data"
    view = peak_view("traffic")
    assert view["badge"] == "Your data"
    assert view["real_runs"] == NEEDED_REAL_RUNS
    assert view["not_verified"] is True
    assert view["series"][8] == 3 * NEEDED_REAL_RUNS
    # Tuesday 2026-10-27 is weekday 1.
    assert view["heatmap"][1][8] == 3 * NEEDED_REAL_RUNS


def test_mock_runs_and_other_packs_are_not_stored():
    note_finished_run("transito", {"is_mock": True, "local_hour": 8, "naive_count": 9, "station": "x"})
    note_finished_run("fauna", {"is_mock": False, "local_hour": 8, "naive_count": 2, "station": "trap"})
    assert peak_view("traffic")["real_runs"] == 0


def test_open_feed_is_read_only_peak_hours_per_camera():
    from rastro.peaks import open_peak_hours

    feed = open_peak_hours()
    assert feed["not_verified"] is True
    assert "Waze for Cities" in feed["description"]
    assert feed["cameras"][0]["camera_id"] == "example-intersection"
    assert feed["cameras"][0]["peak_hours"]
    assert "vehicles" in feed["cameras"][0]["peak_hours"][0]
    blob = str(feed).lower()
    for banned in ("uber", "didi", "google maps"):
        assert banned not in blob
    from pathlib import Path

    readme = Path(__file__).resolve().parents[1].joinpath("README.md").read_text().lower()
    assert "waze for cities" in readme
    for banned in ("uber", "didi", "google maps"):
        assert banned not in readme


def test_aggregate_rows_have_no_media_fields():
    note_finished_run(
        "multitudes",
        {
            "is_mock": False,
            "local_hour": 12,
            "station": "plaza",
            "peak_density": {"persons": 40},
            "video": {"path": "/secret/clip.mp4"},
            "created_at": "2026-10-26T18:00:00+00:00",
        },
    )
    from rastro.peaks import _rows

    assert len(_rows) == 1
    assert set(_rows[0]) == {
        "station",
        "pack",
        "weekday",
        "hour",
        "metric",
        "value",
        "verified",
        "source",
    }
    assert "clip.mp4" not in str(_rows[0])
