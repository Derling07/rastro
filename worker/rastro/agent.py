"""Agente Muse Spark Open: recibe el resumen y arma reporte + alertas.

Usa Baseten. Si Baseten no está disponible, genera un reporte local
determinista para no bloquear el CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .spark_client import SparkClient
from .types import RunSummary

SYSTEM = """You are Rastro's report agent. You write in English only.

You receive JSON counts already computed by code. Do not change the numbers.
Write a short report for a field operator.
Confirm or restate the alerts already in the JSON.
Return ONLY JSON of this shape:
{
  "titulo": "...",
  "resumen": "2-4 sentences in English",
  "especies": [{"clase": "...", "individuos": N}],
  "alertas": [{"id": "...", "severidad": "...", "mensaje": "..."}],
  "recomendaciones": ["..."],
  "gancho_demo": "one short English line"
}

Rules:
- Never include a filesystem path. Refer to the clip by its file name only.
- For a density / crowd pack, do not talk about unique individuals or "N, not M".
  Say how many people are in view at once and the peak people per square meter.
- For traffic, do not call people "vehicles".
"""


def build_report(
    summary: RunSummary, *, use_spark: bool = True
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Arma el reporte y una bitácora agent_log. Intenta Spark; si falla, local."""
    payload = summary.to_dict()
    log: list[dict[str, Any]] = [
        {
            "step": 1,
            "tool": "agent.build_report",
            "detail": f"pack={summary.pack_id} unique={summary.unique_count}",
        }
    ]
    if use_spark:
        try:
            client = SparkClient()
            log.append({"step": 2, "tool": "spark.chat_json", "detail": "request"})
            data, reply = client.chat_json(
                prompt=(
                    "Numeric summary of a Rastro run. Do not change the numbers. "
                    "Write the report in English.\n\n"
                    + json.dumps(payload, ensure_ascii=False, indent=2)
                ),
                system=SYSTEM,
                schema_hint="titulo, resumen, especies, alertas, recomendaciones, gancho_demo",
            )
            data["_spark_model"] = reply.model
            data["_spark_usage"] = reply.usage
            data["_source"] = "baseten-spark"
            log.append(
                {
                    "step": 3,
                    "tool": "spark.chat_json",
                    "detail": f"source=baseten-spark model={reply.model}",
                }
            )
            return data, log
        except Exception as exc:  # noqa: BLE001
            fallback = _local_report(summary)
            fallback["_spark_error"] = str(exc)
            fallback["_source"] = "local-fallback"
            log.append(
                {
                    "step": 3,
                    "tool": "spark.chat_json",
                    "detail": f"fallback error={exc!s}"[:200],
                }
            )
            return fallback, log
    report = _local_report(summary)
    log.append({"step": 2, "tool": "agent.local_report", "detail": "source=local"})
    return report, log


def _clip_name(video: str) -> str:
    name = Path(video).name
    return name or "clip"


def _is_crowd(pack_id: str) -> bool:
    pid = pack_id.lower()
    return "multitud" in pid or "crowd" in pid or "densidad" in pid


def unique_noun(by_class: dict[str, int]) -> str:
    names = [(str(k), int(v)) for k, v in by_class.items() if int(v) > 0]
    if len(names) != 1:
        return "individuals"
    name, count = names[0]
    if count == 1 or name.endswith("s"):
        return name
    return f"{name}s"


def tracking_line(
    *,
    detections_total: int,
    naive: int,
    unique: int,
    by_class: dict[str, int],
) -> str:
    """Same sentence the UI headline uses."""
    if detections_total:
        left, word = detections_total, "raw detections"
    else:
        left, word = naive, "sightings"
    return f"{left} {word} → {unique} unique {unique_noun(by_class)}"


def crowd_line(density: float | None, zone: str | None = None) -> str:
    """Density only. A missing per-frame series is not a person count."""
    from .display_names import zone_label

    if not isinstance(density, (int, float)):
        return "No verified person count."
    line = f"Peak density {float(density):g} people/m² (NOT VERIFIED)"
    label = zone_label(zone)
    return f"{line}. {label}." if label else line


def _local_report(summary: RunSummary) -> dict[str, Any]:
    notas = list(summary.notes or [])
    clip = _clip_name(summary.video)
    if _is_crowd(summary.pack_id):
        line = crowd_line(None)
        resumen = (
            f"{line} This sector measures how many people are in view at once. "
            "It does not re-identify them."
        )
        gancho = line
        especies: list[dict[str, Any]] = []
        recomendaciones = [
            "Read the peak as density, not as unique people.",
        ]
    elif "transito" in summary.pack_id.lower() or "transit" in summary.pack_id.lower():
        resumen = f"{summary.naive_count} sightings in this clip. No verified vehicle count."
        gancho = resumen
        especies = []
        recomendaciones = [
            "Do not treat this as a verified traffic count.",
        ]
    else:
        clases = ", ".join(f"{k}={v}" for k, v in summary.by_class.items()) or "none"
        resumen = (
            f"Clip {clip}: {summary.naive_count} sightings, "
            f"{summary.unique_count} unique individuals. Classes: {clases}."
        )
        gancho = f"{summary.unique_count} unique, not {summary.naive_count} sightings"
        especies = [
            {"clase": k, "individuos": v} for k, v in sorted(summary.by_class.items())
        ]
        recomendaciones = [
            "Review clips with a high-severity alert.",
            "Check re-entries at the frame edge if the count looks low.",
        ]
    if notas:
        resumen += " Field note: " + " | ".join(notas[:2])
    return {
        "titulo": f"Rastro report — {summary.pack_id}",
        "resumen": resumen,
        "especies": especies,
        "alertas": summary.alerts,
        "notas_campo": notas,
        "recomendaciones": recomendaciones,
        "gancho_demo": gancho,
        "_source": "local",
    }
