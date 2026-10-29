"""Each recorded camera may only carry boxes and a video from its own clip."""

from __future__ import annotations

from rastro.cameras import get_camera, reset_camera_state

OWN = {
    "gray-fox": {
        "video": "/cameras/gray-fox.mp4",
        "classes": {"fox"},
    },
    "goat-lane": {
        "video": "/cameras/goats.mp4",
        "classes": {"goat"},
    },
    "forest-trail": {
        "video": "/cameras/person-trail.mp4",
        "classes": {"person"},
    },
    "plaza-mayor": {
        "video": "/cameras/plaza.mp4",
        "classes": {"person"},
    },
    "wicker-park": {
        "video": "/cameras/wicker.mp4",
        "classes": {"car", "bus", "truck", "motorcycle", "bicycle"},
    },
}


def _classes(camera: dict) -> set[str]:
    found: set[str] = set()
    for frame in camera["frames"]:
        for obj in frame["objects"]:
            found.add(obj["class"])
    return found


def _first_box(camera: dict):
    for frame in camera["frames"]:
        if frame["objects"]:
            return frame["t_s"], tuple(frame["objects"][0]["bbox"]), frame["objects"][0]["class"]
    return None


def test_each_camera_frames_belong_only_to_its_clip():
    reset_camera_state()
    videos = []
    signatures = []
    for camera_id, expect in OWN.items():
        camera = get_camera(camera_id)
        assert camera is not None
        assert camera["id"] == camera_id
        assert camera["video_url"] == expect["video"]
        classes = _classes(camera)
        assert classes, camera_id
        assert classes <= expect["classes"], (camera_id, classes)
        videos.append(camera["video_url"])
        signatures.append(_first_box(camera))
    assert len(videos) == len(set(videos))
    assert len(signatures) == len(set(signatures))

    trail = get_camera("forest-trail")
    assert trail is not None
    blob = str(trail["frames"]) + str(trail["alerts"]) + str(trail["video_url"])
    for foreign in ("goat", "fox", "gray-fox", "goats.mp4", "coyote"):
        assert foreign not in blob
    assert trail["video_url"].endswith("person-trail.mp4")
    assert all(alert["snapshot"]["blurred"] is True for alert in trail["alerts"])
    assert all("track_id" not in alert for alert in trail["alerts"])
