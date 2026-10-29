"""HTTP API and in-process job worker for Rastro.

No keys → mock SAM and a local report. META_API_KEY / BASETEN_API_KEY on an
uploaded video use the live models. Placeholder samples never call a paid API,
because they are not real media. Secrets are never printed.

  python -m rastro.api
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from email import message_from_bytes
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[2]
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_VOICE_BYTES = 32 * 1024 * 1024
MAX_DURATION_S = 120.0
ACCEPTED_TYPES = {"video/mp4": ".mp4", "video/quicktime": ".mov"}
_MP4_BRANDS = {
    b"isom",
    b"iso2",
    b"iso5",
    b"iso6",
    b"mp41",
    b"mp42",
    b"avc1",
    b"mp4v",
    b"M4V ",
    b"MSNV",
    b"dash",
}
_MOV_BRANDS = {b"qt  "}


class UploadError(ValueError):
    """Rejected upload. status is the HTTP code (400 or 413)."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def video_ext_from_bytes(data: bytes, content_type: str, filename: str) -> str:
    """Require a .mp4/.mov name and an ISO BMFF ftyp box. Returns the extension."""
    suffix = Path(filename).suffix.lower()
    if suffix not in {".mp4", ".mov"}:
        raise UploadError("Only .mp4 or .mov files are accepted.", 400)
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype and ctype not in ACCEPTED_TYPES and ctype != "application/octet-stream":
        raise UploadError("Only MP4 or MOV videos are accepted.", 400)
    idx = data.find(b"ftyp")
    if idx < 4 or idx > 64 or idx + 8 > len(data):
        raise UploadError("File is not an MP4 or MOV (missing ftyp).", 400)
    brand = data[idx + 4 : idx + 8]
    if brand in _MOV_BRANDS:
        return ".mov"
    if brand in _MP4_BRANDS:
        return ".mp4"
    raise UploadError("File is not an MP4 or MOV.", 400)


def validate_voice(name: str | None, content_type: str | None, body: bytes | None) -> None:
    """Check a voice note in memory. Call this before writing the video."""
    if body is None:
        return
    if len(body) == 0:
        raise UploadError("Voice note is empty.", 400)
    if len(body) > MAX_VOICE_BYTES:
        raise UploadError("Voice note exceeds 32 MB.", 413)
    suffix = Path(name or "").suffix.lower()
    ctype = (content_type or "").split(";")[0].strip().lower()
    wav = suffix == ".wav" or ctype in {"audio/wav", "audio/x-wav", "audio/wave"}
    mp3 = suffix == ".mp3" or ctype in {"audio/mpeg", "audio/mp3"}
    if not wav and not mp3:
        raise UploadError("Voice note must be WAV or MP3.", 400)
    if key_status()["meta"] and not wav:
        raise UploadError("Live voice notes must be WAV.", 400)
    if wav and (len(body) < 12 or not body.startswith(b"RIFF") or body[8:12] != b"WAVE"):
        raise UploadError("Voice note is not a WAV file.", 400)
    if mp3 and not (body.startswith(b"ID3") or (len(body) >= 2 and body[0] == 0xFF and (body[1] & 0xE0) == 0xE0)):
        raise UploadError("Voice note is not an MP3 file.", 400)


def video_duration_s(path: Path) -> float:
    """Duration in seconds via ffprobe. Raises UploadError if it cannot be read."""
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise UploadError("ffprobe is not installed; cannot check duration.", 400) from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise UploadError("Could not read the video duration.", 400) from exc
    try:
        return float(out.strip())
    except ValueError as exc:
        raise UploadError("Could not read the video duration.", 400) from exc


def _network_error(exc: BaseException) -> bool:
    if isinstance(exc, FileNotFoundError):
        return False
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    module = type(exc).__module__
    if module.startswith(("requests", "httpx", "httpcore", "urllib3")):
        return True
    text = str(exc).lower()
    return any(
        bit in text
        for bit in (
            "timed out",
            "connection reset",
            "connection aborted",
            "temporarily unavailable",
            "name or service not known",
        )
    )


def _retry_sleep() -> float:
    try:
        return max(0.0, float(os.environ.get("RASTRO_RETRY_SLEEP", "0.5")))
    except ValueError:
        return 0.5
