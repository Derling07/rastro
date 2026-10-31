"""Hour and weekday aggregates. Rows never include video, frames, or identities.

Seven real runs replace the example chart. Fewer than that, and the chart
stays labeled Example data. Traffic stays not verified either way.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

NEEDED_REAL_RUNS = 7
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_rows: list[dict[str, Any]] = []
_path: Path | None = None


def reset_peaks(path: Path | None = None) -> None:
    global _path
    _rows.clear()
    _path = path
    if path is not None and path.exists():
        path.unlink()


def _persist() -> None:
    if _path is None:
        return
    _path.parent.mkdir(parents=True, exist_ok=True)
    _path.write_text(json.dumps(_rows), encoding="utf-8")


def _weekday(created_at: str | None) -> int | None:
    if not created_at:
        return None
    text = created_at.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).weekday()
    except ValueError:
        return None


def note_finished_run(pack: str | None, result: dict[str, Any]) -> None:
    """Store one aggregate from a finished run. Mock runs and other packs are ignored."""
    if result.get("is_mock") is not False:
        return
    if pack not in {"transito", "multitudes"}:
        return
    hour = result.get("local_hour")
    if not isinstance(hour, int) or not 0 <= hour <= 23:
        return
    if pack == "transito":
        metric = "vehicles"
        value = int(result.get("naive_count") or 0)
        verified = False
    else:
        metric = "people"
        peak = result.get("peak_density") if isinstance(result.get("peak_density"), dict) else {}
        value = int((peak or {}).get("persons") or result.get("unique_count") or 0)
        verified = True
    row = {
        "station": str(result.get("station") or "station"),
        "pack": pack,
        "weekday": _weekday(str(result.get("created_at") or "")) if result.get("created_at") else None,
        "hour": hour,
        "metric": metric,
        "value": value,
        "verified": verified,
        "source": "real",
    }
    _rows.append(row)
    _persist()


def _example_value(module: str, weekday: int, hour: int) -> int:
    weekend = weekday >= 5
    if module == "traffic":
        if weekend:
            return 4 if 11 <= hour <= 16 else 0
        if hour in {7, 8, 9, 16, 17, 18}:
            return 12
        if 10 <= hour <= 15:
            return 5
        return 0
    if weekend and 12 <= hour <= 18:
        return 9
    if hour in {8, 12, 13, 17, 18}:
        return 6
    if 9 <= hour <= 16:
        return 3
    return 0


def _pack_rows(module: str, rows: list[dict[str, Any]]) -> tuple[list[list[int]], list[int]]:
    heat = [[0 for _ in range(24)] for _ in range(7)]
    series = [0 for _ in range(24)]
    for row in rows:
        hour = int(row["hour"])
        value = int(row["value"])
        series[hour] += value
        weekday = row.get("weekday")
        if isinstance(weekday, int) and 0 <= weekday <= 6:
            heat[weekday][hour] += value
    return heat, series


def open_peak_hours() -> dict[str, Any]:
    """Read-only traffic feed. Ready for a routing app to pull. Not a live integration."""
    view = peak_view("traffic")
    if view["badge"] == "Your data":
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in _rows:
            if row.get("source") != "real" or row.get("pack") != "transito":
                continue
            station = str(row["station"])
            weekday = row.get("weekday")
            grouped.setdefault(station, []).append(
                {
                    "weekday": WEEKDAYS[weekday] if isinstance(weekday, int) and 0 <= weekday <= 6 else None,
                    "hour": int(row["hour"]),
                    "vehicles": int(row["value"]),
                }
            )
        cameras = [
            {
                "camera_id": station,
                "not_verified": True,
                "peak_hours": sorted(hours, key=lambda item: (-item["vehicles"], item["hour"]))[:24],
            }
            for station, hours in sorted(grouped.items())
        ]
    else:
        hours = []
        for day, row in enumerate(view["heatmap"]):
            for hour, value in enumerate(row):
                if value:
                    hours.append({"weekday": WEEKDAYS[day], "hour": hour, "vehicles": value})
        hours.sort(key=lambda item: (-item["vehicles"], item["weekday"], item["hour"]))
        cameras = [
            {
                "camera_id": "example-intersection",
                "not_verified": True,
                "peak_hours": hours[:24],
            }
        ]
    return {
        "badge": view["badge"],
        "not_verified": True,
        "stores": "aggregates_only",
        "description": (
            "Read-only peak hours per camera. Exports in a standard format compatible with Waze for Cities. "
            "This server does not send the feed to Waze. Real ingestion requires joining Waze for Cities."
        ),
        "cameras": cameras,
    }


def peak_view(module: str) -> dict[str, Any]:
    if module not in {"crowd", "traffic"}:
        raise ValueError("module must be crowd or traffic")
    pack = "multitudes" if module == "crowd" else "transito"
    real = [row for row in _rows if row.get("source") == "real" and row.get("pack") == pack]
    yours = len(real) >= NEEDED_REAL_RUNS
    if yours:
        heat, series = _pack_rows(module, real)
        badge = "Your data"
    else:
        heat = [[_example_value(module, day, hour) for hour in range(24)] for day in range(7)]
        series = [sum(heat[day][hour] for day in range(7)) for hour in range(24)]
        badge = "Example data"
    return {
        "module": module,
        "badge": badge,
        "real_runs": len(real),
        "needed_runs": NEEDED_REAL_RUNS,
        "not_verified": module == "traffic",
        "unit": "vehicles" if module == "traffic" else "people",
        "weekdays": WEEKDAYS,
        "heatmap": heat,
        "series": series,
        "stores": "aggregates_only",
    }
