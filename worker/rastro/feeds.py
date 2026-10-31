"""Read-only event export in a Waze CIFS-compatible shape, plus webhook outbox.

The incidents array follows the public Closure and Incident Feed fields
(id, type, street, polyline, direction, starttime, description). This process
does not send the file to Waze. Joining Waze for Cities is required before
ingestion. The file was not submitted, so it is NOT VERIFIED against the
live service. Coordinates are an example in San José, not a surveyed camera.
"""

from __future__ import annotations

import ipaddress
import socket
import threading
import xml.sax.saxutils as xml_escape
from typing import Any
from urllib.parse import urlparse

# Example point only. Not a measured camera position.
EXAMPLE_LAT = 9.928069
EXAMPLE_LON = -84.090725
EXAMPLE_POLYLINE = "9.928069 -84.090725 9.932100 -84.090725"
EXAMPLE_STREET = "Example road"
EXAMPLE_START = "2026-10-29T12:00:00-06:00"

CAP = 50
state_lock = threading.Lock()
_subscribers: list[dict[str, str]] = []
_outbox: list[dict[str, Any]] = []


def reset_feeds() -> None:
    with state_lock:
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
        _incident("example-crowd", "HAZARD", "Example crowd alert"),
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
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!-- Example data. NOT VERIFIED. Not submitted to Waze. -->",
        "<incidents>",
    ]
    for row in feed["incidents"]:
        parts.append("  <incident>")
        for key in ("id", "type", "description", "street", "direction", "polyline", "starttime", "creationtime"):
            value = xml_escape.escape(str(row[key]))
            parts.append(f"    <{key}>{value}</{key}>")
        parts.append("  </incident>")
    parts.append("</incidents>")
    return "\n".join(parts) + "\n"


def _blocked_ip(raw: str) -> bool:
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _addresses_for(host: str) -> list[str]:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return [host]
    found: list[str] = []
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError("webhook host did not resolve") from exc
    for info in infos:
        sockaddr = info[4]
        if sockaddr:
            found.append(str(sockaddr[0]))
    if not found:
        raise ValueError("webhook host did not resolve")
    return found


def _acceptable_webhook(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("webhook url must be http or https")
    if parsed.username or parsed.password:
        raise ValueError("webhook url must not include a secret")
    if not parsed.hostname:
        raise ValueError("webhook url needs a host")
    host = parsed.hostname
    if host.lower().endswith(".local"):
        raise ValueError("webhook host is not allowed")
    for address in _addresses_for(host):
        if _blocked_ip(address):
            raise ValueError("webhook host is not allowed")
    return parsed.geturl()


def mask_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return f"{parsed.scheme}://{host}/***"


def subscribe_webhook(url: str) -> dict[str, Any]:
    clean = _acceptable_webhook(url)
    with state_lock:
        for row in _subscribers:
            if row["url"] == clean:
                return {"id": row["id"], "url": mask_url(clean), "delivery": "off"}
        if len(_subscribers) >= CAP:
            raise ValueError("too many webhooks")
        row = {"id": f"wh-{len(_subscribers) + 1}", "url": clean}
        _subscribers.append(row)
    return {"id": row["id"], "url": mask_url(clean), "delivery": "off"}


def list_webhooks() -> dict[str, Any]:
    with state_lock:
        rows = list(_subscribers)
        outbox = list(_outbox)
    return {
        "delivery": "off",
        "not_verified": True,
        "memory_only": True,
        "note": "Subscriptions are stored in memory only. This demo does not POST to them.",
        "webhooks": [{"id": row["id"], "url": mask_url(row["url"])} for row in rows],
        "outbox": outbox,
    }


def enqueue_webhook(event: dict[str, Any]) -> None:
    """Record the payload that would be sent. Does not open a socket."""
    with state_lock:
        targets = [row["id"] for row in _subscribers]
        _outbox.append(
            {
                "event": event,
                "targets": targets,
                "delivered": False,
                "reason": "delivery off in this demo",
            }
        )
        del _outbox[:-CAP]