PACK_ALIASES = {
    "fauna": "fauna",
    "fauna-camtrap": "fauna",
    "transito": "transito",
    "transito-giros": "transito",
    "multitudes": "multitudes",
    "multitudes-densidad": "multitudes",
}

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_results: dict[str, dict[str, Any]] = {}


def jobs_dir() -> Path:
    raw = os.environ.get("RASTRO_JOBS_DIR") or str(REPO / "outputs" / "api-jobs")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def stage_sleep() -> float:
    try:
        return max(0.0, float(os.environ.get("RASTRO_STAGE_SLEEP", "0.35")))
    except ValueError:
        return 0.35


def _vehicle_count(by_class: Any) -> int | None:
    if not isinstance(by_class, dict):
        return None
    people = {"person", "persona", "people", "pedestrian"}
    return sum(int(count) for name, count in by_class.items() if str(name).lower() not in people)


def key_status() -> dict[str, bool]:
    meta = bool(os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY"))
    baseten = bool(os.environ.get("BASETEN_API_KEY"))
    supabase = bool(
        os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    )
    return {"meta": meta, "baseten": baseten, "supabase": supabase}


def mock_mode() -> bool:
    """Server-level mock: true when Meta and Baseten keys are both absent."""
    keys = key_status()
    return not (keys["meta"] or keys["baseten"])


def samples() -> list[dict[str, Any]]:
    return [
        {
            "id": "fauna-trap",
            "pack": "fauna",
            "kind": "engine",
            "title": "Camera trap",
            "hint": "Mock tracker. A coyote leaves and comes back under a new id.",
        },
        {
            "id": "stored-dscf0112",
            "pack": "fauna",
            "kind": "stored-run",
            "title": "DSCF0112",
            "hint": "Stored SAM run. Two coyotes. Not a new model call.",
        },
        {
            "id": "transito-intersection",
            "pack": "transito",
            "kind": "engine",
            "title": "Intersection",
            "hint": "Mock turns. Not a verified traffic count.",
        },
        {
            "id": "multitudes-plaza",
            "pack": "multitudes",
            "kind": "engine",
            "title": "Plaza",
            "hint": "Mock density. People are not re-identified.",
        },
        {
            "id": "mock-fail",
            "pack": "fauna",
            "kind": "fail",
            "title": "Failing job",
            "hint": "Mock path that fails, so the error state can be tested.",
        },
        {
            "id": "mock-empty",
            "pack": "fauna",
            "kind": "empty",
            "title": "Empty result",
            "hint": "Mock path with no counts, so the empty state can be tested.",
        },
    ]


def _sample(sample_id: str) -> dict[str, Any] | None:
    for item in samples():
        if item["id"] == sample_id:
            return item
    return None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _replay_paths(sample_id: str) -> tuple[Path, Path | None]:
    if sample_id == "stored-dscf0112":
        folder = REPO / "web" / "public" / "runs" / "demo-real-coyote-0112"
        return folder / "result.json", folder / "tracks.json"
    raise FileNotFoundError(sample_id)


def identities_from_tracks(tracks: list[dict[str, Any]], *, fps: float) -> list[dict[str, Any]]:
    """One row per stitched individual. Multiple object ids in a track were re-identified."""
    fps = fps if fps > 0 else 1.0
    rows: list[dict[str, Any]] = []
    for track in tracks:
        dets = list(track.get("detections") or [])
        dets.sort(key=lambda d: int(d.get("frame") or 0))
        sightings: list[dict[str, Any]] = []
        for det in dets:
            oid = det.get("object_id")
            frame = int(det.get("frame") or 0)
            chunk = det.get("chunk_index")
            if sightings and sightings[-1]["object_id"] == oid and sightings[-1].get("chunk_index") == chunk:
                sightings[-1]["end_frame"] = frame
                sightings[-1]["end_s"] = round(frame / fps, 3)
                sightings[-1]["n"] += 1
            else:
                sightings.append(
                    {
                        "object_id": oid,
                        "chunk_index": chunk,
                        "start_frame": frame,
                        "end_frame": frame,
                        "start_s": round(frame / fps, 3),
                        "end_s": round(frame / fps, 3),
                        "n": 1,
                    }
                )
        class_name = track.get("class_name") or track.get("class") or "object"
        rows.append(
            {
                "track_id": track.get("track_id"),
                "class": class_name,
                "start_frame": track.get("start_frame"),
                "end_frame": track.get("end_frame"),
                "start_s": round(int(track.get("start_frame") or 0) / fps, 3),
                "end_s": round(int(track.get("end_frame") or 0) / fps, 3),
                "sightings": sightings,
                "reidentified": len(sightings) > 1,
            }
        )
    return rows


def _sample_clip_name(title: str) -> str:
    """Filename the report should name. Samples have no real media, so the title is the name."""
    name = Path(str(title or "sample")).name.strip() or "sample"
    if not name.lower().endswith((".mp4", ".mov")):
        name = f"{name}.mp4"
    return name


def _placeholder_video(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size < 16:
        dest.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 32)
    return dest


def _engine_result(
    pack: str,
    video: Path,
    out_dir: Path,
    *,
    voice: Path | None,
    voice_public: bool,
    force_mock: bool,
) -> dict[str, Any]:
    from .pipeline import run_pipeline

    keys = key_status()
    mock_sam = True if force_mock or not keys["meta"] else False
    use_spark = bool(keys["baseten"] and not force_mock and not mock_sam)
    bundle = run_pipeline(
        pack=pack,
        video=video,
        out_dir=out_dir,
        mock_sam=mock_sam,
        use_spark=use_spark,
        voice_wav=voice,
        voice_public=voice_public,
        local_hour=22,
        station="demo",
        annotate=False,
        blur=False,
    )
    result = bundle.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("engine returned no result.json")
    return result


def _hint(job: dict[str, Any], result: dict[str, Any]) -> str:
    if result.get("uncomputed"):
        return "Sample result, not from your video"
    if job.get("kind") == "stored-run":
        text = "Stored SAM run. This server did not call the model again."
    elif result.get("is_mock"):
        text = "Mock. Synthetic tracker output, not a field count."
    else:
        text = "Live model run."
    if job.get("pack") == "transito":
        text += " Traffic counts are not verified."
    if result.get("sampling_mode") == "image_sample":
        text += " This pack does not re-identify people."
    return text


def _attach_identities(result: dict[str, Any], tracks_path: Path | None) -> list[dict[str, Any]]:
    if result.get("sampling_mode") == "image_sample":
        return []
    if tracks_path is None or not tracks_path.exists():
        return []
    tracks = _read_json(tracks_path)
    if not isinstance(tracks, list):
        return []
    video = result.get("video") if isinstance(result.get("video"), dict) else {}
    fps = float(video.get("fps") or 5)
    return identities_from_tracks(tracks, fps=fps)


_ABS_PATH = re.compile(r"/[\w.@+-]+(?:/[\w.@+-]+)+")


def _scrub_abs(value: Any) -> Any:
    """Drop absolute filesystem paths before a result leaves the server."""
    if isinstance(value, str):
        return _ABS_PATH.sub(lambda match: Path(match.group(0)).name, value)
    if isinstance(value, list):
        return [_scrub_abs(item) for item in value]
    if isinstance(value, dict):
        return {key: _scrub_abs(item) for key, item in value.items()}
    return value


def uncomputed_upload_result(job_id: str, filename: str) -> dict[str, Any]:
    """Mock mode must not invent counts for a file the tracker did not read."""
    name = Path(filename).name or "upload.mp4"
    line = "Sample result, not from your video"
    return {
        "schema_version": "1.1",
        "run_id": job_id,
        "source_video_id": Path(name).stem,
        "pack": {"id": "upload", "version": "0", "path": ""},
        "video": {"path": name, "fps": 0},
        "naive_count": 0,
        "unique_count": 0,
        "detections_total": None,
        "by_class": {},
        "tracks": [],
        "frames": [],
        "events": [],
        "alerts": [],
        "voice": None,
        "agent_log": [],
        "report": {
            "titulo": line,
            "resumen": "No API key is set, so this file was not tracked. Sample result, not from your video.",
            "gancho_demo": line,
            "recomendaciones": [],
        },
        "artifacts": {},
        "cost_usd": 0,
        "cost": {"est_usd_sam": 0, "est_usd_voice": 0, "est_usd_total": 0},
        "is_mock": True,
        "uncomputed": True,
        "sampling_mode": "video_track",
    }


def empty_result(job_id: str) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "run_id": job_id,
        "source_video_id": "empty",
        "pack": {"id": "fauna-camtrap", "version": "0", "path": "packs/fauna.json"},
        "video": {"path": "empty.mp4", "fps": 5},
        "naive_count": 0,
        "unique_count": 0,
        "detections_total": 0,
        "by_class": {},
        "tracks": [],
        "frames": [],
        "events": [],
        "alerts": [],
        "voice": None,
        "agent_log": [],
        "report": {"titulo": "Empty result", "resumen": "", "gancho_demo": ""},
        "artifacts": {},
        "cost_usd": 0,
        "cost": {"est_usd_sam": 0, "est_usd_voice": 0, "est_usd_total": 0},
        "is_mock": True,
        "empty": True,
        "sampling_mode": "video_track",
    }


