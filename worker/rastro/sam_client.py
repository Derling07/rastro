"""Cliente de SAM 3.1 (Meta Model API) — verificado 26 oct 2026.

Firma real (probada):
  POST https://api.meta.ai/v1/responses
  Authorization: Bearer $META_API_KEY  (docs: MODEL_API_KEY)
  body: {
    "model": "sam-3.1",
    "input": [{
      "type": "message", "role": "user",
      "content": [
        {"type": "input_text", "text": "<concepto>"},
        {"type": "input_video", "file_id": "file-..."}
        # o {"type": "input_image", "image_url": "data:image/png;base64,..."}
      ]
    }],
    "stream": true,                 # recomendado para video
    "metadata": {"mask_encoding": "one_bit"}  # SOLO "one_bit" | "lossless"
  }

Subida de archivo (probada):
  POST /v1/files  purpose=user_data  →  id "file-..."

Respuesta (probada):
  - Texto especial en output_text, una línea por frame CON detecciones.
    Frames sin match se OMITEN (no llegan como línea vacía).
  - Cero matches → output_text vacío y status completed (válido).
  - usage.video_frames_processed (video) o usage.images_processed (imagen).
  - Precio video: USD 0,20 / 1000 frames, mínimo 50 frames por petición.
  - Precio imagen: USD 2,50 / 1000 imágenes.

Hallazgo de prompts (IR nocturno LILA, oct 2026):
  - El prompt óptimo es FRAME-DEPENDIENTE.
  - DSCF0104: "animal"/"dog"=0, "coyote"/"fox"=1 en el mismo frame.
  - DSCF0112: "animal" → 2 individuos (video).
  - Probar "coyote" y "animal" como fallback; no asumir uno solo.

SIN CLAVE o mock=True: detecciones sintéticas para el motor/tests.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .types import Box, Detection

META_BASE_URL = "https://api.meta.ai/v1"
SAM_MODEL = "sam-3.1"
# Precio oficial (docs Meta, oct 2026)
USD_PER_1K_VIDEO_FRAMES = 0.20
USD_PER_1K_IMAGES = 2.50
MIN_BILLABLE_FRAMES = 50

_FRAME_RE = re.compile(r"<(\d+)f>")
_BOX_RE = re.compile(
    r"(\d+)<\|box;x1=([^;]+);y1=([^;]+);x2=([^;]+);y2=([^;]+);w=([^;]+);h=([^|;]+)(?:;c=([^|]+))?\|>"
)


@dataclass
class SamResult:
    """Resultado de una petición a SAM (un concepto sobre un clip/imagen)."""

    concept: str
    class_name: str
    detections: list[Detection]
    raw_text: str
    usage: dict[str, Any]
    mock: bool
    elapsed_s: float
    est_usd: float = 0.0


def _api_key() -> str | None:
    return os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY")


def has_meta_key() -> bool:
    return bool(_api_key())


def estimate_video_cost(frames_processed: int | None) -> float:
    """Estima USD a partir de usage.video_frames_processed (con mínimo 50)."""
    n = int(frames_processed or 0)
    bill = max(MIN_BILLABLE_FRAMES, n) if n else MIN_BILLABLE_FRAMES
    return bill * USD_PER_1K_VIDEO_FRAMES / 1000.0


def estimate_image_cost(images_processed: int | None = 1) -> float:
    return max(1, int(images_processed or 1)) * USD_PER_1K_IMAGES / 1000.0


class SamClient:
    """Habla con SAM 3.1 o simula la respuesta."""

    def __init__(
        self,
        mock: bool | None = None,
        cache_dir: Path | None = None,
        base_url: str = META_BASE_URL,
        mask_encoding: str = "one_bit",
        delete_uploads: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_dir = cache_dir or Path(".cache/sam")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if mask_encoding not in ("one_bit", "lossless"):
            raise ValueError("mask_encoding debe ser 'one_bit' o 'lossless'")
        self.mask_encoding = mask_encoding
        self.delete_uploads = delete_uploads
        if mock is None:
            mock = not has_meta_key()
        self.mock = mock
        self._client = None
        self.total_est_usd = 0.0
        if not self.mock:
            from openai import OpenAI

            key = _api_key()
            if not key:
                raise RuntimeError(
                    "Falta META_API_KEY / MODEL_API_KEY. "
                    "Pasá mock=True o pedí los créditos de Meta."
                )
            self._client = OpenAI(base_url=self.base_url, api_key=key)

    def segment_video(
        self,
        video_path: Path | str,
        concept: str,
        class_name: str,
        *,
        video_url: str | None = None,
        file_id: str | None = None,
        chunk_index: int = 0,
        frame_offset: int = 0,
        mask_encoding: str | None = None,
    ) -> SamResult:
        """Segmenta un video con un solo concepto (una petición = un prompt)."""
        video_path = Path(video_path)
        started = time.time()
        encoding = mask_encoding or self.mask_encoding

        if self.mock:
            dets = _mock_detections(
                concept=concept,
                class_name=class_name,
                chunk_index=chunk_index,
                frame_offset=frame_offset,
                seed=f"{video_path.name}:{concept}",
            )
            return SamResult(
                concept=concept,
                class_name=class_name,
                detections=dets,
                raw_text="(mock)",
                usage={"video_frames_processed": 0, "mock": True},
                mock=True,
                elapsed_s=time.time() - started,
                est_usd=0.0,
            )

        cache_key = _cache_key(video_path, concept, encoding, file_id, video_url)
        cache_file = self.cache_dir / f"{cache_key}.txt"
        usage_cache = self.cache_dir / f"{cache_key}.usage.json"
        if cache_file.exists():
            raw = cache_file.read_text(encoding="utf-8")
            usage = {}
            if usage_cache.exists():
                try:
                    usage = json.loads(usage_cache.read_text(encoding="utf-8"))
                    usage["cached"] = True
                except Exception:
                    usage = {"cached": True}
            else:
                usage = {"cached": True}
            dets = parse_sam_output(
                raw, class_name=class_name, chunk_index=chunk_index, frame_offset=frame_offset
            )
            return SamResult(
                concept=concept,
                class_name=class_name,
                detections=dets,
                raw_text=raw,
                usage=usage,
                mock=False,
                elapsed_s=time.time() - started,
                est_usd=0.0,  # no se cobra de nuevo
            )

        assert self._client is not None
        uploaded_id: str | None = None
        if file_id:
            media: dict[str, Any] = {"type": "input_video", "file_id": file_id}
        elif video_url:
            media = {"type": "input_video", "video_url": video_url}
        else:
            with video_path.open("rb") as fh:
                uploaded = self._client.files.create(purpose="user_data", file=fh)
            uploaded_id = uploaded.id
            media = {"type": "input_video", "file_id": uploaded_id}

        raw, usage = self._stream_segment(
            concept=concept,
            media=media,
            encoding=encoding,
        )

        if self.delete_uploads and uploaded_id:
            try:
                self._client.files.delete(uploaded_id)
            except Exception:
                pass

        cache_file.write_text(raw, encoding="utf-8")
        usage_cache.write_text(json.dumps(usage, default=str), encoding="utf-8")
        dets = parse_sam_output(
            raw, class_name=class_name, chunk_index=chunk_index, frame_offset=frame_offset
        )
        est = estimate_video_cost(usage.get("video_frames_processed"))
        self.total_est_usd += est
        return SamResult(
            concept=concept,
            class_name=class_name,
            detections=dets,
            raw_text=raw,
            usage=usage,
            mock=False,
            elapsed_s=time.time() - started,
            est_usd=est,
        )

    def segment_image(
        self,
        image_path: Path | str,
        concept: str,
        class_name: str,
        *,
        mask_encoding: str | None = None,
    ) -> SamResult:
        """Segmenta una sola imagen (útil para probes baratos)."""
        import base64

        image_path = Path(image_path)
        started = time.time()
        encoding = mask_encoding or self.mask_encoding
        if self.mock:
            dets = _mock_image_detections(
                concept=concept,
                class_name=class_name,
                frame=0,
                seed=f"{image_path.name}:{concept}",
            )
            return SamResult(
                concept=concept,
                class_name=class_name,
                detections=dets,
                raw_text="(mock)",
                usage={"images_processed": 0, "mock": True},
                mock=True,
                elapsed_s=time.time() - started,
                est_usd=0.0,
            )
        assert self._client is not None
        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        data_url = f"data:{mime};base64," + base64.b64encode(image_path.read_bytes()).decode()
        media = {"type": "input_image", "image_url": data_url}
        raw, usage = self._stream_segment(concept=concept, media=media, encoding=encoding)
        # Non-stream also works; _stream_segment handles both.
        dets = parse_sam_output(raw, class_name=class_name)
        est = estimate_image_cost(usage.get("images_processed"))
        self.total_est_usd += est
        return SamResult(
            concept=concept,
            class_name=class_name,
            detections=dets,
            raw_text=raw,
            usage=usage,
            mock=False,
            elapsed_s=time.time() - started,
            est_usd=est,
        )

    def _stream_segment(
        self,
        *,
        concept: str,
        media: dict[str, Any],
        encoding: str,
    ) -> tuple[str, dict[str, Any]]:
        """Llama a /v1/responses con stream y junta el output_text."""
        assert self._client is not None
        raw_parts: list[str] = []
        usage: dict[str, Any] = {}
        kwargs = dict(
            model=SAM_MODEL,
            input=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": concept},
                        media,
                    ],
                }
            ],
            metadata={"mask_encoding": encoding},
        )
        # Preferimos el context manager responses.stream (probado).
        if hasattr(self._client.responses, "stream"):
            with self._client.responses.stream(**kwargs) as stream:
                for event in stream:
                    et = getattr(event, "type", None)
                    if et == "response.output_text.delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            raw_parts.append(delta)
                    elif et == "response.completed":
                        resp = getattr(event, "response", None)
                        if resp is not None and getattr(resp, "usage", None):
                            u = resp.usage
                            usage = u.model_dump() if hasattr(u, "model_dump") else dict(u)
                try:
                    final = stream.get_final_response()
                    if not raw_parts:
                        t = getattr(final, "output_text", None) or ""
                        if t:
                            raw_parts.append(t)
                    if not usage and getattr(final, "usage", None):
                        usage = final.usage.model_dump()
                except Exception:
                    pass
        else:
            # Fallback no-stream
            resp = self._client.responses.create(**kwargs)
            t = getattr(resp, "output_text", None) or ""
            if not t:
                d = resp.model_dump()
                for item in d.get("output") or []:
                    for c in item.get("content") or []:
                        if c.get("text"):
                            t = c["text"]
                            break
            raw_parts.append(t)
            if getattr(resp, "usage", None):
                usage = resp.usage.model_dump()
        return "".join(raw_parts), usage


def parse_sam_output(
    raw: str,
    *,
    class_name: str,
    chunk_index: int = 0,
    frame_offset: int = 0,
) -> list[Detection]:
    """Parsea el texto especial de SAM a Detection (solo cajas)."""
    detections: list[Detection] = []
    if not raw or not raw.strip():
        return detections
    parts = _FRAME_RE.split(raw)
    if len(parts) == 1:
        # Imagen: a veces viene sin <0f>; tratamos como frame 0.
        if "<|box;" in raw:
            frame_chunks = [(0, raw)]
        else:
            return detections
    else:
        frame_chunks = []
        it = iter(parts[1:])
        for frame_s, body in zip(it, it):
            frame_chunks.append((int(frame_s), body))

    for frame_idx, body in frame_chunks:
        for m in _BOX_RE.finditer(body):
            obj_id = int(m.group(1))
            conf = float(m.group(8)) if m.group(8) else None
            box = Box(
                x1=float(m.group(2)),
                y1=float(m.group(3)),
                x2=float(m.group(4)),
                y2=float(m.group(5)),
                w=float(m.group(6)),
                h=float(m.group(7)),
            )
            detections.append(
                Detection(
                    frame=frame_offset + frame_idx,
                    object_id=obj_id,
                    box=box,
                    class_name=class_name,
                    confidence=conf,
                    chunk_index=chunk_index,
                )
            )
    return detections


def _cache_key(
    video_path: Path,
    concept: str,
    mask_encoding: str,
    file_id: str | None,
    video_url: str | None,
) -> str:
    h = hashlib.sha256()
    h.update(str(video_path.resolve()).encode())
    try:
        st = video_path.stat()
        h.update(str(st.st_mtime_ns).encode())
        h.update(str(st.st_size).encode())
    except OSError:
        pass
    h.update(concept.encode())
    h.update(mask_encoding.encode())
    if file_id:
        h.update(file_id.encode())
    if video_url:
        h.update(video_url.encode())
    return h.hexdigest()[:24]


def _mock_detections(
    *,
    concept: str,
    class_name: str,
    chunk_index: int,
    frame_offset: int,
    seed: str,
) -> list[Detection]:
    """Pistas sintéticas: un animal sale y vuelve (ID nuevo) + otros dos."""
    import hashlib

    digest = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    w, h = 1920.0, 1080.0
    y_base = 400.0 + (digest % 40)

    if class_name == "persona" or concept == "person":
        script = [(0, 5, 60, 700, 900, 300)]
    elif concept in ("animal", "fox", "dog") and class_name == "coyote":
        # Fallback sintético: un solo individuo (para probar multi-prompt).
        script = [(0, 10, 40, 400, 700, y_base)]
    elif class_name == "animal_generico":
        return []
    else:
        script = [
            (0, 0, 40, 220, 20, y_base),
            (1, 20, 70, 900, 1100, y_base + 80),
            (3, 55, 90, 30, 200, y_base),
            (2, 75, 100, 1400, 1600, y_base + 40),
        ]

    dets: list[Detection] = []
    for local_id, start, end, x0, x1, y in script:
        n = max(1, end - start)
        for i, f in enumerate(range(start, end + 1)):
            t = i / n
            x = x0 + (x1 - x0) * t
            box = Box(x1=x, y1=y, x2=x + 120, y2=y + 90, w=w, h=h)
            dets.append(
                Detection(
                    frame=frame_offset + f,
                    object_id=local_id,
                    box=box,
                    class_name=class_name,
                    confidence=0.9,
                    chunk_index=chunk_index,
                )
            )
    return dets


def _mock_image_detections(
    *,
    concept: str,
    class_name: str,
    frame: int,
    seed: str,
    n_persons: int | None = None,
) -> list[Detection]:
    """Detecciones sintéticas para modo imagen (multitudes / probes)."""
    import hashlib

    digest = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    w, h = 1920.0, 1080.0
    if class_name == "persona" or concept in ("person", "people", "persona"):
        if n_persons is None:
            n_persons = 80 + (digest % 41)
        dets: list[Detection] = []
        cols = max(1, int(n_persons ** 0.5) + 1)
        for i in range(n_persons):
            row, col = divmod(i, cols)
            cx = 0.15 + (col + 0.5) / cols * 0.7
            cy = 0.55 + (row + 0.5) / max(1, (n_persons // cols) + 1) * 0.35
            bw, bh = 40.0, 80.0
            x1 = cx * w - bw / 2
            y1 = cy * h - bh
            x2 = x1 + bw
            y2 = y1 + bh
            dets.append(
                Detection(
                    frame=frame,
                    object_id=i,
                    box=Box(x1=x1, y1=y1, x2=x2, y2=y2, w=w, h=h),
                    class_name=class_name,
                    confidence=0.9,
                    chunk_index=0,
                )
            )
        return dets
    if class_name == "animal_generico":
        return []
    box = Box(x1=800, y1=400, x2=1000, y2=600, w=w, h=h)
    return [
        Detection(
            frame=frame,
            object_id=0,
            box=box,
            class_name=class_name,
            confidence=0.85,
            chunk_index=0,
        )
    ]


def probe_duration_s(video: Path | str, default: float = 10.0) -> float:
    """Duración del video en segundos (ffprobe); default si falla."""
    import subprocess

    video = Path(video)
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video),
            ],
            text=True,
        ).strip()
        return float(out) if out else default
    except Exception:
        return default


def extract_frames_at_fps(
    video: Path | str,
    out_dir: Path | str,
    *,
    fps: float = 1.0,
) -> list[tuple[int, Path, float]]:
    """Extrae frames a `fps` con ffmpeg. Devuelve (sample_idx, path, t_s)."""
    import subprocess

    video = Path(video)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("s_*.png"):
        old.unlink()
    pattern = str(out_dir / "s_%05d.png")
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            f"fps={fps}",
            pattern,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    frames = sorted(out_dir.glob("s_*.png"))
    out: list[tuple[int, Path, float]] = []
    for i, fp in enumerate(frames):
        out.append((i, fp, round(i / fps, 4) if fps else float(i)))
    return out
