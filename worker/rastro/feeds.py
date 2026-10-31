"""Read-only event export in a Waze CIFS-compatible shape, plus webhook outbox.

The incidents array follows the public Closure and Incident Feed fields
(id, type, street, polyline, direction, starttime, description). This process
does not send the file to Waze. Joining Waze for Cities is required before
ingestion. The file was not submitted, so it is NOT VERIFIED against the
live service. Coordinates are an example in San José, not a surveyed camera.
"""

from __future__ import annotations

import xml.sax.saxutils as xml_escape
from typing import Any
from urllib.parse import urlparse

# Example point only. Not a measured camera position.
EXAMPLE_LAT = 9.928069
EXAMPLE_LON = -84.090725
EXAMPLE_POLYLINE = "9.928069 -84.090725 9.932100 -84.090725"
EXAMPLE_STREET = "Example road"
EXAMPLE_START = "2026-10-29T12:00:00-06:00"

_subscribers: list[dict[str, str]] = []
_outbox: list[dict[str, Any]] = []


def reset_feeds() -> None:
    _subscribers.clear()
    _outbox.clear()


def waze_ul(lat: float = EXAMPLE_LAT, lon: float = EXAMPLE_LON) -> str:
    """Deep link. Opens Waze at an example coordinate. Does not publish an incident."""
    return f"https://www.waze.com/ul?ll={lat},{lon}&navigate=yes&zoom=16"


def _incident(incident_id: str, incident_type: str, description: str) -> dict[str, str]:
    # Fields match the public CIFS JSON example. No extra keys inside the incident.
    return {
        "id": incident_id,
        "type": incident_type,
        "description": description,
        "street": EXAMPLE_STREET,
        "direction": "BOTH_DIRECTIONS",
        "polyline": EXAMPLE_POLYLINE,
        "starttime": EXAMPLE_START,
        "creationtime": EXAMPLE_START,
    }


def cifs_feed() -> dict[str, Any]:
    """Example incidents only. Do not submit this file to Waze as a live closure."""
    incidents = [
        _incident("example-traffic", "HAZARD", "Example traffic alert"),
        _incident("example-crowd", "JAM", "Example crowd alert"),
    ]
    return {
        "description": (
            "Exports in a standard format compatible with Waze for Cities. "
            "Not a partnership. This server does not send the feed to Waze. "
            "Real ingestion requires joining Waze for Cities. NOT VERIFIED."
        ),
        "partnership": False,
        "not_verified": True,
        "example_data": True,
        "submit_to_waze": False,
        "incidents": incidents,
        "links": [
            {
                "incident_id": row["id"],
                "waze_ul": waze_ul(),
                "example_data": True,
                "note": "Deep link only. It does not publish the incident.",
            }
            for row in incidents
        ],
    }


def cifs_xml(feed: dict[str, Any] | None = None) -> str:
    feed = feed or cifs_feed()
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<incidents>"]
    for row in feed["incidents"]:
        parts.append("  <incident>")
        for key in ("id", "type", "description", "street", "direction", "polyline", "starttime", "creationtime"):
            value = xml_escape.escape(str(row[key]))
            parts.append(f"    <{key}>{value}</{key}>")
        parts.append("  </incident>")
    parts.append("</incidents>")
    return "\n".join(parts) + "\n"


def _acceptable_webhook(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("webhook url must be http or https")
    if parsed.username or parsed.password:
        raise ValueError("webhook url must not include a secret")
    if not parsed.hostname:
        raise ValueError("webhook url needs a host")
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
        raise ValueError("webhook host is not allowed")
    if host == "169.254.169.254" or host.startswith("169.254."):
        raise ValueError("webhook host is not allowed")
    return parsed.geturl()


def subscribe_webhook(url: str) -> dict[str, Any]:
    clean = _acceptable_webhook(url)
    for row in _subscribers:
        if row["url"] == clean:
            return {"id": row["id"], "url": clean, "delivery": "off"}
    row = {"id": f"wh-{len(_subscribers) + 1}", "url": clean}
    _subscribers.append(row)
    return {"id": row["id"], "url": clean, "delivery": "off"}


def list_webhooks() -> dict[str, Any]:
    return {
        "delivery": "off",
        "not_verified": True,
        "note": "Subscriptions are stored in memory. This demo does not POST to them.",
        "webhooks": [{"id": row["id"], "url": row["url"]} for row in _subscribers],
        "outbox": list(_outbox),
    }


def enqueue_webhook(event: dict[str, Any]) -> None:
    """Record the payload that would be sent. Does not open a socket."""
    _outbox.append(
        {
            "event": event,
            "targets": [row["id"] for row in _subscribers],
            "delivered": False,
            "reason": "delivery off in this demo",
        }
    )
