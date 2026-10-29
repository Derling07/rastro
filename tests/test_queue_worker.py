import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
import queue_worker as qw  # noqa: E402


class FakeSB:
    def __init__(self, jobs):
        self.jobs, self.calls = jobs, []

    def rpc(self, fn, args):
        self.calls.append((fn, args))
        if fn == "claim_job":
            return [self.jobs.pop(0)] if self.jobs else []
        if fn == "ingest_run":
            return "run-uuid"
        return None

    def download(self, path, dest):
        Path(dest).write_bytes(b"fake")


JOB = {"id": "j1", "storage_path": "videos/a.mp4", "pack_id": "fauna-camtrap"}


def test_cola_vacia():
    sb = FakeSB([])
    assert qw.process_one(sb, "t") is False
    assert [c[0] for c in sb.calls] == ["claim_job"]


def test_exito_ingiere_y_cierra():
    sb = FakeSB([dict(JOB)])
    assert qw.process_one(sb, "t", engine=lambda p, v, o: {"run_id": "x", "pack": {"id": p}}) is True
    names = [c[0] for c in sb.calls if c[0] != "set_job_stage"]
    assert names == ["claim_job", "ingest_run", "finish_job"]
    stages = [c[1]["new_stage"] for c in sb.calls if c[0] == "set_job_stage"]
    assert stages == ["descargando", "motor", "guardando"]
    assert sb.calls[-1][1] == {"job": "j1", "ok": True, "run": "run-uuid", "err": None}


def test_fallo_del_motor_cierra_con_error():
    def boom(*_):
        raise RuntimeError("SAM caído")
    sb = FakeSB([dict(JOB)])
    qw.process_one(sb, "t", engine=boom)
    fn, args = sb.calls[-1]
    assert fn == "finish_job" and args["ok"] is False and "SAM caído" in args["err"]
    assert "ingest_run" not in [c[0] for c in sb.calls]


def test_main_sin_claves(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert qw.main(["--once", "--env-file", "/nonexistent"]) == 2


def test_env_file_no_pisa(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("SUPABASE_URL=https://x.supabase.co\n# c\nSUPABASE_SERVICE_ROLE_KEY='k'\n")
    monkeypatch.setenv("SUPABASE_URL", "ya")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    qw.load_env_file(f)
    import os
    assert os.environ["SUPABASE_URL"] == "ya" and os.environ["SUPABASE_SERVICE_ROLE_KEY"] == "k"
