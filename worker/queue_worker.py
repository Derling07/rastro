"""Worker de la cola de Rastro (corre en la PC de ORION).

Reclama un trabajo, baja el video de Storage, corre `rastro run`, sube el
result.json con ingest_run y cierra el trabajo. Variables de entorno:
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (nunca se imprimen).

Uso:  python worker/queue_worker.py            # bucle
      python worker/queue_worker.py --once     # un solo trabajo
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    """Carga KEY=VALUE de un .env local (no commiteado) sin pisar variables ya puestas."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class Supabase:
    def __init__(self, url: str, key: str, session: requests.Session | None = None):
        self.url = url.rstrip("/")
        self.s = session or requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {key}", "apikey": key})

    def rpc(self, fn: str, args: dict):
        r = self.s.post(f"{self.url}/rest/v1/rpc/{fn}", json=args, timeout=60)
        r.raise_for_status()
        return r.json() if r.content else None

    def check(self) -> dict:
        """Verifica conexión sin tocar datos: cuenta trabajos en cola y revisa el bucket."""
        r = self.s.get(f"{self.url}/rest/v1/jobs", params={"select": "id", "status": "eq.queued"},
                       headers={"Prefer": "count=exact", "Range": "0-0"}, timeout=30)
        r.raise_for_status()
        queued = r.headers.get("Content-Range", "*/0").split("/")[-1]
        b = self.s.get(f"{self.url}/storage/v1/bucket/videos", timeout=30)
        return {"rest": "ok", "queued": queued, "bucket_videos": "ok" if b.ok else f"HTTP {b.status_code}"}

    def download(self, storage_path: str, dest: Path) -> None:
        with self.s.get(f"{self.url}/storage/v1/object/{storage_path}", stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)


def run_engine(pack_id: str, video: Path, out_dir: Path) -> dict:
    cmd = [sys.executable, "-m", "rastro", "run", "--pack", pack_id,
           "--video", str(video), "--out", str(out_dir)]
    env = {**os.environ, "PYTHONPATH": str(REPO / "worker")}
    p = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, timeout=1800)
    if p.returncode != 0:
        raise RuntimeError(f"rastro run falló ({p.returncode}): {p.stderr[-1500:]}")
    return json.loads((out_dir / "result.json").read_text(encoding="utf-8"))


def process_one(sb: Supabase, worker_name: str, engine=run_engine) -> bool:
    """Devuelve True si procesó un trabajo, False si la cola estaba vacía."""
    jobs = sb.rpc("claim_job", {"worker_name": worker_name}) or []
    if not jobs:
        return False
    job = jobs[0]
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            video = tmp / Path(job["storage_path"]).name
            sb.rpc("set_job_stage", {"job": job["id"], "new_stage": "descargando"})
            sb.download(job["storage_path"], video)
            out = REPO / "outputs" / f"job-{job['id']}"
            sb.rpc("set_job_stage", {"job": job["id"], "new_stage": "motor"})
            result = engine(job["pack_id"], video, out)
            sb.rpc("set_job_stage", {"job": job["id"], "new_stage": "guardando"})
            run_uuid = sb.rpc("ingest_run", {"payload": result})
        sb.rpc("finish_job", {"job": job["id"], "ok": True, "run": run_uuid, "err": None})
    except Exception as e:  # noqa: BLE001 — cualquier fallo vuelve a la cola o queda failed
        sb.rpc("finish_job", {"job": job["id"], "ok": False, "run": None, "err": str(e)})
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--check", action="store_true", help="Solo probar la conexión")
    ap.add_argument("--env-file", default=str(REPO / "worker" / ".env"))
    a = ap.parse_args(argv)
    load_env_file(Path(a.env_file))
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY.", file=sys.stderr)
        return 2
    sb, name = Supabase(url, key), f"orion@{socket.gethostname()}"
    if a.check:
        print(json.dumps(sb.check()))  # nunca imprime la clave
        return 0
    while True:
        did = process_one(sb, name)
        if a.once:
            return 0
        if not did:
            time.sleep(a.interval)


if __name__ == "__main__":
    raise SystemExit(main())
