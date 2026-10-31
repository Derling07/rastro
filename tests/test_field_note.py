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
    assert note["summary"] == result["report"]["resumen"]
    assert note["summary_label"] == "Muse Spark summary"
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

    farm = note_for_camera("gray-fox")
    assert farm is not None
    assert farm["not_sure"] is False
    assert "confirm" in farm["actions"]
    assert farm["context"]["example_data"] is False
    confirmed = decide_note(farm["id"], "confirm")
    assert confirmed["status"] == "confirmed"


def test_traffic_note_does_not_invent_a_vehicle_total():
    note = note_for_camera("wicker-park")
    assert note is not None
    assert note["context"]["example_data"] is True
    assert note["severity"] == "not sure"
    assert note["engine_count"] == "No verified vehicle count"
    assert note["engine"]["unique_count"] is None
    assert note["paid_call"] is False
