"""Field notes keep engine numbers and do not call Muse Spark."""

from __future__ import annotations

import json
from pathlib import Path

from rastro.field_note import assemble_note, decide_note, note_dscf0112, note_for_camera, reset_field_notes


def setup_function():
    reset_field_notes()


def test_dscf0112_uses_engine_counts_and_recorded_prose():
    result = json.loads(
        Path("web/public/runs/demo-real-coyote-0112/result.json").read_text(encoding="utf-8")
    )
    note = note_dscf0112()
    assert note["paid_call"] is False
    assert note["live_call"] is False
    assert note["sam_called_on_this_request"] is False
    assert note["recorded"] is True
    assert note["source"] == "baseten-spark"
    assert note["model"] == "meta-models/muse-spark-open-1026"
    assert note["engine"]["detections_total"] == result["detections_total"] == 90
    assert note["engine"]["unique_count"] == result["unique_count"] == 2
    assert note["engine"]["naive_count"] == result["naive_count"] == 2
    assert note["engine_count"] == "90 raw detections → 2 unique coyotes"
    assert "DSCF0112.mp4" in result["report"]["resumen"]
    assert ".mp4" not in note["summary"]
    assert "fauna-camtrap" not in note["summary"]
    assert "2 unique coyotes" in note["summary"]
    assert note["title"] == "Rastro report — Wildlife camera"
    assert note["summary_label"] == "Muse Spark summary (recorded)"
    assert note["not_sure"] is False
    assert note["severity"] == "info"
    assert note["confidence"] == "high"
    assert "SAM" in note["why"]["sam"]
    assert "stitch" in note["why"]["rule"].lower() or "re-entry" in note["why"]["rule"].lower()
    assert note["context"]["example_data"] is False
    assert note["crop"]["class"] == "coyote"
    assert note["crop"]["pixels"] is False


def test_summary_text_cannot_replace_the_engine_count():
    note = assemble_note(
        note_id="clip:test",
        module="fauna",
        title="Test",
        engine={"detections_total": 90, "naive_count": 2, "unique_count": 2, "by_class": {"coyote": 2}},
        noun="coyotes",
        summary="The model thinks there are 9 coyotes.",
        source="baseten-spark",
        model="meta-models/muse-spark-open-1026",
        recorded=True,
        sam_saw="coyote",
        sam_on_this_request=False,
        rule="Rule: re-entry stitch.",
        context_lines=["Stored run."],
        example_data=False,
        confidence="high",
        actions=["confirm", "dismiss"],
        crop=None,
    )
    assert note["engine"]["unique_count"] == 2
    assert note["engine_count"] == "90 raw detections → 2 unique coyotes"
    assert "9 coyotes" not in note["engine_count"]
    assert note["summary"].startswith("The model thinks")


def test_low_confidence_is_not_sure_and_a_person_decides():
    note = assemble_note(
        note_id="camera:wicker-park",
        module="traffic",
        title="Wicker",
        engine={"detections_total": None, "naive_count": None, "unique_count": None, "by_class": {}},
        noun="vehicles",
        summary="Not sure.",
        source="local-rules",
        model=None,
        recorded=False,
        sam_saw="vehicles",
        sam_on_this_request=False,
        rule="Rule: not verified.",
        context_lines=["Example data."],
        example_data=True,
        confidence="low",
        actions=["confirm", "dismiss"],
        crop=None,
    )
    assert note["severity"] == "not sure"
    assert note["not_sure"] is True
    assert note["context"]["label"] == "Example data"
    assert note["summary_label"] == "Rules engine note"
    assert "The engine has no verified count for this clip." in note["why"]["sam"]
    assert "No verified count." not in note["why"]["sam"]


