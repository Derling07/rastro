"""Agente Muse Spark Open: recibe el resumen y arma reporte + alertas.

Usa Baseten. Si Baseten no está disponible, genera un reporte local
determinista para no bloquear el CLI.
"""

from __future__ import annotations

import json
from typing import Any

from .spark_client import SparkClient
from .types import RunSummary

SYSTEM = """Sos el agente de reportes de Rastro, un sistema que sigue animales
y personas en video de cámaras trampa sin contarlas dos veces.

Recibís un JSON con conteos ya calculados por código (NO los inventes).
Tu trabajo:
1) Redactar un reporte corto en español (Costa Rica), claro para un guardaparque.
2) Confirmar o reforzar las alertas que ya vienen en el JSON.
3) Devolver SOLO un JSON con esta forma:
{
  "titulo": "...",
  "resumen": "2-4 oraciones",
  "especies": [{"clase": "...", "individuos": N}],
  "alertas": [{"id": "...", "severidad": "...", "mensaje": "..."}],
  "recomendaciones": ["..."],
  "gancho_demo": "frase corta tipo: 3, no 11"
}
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
                    "Este es el resumen numérico de una corrida de Rastro. "
                    "No cambies los números. Redactá el reporte.\n\n"
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


def _local_report(summary: RunSummary) -> dict[str, Any]:
    especies = [
        {"clase": k, "individuos": v} for k, v in sorted(summary.by_class.items())
    ]
    notas = list(summary.notes or [])
    resumen = (
        f"Video {summary.video}: conteo ingenuo {summary.naive_count}, "
        f"individuos únicos {summary.unique_count}. "
        f"Clases: {', '.join(f'{k}={v}' for k, v in summary.by_class.items()) or 'ninguna'}."
    )
    if notas:
        resumen += " Nota de campo: " + " | ".join(notas[:2])
    return {
        "titulo": f"Reporte Rastro — {summary.pack_id}",
        "resumen": resumen,
        "especies": especies,
        "alertas": summary.alerts,
        "notas_campo": notas,
        "recomendaciones": [
            "Revisar clips con alerta alta.",
            "Confirmar reentradas en el borde del frame si el conteo parece bajo.",
        ],
        "gancho_demo": f"{summary.unique_count}, no {summary.naive_count}",
        "_source": "local",
    }
