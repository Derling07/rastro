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
    assert alert["message"] == "Possible person inside the protected area — review needed"
    assert "hunter" not in alert["message"].lower()
    assert alert["label"] == "Possible. A person reviews. Rastro does not notify authorities."
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


def test_farm_pack_and_real_cameras():
    pack = load_pack("farm")
    assert pack.id == "farm-pen"
    assert pack.alerts[0]["sustain_s"] == 3
    assert pack.privacy["identity"] is False
    reset_camera_state()
    fox = get_camera("gray-fox")
    goats = get_camera("goat-lane")
    assert fox is not None and goats is not None
    assert fox["recorded"] is True and fox["video_url"]
    assert fox["verification"] == "PASS"
    assert any(alert["kind"] == "wild_enters" for alert in fox["alerts"])
    assert any(alert["kind"] == "farm_leaves" for alert in goats["alerts"])
    alert_id = fox["alerts"][0]["id"]
    updated = decide("gray-fox", alert_id, "confirm")
    saved = next(alert for alert in updated["alerts"] if alert["id"] == alert_id)
    assert saved["status"] == "confirmed"
    redrawn = set_zone("gray-fox", [[0.0, 0.0], [0.05, 0.0], [0.05, 0.05], [0.0, 0.05]])
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
    camera = get_camera("forest-trail")
    assert camera is not None
    assert camera["verification"] == "PASS"
    assert camera["actions"] == ["review"]
    assert len(camera["alerts"]) == 1
    alert = camera["alerts"][0]
    assert alert["message"] == "Possible person inside the protected area — review needed"
    assert "hunter" not in json.dumps(alert).lower()
    assert alert["label"] == "Possible. A person reviews. Rastro does not notify authorities."
    assert alert["authorities"] is False
    assert alert["snapshot"]["blurred"] is True
    blob = json.dumps(alert)
    assert "track_id" not in alert
    assert "name" not in blob
    try:
        decide("forest-trail", alert["id"], "confirm")
        raise AssertionError("confirm must not be allowed")
    except ValueError:
        pass
    updated = decide("forest-trail", alert["id"], "review")
    saved = updated["alerts"][0]
    assert saved["status"] == "reviewed"
    reset_camera_state()


def test_one_frame_does_not_alert_and_a_blip_does_not_flip():
    lone = track_at("goat-1", "goat", _inside(4) + _outside(1))
    assert sustained_zone_alerts(
        [lone], {"id": "pen", "polygon": PEN}, fps=1, sustain_s=0, sustain_frames=3
    ) == []
    noisy = track_at("goat-1", "goat", _inside(5) + _outside(1) + _inside(4))
    assert sustained_zone_alerts(
        [noisy], {"id": "pen", "polygon": PEN}, fps=1, sustain_s=0, sustain_frames=3
    ) == []
    entered = track_at("coyote-1", "coyote", _outside(2) + _inside(4))
    wild = sustained_zone_alerts(
        [entered], {"id": "pen", "polygon": PEN}, fps=1, sustain_s=0, sustain_frames=3
    )
    assert len(wild) == 1 and wild[0]["kind"] == "wild_enters"
    assert wild[0]["confidence"] >= 0.7
    assert "x" in wild[0]["trigger"] and "y" in wild[0]["trigger"]
    left = track_at("goat-2", "goat", _inside(4) + _outside(4))
    farm = sustained_zone_alerts(
        [left], {"id": "pen", "polygon": PEN}, fps=1, sustain_s=0, sustain_frames=3
    )
    assert len(farm) == 1
    assert farm[0]["message"] == "Animal left the safe zone"
    assert farm[0]["severity"] == "high"
    assert farm[0]["track_id"] == "goat-2"
    person = track_at("hidden", "person", _outside(2) + _inside(4))
    guarded = sustained_zone_alerts(
        [person], {"id": "ridge", "polygon": PEN}, fps=1, sustain_s=0, sustain_frames=3
    )
    assert len(guarded) == 1
    assert guarded[0]["message"] == "Possible person inside the protected area — review needed"
    assert guarded[0]["authorities"] is False
    assert "hidden" not in json.dumps(guarded[0])
    assert "track_id" not in guarded[0]


def test_farm_and_protected_cameras_reach_the_inbox():
    reset_camera_state()
    from rastro.cameras import inbox

    goats = get_camera("goat-lane")
    trail = get_camera("forest-trail")
    assert goats is not None and trail is not None
    assert goats["video_url"].endswith("goats.mp4")
    assert trail["video_url"].endswith("person-trail.mp4")
    farm_alerts = [alert for alert in goats["alerts"] if alert["kind"] == "farm_leaves"]
    assert farm_alerts, "Goat lane did not show a sustained exit"
    assert farm_alerts[0]["message"] == "Animal left the safe zone"
    near = min(goats["frames"], key=lambda row: abs(row["t_s"] - farm_alerts[0]["t_s"]))
    ids = [obj.get("track_id") for obj in near["objects"]]
    assert farm_alerts[0]["track_id"] in ids
    assert len(ids) == len(set(ids))
    assert all("track_id" not in obj for frame in trail["frames"] for obj in frame["objects"])
    assert farm_alerts[0]["severity"] == "high"
    assert farm_alerts[0]["snapshot"]["boxes"]
    person_alerts = trail["alerts"]
    assert len(person_alerts) == 1
    assert person_alerts[0]["message"] == "Possible person inside the protected area — review needed"
    assert person_alerts[0]["snapshot"]["blurred"] is True
    rows = inbox()
    farm_row = next(row for row in rows if row["camera_id"] == "goat-lane" and row["kind"] == "farm_leaves")
    person_row = next(row for row in rows if row["camera_id"] == "forest-trail")
    assert farm_row["severity"] == "high"
    assert farm_row["message"] == "Animal left the safe zone"
    assert person_row["severity"] == "not sure"
    assert person_row["message"].startswith("Possible person")
    assert "hunter" not in person_row["message"].lower()
    reset_camera_state()


def test_alert_set_marks_missing_clips_not_verified():
    manifest = json.loads((ROOT / "eval" / "alert_set" / "manifest.json").read_text())
    by_id = {row["id"]: row for row in manifest["alerts"]}
    assert by_id["wild_enters"]["status"] == "PASS"
    assert by_id["farm_leaves"]["status"] == "PASS"
    assert by_id["person_in_zone"]["status"] == "PASS"
    assert by_id["crowd_plaza"]["status"] == "PASS"
    assert by_id["traffic_wicker"]["status"] == "NOT VERIFIED"
