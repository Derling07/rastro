"""Contrato estable result.json (schema 1.1) para web/ y CORE (supabase)."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.1"

REQUIRED_KEYS = [
    "schema_version",
    "run_id",
    "source_video_id",
    "created_at",
    "pack",
    "video",
    "station",
    "local_hour",
    "naive_count",
    "unique_count",
    "by_class",
    "cost_usd",
    "counts",
    "tracks",
    "frames",
    "events",
    "alerts",
    "voice",
    "agent_log",
    "report",
    "artifacts",
    "cost",
    "sam",
    "is_mock",
]


def make_run_id(pack_id: str, video_stem: str, when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    safe_pack = pack_id.replace("/", "-")
    safe_stem = video_stem.replace("/", "-")
    return f"{safe_pack}-{safe_stem}-{stamp}"


def source_video_id_from_path(video_path: str | Path) -> str:
    """Id estable del video para comparar paquetes (stem sin extensión)."""
    return Path(video_path).stem


def frames_from_tracks(tracks: Iterable[Any], *, fps: float) -> list[dict[str, Any]]:
    """Por cuadro: bboxes + track_id. Sin máscaras (esas van en annotated.mp4)."""
    by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for t in tracks:
        tid = getattr(t, "track_id", None) or t.get("track_id")
        cls = getattr(t, "class_name", None) or t.get("class") or t.get("class_name")
        dets = getattr(t, "detections", None) or t.get("detections") or []
        for d in dets:
            if hasattr(d, "box"):
                frame = d.frame
                b = d.box
                bbox = [float(b.x1), float(b.y1), float(b.x2), float(b.y2)]
                cls_d = d.class_name
            else:
                frame = int(d["frame"])
                box = d["box"]
                bbox = [float(box["x1"]), float(box["y1"]), float(box["x2"]), float(box["y2"])]
                cls_d = d.get("class_name") or cls
            by_frame[frame].append(
                {"track_id": tid, "class": cls_d or cls, "bbox": bbox}
            )
    out: list[dict[str, Any]] = []
    for frame in sorted(by_frame):
        out.append(
            {
                "frame": frame,
                "t_s": round(frame / fps, 4) if fps else float(frame),
                "objects": by_frame[frame],
            }
        )
    return out


def normalize_voice_payload(voice: dict[str, Any] | None) -> dict[str, Any] | None:
    """Asegura turns con speaker, start_s, end_s."""
    if voice is None:
        return None
    turns_out = []
    for t in voice.get("turns") or []:
        if "start_s" in t and "end_s" in t:
            start_s = float(t["start_s"])
            end_s = float(t["end_s"])
        else:
            start_s = float(t.get("start_ms") or 0) / 1000.0
            end_s = float(t.get("end_ms") or 0) / 1000.0
        turns_out.append(
            {
                "turn_id": t.get("turn_id", t.get("turnId", 0)),
                "speaker": t.get("speaker"),
                "start_s": round(start_s, 3),
                "end_s": round(end_s, 3),
                "transcript": t.get("transcript") or "",
            }
        )
    out = dict(voice)
    out["turns"] = turns_out
    if "is_mock" not in out:
        out["is_mock"] = bool(out.get("mock", False))
    # Opcional: nota de campo pública (default false)
    out["is_public"] = bool(out.get("is_public", False))
    return out


def build_result(
    *,
    run_id: str,
    source_video_id: str,
    pack_id: str,
    pack_version: str,
    pack_path: str,
    video_path: str,
    track_fps: float,
    native_fps: float,
    station: str,
    local_hour: int | None,
    naive_count: int,
    unique_count: int,
    by_class: dict[str, int],
    tracks: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    events: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    voice: dict[str, Any] | None,
    agent_log: list[dict[str, Any]],
    report: dict[str, Any],
    artifacts: dict[str, str | None],
    cost: dict[str, float],
    sam: list[dict[str, Any]],
    is_mock: bool,
    created_at: str | None = None,
    density: list[dict[str, Any]] | None = None,
    peak_density: dict[str, Any] | None = None,
    persons_per_zone: dict[str, int] | None = None,
    sampling_mode: str | None = None,
    partial: bool | None = None,
    max_objects_hit: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Arma el dict canónico schema 1.1 (compatible CORE/supabase).

    Campos aditivos 1.1: density[] / peak_density / persons_per_zone (multitudes);
    partial / max_objects_hit (tránsito / tope SAM 16 objetos).
    """
    est_sam = float(cost.get("est_usd_sam") or 0.0)
    est_voice = float(cost.get("est_usd_voice") or 0.0)
    est_total = float(cost.get("est_usd_total") or (est_sam + est_voice))
    voice_n = normalize_voice_payload(voice)
    # Asegurar t_s en cada alerta
    alerts_out = []
    for a in alerts:
        aa = dict(a)
        if "t_s" not in aa:
            aa["t_s"] = float(aa.get("t_s") or 0.0)
        alerts_out.append(aa)

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "source_video_id": source_video_id,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "pack": {"id": pack_id, "version": pack_version, "path": pack_path},
        "video": {
            "path": video_path,
            "fps": float(track_fps),
            "native_fps": float(native_fps),
        },
        "station": station,
        "local_hour": local_hour,
        # CORE / supabase planos
        "naive_count": int(naive_count),
        "unique_count": int(unique_count),
        "detections_total": int(sum(int(m.get("n_detections") or 0) for m in (sam or []))),
        "by_class": dict(by_class),
        "cost_usd": round(est_total, 6),
        "counts": {
            "naive": int(naive_count),
            "unique": int(unique_count),
            "by_class": dict(by_class),
        },
        "tracks": tracks,
        "frames": frames,
        "events": events,
        "alerts": alerts_out,
        "voice": voice_n,
        "agent_log": list(agent_log),
        "report": report,
        "artifacts": artifacts,
        "cost": {
            "est_usd_sam": est_sam,
            "est_usd_voice": est_voice,
            "est_usd_total": est_total,
        },
        "sam": sam,
        "is_mock": bool(is_mock),
    }
    # Campos aditivos 1.1 (multitudes): opcionales para no romper fauna
    if sampling_mode is not None:
        out["sampling_mode"] = sampling_mode
    if density is not None:
        out["density"] = list(density)
    if peak_density is not None:
        out["peak_density"] = peak_density
    if persons_per_zone is not None:
        out["persons_per_zone"] = dict(persons_per_zone)
    # Aditivos tránsito / tope SAM 16
    if partial is not None:
        out["partial"] = bool(partial)
    if max_objects_hit is not None:
        out["max_objects_hit"] = list(max_objects_hit)
    return out


def write_result(out_dir: Path, result: dict[str, Any]) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "result.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def validate_result_keys(result: dict[str, Any]) -> list[str]:
    return [k for k in REQUIRED_KEYS if k not in result]
