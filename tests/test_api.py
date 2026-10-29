"""Local demo API: sample and upload jobs finish in mock mode without keys."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from rastro import api


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("RASTRO_JOBS_DIR", str(tmp_path))
    monkeypatch.setenv("RASTRO_STAGE_SLEEP", "0")
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("RASTRO_ALLOW_LIVE", raising=False)
    monkeypatch.setenv("RASTRO_RETRY_SLEEP", "0")
    api.reset_state()
    yield
    api.reset_state()


def _wait(job_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = api.get_job(job_id)
        assert last is not None
        if last["status"] in {"done", "failed"}:
            return last
        time.sleep(0.02)
    raise AssertionError(f"job stuck: {last}")


def test_health_is_mock_without_keys():
    body = api.health()
    assert body["ok"] is True
    assert body["mock_mode"] is True
    assert body["keys_configured"] == {"meta": False, "baseten": False, "supabase": False}
    assert body["supabase_queue"] is False


def test_fauna_trap_reidentifies_and_labels_mock():
    job = api.create_sample_job("fauna-trap")
    done = _wait(job["id"])
    assert done["status"] == "done", done.get("error")
    envelope = api.get_result(job["id"])
    assert envelope is not None
    result = envelope["result"]
    assert result["is_mock"] is True
    assert envelope["mock_mode"] is True
    assert result["naive_count"] > result["unique_count"]
    assert envelope["reidentifies"] is True
    identities = envelope["identities"]
    assert any(row["reidentified"] for row in identities)
    extra = sum(len(row["sightings"]) - 1 for row in identities)
    assert extra == result["naive_count"] - result["unique_count"]
    assert "Mock" in envelope["hint"]
    line = (
        f"{result['detections_total']} raw detections → {result['unique_count']} unique"
    )
    assert result["report"]["gancho_demo"].startswith(line)
    assert line in result["report"]["resumen"]


def test_stored_dscf0112_replays_measured_counts():
    job = api.create_sample_job("stored-dscf0112")
    done = _wait(job["id"])
    assert done["status"] == "done", done.get("error")
    result = api.get_result(job["id"])["result"]
    assert result["detections_total"] == 90
    assert result["unique_count"] == 2
    assert result["naive_count"] == 2
    assert result["is_mock"] is False
    assert result["report"]["titulo"]
    assert "DSCF0112" in result["report"]["titulo"] or "coyote" in result["report"]["titulo"].lower()


@pytest.mark.parametrize(
    "sample_id",
    ["fauna-trap", "transito-intersection", "multitudes-plaza"],
)
def test_engine_samples_return_counts_and_report(sample_id):
    job = api.create_sample_job(sample_id)
    done = _wait(job["id"], timeout=60)
    assert done["status"] == "done", done.get("error")
    envelope = api.get_result(job["id"])
    result = envelope["result"]
    assert isinstance(result["unique_count"], int)
    assert isinstance(result["naive_count"], int)
    assert result["naive_count"] >= result["unique_count"]
    assert result["is_mock"] is True
    report = result["report"]
    assert report.get("titulo")
    assert report.get("resumen")
    assert envelope["mock_mode"] is True
    assert envelope["hint"]


def _ftyp(brand: bytes = b"isom") -> bytes:
    payload = brand + b"\x00\x00\x00\x00" + brand
    return (8 + len(payload)).to_bytes(4, "big") + b"ftyp" + payload


def test_upload_in_mock_mode_is_not_counted_as_the_sample(monkeypatch):
    monkeypatch.setattr(api, "video_duration_s", lambda _path: 2.0)
    job = api.create_upload_job("fauna-camtrap", "fake.mp4", "video/mp4", _ftyp())
    done = _wait(job["id"], timeout=60)
    assert done["status"] == "done", done.get("error")
    envelope = api.get_result(job["id"])
    result = envelope["result"]
    assert envelope["uncomputed"] is True
    assert result["is_mock"] is True
    assert result["unique_count"] == 0
    assert result["naive_count"] == 0
    assert result["report"]["gancho_demo"] == "Sample result, not from your video"


def test_upload_rejects_bad_bytes_and_long_videos(monkeypatch, tmp_path):
    with pytest.raises(api.UploadError):
        api.create_upload_job("fauna", "clip.mp4", "video/mp4", b"\x00" * 64)
    monkeypatch.setattr(api, "video_duration_s", lambda _path: 121.0)
    with pytest.raises(api.UploadError) as exc:
        api.create_upload_job("fauna", "long.mp4", "video/mp4", _ftyp())
    assert exc.value.status == 400
    assert "120" in str(exc.value)
    assert list(tmp_path.rglob("upload*")) == []


def test_voice_is_checked_before_the_video_is_written(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "video_duration_s", lambda _path: 1.0)
    with pytest.raises(api.UploadError):
        api.create_upload_job(
            "fauna",
            "clip.mp4",
            "video/mp4",
            _ftyp(),
            voice_name="note.wav",
            voice_type="audio/wav",
            voice_body=b"not-a-wav",
        )
    assert list(tmp_path.rglob("*")) == []


def test_restart_marks_inflight_jobs_interrupted():
    folder = api.jobs_dir() / "stuck"
    folder.mkdir()
    (folder / "job.json").write_text(
        json.dumps({"id": "stuck", "status": "processing", "stage": "motor", "pack": "fauna"}),
        encoding="utf-8",
    )
    api.hydrate()
    job = api.get_job("stuck")
    assert job is not None
    assert job["status"] == "failed"
    assert job["error"] == "interrupted"
    disk = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    assert disk["status"] == "failed"


def test_network_errors_retry_then_succeed(monkeypatch):
    calls = {"n": 0}
    real = api._engine_result

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("connection reset")
        return real(*args, **kwargs)

    monkeypatch.setattr(api, "_engine_result", flaky)
    job = api.create_sample_job("fauna-trap")
    done = _wait(job["id"])
    assert done["status"] == "done", done.get("error")
    assert calls["n"] == 2


def test_txt_sent_as_mp4_is_rejected():
    with pytest.raises(api.UploadError) as exc:
        api.create_upload_job("fauna", "notes.txt", "video/mp4", _ftyp())
    assert exc.value.status == 400
    assert ".mp4" in str(exc.value) or ".mov" in str(exc.value)


def test_mock_fail_and_empty_paths():
    failed = _wait(api.create_sample_job("mock-fail")["id"])
    assert failed["status"] == "failed"
    assert "mock failure" in (failed.get("error") or "")
    done = _wait(api.create_sample_job("mock-empty")["id"])
    assert done["status"] == "done", done.get("error")
    envelope = api.get_result(done["id"])
    assert envelope["empty"] is True
    assert envelope["result"]["unique_count"] == 0
    assert envelope["identities"] == []


def test_crowd_report_is_density_only_and_has_no_absolute_path():
    job = api.create_sample_job("multitudes-plaza")
    done = _wait(job["id"], timeout=60)
    assert done["status"] == "done", done.get("error")
    envelope = api.get_result(job["id"])
    report = envelope["result"]["report"]
    assert report["gancho_demo"].startswith("Up to ")
    assert "people/m²" in report["gancho_demo"]
    assert "unique" not in report["resumen"].lower()
    blob = json.dumps(envelope["result"])
    assert "/data/" not in blob
    assert "/tmp/" not in blob
    assert "/workspace/" not in blob
    labels = envelope["result"]["count_labels"]
    assert "not unique people" in labels["naive_count"]
    assert "not a unique-individual count" in labels["unique_count"]
    assert done["sampling_mode"] == "image_sample"
    assert isinstance(done["peak_persons"], int)


def test_transit_report_does_not_call_people_vehicles():
    job = api.create_sample_job("transito-intersection")
    done = _wait(job["id"], timeout=60)
    assert done["status"] == "done", done.get("error")
    report = api.get_result(job["id"])["result"]["report"]
    assert "unique vehicles" in report["gancho_demo"]
    assert "person" in report["gancho_demo"].lower()
    assert done["naive_count"] == 16
    assert done["unique_count"] == 11
    assert done["vehicle_count"] == 10
    blob = json.dumps(report)
    assert "/tmp/" not in blob and "/data/" not in blob
    assert "placeholder" not in report["resumen"]
    assert "Intersection.mp4" in report["resumen"]


def test_upload_rejects_unknown_pack_and_empty_file():
    with pytest.raises(ValueError):
        api.create_upload_job("nope", "a.mp4", "video/mp4", _ftyp())
    with pytest.raises(ValueError):
        api.create_upload_job("fauna", "a.mp4", "video/mp4", b"")


def test_http_roundtrip_sample_job():
    server = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/jobs",
            data=json.dumps({"sample_id": "fauna-trap"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            assert res.status == 201
            created = json.loads(res.read().decode())
        job_id = created["id"]
        deadline = time.time() + 10
        status = "queued"
        while time.time() < deadline and status not in {"done", "failed"}:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/jobs/{job_id}", timeout=5) as res:
                body = json.loads(res.read().decode())
            status = body["status"]
            time.sleep(0.02)
        assert status == "done"
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/jobs/{job_id}/result", timeout=5
        ) as res:
            envelope = json.loads(res.read().decode())
        assert envelope["result"]["is_mock"] is True
        assert envelope["result"]["naive_count"] > envelope["result"]["unique_count"]
        assert any(row["reidentified"] for row in envelope["identities"])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as res:
            health = json.loads(res.read().decode())
        assert health["mock_mode"] is True
    finally:
        server.shutdown()


def test_keys_switch_mock_mode(monkeypatch):
    assert api.mock_mode() is True
    monkeypatch.setenv("META_API_KEY", "not-a-real-key")
    assert api.mock_mode() is False
    monkeypatch.delenv("META_API_KEY")


def test_ui_uploads_only_through_engine():
    from pathlib import Path

    studio = Path(__file__).resolve().parents[1] / "web" / "src" / "components" / "studio" / "Studio.tsx"
    text = studio.read_text(encoding="utf-8")
    assert "/engine/api/jobs" in text
    assert "/api/upload" not in text
    assert "Not verified" in text
    assert "PartialBanner" in text
    assert 'item.status === "queued" || item.status === "processing"' in text
    assert "Up to" in text and "people at once" in text
    assert "busiest frame" not in text
    assert "Mock mode." in text and "Live keys." in text
    assert not (studio.parents[1] / "DemoPanel.tsx").exists()


def test_history_lists_finished_job():
    job = api.create_sample_job("fauna-trap")
    done = _wait(job["id"])
    assert done["status"] == "done"
    rows = api.list_jobs()
    match = next(row for row in rows if row["id"] == job["id"])
    assert match["status"] == "done"
    assert match["is_mock"] is True
    assert match["naive_count"] > match["unique_count"]
