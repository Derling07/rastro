"""Une pistas de SAM y cuenta individuos sin duplicar.

Dos problemas distintos:
1) Dentro de un trozo (chunk): SAM ya mantiene object_id entre frames.
2) Entre trozos / reentradas: si el animal sale y vuelve, SAM puede dar
   un object_id nuevo. Acá unimos por cercanía en el tiempo + borde + IoU.

También calculamos el conteo "ingenuo" (suma de apariciones) para el
contraste del demo: «3, no 11».
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .types import Detection, Track


@dataclass
class CountResult:
    tracks: list[Track]
    unique_count: int
    naive_count: int
    by_class: dict[str, int]


def build_tracks_from_sam_ids(
    detections: list[Detection],
    *,
    class_name: str | None = None,
) -> list[Track]:
    """Agrupa detecciones por (chunk_index, object_id, class_name).

    Eso es lo que SAM garantiza DENTRO de una petición.
    """
    groups: dict[tuple[int, int, str], list[Detection]] = defaultdict(list)
    for d in detections:
        if class_name is not None and d.class_name != class_name:
            continue
        groups[(d.chunk_index, d.object_id, d.class_name)].append(d)

    tracks: list[Track] = []
    for (chunk, oid, cls), dets in sorted(groups.items(), key=lambda x: min(d.frame for d in x[1])):
        dets_sorted = sorted(dets, key=lambda d: d.frame)
        tid = f"{cls}-c{chunk}-o{oid}-f{dets_sorted[0].frame}"
        tracks.append(Track(track_id=tid, class_name=cls, detections=dets_sorted))
    return tracks


def naive_appearance_count(detections: list[Detection]) -> int:
    """Conteo ingenuo: cuántas 'apariciones' hay si no unís reentradas.

    Contamos cada grupo (chunk, object_id, class) como si fuera un individuo.
    Es el número alto del demo («11»).
    """
    keys = {(d.chunk_index, d.object_id, d.class_name) for d in detections}
    return len(keys)


def stitch_reentries(
    tracks: list[Track],
    *,
    fps: float,
    reentry_window_s: float = 20.0,
    reentry_edge_px: float = 80.0,
    iou_stitch: float = 0.3,
    center_dist_factor: float = 2.0,
    edge_dist_factor: float = 4.0,
) -> list[Track]:
    """Une pistas de la misma clase si una termina y otra empieza pronto.

    Umbrales configurables desde packs/*.json → dedup:
      reentry_window_s, reentry_edge_px, iou_stitch,
      center_dist_factor, edge_dist_factor.
    """
    if fps <= 0:
        raise ValueError("fps debe ser > 0")

    # Trabajamos por clase para no mezclar coyote con persona.
    by_class: dict[str, list[Track]] = defaultdict(list)
    for t in tracks:
        by_class[t.class_name].append(t)

    merged: list[Track] = []
    for cls, cls_tracks in by_class.items():
        # Orden por frame de inicio.
        pending = sorted(cls_tracks, key=lambda t: t.start_frame)
        active: list[Track] = []
        for cand in pending:
            matched = None
            for prev in active:
                gap_frames = cand.start_frame - prev.end_frame
                if gap_frames < 0:
                    continue  # se solapan: no es reentrada, son dos a la vez
                gap_s = gap_frames / fps
                if gap_s > reentry_window_s:
                    continue
                if _looks_like_same(
                    prev,
                    cand,
                    reentry_edge_px,
                    iou_stitch,
                    center_dist_factor=center_dist_factor,
                    edge_dist_factor=edge_dist_factor,
                ):
                    matched = prev
                    break
            if matched is None:
                active.append(cand)
            else:
                # Fusionamos detecciones en la pista anterior.
                matched.detections.extend(cand.detections)
                matched.detections.sort(key=lambda d: d.frame)
        merged.extend(active)

    # Reasignamos IDs limpios.
    out: list[Track] = []
    counters: dict[str, int] = defaultdict(int)
    for t in sorted(merged, key=lambda x: x.start_frame):
        counters[t.class_name] += 1
        out.append(
            Track(
                track_id=f"{t.class_name}-{counters[t.class_name]}",
                class_name=t.class_name,
                detections=t.detections,
            )
        )
    return out


def _looks_like_same(
    a: Track,
    b: Track,
    edge_px: float,
    iou_thresh: float,
    *,
    center_dist_factor: float = 2.0,
    edge_dist_factor: float = 4.0,
) -> bool:
    last = a.detections[-1].box
    first = b.detections[0].box
    if last.iou(first) >= iou_thresh:
        return True
    near_edge = (
        last.x1 <= edge_px
        or last.y1 <= edge_px
        or (last.w - last.x2) <= edge_px
        or (last.h - last.y2) <= edge_px
    )
    dist = abs(last.cx - first.cx) + abs(last.cy - first.cy)
    if near_edge and dist <= edge_px * edge_dist_factor:
        return True
    if dist <= edge_px * center_dist_factor:
        return True
    return False


def count_unique(
    detections: list[Detection],
    *,
    fps: float,
    reentry_window_s: float = 20.0,
    reentry_edge_px: float = 80.0,
    iou_stitch: float = 0.5,
    center_dist_factor: float = 2.0,
    edge_dist_factor: float = 4.0,
) -> CountResult:
    """Pipeline corto: agrupar por ID de SAM → unir reentradas → contar."""
    base = build_tracks_from_sam_ids(detections)
    naive = naive_appearance_count(detections)
    stitched = stitch_reentries(
        base,
        fps=fps,
        reentry_window_s=reentry_window_s,
        reentry_edge_px=reentry_edge_px,
        iou_stitch=iou_stitch,
        center_dist_factor=center_dist_factor,
        edge_dist_factor=edge_dist_factor,
    )
    by_class: dict[str, int] = defaultdict(int)
    for t in stitched:
        by_class[t.class_name] += 1
    return CountResult(
        tracks=stitched,
        unique_count=len(stitched),
        naive_count=naive,
        by_class=dict(by_class),
    )
