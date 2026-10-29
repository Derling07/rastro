"""Pruebas reales contra Baseten (Muse Spark Open).

Nunca imprime la API key.
"""

from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path

from .spark_client import DEFAULT_MODEL, FALLBACK_MODEL, SparkClient

ROOT = Path(__file__).resolve().parents[2]
IMAGE = ROOT / "data" / "probe_animal.png"
AUDIO = ROOT / "data" / "probe_jfk.wav"


def _ok(name: str, detail: str) -> None:
    print(f"✅ {name}: {detail}")


def _fail(name: str, detail: str) -> None:
    print(f"❌ {name}: {detail}")


def _skip(name: str, detail: str) -> None:
    print(f"⚠️  {name}: {detail}")


def main() -> int:
    if not os.environ.get("BASETEN_API_KEY"):
        _fail("env", "BASETEN_API_KEY no está definida")
        return 1

    # Confirmamos que la clave existe sin mostrarla.
    key = os.environ["BASETEN_API_KEY"]
    _ok("env", f"BASETEN_API_KEY presente (len={len(key)}, prefix={key[:4]}…)")

    client = SparkClient()
    results: dict[str, dict] = {}

    # 1) Texto
    try:
        t0 = time.time()
        reply = client.chat_text(
            "Respondé con una sola palabra: hola",
            system="Sos un chequeo de conectividad. Respondé breve.",
        )
        dt = time.time() - t0
        results["text"] = {
            "ok": True,
            "model": reply.model,
            "text": reply.text[:200],
            "usage": reply.usage,
            "s": round(dt, 2),
        }
        _ok("texto", f"model={reply.model} s={dt:.2f} → {reply.text[:80]!r}")
    except Exception as exc:  # noqa: BLE001
        results["text"] = {"ok": False, "error": str(exc)}
        _fail("texto", str(exc))
        traceback.print_exc()

    # 2) Imagen
    if not IMAGE.exists():
        _skip("imagen", f"no está {IMAGE}")
        results["image"] = {"ok": False, "error": "missing image"}
    else:
        try:
            t0 = time.time()
            reply = client.chat_with_image(
                "En una frase: ¿qué forma y color dominante ves?",
                IMAGE,
            )
            dt = time.time() - t0
            results["image"] = {
                "ok": True,
                "model": reply.model,
                "text": reply.text[:300],
                "usage": reply.usage,
                "s": round(dt, 2),
            }
            _ok("imagen", f"model={reply.model} s={dt:.2f} → {reply.text[:100]!r}")
        except Exception as exc:  # noqa: BLE001
            results["image"] = {"ok": False, "error": str(exc)}
            _fail("imagen", str(exc))

    # 3) Audio
    if not AUDIO.exists():
        _skip("audio", f"no está {AUDIO}")
        results["audio"] = {"ok": False, "error": "missing audio"}
    else:
        try:
            t0 = time.time()
            reply = client.chat_with_audio(
                "Transcribí o resumí en una frase lo que se oye.",
                AUDIO,
            )
            dt = time.time() - t0
            results["audio"] = {
                "ok": True,
                "model": reply.model,
                "text": reply.text[:300],
                "usage": reply.usage,
                "s": round(dt, 2),
            }
            _ok("audio", f"model={reply.model} s={dt:.2f} → {reply.text[:100]!r}")
        except Exception as exc:  # noqa: BLE001
            results["audio"] = {"ok": False, "error": str(exc)}
            _fail("audio", str(exc))

    # 4) JSON estructurado
    try:
        t0 = time.time()
        data, reply = client.chat_json(
            'Devolvé {"saludo":"hola","n":1}',
            schema_hint='{"saludo": string, "n": number}',
        )
        dt = time.time() - t0
        results["json"] = {
            "ok": True,
            "model": reply.model,
            "data": data,
            "usage": reply.usage,
            "s": round(dt, 2),
        }
        _ok("json", f"model={reply.model} s={dt:.2f} → {data}")
    except Exception as exc:  # noqa: BLE001
        results["json"] = {"ok": False, "error": str(exc)}
        _fail("json", str(exc))

    # 5) Tool calling (si el modelo lo soporta)
    try:
        t0 = time.time()
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_counts",
                    "description": "Devuelve el conteo único de una corrida",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "run_id": {"type": "string"},
                        },
                        "required": ["run_id"],
                    },
                },
            }
        ]
        reply = client.chat(
            [
                {
                    "role": "user",
                    "content": "Usá la herramienta get_counts con run_id='demo-1'.",
                }
            ],
            tools=tools,
            tool_choice="auto",
        )
        dt = time.time() - t0
        # Inspeccionamos tool_calls en el raw si existen.
        tool_calls = None
        try:
            msg = reply.raw.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None)
        except Exception:
            tool_calls = None
        results["tools"] = {
            "ok": True,
            "model": reply.model,
            "text": (reply.text or "")[:200],
            "tool_calls": str(tool_calls)[:300] if tool_calls else None,
            "s": round(dt, 2),
        }
        if tool_calls:
            _ok("tools", f"model={reply.model} s={dt:.2f} tool_calls={tool_calls}")
        else:
            _skip(
                "tools",
                f"respondió sin tool_calls (texto={reply.text[:80]!r}). "
                "Puede que el modelo no soporte tools en este endpoint.",
            )
    except Exception as exc:  # noqa: BLE001
        results["tools"] = {"ok": False, "error": str(exc)}
        _fail("tools", str(exc))

    out = ROOT / "outputs" / "baseten_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "default_model": DEFAULT_MODEL,
                "fallback_model": FALLBACK_MODEL,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nResultados guardados en {out}")
    # Código de salida: 0 si texto OK (mínimo vital); avisamos el resto.
    return 0 if results.get("text", {}).get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