def _envelope(
    job: dict[str, Any],
    result: dict[str, Any],
    identities: list[dict[str, Any]],
) -> dict[str, Any]:
    result = _scrub_abs(result)
    crowd = result.get("sampling_mode") == "image_sample" or job.get("pack") == "multitudes"
    if crowd:
        result["count_labels"] = {
            "naive_count": "detection boxes across frames, not unique people",
            "unique_count": "peak people in one frame, not a unique-individual count",
        }
    return {
        "job_id": job["id"],
        "mock_mode": bool(result.get("is_mock")),
        "server_mock": mock_mode(),
        "keys_configured": key_status(),
        "source": job.get("kind"),
        "pack": job.get("pack"),
        "hint": _hint(job, result),
        "reidentifies": not crowd and job.get("kind") != "empty" and not result.get("uncomputed"),
        "empty": bool(result.get("empty") or job.get("kind") == "empty"),
        "uncomputed": bool(result.get("uncomputed")),
        "identities": [] if crowd or job.get("kind") == "empty" or result.get("uncomputed") else identities,
        "result": result,
    }


def _persist_job(job: dict[str, Any]) -> None:
    folder = jobs_dir() / str(job["id"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "job.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")


def _persist_envelope(job_id: str, envelope: dict[str, Any]) -> None:
    folder = jobs_dir() / job_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "envelope.json").write_text(
        json.dumps(envelope, ensure_ascii=False),
        encoding="utf-8",
    )


