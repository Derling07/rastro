"""Pruebas del conteo y la deduplicación con datos sintéticos."""

from __future__ import annotations

from rastro.sam_client import _mock_detections, parse_sam_output
from rastro.tracking import (
    build_tracks_from_sam_ids,
    count_unique,
    naive_appearance_count,
    stitch_reentries,
)
from rastro.types import Box, Detection


def _det(frame, oid, x, y, cls="coyote", chunk=0):
    return Detection(
        frame=frame,
        object_id=oid,
        box=Box(x1=x, y1=y, x2=x + 100, y2=y + 80, w=1920, h=1080),
        class_name=cls,
        chunk_index=chunk,
    )


def test_naive_vs_unique_reentry():
    """El caso demo: el mismo animal sale y vuelve → 3 únicos, naive > 3."""
    dets = _mock_detections(
        concept="coyote",
        class_name="coyote",
        chunk_index=0,
        frame_offset=0,
        seed="demo",
    )
    naive = naive_appearance_count(dets)
    result = count_unique(
        dets,
        fps=10.0,
        reentry_window_s=20.0,
        reentry_edge_px=80.0,
        iou_stitch=0.3,
    )
    assert naive == 4
    assert result.unique_count == 3
    assert result.by_class["coyote"] == 3
    assert result.unique_count < naive


def test_overlapping_animals_are_not_merged():
    """Dos animales a la vez (frames solapados) no se fusionan."""
    dets = [
        _det(0, 0, 50, 400),
        _det(1, 0, 60, 400),
        _det(0, 1, 900, 500),
        _det(1, 1, 910, 500),
    ]
    result = count_unique(dets, fps=10.0)
    assert result.unique_count == 2


def test_chunk_stitch_by_iou():
    """Misma pista partida en dos trozos se une si el IoU es alto."""
    # Trozo 0 termina
    t0 = [
        _det(58, 0, 100, 400, chunk=0),
        _det(59, 0, 105, 400, chunk=0),
    ]
    # Trozo 1 empieza casi en el mismo lugar (traslape)
    t1 = [
        _det(60, 7, 108, 402, chunk=1),  # object_id distinto (SAM reinició)
        _det(61, 7, 110, 402, chunk=1),
    ]
    base = build_tracks_from_sam_ids(t0 + t1)
    assert len(base) == 2
    stitched = stitch_reentries(
        base, fps=10.0, reentry_window_s=5.0, reentry_edge_px=80.0, iou_stitch=0.3
    )
    assert len(stitched) == 1


def test_parse_sam_output_boxes():
    raw = (
        "<0f>0<|box;x1=10;y1=20;x2=30;y2=40;w=100;h=200;c=0.9|>"
        "<|mask;x=0;y=0;data=1,~abc|>,"
        "1<|box;x1=50;y1=60;x2=70;y2=80;w=100;h=200|>"
        "<|mask;x=0;y=0;data=1,~xyz|>"
        "<1f>0<|box;x1=11;y1=21;x2=31;y2=41;w=100;h=200|>"
        "<|mask;x=0;y=0;data=1,~abc|>"
    )
    dets = parse_sam_output(raw, class_name="coyote", frame_offset=10)
    assert len(dets) == 3
    assert dets[0].frame == 10
    assert dets[0].object_id == 0
    assert dets[0].box.x1 == 10
    assert dets[0].confidence == 0.9
    assert dets[2].frame == 11


def test_person_mock_single_track():
    dets = _mock_detections(
        concept="person",
        class_name="persona",
        chunk_index=0,
        frame_offset=0,
        seed="night",
    )
    result = count_unique(dets, fps=10.0)
    assert result.unique_count == 1
    assert result.by_class == {"persona": 1}
