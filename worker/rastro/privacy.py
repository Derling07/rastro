"""Privacidad: difuminar personas con las cajas/máscaras de SAM.

Regla del producto: SIN reconocimiento facial. Solo manchas sobre la
región que SAM marcó como persona (caja = bbox de la máscara).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageFilter

from .types import Detection


def should_blur(pack_privacy: dict) -> list[str]:
    """Qué clases pide difuminar el paquete (p. ej. persona)."""
    return list(pack_privacy.get("blur") or [])


def boxes_by_frame(
    detections: Iterable[Detection],
    *,
    class_names: set[str],
) -> dict[int, list[tuple[int, int, int, int]]]:
    """frame → lista de (x1,y1,x2,y2) enteros para las clases a difuminar."""
    out: dict[int, list[tuple[int, int, int, int]]] = {}
    for d in detections:
        if d.class_name not in class_names:
            continue
        b = d.box
        xyxy = (
            max(0, int(b.x1)),
            max(0, int(b.y1)),
            max(0, int(b.x2)),
            max(0, int(b.y2)),
        )
        out.setdefault(d.frame, []).append(xyxy)
    return out


def blur_image_region(img: Image.Image, box: tuple[int, int, int, int], radius: int = 28) -> None:
    """Difumina in-place una región (caja SAM). Sin face ID."""
    x1, y1, x2, y2 = box
    x1 = max(0, min(x1, img.width - 1))
    y1 = max(0, min(y1, img.height - 1))
    x2 = max(x1 + 1, min(x2, img.width))
    y2 = max(y1 + 1, min(y2, img.height))
    crop = img.crop((x1, y1, x2, y2))
    crop = crop.filter(ImageFilter.GaussianBlur(radius=radius))
    img.paste(crop, (x1, y1))


def blur_video(
    video_in: Path,
    video_out: Path,
    person_boxes: dict[int, list[tuple[int, int, int, int]]],
    *,
    fps: float,
    blur_radius: int = 28,
    det_fps: float | None = None,
    native_fps: float | None = None,
) -> Path:
    """Genera un MP4 con regiones de persona difuminadas (cajas SAM = full_bbox).

    det_fps/native_fps: mapeo para image_sample (detecciones a fps de muestreo).
    """
    video_in = Path(video_in)
    video_out = Path(video_out)
    video_out.parent.mkdir(parents=True, exist_ok=True)
    work = video_out.parent / f".blur_frames_{video_out.stem}"
    if work.exists():
        for old in work.glob("*"):
            old.unlink()
    else:
        work.mkdir(parents=True)

    subprocess.check_call(
        [
            "ffmpeg", "-y", "-i", str(video_in),
            "-vsync", "0",
            str(work / "f_%05d.png"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    frames = sorted(work.glob("f_*.png"))

    def _lookup_boxes(native_i: int) -> list[tuple[int, int, int, int]]:
        if det_fps and native_fps and native_fps > 0 and abs(det_fps - native_fps) > 1e-6:
            sample_idx = int(native_i * det_fps / native_fps)
            return person_boxes.get(sample_idx, [])
        return person_boxes.get(native_i, [])

    for i, fp in enumerate(frames):
        img = Image.open(fp).convert("RGB")
        for box in _lookup_boxes(i):
            blur_image_region(img, box, radius=blur_radius)
        img.save(fp)

    subprocess.check_call(
        [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(work / "f_%05d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-an",
            str(video_out),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for fp in frames:
        fp.unlink()
    try:
        work.rmdir()
    except OSError:
        pass
    return video_out
