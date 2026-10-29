from pathlib import Path

from rastro.result_schema import (
    SCHEMA_VERSION,
    build_result,
    validate_result_keys,
    write_result,
    frames_from_tracks,
)
from rastro.pipeline import run_pipeline
from rastro.types import Box, Detection, Track


def test_build_result_has_required_keys_v11(tmp_path: Path):
    r = build_result(
        run_id="r1",
        source_video_id="clip",
        pack_id="fauna-camtrap",
        pack_version="0.4.0",
        pack_path="packs/fauna.json",
        video_path="x.mp4",
        track_fps=5,
        native_fps=5,
        station="norte",
        local_hour=21,
        naive_count=1,
        unique_count=1,
        by_class={"coyote": 1},
        tracks=[],
        frames=[],
        events=[],
        alerts=[{"id": "a", "severity": "info", "message": "m", "t_s": 0.0}],
        voice={
            "transcript": "hola",
            "turns": [{"turn_id": 0, "start_ms": 100, "end_ms": 2000, "speaker": "A", "transcript": "hola"}],
        },
        agent_log=[{"step": 1, "tool": "x", "detail": "y"}],
        report={"titulo": "t"},
        artifacts={"annotated_video": None},
        cost={"est_usd_sam": 0.01, "est_usd_voice": 0, "est_usd_total": 0.01},
        sam=[],
        is_mock=True,
    )
    assert validate_result_keys(r) == []
    assert r["schema_version"] == SCHEMA_VERSION == "1.1"
    assert r["is_mock"] is True
    assert r["naive_count"] == 1
    assert r["unique_count"] == 1
    assert r["cost_usd"] == 0.01
    assert r["source_video_id"] == "clip"
    assert r["voice"]["turns"][0]["start_s"] == 0.1
    assert r["voice"]["turns"][0]["end_s"] == 2.0
    assert r["voice"]["is_public"] is False
    assert r["alerts"][0]["t_s"] == 0.0
    assert "agent_log" in r
    path = write_result(tmp_path, r)
    assert path.exists()


def test_frames_have_bbox_not_masks():
    t = Track(
        track_id="coyote-1",
        class_name="coyote",
        detections=[
            Detection(
                frame=3,
                object_id=0,
                box=Box(10, 20, 30, 40, 100, 200),
                class_name="coyote",
            )
        ],
    )
    frames = frames_from_tracks([t], fps=5.0)
    assert frames[0]["frame"] == 3
    assert frames[0]["t_s"] == 0.6
    obj = frames[0]["objects"][0]
    assert obj["track_id"] == "coyote-1"
    assert obj["bbox"] == [10.0, 20.0, 30.0, 40.0]
    assert "mask" not in obj


def test_pipeline_writes_result_json_v11(tmp_path: Path):
    src = Path("data/lila5fps/DSCF0104.mp4")
    if not src.exists():
        return
    out = tmp_path / "run1"
    bundle = run_pipeline(
        pack="fauna",
        video=src,
        out_dir=out,
        mock_sam=True,
        use_spark=False,
        concepts=["coyote"],
        station="norte",
        local_hour=23,
        annotate=False,
        blur=False,
    )
    r = bundle["result"]
    assert (out / "result.json").exists()
    assert r["schema_version"] == "1.1"
    assert r["source_video_id"] == "DSCF0104"
    assert r["is_mock"] is True
    assert "naive_count" in r and "unique_count" in r and "cost_usd" in r
    assert isinstance(r["frames"], list)
    assert all("t_s" in a for a in r["alerts"])
    assert isinstance(r["agent_log"], list)
    assert len(r["agent_log"]) >= 1


def test_voice_is_public_default_and_override():
    from rastro.result_schema import normalize_voice_payload

    base = {"transcript": "x", "turns": []}
    assert normalize_voice_payload(base)["is_public"] is False
    assert normalize_voice_payload({**base, "is_public": True})["is_public"] is True
    assert normalize_voice_payload({**base, "is_public": 0})["is_public"] is False


def test_pipeline_voice_public_flag(tmp_path: Path):
    src = Path("data/lila5fps/DSCF0104.mp4")
    wav = Path("data/probe/nota_campo_es.wav")
    if not src.exists() or not wav.exists():
        return
    out = tmp_path / "voice-pub"
    bundle = run_pipeline(
        pack="fauna",
        video=src,
        out_dir=out,
        mock_sam=True,
        use_spark=False,
        concepts=["coyote"],
        voice_wav=wav,
        voice_public=True,
        annotate=False,
        blur=False,
    )
    assert bundle["result"]["voice"]["is_public"] is True
