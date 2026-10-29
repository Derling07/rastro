"""Fallback multi-prompt: si el prompt primario no detecta, probar siguientes.

El caché de SamClient ya incluye el `concept` en la clave — no se mezclan
respuestas entre 'coyote' y 'animal'.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .sam_client import SamClient, SamResult


def prompts_for_target(target: dict[str, Any]) -> list[str]:
    """Orden: prompt principal + fallbacks del target."""
    primary = str(target["prompt"])
    fbs = target.get("fallbacks") or []
    out = [primary]
    for p in fbs:
        p = str(p)
        if p not in out:
            out.append(p)
    return out


def segment_with_fallback(
    sam: SamClient,
    *,
    video_path: str,
    target: dict[str, Any],
    chunk_index: int = 0,
) -> tuple[SamResult, list[dict[str, Any]]]:
    """Prueba prompts en orden; se queda con el primero que traiga detecciones.

    Si todos dan 0, devuelve el último resultado (vacío) y la bitácora.
    """
    class_name = str(target["class"])
    log: list[dict[str, Any]] = []
    last: SamResult | None = None
    for prompt in prompts_for_target(target):
        result = sam.segment_video(
            video_path=video_path,
            concept=prompt,
            class_name=class_name,
            chunk_index=chunk_index,
        )
        entry = {
            "concept": prompt,
            "class": class_name,
            "n_detections": len(result.detections),
            "mock": result.mock,
            "elapsed_s": result.elapsed_s,
            "usage": result.usage,
            "est_usd": result.est_usd,
            "chosen": False,
            "mode": "video_track",
        }
        log.append(entry)
        last = result
        if result.detections:
            entry["chosen"] = True
            return result, log
    assert last is not None
    if log:
        log[-1]["chosen"] = True  # vacío, pero es el que queda
    return last, log


def segment_image_with_fallback(
    sam: SamClient,
    *,
    image_path: str | Path,
    target: dict[str, Any],
    frame_index: int = 0,
) -> tuple[SamResult, list[dict[str, Any]]]:
    """Igual que segment_with_fallback pero en modo imagen (sin límite de 16)."""
    class_name = str(target["class"])
    log: list[dict[str, Any]] = []
    last: SamResult | None = None
    for prompt in prompts_for_target(target):
        result = sam.segment_image(
            image_path=image_path,
            concept=prompt,
            class_name=class_name,
        )
        # Reasignar frame al índice de muestra del video.
        for d in result.detections:
            d.frame = frame_index
        entry = {
            "concept": prompt,
            "class": class_name,
            "n_detections": len(result.detections),
            "mock": result.mock,
            "elapsed_s": result.elapsed_s,
            "usage": result.usage,
            "est_usd": result.est_usd,
            "chosen": False,
            "mode": "image_sample",
            "frame": frame_index,
        }
        log.append(entry)
        last = result
        if result.detections:
            entry["chosen"] = True
            return result, log
    assert last is not None
    if log:
        log[-1]["chosen"] = True
    return last, log
