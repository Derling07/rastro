"""Cliente de Muse Spark Open vía Baseten (créditos del hackathon).

Base: https://inference.baseten.co/v1  (compatible con OpenAI Chat Completions)
Modelo exacto (correo de Baseten): meta-models/muse-spark-open-1026
Clave: $BASETEN_API_KEY

Docs vision: https://docs.baseten.co/inference/model-apis/vision
Docs audio:  https://docs.baseten.co/inference/model-apis/audio

Nota: la tabla pública de Baseten lista el slug corto
`meta-models/muse-spark-open`. El correo del evento pide el slug con
sufijo `-1026`. Probamos el del correo primero.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

BASETEN_BASE_URL = "https://inference.baseten.co/v1"
# Slug exacto del correo de Baseten para el hackathon.
DEFAULT_MODEL = "meta-models/muse-spark-open-1026"
# Fallback documentado en la tabla pública de Baseten.
FALLBACK_MODEL = "meta-models/muse-spark-open"


def _api_key() -> str:
    key = os.environ.get("BASETEN_API_KEY")
    if not key:
        raise RuntimeError(
            "Falta BASETEN_API_KEY. Pegala en el vault / exportala en el shell."
        )
    return key


@dataclass
class SparkReply:
    text: str
    model: str
    usage: dict[str, Any]
    raw: Any = None


class SparkClient:
    """Habla con Muse Spark Open en Baseten."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = BASETEN_BASE_URL,
    ) -> None:
        self.model = model
        self.client = OpenAI(base_url=base_url, api_key=_api_key())

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> SparkReply:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        try:
            resp = self.client.chat.completions.create(**kwargs)
        except Exception as first_err:
            # Si el slug -1026 falla, probamos el corto documentado.
            if self.model == DEFAULT_MODEL:
                self.model = FALLBACK_MODEL
                kwargs["model"] = self.model
                resp = self.client.chat.completions.create(**kwargs)
            else:
                raise first_err

        choice = resp.choices[0].message
        text = choice.content or ""
        usage = {}
        if resp.usage is not None:
            usage = {
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                "completion_tokens": getattr(resp.usage, "completion_tokens", None),
                "total_tokens": getattr(resp.usage, "total_tokens", None),
            }
        return SparkReply(text=text, model=self.model, usage=usage, raw=resp)

    def chat_text(self, prompt: str, system: str | None = None) -> SparkReply:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages)

    def chat_with_image(
        self,
        prompt: str,
        image_path: Path | str,
        *,
        system: str | None = None,
    ) -> SparkReply:
        """Manda una imagen local como data URL (docs: image_url)."""
        image_path = Path(image_path)
        mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url, "detail": "auto"},
                    },
                ],
            }
        )
        return self.chat(messages)

    def chat_with_audio(
        self,
        prompt: str,
        audio_path: Path | str,
        *,
        system: str | None = None,
    ) -> SparkReply:
        """Manda un audio local como data URL (docs: audio_url)."""
        audio_path = Path(audio_path)
        mime = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"
        b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "audio_url", "audio_url": {"url": data_url}},
                ],
            }
        )
        return self.chat(messages)

    def chat_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        schema_hint: str | None = None,
    ) -> tuple[dict[str, Any], SparkReply]:
        """Pide JSON. Intenta response_format=json_object; si falla, parsea el texto."""
        sys = system or "Respondé SOLO con JSON válido, sin markdown."
        if schema_hint:
            sys = f"{sys}\nEsquema esperado: {schema_hint}"
        messages = [
            {"role": "system", "content": sys},
            {"role": "user", "content": prompt},
        ]
        try:
            reply = self.chat(
                messages, response_format={"type": "json_object"}
            )
        except Exception:
            reply = self.chat(messages)

        text = reply.text.strip()
        if text.startswith("```"):
            # Por si el modelo envuelve en fence a pesar de la instrucción.
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        return json.loads(text), reply
