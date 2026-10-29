"""Simulated cameras: a clip counted once, then looped with alerts at t_s.

Nothing here is a live stream. Farm alerts are NOT VERIFIED until a labeled
field clip exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .types import Track
from .zones import sustained_zone_alerts, track_at

FARM_ZONE = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
FARM_SUSTAIN_S = 3.0

_zones: dict[str, list[list[float]]] = {}
_status: dict[str, str] = {}


def reset_camera_state() -> None:
    _zones.clear()
    _status.clear()


def _repeat(point: tuple[float, float], n: int) -> list[tuple[float, float]]:
    return [point for _ in range(n)]


def farm_tracks() -> list[Track]:
    """12 s script. Coyote steps into the pen; a goat steps out. A cow stays."""
    outside = (0.05, 0.5)
    inside = (0.5, 0.5)
    return [
        track_at("cow-1", "cow", _repeat(inside, 12)),
        track_at("coyote-1", "coyote", _repeat(outside, 3) + _repeat(inside, 9)),
        track_at("goat-1", "goat", _repeat(inside, 3) + _repeat(outside, 9)),
    ]


def _frames_from_tracks(tracks: list[Track], fps: float) -> list[dict[str, Any]]:
    by_frame: dict[int, list[dict[str, Any]]] = {}
    for track in tracks:
        for det in track.detections:
            box = det.box
            by_frame.setdefault(det.frame, []).append(
                {
                    "track_id": track.track_id,
                    "class": track.class_name,
                    "bbox": [box.x1, box.y1, box.x2, box.y2],
                }
            )
    frames = []
    for frame in sorted(by_frame):
        frames.append({"frame": frame, "t_s": round(frame / fps, 4), "objects": by_frame[frame]})
    return frames


def _apply_status(camera_id: str, alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for alert in alerts:
        row = dict(alert)
        row["status"] = _status.get(f"{camera_id}:{alert['id']}", "open")
        out.append(row)
    return out


def _farm_camera() -> dict[str, Any]:
    zone = _zones.get("north-pen", FARM_ZONE)
    tracks = farm_tracks()
    alerts = sustained_zone_alerts(
        tracks,
        {"id": "pen", "polygon": zone},
        fps=1.0,
        sustain_s=FARM_SUSTAIN_S,
    )
    return {
        "id": "north-pen",
        "name": "North pen",
        "site": "Farm",
        "module": "farm",
        "simulated": True,
        "verified": False,
        "verification": "NOT VERIFIED",
        "verification_note": "No labeled field clip yet. This loop is a scripted example.",
        "headline": "Draw the pen. A wild animal inside, or a farm animal outside, alerts after 3 seconds.",
        "duration_s": 11.0,
        "fps": 1.0,
        "sustain_s": FARM_SUSTAIN_S,
        "zone": {"id": "pen", "polygon": zone},
        "zone_editable": True,
        "frames": _frames_from_tracks(tracks, 1.0),
        "alerts": _apply_status("north-pen", alerts),
        "actions": ["confirm", "dismiss"],
    }


def _trap_camera() -> dict[str, Any] | None:
    path = Path(__file__).resolve().parents[2] / "web/public/runs/demo-real-coyote-0112/result.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    frames = list(data.get("frames") or [])
    duration = float(frames[-1]["t_s"]) if frames else 0.0
    detections = data.get("detections_total")
    unique = data.get("unique_count")
    headline = (
        f"{detections} raw detections → {unique} unique coyotes"
        if detections is not None and unique is not None
        else "Stored camera-trap count"
    )
    return {
        "id": "trap-dscf0112",
        "name": "Trap line",
        "site": "Camera trap",
        "module": "fauna",
        "simulated": True,
        "verified": True,
        "verification": "STORED RUN",
        "verification_note": "Stored SAM 3.1 run. The server did not call the model again.",
        "headline": headline,
        "duration_s": duration,
        "fps": float((data.get("video") or {}).get("fps") or 5),
        "sustain_s": None,
        "zone": None,
        "zone_editable": False,
        "frames": frames,
        "alerts": _apply_status(
            "trap-dscf0112",
            [
                {
                    "id": "coyote-recorded",
                    "kind": "count",
                    "severity": "info",
                    "message": "Coyote recorded: 2 individuals",
                    "t_s": 1.2,
                    "status": "open",
                    "notify": "in_app",
                    "snapshot": {"t_s": 1.2, "blurred": False, "boxes": []},
                }
            ],
        ),
        "actions": [],
    }


def camera_catalog() -> list[dict[str, Any]]:
    cameras = [_farm_camera()]
    trap = _trap_camera()
    if trap:
        cameras.append(trap)
    return cameras


def list_cameras() -> list[dict[str, Any]]:
    rows = []
    for camera in camera_catalog():
        open_n = sum(1 for alert in camera["alerts"] if alert.get("status") == "open")
        rows.append(
            {
                "id": camera["id"],
                "name": camera["name"],
                "site": camera["site"],
                "module": camera["module"],
                "simulated": True,
                "verified": camera["verified"],
                "verification": camera["verification"],
                "open_alerts": open_n,
                "headline": camera["headline"],
            }
        )
    return rows


def get_camera(camera_id: str) -> dict[str, Any] | None:
    for camera in camera_catalog():
        if camera["id"] == camera_id:
            return camera
    return None


def set_zone(camera_id: str, polygon: list[list[float]]) -> dict[str, Any]:
    camera = get_camera(camera_id)
    if camera is None:
        raise ValueError("unknown camera")
    if not camera.get("zone_editable"):
        raise ValueError("this camera has no pen to draw")
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError("a zone needs at least 3 points")
    clean: list[list[float]] = []
    for point in polygon:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise ValueError("each point is [x, y]")
        x, y = float(point[0]), float(point[1])
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError("points must be between 0 and 1")
        clean.append([round(x, 4), round(y, 4)])
    _zones[camera_id] = clean
    updated = get_camera(camera_id)
    assert updated is not None
    return updated


def decide(camera_id: str, alert_id: str, action: str) -> dict[str, Any]:
    camera = get_camera(camera_id)
    if camera is None:
        raise ValueError("unknown camera")
    if action not in {"confirm", "dismiss"}:
        raise ValueError("action must be confirm or dismiss")
    if action not in camera.get("actions", []):
        raise ValueError("this camera does not use that action")
    known = {alert["id"] for alert in camera["alerts"]}
    if alert_id not in known:
        raise ValueError("unknown alert")
    _status[f"{camera_id}:{alert_id}"] = "confirmed" if action == "confirm" else "dismissed"
    updated = get_camera(camera_id)
    assert updated is not None
    return updated


def inbox() -> list[dict[str, Any]]:
    rows = []
    for camera in camera_catalog():
        for alert in camera["alerts"]:
            rows.append(
                {
                    "camera_id": camera["id"],
                    "camera_name": camera["name"],
                    "site": camera["site"],
                    "verified": camera["verified"],
                    "verification": camera["verification"],
                    **alert,
                }
            )
    rows.sort(key=lambda row: (row.get("status") != "open", row.get("t_s") or 0))
    return rows