def _set_job(job_id: str, **fields: Any) -> dict[str, Any]:
    with _lock:
        job = _jobs[job_id]
        job.update(fields)
        snapshot = dict(job)
    _persist_job(snapshot)
    return snapshot


def _process_once(job_id: str) -> None:
    sleep = stage_sleep()
    current = get_job(job_id) or {}
    job = _set_job(
        job_id,
        status="processing",
        stage="descargando",
        started_at=current.get("started_at") or _now(),
        error=None,
    )
    time.sleep(sleep)
    _set_job(job_id, stage="motor")
    sample = _sample(job["sample_id"]) if job.get("sample_id") else None
    out = jobs_dir() / job_id
    out.mkdir(parents=True, exist_ok=True)
    tracks_path: Path | None = out / "tracks.json"
    if job["kind"] == "fail":
        time.sleep(sleep)
        raise RuntimeError("mock failure")
    if job["kind"] == "empty":
        time.sleep(sleep)
        result = empty_result(job_id)
        tracks_path = None
    elif job["kind"] == "upload" and not key_status()["meta"]:
        time.sleep(sleep)
        result = uncomputed_upload_result(job_id, str(job.get("original_name") or "upload.mp4"))
        tracks_path = None
    elif job["kind"] == "stored-run":
        if sample is None:
            raise RuntimeError("unknown sample")
        time.sleep(sleep)
        result_path, tracks_path = _replay_paths(sample["id"])
        result = dict(_read_json(result_path))
        result["_replayed_from"] = str(result_path.relative_to(REPO))
    else:
        video = Path(job["video_path"])
        if not video.exists():
            raise FileNotFoundError(str(video))
        voice = Path(job["voice_path"]) if job.get("voice_path") else None
        result = _engine_result(
            str(job["pack"]),
            video,
            out,
            voice=voice,
            voice_public=bool(job.get("voice_public")),
            force_mock=bool(job.get("force_mock")),
        )
    identities = _attach_identities(result, tracks_path)
    _set_job(job_id, stage="guardando")
    time.sleep(sleep)
    fresh = get_job(job_id) or job
    envelope = _envelope(fresh, result, identities)
    _persist_envelope(job_id, envelope)
    with _lock:
        _results[job_id] = envelope
    _set_job(
        job_id,
        status="done",
        stage=None,
        run_id=str(result.get("run_id") or job_id),
        finished_at=_now(),
        error=None,
        naive_count=result.get("naive_count"),
        unique_count=result.get("unique_count"),
        detections_total=result.get("detections_total"),
        vehicle_count=_vehicle_count(result.get("by_class")) if job.get("pack") == "transito" else None,
        is_mock=bool(result.get("is_mock")),
        sampling_mode=result.get("sampling_mode"),
        peak_persons=(result.get("peak_density") or {}).get("persons")
        if isinstance(result.get("peak_density"), dict)
        else None,
        peak_density_per_m2=(result.get("peak_density") or {}).get("density_per_m2")
        if isinstance(result.get("peak_density"), dict)
        else None,
    )
    from .peaks import note_finished_run

    note_finished_run(str(job.get("pack") or ""), result)