def test_protected_review_does_not_confirm_and_farm_can_confirm():
    protected = note_for_camera("forest-trail")
    assert protected is not None
    assert protected["actions"] == ["review"]
    assert protected["not_sure"] is True
    assert protected["severity"] == "not sure"
    assert "authorities" in protected["why"]["rule"]
    assert protected["engine_count"] == "Person box. No identity."
    try:
        decide_note(protected["id"], "confirm")
        raise AssertionError("confirm must not be allowed")
    except ValueError:
        pass
    reviewed = decide_note(protected["id"], "review")
    assert reviewed["status"] == "reviewed"

    fox = note_for_camera("gray-fox")
    assert fox is not None
    assert fox["module"] == "fauna"
    assert fox["severity"] == "info"
    assert fox["not_sure"] is False
    assert "confirm" in fox["actions"]
    assert fox["context"]["example_data"] is False
    confirmed = decide_note(fox["id"], "confirm")
    assert confirmed["status"] == "confirmed"


def test_inbox_severity_comes_from_each_camera_note():
    from rastro.cameras import inbox, reset_camera_state

    reset_camera_state()
    rows = inbox()
    ids = {row["camera_id"] for row in rows}
    assert {"gray-fox", "goat-lane", "forest-trail"} <= ids
    for row in rows:
        note = note_for_camera(row["camera_id"])
        assert note is not None
        assert row["severity"] == note["severity"]
    forest = next(row for row in rows if row["camera_id"] == "forest-trail")
    assert forest["severity"] == "not sure"


def test_empty_token_allows_loopback_and_rejects_other_hosts(monkeypatch):
    from rastro.api import writes_allowed

    monkeypatch.delenv("RASTRO_WRITE_TOKEN", raising=False)
    assert writes_allowed("127.0.0.1", None) is True
    assert writes_allowed("::1", None) is True
    assert writes_allowed("172.18.0.5", None) is False
    route = Path("web/src/app/api/field-note/route.ts").read_text(encoding="utf-8")
    assert "x-rastro-token" in route
    assert "if (!token)" not in route
    card = Path("web/src/components/notebook/AlertCard.tsx").read_text(encoding="utf-8")
    assert "Could not save:" in card


def test_visible_note_hides_filenames_and_pack_ids():
    fox = note_for_camera("forest-trail")
    assert fox is not None
    assert fox["title"] == "Protected area"
    assert "clip" not in fox["title"].lower()
    shown = note_dscf0112()
    visible = shown["title"] + shown["summary"] + shown["engine_count"]
    assert ".mp4" not in visible
    assert "fauna-camtrap" not in visible
    assert "2 unique coyotes" in shown["engine_count"]


def test_traffic_note_does_not_invent_a_vehicle_total():
    note = note_for_camera("wicker-park")
    assert note is not None
    assert note["context"]["example_data"] is True
    assert note["severity"] == "not sure"
    assert note["engine_count"] == "No verified vehicle count"
    assert note["engine"]["unique_count"] is None
    assert note["paid_call"] is False


