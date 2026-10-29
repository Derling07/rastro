"""Recortes por acceso, tope 16 y campos partial / max_objects_hit."""

from __future__ import annotations

import json
from pathlib import Path

from rastro.result_schema import build_result, validate_result_keys
from rastro.transit import (
    DEFAULT_BUDGET_USD,
    SAM_MAX_OBJECTS_PER_FRAME,
    access_rois_from_geometry,
    crop_rect_px,
    filter_detections_in_roi,
    frames_hitting_object_cap,
    remap_detections_to_full,
    wants_access_crops,
)
from rastro.types import Box, Detection


def test_access_rois_from_approaches():
    geom = {
        "approaches": [
            {"id": "acceso_N", "line": [[0.2, 0.05], [0.8, 0.05]]},
            {"id": "acceso_S", "line": [[0.2, 0.95], [0.8, 0.95]]},
            {"id": "acceso_E", "line": [[0.95, 0.2], [0.95, 0.8]]},
            {"id": "acceso_O", "line": [[0.05, 0.2], [0.05, 0.8]]},
        ]
    }
    rois = access_rois_from_geometry(geom)
    cards = [r["cardinal"] for r in rois]
    assert cards == ["N", "S", "E", "O"]
    north = rois[0]
    assert north["y1"] < north["y2"]
    assert north["y2"] <= 0.5  # banda superior


def test_access_rois_from_zone_roi():
    geom = {
        "zones": [
            {"id": "acceso_N", "roi": [0.0, 0.0, 1.0, 0.3]},
        ]
    }
    rois = access_rois_from_geometry(geom)
    assert len(rois) == 4  # completa con defaults
    n = next(r for r in rois if r["cardinal"] == "N")
    assert n["y2"] == 0.3


def test_wants_access_crops():
    assert wants_access_crops({"id": "transito-giros", "metrics": []})
    assert wants_access_crops({"id": "x", "metrics": ["turning_movements"]})
    assert wants_access_crops({"id": "x", "access_crops": True})
    assert not wants_access_crops({"id": "fauna-camtrap", "metrics": ["unique_count"]})


def test_remap_detections_to_full():
    crop = {"x": 100, "y": 50, "w": 400, "h": 300, "full_w": 1280, "full_h": 720}
    d = Detection(
        frame=2,
        object_id=1,
        box=Box(10, 20, 30, 40, 400, 300),
        class_name="car",
        chunk_index=1,
    )
    out = remap_detections_to_full([d], crop)[0]
    assert out.box.x1 == 110
    assert out.box.y1 == 70
    assert out.box.x2 == 130
    assert out.box.y2 == 90
    assert out.box.w == 1280
    assert out.box.h == 720


def test_filter_detections_in_roi():
    roi = {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 0.4}
    top = Detection(
        frame=0,
        object_id=0,
        box=Box(100, 100, 200, 200, 1000, 1000),  # center y=0.15
        class_name="car",
    )
    bottom = Detection(
        frame=0,
        object_id=1,
        box=Box(100, 700, 200, 800, 1000, 1000),  # center y=0.75
        class_name="car",
    )
    kept = filter_detections_in_roi([top, bottom], roi)
    assert [d.object_id for d in kept] == [0]


def test_frames_hitting_object_cap():
    dets = [
        Detection(
            frame=5,
            object_id=i,
            box=Box(0, 0, 1, 1, 100, 100),
            class_name="car",
        )
        for i in range(SAM_MAX_OBJECTS_PER_FRAME)
    ]
    dets.append(
        Detection(
            frame=6,
            object_id=0,
            box=Box(0, 0, 1, 1, 100, 100),
            class_name="car",
        )
    )
    hits = frames_hitting_object_cap(
        dets, fps=5.0, access="N", concept="car"
    )
    assert len(hits) == 1
    assert hits[0]["frame"] == 5
    assert hits[0]["t_s"] == 1.0
    assert hits[0]["n_objects"] == 16
    assert hits[0]["access"] == "N"


