from rastro.tracking import count_unique, stitch_reentries, build_tracks_from_sam_ids
from rastro.types import Box, Detection


def _det(frame, oid, x, y, cls="coyote", chunk=0):
    return Detection(
        frame=frame,
        object_id=oid,
        box=Box(x1=x, y1=y, x2=x + 100, y2=y + 80, w=1920, h=1080),
        class_name=cls,
        chunk_index=chunk,
    )


def test_tight_center_factor_does_not_merge_far_reentry():
    """Con center_dist_factor bajo, una reaparición lejos NO se fusiona."""
    t0 = [_det(0, 0, 50, 400), _det(5, 0, 40, 400)]  # near left edge
    t1 = [_det(20, 1, 1700, 400), _det(25, 1, 1710, 400)]  # far right, gap 1.5s @10fps
    base = build_tracks_from_sam_ids(t0 + t1)
    # window ok (1.5s < 20), but centers far → with factor 0.1 no merge
    stitched = stitch_reentries(
        base,
        fps=10.0,
        reentry_window_s=20.0,
        reentry_edge_px=80.0,
        iou_stitch=0.99,  # IoU won't match
        center_dist_factor=0.1,
        edge_dist_factor=0.1,
    )
    assert len(stitched) == 2


def test_loose_center_factor_merges_near_reentry():
    t0 = [_det(0, 0, 100, 400), _det(10, 0, 110, 400)]
    t1 = [_det(30, 1, 130, 410), _det(40, 1, 140, 410)]  # gap 2s, close center
    base = build_tracks_from_sam_ids(t0 + t1)
    stitched = stitch_reentries(
        base,
        fps=10.0,
        reentry_window_s=20.0,
        reentry_edge_px=80.0,
        iou_stitch=0.99,
        center_dist_factor=2.0,
        edge_dist_factor=4.0,
    )
    assert len(stitched) == 1
