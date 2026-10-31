"""One field note per clip. Engine numbers stay fixed. Muse Spark is not called here.

DSCF0112 reuses the report already stored from Muse Spark Open
(meta-models/muse-spark-open-1026). Other modules use the rules engine.
Nothing in this module opens a network connection or reads an API key.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .feeds import state_lock

REPO = Path(__file__).resolve().parents[2]
STORED_0112 = REPO / "web" / "public" / "runs" / "demo-real-coyote-0112" / "result.json"
STATUS_CAP = 50
NO_COUNT = "The engine has no verified count for this clip."

_status: dict[str, str] = {}


def reset_field_notes() -> None:
    with state_lock:
        _status.clear()


def status_key(note_id: str) -> str:
    """DSCF0112 is one clip, whether the caller names the file or the trap camera."""
    if note_id in {"DSCF0112", "clip:DSCF0112", "camera:trap-dscf0112", "trap-dscf0112"}:
        return "clip:DSCF0112"
    return note_id


def summary_label_for(source: str) -> str:
    if source == "baseten-spark":
        return "Muse Spark summary (recorded)"
    return "Rules engine note"


def _load_0112() -> dict[str, Any]:
    return json.loads(STORED_0112.read_text(encoding="utf-8"))


def engine_count_line(engine: dict[str, Any], noun: str) -> str:
    """Build the count from engine fields only. Ignore any prose."""
    detections = engine.get("detections_total")
    unique = engine.get("unique_count")
    if isinstance(detections, int) and isinstance(unique, int):
        return f"{detections} raw detections → {unique} unique {noun}"
    if isinstance(unique, int) and unique > 0:
        return f"{unique} unique {noun}"
    return NO_COUNT


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
    if count == NO_COUNT:
        count_sentence = NO_COUNT
    else:
        count_sentence = f"The engine count is {count}."
    if not sam_on_this_request and source != "baseten-spark":
        why_sam = f"This request did not call SAM. The stored label is {sam_saw}. {count_sentence}"
    else:
        why_sam = (
            f"SAM 3.1 saw {sam_saw}. {count_sentence} "
            "That number is copied from the engine, not read out of the summary."
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
        "summary_label": summary_label_for(source),
        "why": {"sam": why_sam, "rule": rule},
        "severity": severity,
        "not_sure": not_sure,
        "confidence": confidence,
        "status": _status.get(status_key(note_id), "open"),
        "actions": list(actions),
    }


def _frame_size(result: dict[str, Any]) -> tuple[float | None, float | None]:
    video = result.get("video") if isinstance(result.get("video"), dict) else {}
    width = result.get("frame_width")
    height = result.get("frame_height")
    if width is None:
        width = video.get("frame_width", video.get("width"))
    if height is None:
        height = video.get("frame_height", video.get("height"))
    try:
        if width is None or height is None:
            return None, None
        return float(width), float(height)
    except (TypeError, ValueError):
        return None, None


def _crop(result: dict[str, Any], class_name: str) -> dict[str, Any] | None:
    width, height = _frame_size(result)
    found: dict[str, Any] | None = None
    extent_w = 0.0
    extent_h = 0.0
    for frame in result.get("frames") or []:
        for obj in frame.get("objects") or []:
            box = obj.get("bbox") or []
            if len(box) < 4:
                continue
            extent_w = max(extent_w, float(box[2]))
            extent_h = max(extent_h, float(box[3]))
            if found is None and str(obj.get("class")) == class_name:
                found = {
                    "class": class_name,
                    "bbox": [float(v) for v in box[:4]],
                    "t_s": frame.get("t_s"),
                }
    if not found:
        return None
    found["width"] = width if width and width > 0 else (extent_w or 1.0)
    found["height"] = height if height and height > 0 else (extent_h or 1.0)
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
    if camera_id == "trap-dscf0112":
        note = note_dscf0112()
        note["camera_id"] = camera_id
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
        note["why"]["sam"] = "This request did not call SAM. No verified vehicle count."
    elif module == "crowd":
        note["why"]["sam"] = "SAM 3.1 detected people per frame. No re-identification."
        note["engine_count"] = "No people/m² on this clip"
    note["camera_id"] = camera_id
    return note


def _sentence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.endswith((".", "!", "?")):
        cleaned += "."
    return cleaned


def _local_summary(camera: dict[str, Any], alert: dict[str, Any], low: bool) -> str:
    module = str(camera.get("module") or "")
    if module in {"traffic", "crowd"}:
        return (
            "Muse Spark was not called. Confidence is low, so the severity is not sure. "
            "A person decides. This note does not add a vehicle total or a density."
        )
    message = _sentence(str(alert.get("message") or "No alert on this clip."))
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
    if note_id.startswith("run:"):
        from .state import _jobs, _lock, _results

        run_id = note_id.split(":", 1)[1]
        with _lock:
            job = _jobs.get(run_id)
            envelope = _results.get(run_id)
        if not job or job.get("status") != "done" or not isinstance(envelope, dict):
            return None
        return note_for_result(envelope.get("result"), run_id=run_id, pack=job.get("pack"))
    if note_id in {"DSCF0112", "clip:DSCF0112", "camera:trap-dscf0112"}:
        note = note_dscf0112()
        if note_id.startswith("camera:") or note_id == "trap-dscf0112":
            note["camera_id"] = "trap-dscf0112"
        return note
    if note_id.startswith("camera:"):
        return note_for_camera(note_id.split(":", 1)[1])
    if note_id.startswith("clip:"):
        return None
    return note_for_camera(note_id)


def _noun_for(result: dict[str, Any], pack: str | None) -> str:
    if pack == "multitudes" or result.get("sampling_mode") == "image_sample":
        return "people"
    if pack == "transito":
        return "vehicles"
    by_class = result.get("by_class") if isinstance(result.get("by_class"), dict) else {}
    names = [name for name, count in by_class.items() if count]
    if len(names) == 1:
        name = names[0]
        count = by_class[name]
        return name if str(name).endswith("s") or count == 1 else f"{name}s"
    return "individuals"


def note_for_result(result: dict[str, Any] | None, *, run_id: str, pack: str | None) -> dict[str, Any] | None:
    """A note for one finished run. Counts are copied from that result."""
    if not isinstance(result, dict) or result.get("empty"):
        return None
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    source_video = str(result.get("source_video_id") or "")
    recorded = report.get("_source") == "baseten-spark" and source_video == "DSCF0112"
    engine = {
        "detections_total": result.get("detections_total"),
        "naive_count": result.get("naive_count"),
        "unique_count": result.get("unique_count"),
        "by_class": dict(result.get("by_class") or {}),
    }
    source = "baseten-spark" if recorded else "local-rules"
    summary = str(report.get("resumen") or "").strip()
    if not summary:
        summary = "The rules engine finished this run. Muse Spark was not called."
    mock = bool(result.get("is_mock"))
    uncomputed = bool(result.get("uncomputed"))
    low = (not recorded) and (mock or uncomputed or pack == "transito")
    sam_name = _noun_for(result, pack).rstrip("s") if pack != "multitudes" else "person"
    if engine["by_class"]:
        sam_name = next(iter(engine["by_class"]))
    note = assemble_note(
        note_id=f"run:{run_id}",
        module=pack or "fauna",
        title={"fauna": "Camera trap clip", "transito": "Intersection clip", "multitudes": "Crowds"}.get(
            pack or "", "This run"
        ),
        engine=engine,
        noun=_noun_for(result, pack),
        summary=summary,
        source=source,
        model=report.get("_spark_model") if recorded else None,
        recorded=recorded,
        sam_saw=str(sam_name),
        sam_on_this_request=False,
        rule=(
            "Rule: re-entry stitch (tracking.count_unique). The unique count is the engine number."
            if pack not in {"multitudes", "transito"}
            else (
                "Rule: one density alert, at 6 people/m². The peak below is the engine number."
                if pack == "multitudes"
                else "Rule: traffic counts on this run are not a verified survey."
            )
        ),
        context_lines=[
            "Example data. This run used the mock tracker."
            if mock
            else "Measured. Stored run. Opening this note did not call SAM or Muse Spark.",
        ],
        example_data=mock or uncomputed or pack == "transito",
        confidence="low" if low else "high",
        actions=["confirm", "dismiss"],
        crop=_crop(result, str(sam_name)),
    )
    if uncomputed:
        note["engine_count"] = NO_COUNT
    elif pack == "transito":
        note["engine_count"] = "No verified vehicle count"
        note["why"]["sam"] = "This request did not call SAM. No verified vehicle count."
        note["severity"] = "not sure"
        note["not_sure"] = True
    elif pack == "multitudes":
        note["why"]["sam"] = "SAM 3.1 detected people per frame. No re-identification."
        peak = result.get("peak_density") if isinstance(result.get("peak_density"), dict) else {}
        density = peak.get("density_per_m2")
        persons = peak.get("persons")
        if isinstance(density, (int, float)):
            note["engine_count"] = f"Peak {density:g} people/m²"
        elif isinstance(persons, int) and persons != result.get("unique_count"):
            note["engine_count"] = f"Peak {persons} people in one frame"
        else:
            note["engine_count"] = NO_COUNT
    note["run_id"] = run_id
    return note


def decide_note(note_id: str, action: str) -> dict[str, Any]:
    note = get_note(note_id)
    if note is None:
        raise ValueError("unknown note")
    outcomes = {"confirm": "confirmed", "dismiss": "dismissed", "review": "reviewed"}
    if action not in outcomes:
        raise ValueError("action must be confirm, dismiss, or review")
    if action not in note["actions"]:
        raise ValueError("this note does not use that action")
    key = status_key(note["id"])
    desired = outcomes[action]
    with state_lock:
        unchanged = _status.get(key) == desired
        if not unchanged:
            _status.pop(key, None)
            _status[key] = desired
            while len(_status) > STATUS_CAP:
                del _status[next(iter(_status))]
    updated = get_note(note_id)
    assert updated is not None
    if unchanged:
        return updated
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
