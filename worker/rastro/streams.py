"""Classify a camera URL. This demo does not open the stream.

RTSP, HLS, and MJPEG are recognized. Playback stays on a simulated clip.
Nothing here is a live connection, so the result is NOT VERIFIED.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def _redact(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return urlunparse((parsed.scheme, f"{host}{port}", parsed.path, "", "", ""))


def classify_stream(url: str) -> dict[str, object]:
    raw = (url or "").strip()
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"rtsp", "rtsps", "http", "https"}:
        raise ValueError("url must be rtsp, rtsps, http, or https")
    if parsed.username or parsed.password:
        raise ValueError("url must not include a secret")
    if not parsed.hostname:
        raise ValueError("url needs a host")
    path = (parsed.path or "").lower()
    query = (parsed.query or "").lower()
    if scheme in {"rtsp", "rtsps"}:
        kind = "rtsp"
    elif path.endswith(".m3u8") or path.endswith(".m3u") or "format=hls" in query:
        kind = "hls"
    elif (
        path.endswith(".mjpg")
        or path.endswith(".mjpeg")
        or "mjpeg" in path
        or "mjpg" in path
        or "multipart" in query
    ):
        kind = "mjpeg"
    else:
        raise ValueError("url is not rtsp, hls, or mjpeg")
    return {
        "kind": kind,
        "mode": "simulated",
        "connected": False,
        "not_verified": True,
        "redacted_url": _redact(raw),
        "fallback": "simulated clip",
        "note": "The stream was not opened. Playback stays on a simulated clip. NOT VERIFIED.",
    }
