"""One field note per clip. Engine numbers stay fixed. Muse Spark is not called here.

DSCF0112 reuses the report already stored from Muse Spark Open
(meta-models/muse-spark-open-1026). Other modules use the rules engine.
Nothing in this module opens a network connection or reads an API key.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
STORED_0112 = REPO / "web" / "public" / "runs" / "demo-real-coyote-0112" / "result.json"

_status: dict[str, str] = {}


def reset_field_notes() -> None:
    _status.clear()


def _load_0112() -> dict[str, Any]:
    return json.loads(STORED_0112.read_text(encoding="utf-8"))


def engine_count_line(engine: dict[str, Any], noun: str) -> str:
    """Build the count from engine fields only. Ignore any prose."""
    detections = engine.get("detections_total")
    unique = engine.get("unique_count")
    if isinstance(detections, int) and isinstance(unique, int):
        return f"{detections} raw detections → {unique} unique {noun}"
    if isinstance(unique, int):
        return f"{unique} unique {noun}"
    return "No verified count"


def assemble_note(
    *,
    note_id: str,
    module: str,
    title: str,
    engine: dict[str, Any],
    noun: str,
    summary: str,
    source: str,
    model: str | None,
    recorded: bool,
    sam_saw: str,
    sam_on_this_request: bool,
    rule: str,
    context_lines: list[str],
    example_data: bool,
    confidence: str,
    actions: list[str],
    crop: dict[str, Any] | None,
) -> dict[str, Any]:
    """Copy engine facts through. Severity is 'not sure' when confidence is low."""
    facts = {
        "detections_total": engine.get("detections_total"),
        "naive_count": engine.get("naive_count"),
        "unique_count": engine.get("unique_count"),
        "by_class": dict(engine.get("by_class") or {}),
    }
    not_sure = confidence == "low"
    severity = "not sure" if not_sure else "info"
    if not not_sure and module in {"farm", "protected"}:
        severity = "high"
    count = engine_count_line(facts, noun)
    why_sam = (
        f"SAM 3.1 saw {sam_saw}. The engine count is {count}. "
        "That number is copied from the engine, not read out of the summary."
    )
    if not sam_on_this_request and source != "baseten-spark":
        why_sam = (
            f"This request did not call SAM. The stored label is {sam_saw}. "
            f"The engine count on screen is {count}."
        )
    return {
        "id": note_id,
        "module": module,
        "title": title,
        "paid_call": False,
        "live_call": False,
        "sam_called_on_this_request": False,
        "source": source,
        "model": model,
        "recorded": recorded,
        "sam_saw": sam_saw,
        "crop": crop,
        "engine": facts,
        "engine_count": count,
        "context": {
            "example_data": example_data,
            "label": "Example data" if example_data else "Measured",
            "lines": context_lines,
        },
        "summary": summary,
        "summary_label": "Muse Spark summary",
        "why": {"sam": why_sam, "rule": rule},
        "severity": severity,
        "not_sure": not_sure,
        "confidence": confidence,
        "status": _status.get(note_id, "open"),
        "actions": list(actions),
    }


def _crop(result: dict[str, Any], class_name: str) -> dict[str, Any] | None:
    width = 0.0
    height = 0.0
    found: dict[str, Any] | None = None
    for frame in result.get("frames") or []:
        for obj in frame.get("objects") or []:
            box = obj.get("bbox") or []
            if len(box) < 4:
                continue
            width = max(width, float(box[2]))
            height = max(height, float(box[3]))
            if found is None and str(obj.get("class")) == class_name:
                found = {
                    "class": class_name,
                    "bbox": [float(v) for v in box[:4]],
                    "t_s": frame.get("t_s"),
                }
    if not found:
        return None
    found["width"] = width or 1.0
    found["height"] = height or 1.0
    found["pixels"] = False
    return found


def note_dscf0112() -> dict[str, Any]:
    """Hero note. Prose is the stored Muse Spark report. Counts come from the engine."""
    result = _load_0112()
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    engine = {
        "detections_total": result.get("detections_total"),
        "naive_count": result.get("naive_count"),
        "unique_count": result.get("unique_count"),
        "by_class": result.get("by_class") or {},
    }
    summary = str(report.get("resumen") or "").strip()
    return assemble_note(
        note_id="clip:DSCF0112",
        module="fauna",
        title="Camera trap",
        engine=engine,
        noun="coyotes",
        summary=summary,
        source=str(report.get("_source") or "recorded"),
        model=report.get("_spark_model"),
        recorded=True,
        sam_saw="coyote",
        sam_on_this_request=False,
        rule=(
            "Rule: re-entry stitch (tracking.count_unique). "
            "A repeat appearance stays one individual. "
            "Eval on this clip is PASS. The sample is small."
        ),
        context_lines=[
            "Stored SAM 3.1 run of DSCF0112. Opening this note did not call SAM or Muse Spark.",
            "The summary text was recorded earlier from Muse Spark Open. It is not a new reply.",
        ],
        example_data=False,
        confidence="high",
        actions=["confirm", "dismiss"],
        crop=_crop(result, "coyote"),
    )


def _camera_crop(camera: dict[str, Any]) -> dict[str, Any] | None:
    for frame in camera.get("frames") or []:
        for obj in frame.get("objects") or []:
            box = obj.get("bbox") or []
            if len(box) < 4:
                continue
            return {
                "class": obj.get("class"),
                "bbox": [float(v) for v in box[:4]],
                "t_s": frame.get("t_s"),
                "width": float(camera.get("frame_width") or 1000),
                "height": float(camera.get("frame_height") or 1000),
                "pixels": False,
                "blurred": camera.get("module") == "protected" or obj.get("class") == "person",
            }
    return None


def note_for_camera(camera_id: str) -> dict[str, Any] | None:
    from .cameras import get_camera

    camera = get_camera(camera_id)
    if camera is None:
        return None
    module = str(camera.get("module") or "fauna")
    verified = bool(camera.get("verified"))
    alerts = list(camera.get("alerts") or [])
    primary = alerts[0] if alerts else {}
    kind = str(primary.get("kind") or "")
    low = (not verified) or kind == "person_in_zone" or module in {"traffic", "crowd"}
    if module == "farm" and verified:
        low = False
    if module == "fauna" and camera_id == "trap-dscf0112":
        note = note_dscf0112()
        note["id"] = "camera:trap-dscf0112"
        note["status"] = _status.get(note["id"], "open")
        return note
    noun = {
        "farm": "animals",
        "protected": "people",
        "crowd": "people",
        "traffic": "vehicles",
        "fauna": "individuals",
    }.get(module, "individuals")
    engine: dict[str, Any] = {
        "detections_total": None,
        "naive_count": None,
        "unique_count": None,
        "by_class": {},
    }
    if module == "crowd" and isinstance(camera.get("headline"), str):
        # The headline is the stored local-detector sentence. Do not parse a new number.
        engine = {"detections_total": None, "naive_count": None, "unique_count": None, "by_class": {}}
    summary = _local_summary(camera, primary, low)
    rule = _rule_line(camera, primary)
    example = (not verified) or module in {"traffic", "crowd"}
    lines = [str(camera.get("verification_note") or "").strip() or "No extra context."]
    if example:
        lines.append("Example data where a live count was not established. Weather and map context were not added.")
    else:
        lines.append("No weather or map context was added.")
    lines.append("Simulated camera. This is a recorded clip, not a live stream.")
    actions = list(camera.get("actions") or ["confirm", "dismiss"])
    if kind == "person_in_zone":
        actions = ["review"]
    note = assemble_note(
        note_id=f"camera:{camera_id}",
        module=module,
        title=str(camera.get("name") or camera_id),
        engine=engine,
        noun=noun,
        summary=summary,
        source="local-rules",
        model=None,
        recorded=False,
        sam_saw=str(primary.get("class") or kind or camera.get("name")),
        sam_on_this_request=False,
        rule=rule,
        context_lines=[line for line in lines if line],
        example_data=example,
        confidence="low" if low else "high",
        actions=actions,
        crop=_camera_crop(camera),
    )
    if module == "farm":
        note["engine_count"] = "Sustained zone alert. Unique count was not computed on this clip."
    elif module == "protected":
        note["engine_count"] = "Person box. No identity."
    elif module == "traffic":
        note["engine_count"] = "No verified vehicle count"
    elif module == "crowd":
        note["engine_count"] = "No people/m² on this clip"
    return note


def _local_summary(camera: dict[str, Any], alert: dict[str, Any], low: bool) -> str:
    module = str(camera.get("module") or "")
    if module in {"traffic", "crowd"}:
        return (
            "Muse Spark was not called. Confidence is low, so the severity is not sure. "
            "A person decides. This note does not add a vehicle total or a density."
        )
    message = str(alert.get("message") or "No alert on this clip.")
    if low:
        return (
            f"{message} Muse Spark was not called. "
            "Confidence is low, so the severity is not sure. A person decides."
        )
    return (
        f"{message} Muse Spark was not called. "
        "The rules engine raised this from the stored boxes. A person still confirms it."
    )


def _rule_line(camera: dict[str, Any], alert: dict[str, Any]) -> str:
    kind = str(alert.get("kind") or "")
    sustain = camera.get("sustain_s")
    if kind == "person_in_zone":
        return (
            "Rule: a person who stays inside the zone raises an in-app alert. "
            "No name, no face id, no notice to authorities. A person presses Review."
        )
    if kind in {"wild_enters", "farm_leaves"}:
        return (
            f"Rule: the animal must stay in or out of the zone for {sustain:g} seconds "
            "before the alert opens. Confirm or dismiss stays in the app."
            if isinstance(sustain, (int, float))
            else "Rule: zone alert after a sustained stay. Confirm or dismiss stays in the app."
        )
    if camera.get("module") == "traffic":
        return "Rule: traffic counts stay not verified until a labeled clip exists. Nothing is sent to a routing app."
    if camera.get("module") == "crowd":
        return "Rule: one density alert, at 6 people/m², and only when an area in square metres exists. This clip has no area, so that alert is not raised."
    return "Rule: the stored count is shown as-is."


def get_note(note_id: str) -> dict[str, Any] | None:
    if note_id in {"DSCF0112", "clip:DSCF0112"}:
        return note_dscf0112()
    if note_id.startswith("camera:"):
        return note_for_camera(note_id.split(":", 1)[1])
    if note_id.startswith("clip:"):
        if note_id.split(":", 1)[1] == "DSCF0112":
            return note_dscf0112()
        return None
    return note_for_camera(note_id)


def decide_note(note_id: str, action: str) -> dict[str, Any]:
    note = get_note(note_id)
    if note is None:
        raise ValueError("unknown note")
    outcomes = {"confirm": "confirmed", "dismiss": "dismissed", "review": "reviewed"}
    if action not in outcomes:
        raise ValueError("action must be confirm, dismiss, or review")
    if action not in note["actions"]:
        raise ValueError("this note does not use that action")
    _status[note["id"]] = outcomes[action]
    updated = get_note(note["id"])
    assert updated is not None
    if action in {"confirm", "review"}:
        from .feeds import enqueue_webhook

        enqueue_webhook(
            {
                "note_id": updated["id"],
                "module": updated["module"],
                "status": updated["status"],
                "severity": updated["severity"],
                "engine": updated["engine"],
                "engine_count": updated["engine_count"],
            }
        )
    return updated