def _process(job_id: str) -> None:
    """Run a job. Network failures are retried twice, then the job fails."""
    tries = 0
    while True:
        try:
            _process_once(job_id)
            return
        except Exception as exc:  # noqa: BLE001 — keep the server up and show a short error
            if _network_error(exc) and tries < 2:
                tries += 1
                _set_job(
                    job_id,
                    status="processing",
                    stage="descargando",
                    error=f"retry {tries}: {exc}"[:200],
                )
                time.sleep(_retry_sleep())
                continue
            _set_job(job_id, status="failed", stage=None, error=str(exc)[:500], finished_at=_now())
            return


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _start(job: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        _jobs[job["id"]] = job
    _persist_job(job)
    threading.Thread(target=_process, args=(job["id"],), daemon=True).start()
    return dict(job)


def create_sample_job(sample_id: str) -> dict[str, Any]:
    sample = _sample(sample_id)
    if sample is None:
        raise ValueError("unknown sample")
    job_id = uuid.uuid4().hex[:12]
    video_path = None
    # Samples have no real media. Never send the placeholder to a paid API.
    force_mock = sample["kind"] == "engine"
    if force_mock:
        video_path = str(_placeholder_video(jobs_dir() / job_id / _sample_clip_name(sample["title"])))
    job = {
        "id": job_id,
        "status": "queued",
        "stage": None,
        "sample_id": sample_id,
        "kind": sample["kind"],
        "pack": sample["pack"],
        "title": sample["title"],
        "original_name": f"{sample['title']}.mp4",
        "video_path": video_path,
        "voice_path": None,
        "voice_public": False,
        "force_mock": force_mock,
        "run_id": None,
        "error": None,
        "naive_count": None,
        "unique_count": None,
        "is_mock": None,
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
    }
    return _start(job)


def create_upload_job(
    pack: str,
    filename: str,
    content_type: str,
    body: bytes,
    *,
    voice_name: str | None = None,
    voice_type: str | None = None,
    voice_body: bytes | None = None,
    voice_public: bool = False,
) -> dict[str, Any]:
    alias = PACK_ALIASES.get(pack)
    if alias is None:
        raise UploadError("unknown pack", 400)
    if not filename or len(filename) > 200:
        raise UploadError("invalid filename", 400)
    if len(body) <= 0:
        raise UploadError("empty file", 400)
    if len(body) > MAX_UPLOAD_BYTES:
        raise UploadError("file exceeds 50 MB", 413)
    ext = video_ext_from_bytes(body, content_type, filename)
    if voice_name and len(voice_name) > 200:
        raise UploadError("invalid voice filename", 400)
    # Voice is checked before any video bytes are written.
    validate_voice(voice_name, voice_type, voice_body)
    job_id = uuid.uuid4().hex[:12]
    dest = jobs_dir() / job_id / f"upload{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    voice_path = str(dest.parent / "note.wav") if voice_body else None
    try:
        dest.write_bytes(body)
        duration = video_duration_s(dest)
        if duration > MAX_DURATION_S:
            raise UploadError("Video is longer than 120 seconds.", 400)
        if voice_body and voice_path:
            Path(voice_path).write_bytes(voice_body)
    except Exception:
        shutil.rmtree(dest.parent, ignore_errors=True)
        raise
    job = {
        "id": job_id,
        "status": "queued",
        "stage": None,
        "sample_id": None,
        "kind": "upload",
        "pack": alias,
        "title": Path(filename).name,
        "original_name": Path(filename).name,
        "video_path": str(dest),
        "voice_path": voice_path,
        "voice_public": bool(voice_public),
        "force_mock": False,
        "run_id": None,
        "error": None,
        "naive_count": None,
        "unique_count": None,
        "is_mock": None,
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
    }
    return _start(job)


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def list_jobs() -> list[dict[str, Any]]:
    with _lock:
        rows = [dict(job) for job in _jobs.values()]
    rows.sort(key=lambda job: job.get("created_at") or "", reverse=True)
    public = []
    for job in rows:
        public.append(
            {
                "id": job["id"],
                "status": job["status"],
                "stage": job.get("stage"),
                "pack": job.get("pack"),
                "title": job.get("title") or job.get("original_name"),
                "original_name": job.get("original_name"),
                "kind": job.get("kind"),
                "naive_count": job.get("naive_count"),
                "unique_count": job.get("unique_count"),
                "detections_total": job.get("detections_total"),
                "is_mock": job.get("is_mock"),
                "sampling_mode": job.get("sampling_mode"),
                "peak_persons": job.get("peak_persons"),
                "peak_density_per_m2": job.get("peak_density_per_m2"),
                "vehicle_count": job.get("vehicle_count"),
                "error": job.get("error"),
                "created_at": job.get("created_at"),
                "finished_at": job.get("finished_at"),
            }
        )
    return public


def get_result(job_id: str) -> dict[str, Any] | None:
    with _lock:
        found = _results.get(job_id)
        return json.loads(json.dumps(found)) if found else None


def health() -> dict[str, Any]:
    keys = key_status()
    return {
        "ok": True,
        "service": "rastro-api",
        "mock_mode": mock_mode(),
        "keys_configured": keys,
        "supabase_queue": False,
        "note": (
            "Uploads use SAM when META_API_KEY is set and Muse Spark when "
            "BASETEN_API_KEY is set. Sample clips stay on the mock tracker."
        ),
    }


def reset_state() -> None:
    with _lock:
        _jobs.clear()
        _results.clear()


def hydrate() -> None:
    """Load jobs from disk. A restart cannot finish a half-run, so those fail."""
    root = jobs_dir()
    interrupted: list[dict[str, Any]] = []
    with _lock:
        if not root.exists():
            return
        for folder in root.iterdir():
            if not folder.is_dir():
                continue
            job_file = folder / "job.json"
            if not job_file.exists():
                continue
            try:
                job = json.loads(job_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            job_id = str(job.get("id") or folder.name)
            if job.get("status") in {"queued", "processing"}:
                job["status"] = "failed"
                job["stage"] = None
                job["error"] = "interrupted"
                job["finished_at"] = _now()
                interrupted.append(dict(job))
            _jobs[job_id] = job
            env_file = folder / "envelope.json"
            if env_file.exists():
                try:
                    _results[job_id] = json.loads(env_file.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
    for job in interrupted:
        _persist_job(job)


def parse_multipart(body: bytes, content_type: str) -> dict[str, Any]:
    raw = b"MIME-Version: 1.0\r\nContent-Type: " + content_type.encode("utf-8") + b"\r\n\r\n" + body
    msg = message_from_bytes(raw, policy=default)
    if not msg.is_multipart():
        raise ValueError("expected multipart")
    fields: dict[str, str] = {}
    files: dict[str, dict[str, Any]] = {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        data = part.get_payload(decode=True) or b""
        if filename:
            files[name] = {
                "filename": filename,
                "content_type": part.get_content_type(),
                "data": data,
            }
        else:
            fields[name] = data.decode("utf-8", errors="replace").strip()
    return {"fields": fields, "files": files}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_body(self, limit: int) -> bytes:
        length = int(self.headers.get("Content-Length") or "0")
        if length < 0 or length > limit:
            raise UploadError("file exceeds 50 MB", 413)
        return self.rfile.read(length) if length else b""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/health":
            self._send(200, health())
            return
        if path == "/api/samples":
            self._send(200, {"samples": samples(), "mock_mode": mock_mode(), "keys_configured": key_status()})
            return
        if path == "/api/jobs":
            self._send(200, {"jobs": list_jobs()})
            return
        if path == "/api/peaks":
            from .peaks import peak_view

            module = (parse_qs(parsed.query).get("module") or ["crowd"])[0]
            try:
                self._send(200, peak_view(module))
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
            return
        if path == "/api/cameras":
            from .cameras import inbox, list_cameras

            self._send(200, {"cameras": list_cameras(), "inbox": inbox(), "simulated": True})
            return
        parts = [p for p in path.split("/") if p]
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "cameras":
            from .cameras import get_camera

            camera = get_camera(parts[2])
            if not camera:
                self._send(404, {"error": "camera not found"})
                return
            self._send(200, {"camera": camera})
            return
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "jobs":
            job = get_job(parts[2])
            if not job:
                self._send(404, {"error": "job not found"})
                return
            self._send(200, {k: v for k, v in job.items() if k not in {"video_path", "voice_path"}})
            return
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "jobs" and parts[3] == "result":
            job = get_job(parts[2])
            if not job:
                self._send(404, {"error": "job not found"})
                return
            if job["status"] != "done":
                self._send(409, {"error": "job not done", "status": job["status"]})
                return
            result = get_result(parts[2])
            if not result:
                self._send(404, {"error": "result missing"})
                return
            self._send(200, result)
            return
        self._send(404, {"error": "not found"})

    def _camera_post(self, parts: list[str]) -> None:
        from .cameras import decide, set_zone

        try:
            data = json.loads((self._read_body(64_000) or b"{}").decode("utf-8"))
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"})
            return
        camera_id = parts[2]
        try:
            if len(parts) == 4 and parts[3] == "zone":
                camera = set_zone(camera_id, data.get("polygon"))
            elif len(parts) == 5 and parts[3] == "alerts":
                action = data.get("action")
                if not isinstance(action, str):
                    self._send(400, {"error": "action required"})
                    return
                camera = decide(camera_id, parts[4], action)
            else:
                self._send(404, {"error": "not found"})
                return
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
            return
        self._send(200, {"camera": camera})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "cameras":
            self._camera_post(parts)
            return
        if path != "/api/jobs":
            self._send(404, {"error": "not found"})
            return
        ctype = self.headers.get("Content-Type") or ""
        mime = ctype.split(";")[0].strip().lower()
        try:
            if mime == "application/json":
                data = json.loads((self._read_body(64_000) or b"{}").decode("utf-8"))
                sample_id = data.get("sample_id")
                if not isinstance(sample_id, str):
                    self._send(400, {"error": "sample_id required"})
                    return
                job = create_sample_job(sample_id)
            elif mime in ACCEPTED_TYPES or mime == "application/octet-stream":
                qs = parse_qs(parsed.query)
                pack = (qs.get("pack") or [""])[0]
                filename = (qs.get("filename") or ["upload.mp4"])[0]
                raw = self._read_body(MAX_UPLOAD_BYTES)
                job = create_upload_job(
                    pack,
                    filename,
                    mime if mime in ACCEPTED_TYPES else "video/mp4",
                    raw,
                )
            elif mime.startswith("multipart/"):
                form = parse_multipart(self._read_body(MAX_UPLOAD_BYTES + 8_000_000), ctype)
                video = form["files"].get("video")
                if not video:
                    self._send(400, {"error": "video file required"})
                    return
                voice = form["files"].get("voice")
                job = create_upload_job(
                    form["fields"].get("pack") or "",
                    str(video["filename"]),
                    str(video["content_type"] or "video/mp4"),
                    video["data"],
                    voice_name=str(voice["filename"]) if voice else None,
                    voice_type=str(voice["content_type"]) if voice else None,
                    voice_body=voice["data"] if voice else None,
                    voice_public=form["fields"].get("voice_public", "").lower() in {"1", "true", "yes", "on"},
                )
            else:
                self._send(415, {"error": "send JSON {sample_id}, a video body, or multipart"})
                return
        except UploadError as exc:
            self._send(exc.status, {"error": str(exc)})
            return
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
            return
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"})
            return
        self._send(201, {k: v for k, v in job.items() if k not in {"video_path", "voice_path"}})


def serve(host: str | None = None, port: int | None = None) -> None:
    hydrate()
    # Local runs bind localhost. Compose sets RASTRO_BIND=0.0.0.0 so other
    # containers can call http://api:8787, and publishes only 127.0.0.1:8787.
    chosen_host = host or os.environ.get("RASTRO_BIND", "127.0.0.1")
    chosen = port if port is not None else int(os.environ.get("PORT", "8787"))
    httpd = ThreadingHTTPServer((chosen_host, chosen), Handler)
    print(f"rastro-api listening on {chosen_host}:{chosen} mock_mode={mock_mode()}", flush=True)
    httpd.serve_forever()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
