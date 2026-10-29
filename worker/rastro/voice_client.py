"""Cliente de Muse Voice Transcribe 1.0 (Meta Model API).

Firma real (docs oficiales, 26 oct 2026):
  POST https://api.meta.ai/v1/asr/transcribe
  Authorization: Bearer $META_API_KEY
  Accept: application/json
  multipart/form-data:
    request = JSON {
      "model": "muse-voice-transcribe-1.0",
      "audioEncoding": "WAV",
      "mode": "DIARIZATION" | "ENDPOINTING" | "PUSH_TO_TALK",
      "languageBias": ["Spanish", "English"]  # opcional
    }
    audio = archivo WAV mono PCM 16-bit a 16 kHz o 24 kHz, máx 10 min / 32 MB

Respuesta JSON típica:
  {
    "sessionId": "...",
    "transcript": "...",
    "audioDurationMs": 8240,
    "turns": [
      {"turnId": 1, "startMs": 1520, "endMs": 4640,
       "transcript": "...", "speaker": "A"}
    ]
  }

Nota: timestamps son POR TURNO, no por palabra.

SIN CLAVE: modo mock con una nota de guardaparque de ejemplo.

Verificado 26 oct 2026: DIARIZATION + languageBias Spanish + WAV 24 kHz mono
devuelve sessionId, transcript, audioDurationMs, turns[{turnId,startMs,endMs,transcript,speaker}].
Precio: USD 0,18 / hora de audio.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

META_BASE_URL = "https://api.meta.ai/v1"
VOICE_MODEL = "muse-voice-transcribe-1.0"


def _api_key() -> str | None:
    return os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY")


def has_meta_key() -> bool:
    return bool(_api_key())


@dataclass
class VoiceTurn:
    turn_id: int
    start_ms: int
    end_ms: int
    transcript: str
    speaker: str | None = None


@dataclass
class VoiceResult:
    transcript: str
    turns: list[VoiceTurn] = field(default_factory=list)
    audio_duration_ms: int = 0
    session_id: str | None = None
    mock: bool = False
    est_usd: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transcript": self.transcript,
            "audio_duration_ms": self.audio_duration_ms,
            "session_id": self.session_id,
            "mock": self.mock,
            "est_usd": self.est_usd,
            "turns": [
                {
                    "turn_id": t.turn_id,
                    "start_ms": t.start_ms,
                    "end_ms": t.end_ms,
                    "start_s": round(t.start_ms / 1000.0, 3),
                    "end_s": round(t.end_ms / 1000.0, 3),
                    "transcript": t.transcript,
                    "speaker": t.speaker,
                }
                for t in self.turns
            ],
        }


class VoiceClient:
    """Transcribe un WAV con Muse Voice Transcribe, o lo simula."""

    def __init__(
        self,
        mock: bool | None = None,
        base_url: str = META_BASE_URL,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        if mock is None:
            mock = not has_meta_key()
        self.mock = mock

    def transcribe(
        self,
        wav_path: Path | str,
        *,
        mode: str = "DIARIZATION",
        language_bias: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> VoiceResult:
        """Transcribe un archivo WAV mono.

        El audio DEBE estar convertido antes:
          ffmpeg -i input.m4a -ac 1 -ar 24000 -c:a pcm_s16le out.wav
        """
        wav_path = Path(wav_path)
        if self.mock:
            return _mock_voice(wav_path)

        key = _api_key()
        if not key:
            raise RuntimeError("Falta META_API_KEY / MODEL_API_KEY")

        request_body: dict[str, Any] = {
            "model": VOICE_MODEL,
            "audioEncoding": "WAV",
            "mode": mode,
        }
        if language_bias:
            request_body["languageBias"] = language_bias
        if keywords:
            request_body["keywords"] = keywords

        with wav_path.open("rb") as audio:
            response = requests.post(
                f"{self.base_url}/asr/transcribe",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Accept": "application/json",
                },
                files={
                    "request": (None, json.dumps(request_body), "application/json"),
                    "audio": (wav_path.name, audio, "audio/wav"),
                },
                timeout=120,
            )
        response.raise_for_status()
        data = response.json()
        turns = [
            VoiceTurn(
                turn_id=int(t.get("turnId", i + 1)),
                start_ms=int(t.get("startMs", 0)),
                end_ms=int(t.get("endMs", 0)),
                transcript=str(t.get("transcript", "")),
                speaker=t.get("speaker"),
            )
            for i, t in enumerate(data.get("turns") or [])
        ]
        dur_ms = int(data.get("audioDurationMs", 0))
        est = (dur_ms / 1000.0 / 3600.0) * 0.18  # USD/hora
        return VoiceResult(
            transcript=str(data.get("transcript", "")),
            turns=turns,
            audio_duration_ms=dur_ms,
            session_id=data.get("sessionId"),
            mock=False,
            est_usd=est,
            raw=data,
        )


def _mock_voice(wav_path: Path) -> VoiceResult:
    text = (
        "Estación norte, 21:40. Vi movimiento cerca de la cámara tres. "
        "Parece una persona con linterna. Voy a revisar el perímetro."
    )
    return VoiceResult(
        transcript=text,
        turns=[
            VoiceTurn(
                turn_id=1,
                start_ms=0,
                end_ms=8000,
                transcript=text,
                speaker="A",
            )
        ],
        audio_duration_ms=8000,
        session_id=f"mock-{wav_path.stem}",
        mock=True,
        raw={"mock": True},
    )
