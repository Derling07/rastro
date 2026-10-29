"""HTTP API and in-process job worker for Rastro.

No keys → mock SAM and a local report. META_API_KEY / BASETEN_API_KEY on an
uploaded video use the live models. Placeholder samples never call a paid API,
because they are not real media. Secrets are never printed.

  python -m rastro.api
"""

from __future__ import annotations

import json
import os
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
ACCEPTED_TYPES = {"video/mp4": ".mp4", "video/quicktime": ".mov"}
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


def _envelope(
    job: dict[str, Any],
    result: dict[str, Any],
    identities: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "job_id": job["id"],
        "mock_mode": bool(result.get("is_mock")),
        "server_mock": mock_mode(),
        "keys_configured": key_status(),
        "source": job.get("kind"),
        "pack": job.get("pack"),
        "hint": _hint(job, result),
        "reidentifies": result.get("sampling_mode") != "image_sample",
        "identities": identities,
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


def _process(job_id: str) -> None:
    sleep = stage_sleep()
    try:
        job = _set_job(job_id, status="processing", stage="descargando", started_at=_now(), error=None)
        time.sleep(sleep)
        _set_job(job_id, stage="motor")
        sample = _sample(job["sample_id"]) if job.get("sample_id") else None
        out = jobs_dir() / job_id
        out.mkdir(parents=True, exist_ok=True)
        tracks_path: Path | None = out / "tracks.json"
        if job["kind"] == "stored-run":
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
            is_mock=bool(result.get("is_mock")),
        )
    except Exception as exc:  # noqa: BLE001 — keep the server up and show a short error
        _set_job(job_id, status="failed", stage=None, error=str(exc)[:500], finished_at=_now())


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
        video_path = str(_placeholder_video(jobs_dir() / job_id / "placeholder.mp4"))
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
        raise ValueError("unknown pack")
    if content_type not in ACCEPTED_TYPES and not filename.lower().endswith((".mp4", ".mov")):
        raise ValueError("only mp4 or mov")
    if not filename or len(filename) > 200:
        raise ValueError("invalid filename")
    if len(body) <= 0:
        raise ValueError("empty file")
    if len(body) > MAX_UPLOAD_BYTES:
        raise ValueError("file exceeds 50 MB")
    job_id = uuid.uuid4().hex[:12]
    ext = ACCEPTED_TYPES.get(content_type) or (".mov" if filename.lower().endswith(".mov") else ".mp4")
    dest = jobs_dir() / job_id / f"upload{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    voice_path = None
    if voice_body:
        if voice_name and len(voice_name) > 200:
            raise ValueError("invalid voice filename")
        live_voice = key_status()["meta"]
        suffix = Path(voice_name or "note.wav").suffix.lower()
        if live_voice and suffix != ".wav":
            raise ValueError("live voice notes must be WAV")
        voice_path = str(dest.parent / "note.wav")
        Path(voice_path).write_bytes(voice_body)
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
                "is_mock": job.get("is_mock"),
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
    root = jobs_dir()
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
            _jobs[job_id] = job
            env_file = folder / "envelope.json"
            if env_file.exists():
                try:
                    _results[job_id] = json.loads(env_file.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass


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
            raise ValueError("body too large")
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
        parts = [p for p in path.split("/") if p]
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

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
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
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
            return
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"})
            return
        self._send(201, {k: v for k, v in job.items() if k not in {"video_path", "voice_path"}})


def serve(host: str = "0.0.0.0", port: int | None = None) -> None:
    hydrate()
    chosen = port if port is not None else int(os.environ.get("PORT", "8787"))
    httpd = ThreadingHTTPServer((host, chosen), Handler)
    print(f"rastro-api listening on {host}:{chosen} mock_mode={mock_mode()}", flush=True)
    httpd.serve_forever()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
