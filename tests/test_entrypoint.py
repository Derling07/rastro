"""Confirm must work when the API is started with python -m rastro.api."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_confirm_from_module_entrypoint(tmp_path):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "worker")
    env["PORT"] = str(port)
    env["RASTRO_BIND"] = "127.0.0.1"
    env["RASTRO_STAGE_SLEEP"] = "0"
    env["RASTRO_JOBS_DIR"] = str(tmp_path)
    env.pop("RASTRO_WRITE_TOKEN", None)
    env.pop("META_API_KEY", None)
    env.pop("BASETEN_API_KEY", None)
    proc = subprocess.Popen(
        [sys.executable, "-m", "rastro.api"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            if proc.poll() is not None:
                raise AssertionError(proc.stdout.read() if proc.stdout else "api exited")
            try:
                urllib.request.urlopen(f"{base}/health", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("api did not start")
        req = urllib.request.Request(
            f"{base}/api/jobs",
            data=json.dumps({"sample_id": "stored-dscf0112"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            job = json.loads(res.read().decode())
        job_id = job["id"]
        deadline = time.time() + 20
        status = "queued"
        while time.time() < deadline and status not in {"done", "failed"}:
            with urllib.request.urlopen(f"{base}/api/jobs/{job_id}", timeout=5) as res:
                status = json.loads(res.read().decode())["status"]
            time.sleep(0.05)
        assert status == "done"
        confirm = urllib.request.Request(
            f"{base}/api/field-note",
            data=json.dumps({"id": f"run:{job_id}", "action": "confirm"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(confirm, timeout=5) as res:
            body = json.loads(res.read().decode())
            assert res.status == 200
        assert body["note"]["status"] == "confirmed"
        assert body["note"]["engine_count"].startswith("90 raw detections")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
