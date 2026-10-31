"""Names shown in the app. File names and pack ids stay in the stored JSON."""

from __future__ import annotations

import re

PACK_DISPLAY = {
    "fauna": "Wildlife camera",
    "fauna-camtrap": "Wildlife camera",
    "transito": "Intersection",
    "transito-giros": "Intersection",
    "multitudes": "Crowds",
    "multitudes-densidad": "Crowds",
    "farm": "Farm",
    "farm-pen": "Farm",
    "protected": "Protected area",
    "protected-zone": "Protected area",
}

# Camera ids use the site name, not a file name and not the word "clip".
CAMERA_DISPLAY = {
    "gray-fox": "Organ Mountains",
    "goat-lane": "Goat lane",
    "forest-trail": "Protected area",
    "plaza-mayor": "Plaza Mayor",
    "wicker-park": "Wicker Park",
    "trap-dscf0112": "Wildlife camera",
}


def report_title(pack: str | None) -> str:
    label = PACK_DISPLAY.get(pack or "", "This run")
    return f"Rastro report — {label}"


def camera_name(camera_id: str, fallback: str = "") -> str:
    return CAMERA_DISPLAY.get(camera_id, fallback or camera_id)


def public_copy(text: str) -> str:
    """Drop file names, frame rates, pack ids, and the placeholder station."""
    cleaned = text or ""
    cleaned = re.sub(r"\bok\.mp4\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"DSCF0112\.mp4(?:\s*\([^)]*\))?",
        "Wildlife camera",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"Clip\s+Intersection\.mp4", "Intersection", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"Intersection\.mp4", "Intersection", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\([^)]*\bfps\b[^)]*\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b[\w.-]+\.(?:mp4|mov|webm|ogv)\b", "", cleaned, flags=re.IGNORECASE)
    for raw, label in sorted(PACK_DISPLAY.items(), key=lambda item: -len(item[0])):
        cleaned = re.sub(rf"\b{re.escape(raw)}\b", label, cleaned)
    cleaned = re.sub(r"\s+at demo\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,])", r"\1", cleaned)
    return cleaned.strip()
