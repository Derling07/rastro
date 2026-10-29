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


def test_upload_mp4_runs_mock_engine():
    job = api.create_upload_job("fauna-camtrap", "clip.mp4", "video/mp4", b"\x00" * 64)
    done = _wait(job["id"], timeout=60)
    assert done["status"] == "done", done.get("error")
    result = api.get_result(job["id"])["result"]
    assert result["is_mock"] is True
    assert result["unique_count"] >= 1
    assert result["report"]["resumen"]


def test_upload_rejects_unknown_pack_and_empty_file():
    with pytest.raises(ValueError):
        api.create_upload_job("nope", "a.mp4", "video/mp4", b"abc")
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


def test_history_lists_finished_job():
    job = api.create_sample_job("fauna-trap")
    done = _wait(job["id"])
    assert done["status"] == "done"
    rows = api.list_jobs()
    match = next(row for row in rows if row["id"] == job["id"])
    assert match["status"] == "done"
    assert match["is_mock"] is True
    assert match["naive_count"] > match["unique_count"]