def test_crop_rect_px_even():
    roi = {"x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}
    c = crop_rect_px(roi, 1920, 1080)
    assert c["w"] % 2 == 0 and c["h"] % 2 == 0
    assert c["x"] % 2 == 0 and c["y"] % 2 == 0


def test_build_result_emits_partial_and_max_objects_hit():
    r = build_result(
        run_id="r1",
        source_video_id="clip",
        pack_id="transito-giros",
        pack_version="0.1.0",
        pack_path="packs/transito.json",
        video_path="x.mp4",
        track_fps=5,
        native_fps=5,
        station="demo",
        local_hour=12,
        naive_count=0,
        unique_count=0,
        by_class={},
        tracks=[],
        frames=[],
        events=[],
        alerts=[],
        voice=None,
        agent_log=[],
        report={},
        artifacts={},
        cost={"est_usd_sam": 0.02, "est_usd_voice": 0, "est_usd_total": 0.02},
        sam=[],
        is_mock=True,
        partial=True,
        max_objects_hit=[{"t_s": 1.0, "frame": 5, "n_objects": 16, "access": "N"}],
    )
    assert validate_result_keys(r) == []
    assert r["partial"] is True
    assert r["max_objects_hit"][0]["access"] == "N"
    assert DEFAULT_BUDGET_USD == 0.50


def test_pipeline_access_crops_mock(tmp_path: Path):
    from rastro.pipeline import run_pipeline
    from rastro.pack import Pack

    src = Path("data/lila5fps/DSCF0104.mp4")
    if not src.exists():
        # Video mínimo 2 frames para ffprobe; mock no cropea.
        src = tmp_path / "tiny.mp4"
        src.write_bytes(b"not-a-real-mp4")

    pack_path = tmp_path / "transito-test.json"
    pack_path.write_text(
        json.dumps(
            {
                "id": "transito-giros",
                "version": "0.1.0",
                "targets": [{"prompt": "car", "class": "auto"}],
                "sampling": {"fps": 5, "mode": "video_track"},
                "metrics": ["turning_movements"],
                "budget_usd": 0.50,
                "geometry": {
                    "approaches": [
                        {"id": "acceso_N", "line": [[0.2, 0.08], [0.8, 0.08]]},
                        {"id": "acceso_S", "line": [[0.2, 0.92], [0.8, 0.92]]},
                        {"id": "acceso_E", "line": [[0.92, 0.2], [0.92, 0.8]]},
                        {"id": "acceso_O", "line": [[0.08, 0.2], [0.08, 0.8]]},
                    ],
                    "lines": [],
                    "zones": [],
                },
                "dedup": {"reentry_window_s": 20},
                "alerts": [],
                "privacy": {"blur": []},
                "station_defaults": {"station": "demo-transito"},
                "output": {"annotated_video": False, "blurred_video": False},
            }
        ),
        encoding="utf-8",
    )
    # load_pack by path
    out = tmp_path / "run-transito"
    if not Path("data/lila5fps/DSCF0104.mp4").exists():
        # Sin video real el mock igual corre (no cropea con ffmpeg).
        pass
    video = Path("data/lila5fps/DSCF0104.mp4")
    if not video.exists():
        return  # skip soft
    bundle = run_pipeline(
        pack=str(pack_path),
        video=video,
        out_dir=out,
        mock_sam=True,
        use_spark=False,
        annotate=False,
        blur=False,
    )
    r = bundle["result"]
    assert "partial" in r
    assert r["partial"] is False or r["partial"] is True
    assert isinstance(r["max_objects_hit"], list)
    assert any(m.get("mode") == "video_track_access_crop" for m in r["sam"])
    assert any(m.get("access") for m in r["sam"])
    assert r["cost_usd"] <= 0.50 + 1e-6
    # agent log menciona access crops
    assert any(e.get("tool") == "transit.access_crops" for e in r["agent_log"])


def test_pipeline_budget_skip(tmp_path: Path):
    """budget_usd bajo el mínimo por petición → partial + skipped_budget."""
    from rastro.pipeline import run_pipeline

    video = Path("data/lila5fps/DSCF0104.mp4")
    if not video.exists():
        return
    pack_path = tmp_path / "transito-budget.json"
    pack_path.write_text(
        json.dumps(
            {
                "id": "transito-giros",
                "version": "0.1.0",
                "targets": [
                    {"prompt": "car", "class": "auto"},
                    {"prompt": "bus", "class": "bus"},
                ],
                "sampling": {"fps": 5, "mode": "video_track"},
                "metrics": ["turning_movements"],
                "budget_usd": 0.0,
                "geometry": {
                    "approaches": [
                        {"id": "acceso_N", "line": [[0.2, 0.08], [0.8, 0.08]]},
                        {"id": "acceso_S", "line": [[0.2, 0.92], [0.8, 0.92]]},
                        {"id": "acceso_E", "line": [[0.92, 0.2], [0.92, 0.8]]},
                        {"id": "acceso_O", "line": [[0.08, 0.2], [0.08, 0.8]]},
                    ],
                    "lines": [],
                    "zones": [],
                },
                "dedup": {},
                "alerts": [],
                "privacy": {"blur": []},
                "station_defaults": {"station": "demo"},
                "output": {"annotated_video": False, "blurred_video": False},
            }
        ),
        encoding="utf-8",
    )
    bundle = run_pipeline(
        pack=str(pack_path),
        video=video,
        out_dir=tmp_path / "run-budget",
        mock_sam=True,
        use_spark=False,
        annotate=False,
        blur=False,
    )
    r = bundle["result"]
    assert r["partial"] is True
    assert any(m.get("skipped_budget") for m in r["sam"])
    assert r["cost_usd"] <= 0.50 + 1e-6