def test_dscf0112_shares_one_status_and_confirm_is_idempotent(monkeypatch):
    from rastro.feeds import list_webhooks, reset_feeds, subscribe_webhook

    monkeypatch.setattr(
        "rastro.feeds.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    reset_feeds()
    subscribe_webhook("https://example.com/rastro")
    first = decide_note("clip:DSCF0112", "confirm")
    again = decide_note("camera:trap-dscf0112", "confirm")
    assert first["status"] == "confirmed"
    assert again["id"] == "clip:DSCF0112"
    assert again["status"] == "confirmed"
    assert len(list_webhooks()["outbox"]) == 1


def test_crop_uses_frame_size_from_the_result():
    from rastro.field_note import _crop

    crop = _crop(
        {
            "frame_width": 1920,
            "frame_height": 1080,
            "frames": [{"t_s": 1.0, "objects": [{"class": "coyote", "bbox": [10, 20, 30, 40]}]}],
        },
        "coyote",
    )
    assert crop is not None
    assert crop["width"] == 1920
    assert crop["height"] == 1080
    assert crop["class"] == "coyote"


def test_active_run_note_uses_that_runs_numbers():
    import time

    from rastro import api
    from rastro.field_note import note_for_result

    api.reset_state()
    fauna = api.create_sample_job("fauna-trap")
    crowd = api.create_sample_job("multitudes-plaza")
    empty = api.create_sample_job("mock-empty")
    for job in (fauna, crowd, empty):
        for _ in range(200):
            current = api.get_job(job["id"])
            if current and current["status"] in {"done", "failed"}:
                break
            time.sleep(0.02)
    fauna_result = api.get_result(fauna["id"])["result"]
    fauna_note = note_for_result(fauna_result, run_id=fauna["id"], pack="fauna")
    assert fauna_note is not None
    assert fauna_note["engine"]["detections_total"] == fauna_result["detections_total"] == 210
    assert fauna_note["engine"]["unique_count"] == fauna_result["unique_count"] == 4
    assert fauna_note["engine_count"].startswith("210 raw detections → 4 unique")
    assert fauna_note["summary_label"] == "Rules engine note"
    assert fauna_note["not_sure"] is True
    crowd_result = api.get_result(crowd["id"])["result"]
    crowd_note = note_for_result(crowd_result, run_id=crowd["id"], pack="multitudes")
    assert crowd_note is not None
    assert crowd_note["engine_count"] == (
        "Peak density 5.4 people/m² (NOT VERIFIED: area not calibrated). Zone 1."
    )
    assert ".." not in crowd_note["engine_count"]
    assert crowd_note["why"]["sam"] == "SAM 3.1 detected people per frame. No re-identification."
    assert "unique" not in crowd_note["why"]["sam"]
    assert "135" not in crowd_note["engine_count"]
    assert crowd_note["summary_label"] == "Rules engine note"
    transit = api.create_sample_job("transito-intersection")
    for _ in range(200):
        current = api.get_job(transit["id"])
        if current and current["status"] in {"done", "failed"}:
            break
        time.sleep(0.02)
    transit_result = api.get_result(transit["id"])["result"]
    transit_note = note_for_result(transit_result, run_id=transit["id"], pack="transito")
    assert transit_note is not None
    assert transit_note["engine_count"] == "No verified vehicle count"
    assert "3304" not in transit_note["engine_count"]
    assert "3304" not in transit_note["why"]["sam"]
    assert "unique" not in (transit_note["summary"] + transit_note["engine_count"] + transit_note["why"]["sam"]).lower()
    assert transit_note["not_sure"] is True
    visible = crowd_note["summary"] + crowd_note["engine_count"] + crowd_note["why"]["sam"] + crowd_note["title"]
    assert "unique" not in visible.lower()
    assert ".mp4" not in visible
    assert "fauna-camtrap" not in visible
    assert note_for_result(api.get_result(empty["id"])["result"], run_id=empty["id"], pack="fauna") is None


def test_crowd_text_without_a_series_has_no_person_number():
    from rastro.agent import crowd_line
    from rastro.field_note import _frame_peak_persons, note_for_result

    result = {
        "unique_count": 135,
        "naive_count": 900,
        "detections_total": 900,
        "sampling_mode": "image_sample",
        "by_class": {"person": 135},
        "peak_density": {"zone": "zone_1", "t_s": 6, "persons": 135, "density_per_m2": 5.4},
        "report": {
            "titulo": "Crowd density",
            "resumen": "Peak density 5.4 people/m² (NOT VERIFIED: area not calibrated). Zone 1.",
            "_source": "local",
        },
        "is_mock": True,
        "frames": [],
    }
    assert _frame_peak_persons(result) is None
    note = note_for_result(result, run_id="noseries", pack="multitudes")
    assert note is not None
    visible = note["summary"] + note["engine_count"] + note["why"]["sam"] + note["title"]
    assert "135" not in visible
    assert "people in one frame" not in visible
    assert "Peak density 5.4 people/m² (NOT VERIFIED: area not calibrated)" in note["engine_count"]
    assert ".." not in note["engine_count"]
    assert "Zone 1" in note["engine_count"]
    bare = crowd_line(None)
    assert "135" not in bare
    assert bare == "No verified person count."
