"""Tránsito: ROIs por acceso N/S/E/O, recorte SAM y tope de 16 objetos.

SAM video admite ≤16 objetos/frame. En intersecciones densas corremos
una petición por acceso (recorte) en vez del frame entero, remapemos
cajas al frame completo y marcamos partial / max_objects_hit si alguna
petición saturó el tope o si cortamos por presupuesto.
"""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from .types import Box, Detection

SAM_MAX_OBJECTS_PER_FRAME = 16
DEFAULT_BUDGET_USD = 0.50

# Bandas por defecto (coords normalizadas x1,y1,x2,y2) si el pack no trae zona.
_DEFAULT_ROIS: dict[str, tuple[float, float, float, float]] = {
    "N": (0.0, 0.0, 1.0, 0.42),
    "S": (0.0, 0.58, 1.0, 1.0),
    "E": (0.58, 0.0, 1.0, 1.0),
    "O": (0.0, 0.0, 0.42, 1.0),
}


def polygon_bbox(poly: list[list[float]]) -> tuple[float, float, float, float] | None:
    if not poly or len(poly) < 3:
        return None
    xs = [float(p[0]) for p in poly]
    ys = [float(p[1]) for p in poly]
    return (min(xs), min(ys), max(xs), max(ys))


def access_rois_from_geometry(geometry: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Lista de {id, cardinal, x1,y1,x2,y2} normalizados 0..1.

    Fuentes (en orden): zones con id acceso_*/N, approaches con polygon/roi,
    approaches/lines → banda default del cardinal.
    """
    from .rules import CARDINALS, cardinal_from_line_id

    geometry = geometry or {}
    by_card: dict[str, dict[str, Any]] = {}

    def _put(card: str, x1: float, y1: float, x2: float, y2: float, raw_id: str) -> None:
        if card not in CARDINALS:
            return
        x1, x2 = max(0.0, min(x1, x2)), min(1.0, max(x1, x2))
        y1, y2 = max(0.0, min(y1, y2)), min(1.0, max(y1, y2))
        if x2 - x1 < 0.05 or y2 - y1 < 0.05:
            return
        if card in by_card:
            return
        by_card[card] = {
            "id": raw_id if raw_id.startswith("acceso_") else f"acceso_{card}",
            "cardinal": card,
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
        }

    for z in geometry.get("zones") or []:
        if not isinstance(z, dict):
            continue
        zid = str(z.get("id") or "")
        card = cardinal_from_line_id(zid)
        if card is None:
            continue
        if "roi" in z and isinstance(z["roi"], (list, tuple)) and len(z["roi"]) == 4:
            x1, y1, x2, y2 = (float(v) for v in z["roi"])
            _put(card, x1, y1, x2, y2, zid or f"acceso_{card}")
            continue
        bb = polygon_bbox(z.get("polygon") or [])
        if bb:
            _put(card, *bb, zid or f"acceso_{card}")

    for spec in list(geometry.get("approaches") or []) + list(geometry.get("lines") or []):
        if not isinstance(spec, dict):
            continue
        sid = str(spec.get("id") or "")
        card = cardinal_from_line_id(sid)
        if card is None:
            continue
        if "roi" in spec and isinstance(spec["roi"], (list, tuple)) and len(spec["roi"]) == 4:
            x1, y1, x2, y2 = (float(v) for v in spec["roi"])
            _put(card, x1, y1, x2, y2, sid or f"acceso_{card}")
            continue
        if "polygon" in spec:
            bb = polygon_bbox(spec.get("polygon") or [])
            if bb:
                _put(card, *bb, sid or f"acceso_{card}")
                continue
        # Solo línea → banda default del cardinal
        if card in _DEFAULT_ROIS:
            x1, y1, x2, y2 = _DEFAULT_ROIS[card]
            _put(card, x1, y1, x2, y2, sid or f"acceso_{card}")

    # Si hay al menos un acceso tipado, completar los 4 con defaults
    if by_card:
        for card, (x1, y1, x2, y2) in _DEFAULT_ROIS.items():
            if card not in by_card:
                _put(card, x1, y1, x2, y2, f"acceso_{card}")

    order = ["N", "S", "E", "O"]
    return [by_card[c] for c in order if c in by_card]


def probe_video_size(video: Path) -> tuple[int, int]:
    """(width, height) vía ffprobe; fallback 1280x720."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                str(video),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        data = json.loads(proc.stdout or "{}")
        streams = data.get("streams") or []
        if streams:
            w = int(streams[0]["width"])
            h = int(streams[0]["height"])
            if w > 0 and h > 0:
                return w, h
    except Exception:
        pass
    return 1280, 720


def crop_rect_px(
    roi: dict[str, Any], full_w: int, full_h: int
) -> dict[str, int]:
    """ROI normalizado → rectángulo píxeles even (ffmpeg crop)."""
    x1 = int(float(roi["x1"]) * full_w)
    y1 = int(float(roi["y1"]) * full_h)
    x2 = int(float(roi["x2"]) * full_w)
    y2 = int(float(roi["y2"]) * full_h)
    # even dimensions for yuv420
    x1 -= x1 % 2
    y1 -= y1 % 2
    w = max(2, x2 - x1)
    h = max(2, y2 - y1)
    w -= w % 2
    h -= h % 2
    if x1 + w > full_w:
        x1 = max(0, full_w - w)
        x1 -= x1 % 2
    if y1 + h > full_h:
        y1 = max(0, full_h - h)
        y1 -= y1 % 2
    return {
        "x": x1,
        "y": y1,
        "w": w,
        "h": h,
        "full_w": full_w,
        "full_h": full_h,
    }


def crop_video_access(
    video: Path,
    roi: dict[str, Any],
    out_path: Path,
    *,
    full_w: int | None = None,
    full_h: int | None = None,
    fps: float | None = None,
) -> dict[str, int]:
    """Recorta el video al ROI del acceso (opcionalmente a `fps`). Devuelve crop_px.

    Bajar fps (p. ej. al sampling del pack) es clave para caber en budget_usd:
    el cobro SAM es por frames procesados (mín. 50).
    """
    if full_w is None or full_h is None:
        full_w, full_h = probe_video_size(video)
    crop = crop_rect_px(roi, full_w, full_h)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"crop={crop['w']}:{crop['h']}:{crop['x']}:{crop['y']}"]
    if fps is not None and float(fps) > 0:
        parts.append(f"fps={float(fps)}")
    filt = ",".join(parts)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video),
        "-filter:v",
        filt,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
        "-pix_fmt",
        "yuv420p",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(
            f"ffmpeg crop falló ({proc.returncode}): {proc.stderr[-500:]}"
        )
    return crop


