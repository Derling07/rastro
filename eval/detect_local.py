"""Free local detectors. No Meta and no Baseten.

Color frames: OpenCV Zoo YOLOX (COCO), Apache-2.0 weights, $0.
Infrared trail cameras: difference from the first frame. The largest blob
is the animal. Species comes from the dataset label, not from a name.

The YOLOX file is downloaded at runtime and is not committed.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL = Path("/tmp/yolox.onnx")
MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "object_detection_yolox/object_detection_yolox_2022nov.onnx"
)
COCO = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow",
]
FARM = {"horse", "sheep", "cow", "dog"}
WILD_COLOR = {"dog", "cat", "bear", "bird"}
VEHICLE = {"car", "bus", "truck", "motorcycle", "bicycle"}


def ensure_model() -> None:
    if MODEL.exists() and MODEL.stat().st_size > 1_000_000:
        return
    urllib.request.urlretrieve(MODEL_URL, MODEL)


def _yolox():
    import importlib.util

    demo = Path("/tmp/yolox_demo.py")
    if not demo.exists():
        urllib.request.urlretrieve(
            "https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/object_detection_yolox/yolox.py",
            demo,
        )
    spec = importlib.util.spec_from_file_location("yolox", demo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.YoloX(str(MODEL), confThreshold=0.35, nmsThreshold=0.45, objThreshold=0.35)


def detect_color(det, frame) -> list[dict]:
    h, w = frame.shape[:2]
    resized = cv2.resize(frame, (640, 640)).astype(np.float32)
    preds = det.infer(resized)
    if preds is None or len(preds) == 0:
        return []
    sx, sy = w / 640.0, h / 640.0
    rows = []
    for x, y, bw, bh, score, cls in preds:
        name = COCO[int(cls)] if int(cls) < len(COCO) else "other"
        rows.append({
            "class": name,
            "score": round(float(score), 3),
            "bbox": [
                round(float(x) * sx, 1),
                round(float(y) * sy, 1),
                round(float(x + bw) * sx, 1),
                round(float(y + bh) * sy, 1),
            ],
        })
    return rows


def detect_ir(base_gray, frame) -> list[dict]:
    gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (21, 21), 0)
    diff = cv2.absdiff(base_gray, gray)
    _, th = cv2.threshold(diff, 28, 255, cv2.THRESH_BINARY)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = frame.shape[:2]
    boxes = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw * bh < 2000 or bw > w * 0.75:
            continue
        boxes.append((bw * bh, x, y, x + bw, y + bh))
    if not boxes:
        return []
    boxes.sort(reverse=True)
    _, x1, y1, x2, y2 = boxes[0]
    return [{"class": "animal", "score": 1.0, "bbox": [x1, y1, x2, y2]}]


def sample(path: Path, every_s: float, mode: str, det) -> dict:
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    ok, first = cap.read()
    if not ok:
        raise RuntimeError(f"unreadable {path}")
    base = cv2.GaussianBlur(cv2.cvtColor(first, cv2.COLOR_BGR2GRAY), (21, 21), 0)
    frames = []
    index = 0
    next_t = 0.0
    # rewind so t=0 is included
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = index / fps
        if t + 1e-3 >= next_t:
            boxes = detect_ir(base, frame) if mode == "ir" else detect_color(det, frame)
            frames.append({"frame": len(frames), "t_s": round(t, 2), "objects": boxes})
            next_t += every_s
        index += 1
    cap.release()
    return {"fps_sampled": 1 / every_s, "native_fps": fps, "width": int(first.shape[1]), "height": int(first.shape[0]), "frames": frames}


def main() -> None:
    ensure_model()
    det = _yolox()
    jobs = {
        "gray-fox": (ROOT / "web/public/cameras/gray-fox.mp4", 0.5, "ir"),
        "goats": (ROOT / "web/public/cameras/goats.mp4", 0.5, "color"),
        "person": (Path("/tmp/camsrc/dscf0004.mp4"), 0.5, "color"),
        "plaza": (ROOT / "web/public/cameras/plaza.mp4", 1.0, "color"),
        "wicker": (ROOT / "web/public/cameras/wicker.mp4", 1.0, "color"),
    }
    out = ROOT / "eval" / "alert_set" / "detections"
    out.mkdir(parents=True, exist_ok=True)
    for name, (path, every, mode) in jobs.items():
        if not path.exists():
            print("skip", name)
            continue
        doc = sample(path, every, mode, det)
        doc["detector"] = "mog2-static-diff" if mode == "ir" else "opencv-zoo-yolox-coco"
        doc["spend_usd"] = 0
        (out / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
        print(name, "frames", len(doc["frames"]), "spend 0")


if __name__ == "__main__":
    main()
