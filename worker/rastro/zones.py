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


def _samples(track: Track, polygon: list[list[float]], fps: float) -> list[tuple[float, bool, float, float]]:
    """Each detection as (t_s, inside, foot_x, foot_y). The test uses the foot point."""
    if fps <= 0 or not track.detections:
        return []
    rows: list[tuple[float, bool, float, float]] = []
    for det in track.detections:
        nx, ny = foot_norm(det.box)
        rows.append((det.frame / fps, point_in_polygon(nx, ny, polygon), nx, ny))
    rows.sort(key=lambda row: row[0])
    return rows


def _segments(
    samples: list[tuple[float, bool, float, float]],
    sustain_frames: int,
) -> list[dict[str, Any]]:
    """Inside/outside spans. A blip shorter than sustain_frames does not flip a confirmed side."""
    if not samples:
        return []
    raw: list[dict[str, Any]] = []
    flag = samples[0][1]
    chunk = [samples[0]]
    for row in samples[1:]:
        if row[1] != flag:
            raw.append({"inside": flag, "rows": chunk})
            flag = row[1]
            chunk = [row]
        else:
            chunk.append(row)
    raw.append({"inside": flag, "rows": chunk})
    if sustain_frames <= 1:
        return raw
    merged: list[dict[str, Any]] = []
    for seg in raw:
        if not merged:
            merged.append(seg)
            continue
        prev = merged[-1]
        if seg["inside"] == prev["inside"]:
            prev["rows"].extend(seg["rows"])
            continue
        # A confirmed side ignores a shorter burst on the other side.
        if len(prev["rows"]) >= sustain_frames and len(seg["rows"]) < sustain_frames:
            continue
        merged.append(seg)
    return merged


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


def _confidence(held_frames: int, required_frames: int) -> float:
    """Rule confidence from how long the side held. Not a model score."""
    extra = max(0, held_frames - max(1, required_frames))
    return round(min(0.95, 0.7 + 0.05 * extra), 2)


def _trigger_at(rows: list[tuple[float, bool, float, float]], t_s: float) -> dict[str, float]:
    row = min(rows, key=lambda item: abs(item[0] - t_s))
    return {"x": round(row[2], 4), "y": round(row[3], 4), "t_s": round(t_s, 4)}


def sustained_zone_alerts(
    tracks: list[Track],
    zone: dict[str, Any],
    *,
    fps: float,
    sustain_s: float = 3.0,
    sustain_frames: int = 1,
    local_hhmm: str = "06:41",
) -> list[dict[str, Any]]:
    """Wild entry, farm exit, and person-in-zone.

    The foot point is tested against the polygon. A side must hold for
    sustain_s seconds and, when sustain_frames > 1, for that many samples.
    A shorter blip does not flip a side that already held.
    """
    polygon = zone.get("polygon") or []
    frames_needed = max(1, int(sustain_frames))
    if len(polygon) < 3 or sustain_s < 0:
        return []
    zone_id = str(zone.get("id") or "zone")
    fired: list[dict[str, Any]] = []
    for track in tracks:
        segments = _segments(_samples(track, polygon, fps), frames_needed)
        cls = track.class_name

        def _ready(seg: dict[str, Any]) -> tuple[float, int] | None:
            rows = seg["rows"]
            if len(rows) < frames_needed:
                return None
            start = rows[0][0]
            end = rows[-1][0]
            nth = rows[frames_needed - 1][0]
            if _span(start, end) + 1e-9 < sustain_s:
                return None
            at = max(start + sustain_s, nth)
            if at > end + 1e-6:
                return None
            return at, len(rows)

        if cls in WILD:
            for seg in segments:
                ready = _ready(seg) if seg["inside"] else None
                if ready is None:
                    continue
                at, held = ready
                nx_ny = _trigger_at(seg["rows"], at)
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
                        "sustain_frames": frames_needed,
                        "confidence": _confidence(held, frames_needed),
                        "trigger": nx_ny,
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
            for seg in segments:
                if seg["inside"]:
                    if len(seg["rows"]) >= frames_needed:
                        seen_inside = True
                    continue
                if not seen_inside:
                    continue
                ready = _ready(seg)
                if ready is None:
                    continue
                at, held = ready
                fired.append(
                    {
                        "id": f"farm_leaves:{track.track_id}",
                        "kind": "farm_leaves",
                        "severity": "high",
                        "message": "Animal left the safe zone",
                        "t_s": round(at, 4),
                        "zone": zone_id,
                        "class": cls,
                        "track_id": track.track_id,
                        "sustain_s": sustain_s,
                        "sustain_frames": frames_needed,
                        "confidence": _confidence(held, frames_needed),
                        "trigger": _trigger_at(seg["rows"], at),
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
            for seg in segments:
                ready = _ready(seg) if seg["inside"] else None
                if ready is None:
                    continue
                at, held = ready
                clock = _clock(local_hhmm, at)
                alert = {
                    "id": f"person_in_zone:{zone_id}:{round(at, 1)}",
                    "kind": "person_in_zone",
                    "severity": "high",
                    "message": "Possible person inside the protected area — review needed",
                    "label": "Possible. A person reviews. Rastro does not notify authorities.",
                    "t_s": round(at, 4),
                    "zone": zone_id,
                    "class": "person",
                    "local_time": clock,
                    "sustain_s": sustain_s,
                    "sustain_frames": frames_needed,
                    "confidence": _confidence(held, frames_needed),
                    "trigger": _trigger_at(seg["rows"], at),
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
