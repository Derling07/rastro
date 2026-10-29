"""Video de salida anotado: cajas SAM, track IDs y contador único."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .types import Track


COLORS = [
    (255, 200, 40),
    (80, 200, 255),
    (255, 100, 120),
    (120, 255, 140),
    (200, 140, 255),
]


def _font(size: int = 22):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def annotate_video(
    video_in: Path,
    video_out: Path,
    tracks: list[Track],
    *,
    fps: float,
    unique_count: int,
    blur_classes: set[str] | None = None,
    blur_radius: int = 28,
    det_fps: float | None = None,
    native_fps: float | None = None,
) -> Path:
    """Dibuja cajas + IDs + contador; opcionalmente difumina clases sensibles.

    Si det_fps/native_fps vienen (image_sample), las detecciones están a det_fps
    y se mapean al índice nativo del frame extraído.
    """
    from .privacy import blur_image_region

    video_in = Path(video_in)
    video_out = Path(video_out)
    video_out.parent.mkdir(parents=True, exist_ok=True)
    blur_classes = blur_classes or set()

    # frame → list of (track_id, class, box, color_idx)
    by_frame: dict[int, list] = defaultdict(list)
    color_of: dict[str, tuple[int, int, int]] = {}
    for i, t in enumerate(tracks):
        color_of[t.track_id] = COLORS[i % len(COLORS)]
        for d in t.detections:
            by_frame[d.frame].append((t.track_id, t.class_name, d.box, color_of[t.track_id]))

    def _lookup(native_i: int) -> list:
        if det_fps and native_fps and native_fps > 0 and abs(det_fps - native_fps) > 1e-6:
            sample_idx = int(native_i * det_fps / native_fps)
            return by_frame.get(sample_idx, [])
        return by_frame.get(native_i, [])

    work = video_out.parent / f".ann_frames_{video_out.stem}"
    if work.exists():
        for old in work.glob("*"):
            old.unlink()
    else:
        work.mkdir(parents=True)

    subprocess.check_call(
        ["ffmpeg", "-y", "-i", str(video_in), "-vsync", "0", str(work / "f_%05d.png")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    font = _font(22)
    font_sm = _font(18)
    frames = sorted(work.glob("f_*.png"))
    seen_ids: set[str] = set()

    for i, fp in enumerate(frames):
        img = Image.open(fp).convert("RGB")
        draw = ImageDraw.Draw(img)
        objs = _lookup(i)
        for tid, cls, box, color in objs:
            x1, y1, x2, y2 = int(box.x1), int(box.y1), int(box.x2), int(box.y2)
            if cls in blur_classes:
                blur_image_region(img, (x1, y1, x2, y2), radius=blur_radius)
                draw = ImageDraw.Draw(img)
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            label = f"{tid}"
            draw.rectangle([x1, max(0, y1 - 22), x1 + 8 * len(label) + 8, y1], fill=color)
            draw.text((x1 + 4, max(0, y1 - 22)), label, fill=(0, 0, 0), font=font_sm)
            seen_ids.add(tid)

        # HUD contador
        hud = f"únicos: {unique_count}   visibles: {len({t for t,_,_,_ in objs})}   frame: {i}"
        draw.rectangle([8, 8, 8 + 9 * len(hud), 36], fill=(0, 0, 0, 180))
        draw.text((12, 10), hud, fill=(255, 255, 255), font=font)
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
