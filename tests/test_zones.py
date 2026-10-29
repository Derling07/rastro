"""Sustain window, zone in/out, and person alerts without identity."""

from __future__ import annotations

import json
from pathlib import Path

from rastro.cameras import decide, get_camera, reset_camera_state, set_zone
from rastro.pack import load_pack
from rastro.zones import IDENTITY_KEYS, scrub_identity, sustained_zone_alerts, track_at

PEN = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
ROOT = Path(__file__).resolve().parents[1]


def _inside(n: int):
    return [(0.5, 0.5) for _ in range(n)]


def _outside(n: int):
    return [(0.05, 0.5) for _ in range(n)]


def test_wild_entry_needs_three_seconds():
    short = track_at("coyote-1", "coyote", _outside(2) + _inside(3))  # inside span = 2s
    assert sustained_zone_alerts([short], {"id": "pen", "polygon": PEN}, fps=1, sustain_s=3) == []
    held = track_at("coyote-1", "coyote", _outside(2) + _inside(5))  # inside span = 4s
    alerts = sustained_zone_alerts([held], {"id": "pen", "polygon": PEN}, fps=1, sustain_s=3)
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "wild_enters"
    assert alerts[0]["severity"] == "emergency"
    assert alerts[0]["t_s"] == 5  # entered at frame 2, plus 3s


def test_farm_exit_needs_three_seconds_outside():
    brief = track_at("goat-1", "goat", _inside(3) + _outside(2))  # outside span = 1s
    assert sustained_zone_alerts([brief], {"id": "pen", "polygon": PEN}, fps=1, sustain_s=3) == []
    gone = track_at("goat-1", "goat", _inside(3) + _outside(5))  # outside span = 4s
    alerts = sustained_zone_alerts([gone], {"id": "pen", "polygon": PEN}, fps=1, sustain_s=3)
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "farm_leaves"
    assert alerts[0]["t_s"] == 6  # left at frame 3, plus 3s


def test_animal_that_stays_inside_does_not_leave():
    cow = track_at("cow-1", "cow", _inside(8))
    assert sustained_zone_alerts([cow], {"id": "pen", "polygon": PEN}, fps=1, sustain_s=3) == []


def test_person_in_zone_has_no_identity_and_is_blurred():
    person = track_at("should-not-leak", "person", _outside(1) + _inside(5))
    alerts = sustained_zone_alerts(
        [person],
        {"id": "ridge", "polygon": PEN},
        fps=1,
        sustain_s=3,
        local_hhmm="06:41",
    )
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["message"].startswith("Person detected in protected zone at ")
    assert alert["label"] == "Possible intrusion — needs review"
    assert alert["authorities"] is False
    assert alert["snapshot"]["blurred"] is True
    blob = json.dumps(alert)
    assert "should-not-leak" not in blob
    assert "track_id" not in alert
    for key in IDENTITY_KEYS:
        assert key not in alert

    dirty = {"name": "Ada", "face_id": "x", "nested": {"identity": 1, "class": "person"}}
    clean = scrub_identity(dirty)
    assert clean == {"nested": {"class": "person"}}


def test_farm_pack_and_seeded_camera_are_not_verified():
    pack = load_pack("farm")
    assert pack.id == "farm-pen"
    assert pack.alerts[0]["sustain_s"] == 3
    assert pack.privacy["identity"] is False
    reset_camera_state()
    camera = get_camera("north-pen")
    assert camera is not None
    assert camera["simulated"] is True
    assert camera["verification"] == "NOT VERIFIED"
    kinds = {alert["kind"] for alert in camera["alerts"]}
    assert kinds == {"wild_enters", "farm_leaves"}
    updated = decide("north-pen", "wild_enters:coyote-1", "confirm")
    saved = next(alert for alert in updated["alerts"] if alert["id"] == "wild_enters:coyote-1")
    assert saved["status"] == "confirmed"
    redrawn = set_zone("north-pen", [[0.0, 0.0], [0.1, 0.0], [0.1, 0.1], [0.0, 0.1]])
    assert redrawn["alerts"] == []
    reset_camera_state()


def test_protected_camera_is_review_only_and_stores_no_identity():
    from rastro.pack import load_pack

    pack = load_pack("protected")
    assert pack.privacy["identity"] is False
    assert pack.privacy["notify_authorities"] is False
    assert "person" in pack.privacy["blur"]
    assert "face" in pack.privacy["blur"]
    reset_camera_state()
    camera = get_camera("ridge-gate")
    assert camera is not None
    assert camera["verification"] == "NOT VERIFIED"
    assert camera["actions"] == ["review"]
    assert len(camera["alerts"]) == 1
    alert = camera["alerts"][0]
    assert alert["message"] == "Person detected in protected zone at 06:41"
    assert alert["label"] == "Possible intrusion — needs review"
    assert alert["authorities"] is False
    assert alert["snapshot"]["blurred"] is True
    blob = json.dumps(alert)
    assert "track_id" not in alert
    assert "name" not in blob
    try:
        decide("ridge-gate", alert["id"], "confirm")
        raise AssertionError("confirm must not be allowed")
    except ValueError:
        pass
    updated = decide("ridge-gate", alert["id"], "review")
    saved = updated["alerts"][0]
    assert saved["status"] == "reviewed"
    reset_camera_state()


def test_alert_set_marks_missing_clips_not_verified():
    manifest = json.loads((ROOT / "eval" / "alert_set" / "manifest.json").read_text())
    by_id = {row["id"]: row for row in manifest["alerts"]}
    assert by_id["wild_enters"]["status"] == "NOT VERIFIED"
    assert by_id["farm_leaves"]["status"] == "NOT VERIFIED"
    assert by_id["wild_enters"]["clip"] is None
    assert by_id["farm_leaves"]["clip"] is None
    assert by_id["person_in_zone"]["status"] == "NOT VERIFIED"
    assert by_id["person_in_zone"]["clip"] is None
