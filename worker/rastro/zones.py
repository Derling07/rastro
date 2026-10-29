"""Zone alerts for a pen or a protected area.

An alert fires only after the animal or person has stayed in or out of the
zone for sustain_s seconds. Person alerts never carry an identity.
"""

from __future__ import annotations

from typing import Any

from .density import point_in_polygon
from .types import Box, Detection, Track

WILD = frozenset({"coyote", "fox", "dog", "wolf", "wild"})
FARM = frozenset({"cow", "cattle", "horse", "sheep", "goat", "chicken", "pig"})
PERSON = frozenset({"person", "persona"})

# Keys that must never be stored on a person alert.
IDENTITY_KEYS = frozenset(
    {
        "identity",
        "person_id",
        "face_id",
        "face",
        "name",
        "embedding",
        "biometric",
        "subject_id",
        "track_id",
    }
)


def foot_norm(box: Box) -> tuple[float, float]:
    """Feet point in 0..1 coordinates: bottom center of the box."""
    w = box.w if box.w else 1.0
    h = box.h if box.h else 1.0
    return (box.x1 + box.x2) / 2.0 / w, box.y2 / h


def _runs(track: Track, polygon: list[list[float]], fps: float) -> list[tuple[bool, float, float]]:
    """Contiguous inside/outside spans. Times are detection timestamps in seconds."""
    if fps <= 0 or not track.detections:
        return []
    points: list[tuple[float, bool]] = []
    for det in track.detections:
        nx, ny = foot_norm(det.box)
        points.append((det.frame / fps, point_in_polygon(nx, ny, polygon)))
    points.sort()
    flag = points[0][1]
    start = points[0][0]
    prev = start
    runs: list[tuple[bool, float, float]] = []
    for t_s, inside in points[1:]:
        if inside != flag:
            runs.append((flag, start, prev))
            flag = inside
            start = t_s
        prev = t_s
    runs.append((flag, start, prev))
    return runs


def _span(start: float, end: float) -> float:
    return max(0.0, end - start)


def _boxes_at(track: Track, t_s: float, fps: float, *, keep_id: bool) -> list[dict[str, Any]]:
    if fps <= 0 or not track.detections:
        return []
    target = t_s * fps
    det = min(track.detections, key=lambda d: abs(d.frame - target))
    box = det.box
    row: dict[str, Any] = {
        "class": track.class_name if track.class_name not in PERSON else "person",
        "bbox": [round(box.x1, 1), round(box.y1, 1), round(box.x2, 1), round(box.y2, 1)],
    }
    if keep_id:
        row["track_id"] = track.track_id
    return [row]


def scrub_identity(value: Any) -> Any:
    """Drop identity fields anywhere in an alert. Person snapshots stay blurred boxes."""
    if isinstance(value, dict):
        return {
            key: scrub_identity(item)
            for key, item in value.items()
            if key.lower() not in IDENTITY_KEYS
        }
    if isinstance(value, list):
        return [scrub_identity(item) for item in value]
    return value


def _clock(base_hhmm: str, t_s: float) -> str:
    """Local HH:MM after adding the clip offset to a station clock."""
    try:
        hour_s, minute_s = base_hhmm.split(":", 1)
        minutes = int(hour_s) * 60 + int(minute_s) + int(t_s // 60)
    except (ValueError, AttributeError):
        minutes = int(t_s // 60)
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def sustained_zone_alerts(
    tracks: list[Track],
    zone: dict[str, Any],
    *,
    fps: float,
    sustain_s: float = 3.0,
    local_hhmm: str = "06:41",
) -> list[dict[str, Any]]:
    """Wild entry, farm exit, and person-in-zone. Each needs a sustain window."""
    polygon = zone.get("polygon") or []
    if len(polygon) < 3 or sustain_s < 0:
        return []
    zone_id = str(zone.get("id") or "zone")
    fired: list[dict[str, Any]] = []
    for track in tracks:
        runs = _runs(track, polygon, fps)
        cls = track.class_name
        if cls in WILD:
            for inside, start, end in runs:
                if inside and _span(start, end) + 1e-9 >= sustain_s:
                    at = start + sustain_s
                    fired.append(
                        {
                            "id": f"wild_enters:{track.track_id}",
                            "kind": "wild_enters",
                            "severity": "emergency",
                            "message": f"Wild animal entered the pen and stayed {sustain_s:g} s",
                            "t_s": round(at, 4),
                            "zone": zone_id,
                            "class": cls,
                            "track_id": track.track_id,
                            "sustain_s": sustain_s,
                            "notify": "in_app",
                            "snapshot": {
                                "t_s": round(at, 4),
                                "blurred": False,
                                "boxes": _boxes_at(track, at, fps, keep_id=True),
                            },
                        }
                    )
                    break
        elif cls in FARM:
            seen_inside = False
            for inside, start, end in runs:
                if inside:
                    seen_inside = True
                    continue
                if seen_inside and _span(start, end) + 1e-9 >= sustain_s:
                    at = start + sustain_s
                    fired.append(
                        {
                            "id": f"farm_leaves:{track.track_id}",
                            "kind": "farm_leaves",
                            "severity": "high",
                            "message": f"Farm animal left the pen and stayed out {sustain_s:g} s",
                            "t_s": round(at, 4),
                            "zone": zone_id,
                            "class": cls,
                            "track_id": track.track_id,
                            "sustain_s": sustain_s,
                            "notify": "in_app",
                            "snapshot": {
                                "t_s": round(at, 4),
                                "blurred": False,
                                "boxes": _boxes_at(track, at, fps, keep_id=True),
                            },
                        }
                    )
                    break
        elif cls in PERSON:
            for inside, start, end in runs:
                if inside and _span(start, end) + 1e-9 >= sustain_s:
                    at = start + sustain_s
                    clock = _clock(local_hhmm, at)
                    alert = {
                        "id": f"person_in_zone:{zone_id}:{round(at, 1)}",
                        "kind": "person_in_zone",
                        "severity": "high",
                        "message": f"Person detected in protected zone at {clock}",
                        "label": "Possible intrusion — needs review",
                        "t_s": round(at, 4),
                        "zone": zone_id,
                        "class": "person",
                        "local_time": clock,
                        "sustain_s": sustain_s,
                        "notify": "in_app",
                        "authorities": False,
                        "snapshot": {
                            "t_s": round(at, 4),
                            "blurred": True,
                            "boxes": _boxes_at(track, at, fps, keep_id=False),
                        },
                    }
                    fired.append(scrub_identity(alert))
                    break
    return fired


def track_at(track_id: str, class_name: str, points: list[tuple[float, float]], *, fps: float = 1.0) -> Track:
    """Build a track whose feet sit on each normalized point, one frame apart."""
    dets: list[Detection] = []
    for index, (nx, ny) in enumerate(points):
        cx = nx * 1000.0
        cy = ny * 1000.0
        dets.append(
            Detection(
                frame=index,
                object_id=index,
                box=Box(x1=cx - 20, y1=cy - 40, x2=cx + 20, y2=cy, w=1000, h=1000),
                class_name=class_name,
            )
        )
    return Track(track_id=track_id, class_name=class_name, detections=dets)
