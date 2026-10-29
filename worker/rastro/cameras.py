"""Recorded cameras: a real clip counted once, then played back with alerts at t_s.

Nothing here is a live stream. Verification is PASS only when eval/alert_set
says the local detector matched a hand label.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .types import Box, Detection, Track
from .zones import sustained_zone_alerts

_zones: dict[str, list[list[float]]] = {}
_status: dict[str, str] = {}


def reset_camera_state() -> None:
    _zones.clear()
    _status.clear()


def _apply_status(camera_id: str, alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for alert in alerts:
        row = dict(alert)
        row["status"] = _status.get(f"{camera_id}:{alert['id']}", "open")
        out.append(row)
    return out


def _real_specs() -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parent / "real_clips.json"
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("cameras") or [])


def _tracks(frames: list[dict[str, Any]], classes: set[str], width: float, height: float) -> list[Track]:
    tracks: list[Track] = []
    next_id = 1
    limit = max(width, height) * 0.28
    for frame in frames:
        t_s = float(frame["t_s"])
        fresh: list[tuple[str, Box]] = []
        for obj in frame.get("objects") or []:
            if classes and obj.get("class") not in classes:
                continue
            x1, y1, x2, y2 = [float(v) for v in obj["bbox"]]
            fresh.append((str(obj["class"]), Box(x1, y1, x2, y2, width, height)))
        used: set[int] = set()
        for track in tracks:
            if not track.detections:
                continue
            last = track.detections[-1]
            if abs(last.frame / 100.0 - t_s) > 1.6:
                continue
            best = None
            best_dist = 1e9
            for index, (cls, box) in enumerate(fresh):
                if index in used or cls != track.class_name:
                    continue
                dist = ((box.cx - last.box.cx) ** 2 + (box.cy - last.box.cy) ** 2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best = index
            if best is not None and best_dist < limit:
                used.add(best)
                cls, box = fresh[best]
                track.detections.append(
                    Detection(frame=int(round(t_s * 100)), object_id=0, box=box, class_name=cls)
                )
        for index, (cls, box) in enumerate(fresh):
            if index in used:
                continue
            tracks.append(
                Track(
                    track_id=f"{cls}-{next_id}",
                    class_name=cls,
                    detections=[
                        Detection(frame=int(round(t_s * 100)), object_id=0, box=box, class_name=cls)
                    ],
                )
            )
            next_id += 1
    return [track for track in tracks if len(track.detections) >= 2]


def _extent(frames: list[dict[str, Any]]) -> tuple[float, float]:
    width, height = 1.0, 1.0
    for frame in frames:
        for obj in frame.get("objects") or []:
            box = obj.get("bbox") or [0, 0, 0, 0]
            width = max(width, float(box[2]))
            height = max(height, float(box[3]))
    return width, height


def _real_camera(spec: dict[str, Any]) -> dict[str, Any]:
    camera_id = spec["id"]
    classes = set(spec.get("keep_classes") or [])
    frames_out: list[dict[str, Any]] = []
    for frame in spec.get("frames") or []:
        objects = []
        for obj in frame.get("objects") or []:
            if classes and obj.get("class") not in classes:
                continue
            row: dict[str, Any] = {"class": obj["class"], "bbox": obj["bbox"]}
            if not spec.get("strip_ids"):
                row["track_id"] = str(obj["class"])
            objects.append(row)
        frames_out.append({"frame": frame["frame"], "t_s": frame["t_s"], "objects": objects})
    zone_spec = spec.get("zone") or None
    polygon = _zones.get(camera_id)
    if polygon is None and zone_spec:
        polygon = zone_spec.get("polygon")
    alerts: list[dict[str, Any]] = []
    if polygon and spec.get("sustain_s") is not None:
        width = float(spec.get("width") or 0) or _extent(frames_out)[0]
        height = float(spec.get("height") or 0) or _extent(frames_out)[1]
        alerts = sustained_zone_alerts(
            _tracks(frames_out, classes, width, height),
            {"id": (zone_spec or {}).get("id") or "zone", "polygon": polygon},
            fps=100,
            sustain_s=float(spec["sustain_s"]),
            local_hhmm=str(spec.get("local_hhmm") or "12:00"),
        )
        for alert in alerts:
            if alert["kind"] == "wild_enters":
                alert["message"] = f"Wild animal stayed in the marked zone for {float(spec['sustain_s']):g} s"
            elif alert["kind"] == "farm_leaves":
                alert["message"] = f"Farm animal left the yard and stayed out {float(spec['sustain_s']):g} s"
    return {
        "id": camera_id,
        "name": spec["name"],
        "site": spec["site"],
        "module": spec["module"],
        "simulated": False,
        "recorded": True,
        "video_url": spec.get("video_url"),
        "verified": bool(spec.get("verified")),
        "verification": spec.get("verification") or "NOT VERIFIED",
        "verification_note": spec.get("verification_note") or "",
        "headline": spec.get("headline") or spec["name"],
        "duration_s": float(spec.get("duration_s") or 0),
        "fps": float(spec.get("sample_fps") or 1),
        "sustain_s": spec.get("sustain_s"),
        "zone": None if not polygon else {"id": (zone_spec or {}).get("id") or "zone", "polygon": polygon},
        "zone_editable": bool(spec.get("zone_editable")),
        "frame_width": float(spec.get("width") or 1000),
        "frame_height": float(spec.get("height") or 1000),
        "frames": frames_out,
        "alerts": _apply_status(camera_id, alerts),
        "actions": list(spec.get("actions") or []),
        "credit": spec.get("credit") or {},
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
        "simulated": False,
        "recorded": True,
        "video_url": None,
        "verified": True,
        "verification": "STORED RUN",
        "verification_note": "Stored SAM 3.1 run of a Seattle(ish) camera-trap clip. The server did not call the model again. 90 raw detections → 2 unique coyotes.",
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
                    "notify": "in_app",
                    "snapshot": {"t_s": 1.2, "blurred": False, "boxes": []},
                }
            ],
        ),
        "actions": [],
        "credit": {
            "title": "DSCF0112, Seattle(ish) Camera Traps",
            "author": "Dan Morris",
            "license": "Community Data License Agreement, permissive variant",
            "license_url": "https://cdla.dev/permissive-2-0/",
            "source_url": "https://lila.science/datasets/seattleish-camera-traps/",
        },
    }


def camera_catalog() -> list[dict[str, Any]]:
    cameras = [_real_camera(spec) for spec in _real_specs()]
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
                "simulated": camera.get("simulated", False),
                "recorded": camera.get("recorded", False),
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
        raise ValueError("this camera has no zone to draw")
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
    outcomes = {"confirm": "confirmed", "dismiss": "dismissed", "review": "reviewed"}
    if action not in outcomes:
        raise ValueError("action must be confirm, dismiss, or review")
    if action not in camera.get("actions", []):
        raise ValueError("this camera does not use that action")
    known = {alert["id"] for alert in camera["alerts"]}
    if alert_id not in known:
        raise ValueError("unknown alert")
    _status[f"{camera_id}:{alert_id}"] = outcomes[action]
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