def remap_detections_to_full(
    detections: list[Detection], crop: dict[str, int]
) -> list[Detection]:
    """Pasa cajas del recorte al frame completo (w/h = full)."""
    ox, oy = crop["x"], crop["y"]
    fw, fh = float(crop["full_w"]), float(crop["full_h"])
    out: list[Detection] = []
    for d in detections:
        b = d.box
        nb = Box(
            x1=b.x1 + ox,
            y1=b.y1 + oy,
            x2=b.x2 + ox,
            y2=b.y2 + oy,
            w=fw,
            h=fh,
        )
        out.append(
            Detection(
                frame=d.frame,
                object_id=d.object_id,
                box=nb,
                class_name=d.class_name,
                confidence=d.confidence,
                chunk_index=d.chunk_index,
            )
        )
    return out


def frames_hitting_object_cap(
    detections: list[Detection],
    *,
    fps: float,
    limit: int = SAM_MAX_OBJECTS_PER_FRAME,
    access: str | None = None,
    concept: str | None = None,
) -> list[dict[str, Any]]:
    """Frames/t_s donde una petición alcanzó `limit` object_ids distintos."""
    by_frame: dict[int, set[int]] = defaultdict(set)
    for d in detections:
        by_frame[int(d.frame)].add(int(d.object_id))
    hits: list[dict[str, Any]] = []
    for frame in sorted(by_frame):
        n = len(by_frame[frame])
        if n >= limit:
            hit: dict[str, Any] = {
                "frame": frame,
                "t_s": round(frame / fps, 4) if fps > 0 else float(frame),
                "n_objects": n,
            }
            if access:
                hit["access"] = access
            if concept:
                hit["concept"] = concept
            hits.append(hit)
    return hits



def detection_center_norm(d: Detection) -> tuple[float, float]:
    """Centro de caja en coords normalizadas 0..1."""
    w = float(d.box.w) or 1.0
    h = float(d.box.h) or 1.0
    cx = (float(d.box.x1) + float(d.box.x2)) / 2.0 / w
    cy = (float(d.box.y1) + float(d.box.y2)) / 2.0 / h
    return cx, cy


def filter_detections_in_roi(
    detections: list[Detection], roi: dict[str, Any]
) -> list[Detection]:
    """Quédate con detecciones cuyo centro cae en el ROI normalizado."""
    x1, y1, x2, y2 = (
        float(roi["x1"]),
        float(roi["y1"]),
        float(roi["x2"]),
        float(roi["y2"]),
    )
    out: list[Detection] = []
    for d in detections:
        cx, cy = detection_center_norm(d)
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            out.append(d)
    return out


def wants_access_crops(pack_data: dict[str, Any]) -> bool:
    """True si el paquete es de tránsito / pide turning_movements."""
    pid = str(pack_data.get("id") or "")
    metrics = set(pack_data.get("metrics") or [])
    if "turning_movements" in metrics:
        return True
    if pid.startswith("transito"):
        return True
    if pack_data.get("access_crops") is True:
        return True
    return False
