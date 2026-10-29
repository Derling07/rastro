"""Densidad por zona (paquete multitudes): pies en polígono, serie y alertas sostenidas.

Las personas se ubican por el centro inferior de la caja (bbox_bottom_center).
Sin area_m2 no hay densidad ni alertas de densidad: solo conteo de personas.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable

from .types import Box, Detection

_SUSTAINED_RE = re.compile(
    r"density_per_m2\s*>=\s*([0-9.]+)\s+SUSTAINED\s+(\w+)",
    re.IGNORECASE,
)


def bbox_bottom_center_norm(box: Box) -> tuple[float, float]:
    """Punto de los pies en coords normalizadas 0..1: (cx, y2)."""
    w = box.w if box.w else 1.0
    h = box.h if box.h else 1.0
    return (box.x1 + box.x2) / 2.0 / w, box.y2 / h


def point_in_polygon(x: float, y: float, polygon: list[list[float]]) -> bool:
    """Ray casting; polígono en coords normalizadas [[x,y], ...]."""
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = float(polygon[i][0]), float(polygon[i][1])
        xj, yj = float(polygon[j][0]), float(polygon[j][1])
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi
        ):
            inside = not inside
        j = i
    return inside


def zone_of_box(
    box: Box,
    zones: list[dict[str, Any]],
) -> str | None:
    """Primera zona cuyo polígono contiene el centro inferior de la caja."""
    nx, ny = bbox_bottom_center_norm(box)
    for z in zones:
        poly = z.get("polygon") or []
        if point_in_polygon(nx, ny, poly):
            return str(z.get("id") or "zona")
    return None


def count_persons_per_zone(
    detections: Iterable[Detection],
    zones: list[dict[str, Any]],
    *,
    class_names: set[str] | None = None,
) -> dict[str, int]:
    """Cuenta personas (detecciones) por zona en un conjunto de detecciones."""
    counts: dict[str, int] = {str(z.get("id") or "zona"): 0 for z in zones}
    for d in detections:
        if class_names is not None and d.class_name not in class_names:
            continue
        zid = zone_of_box(d.box, zones)
        if zid is not None:
            counts[zid] = counts.get(zid, 0) + 1
    return counts


def build_density_series(
    detections: list[Detection],
    zones: list[dict[str, Any]],
    *,
    fps: float,
    class_names: set[str] | None = None,
    point: str = "bbox_bottom_center",
) -> list[dict[str, Any]]:
    """Serie density[] = {t_s, zone, persons, density_per_m2} por frame muestreado.

    density_per_m2 es null si la zona no tiene area_m2.
    """
    if point != "bbox_bottom_center":
        raise ValueError(f"Punto de densidad no soportado: {point}")
    if fps <= 0:
        raise ValueError("fps debe ser > 0")

    by_frame: dict[int, list[Detection]] = defaultdict(list)
    for d in detections:
        if class_names is not None and d.class_name not in class_names:
            continue
        by_frame[d.frame].append(d)

    area_of = {
        str(z.get("id") or "zona"): z.get("area_m2") for z in zones
    }
    series: list[dict[str, Any]] = []
    for frame in sorted(by_frame):
        t_s = round(frame / fps, 4)
        counts = count_persons_per_zone(by_frame[frame], zones, class_names=None)
        for zid, persons in counts.items():
            area = area_of.get(zid)
            dens: float | None
            if area is None:
                dens = None
            else:
                area_f = float(area)
                dens = round(persons / area_f, 4) if area_f > 0 else None
            series.append(
                {
                    "t_s": t_s,
                    "zone": zid,
                    "persons": int(persons),
                    "density_per_m2": dens,
                }
            )
    # También emitir frames vacíos no: solo frames con al menos una detección
    # de la clase. Para alertas sostenidas necesitamos continuidad temporal.
    # Completamos huecos por zona entre min y max frame a paso 1/fps.
    if not by_frame or not zones:
        return series

    min_f, max_f = min(by_frame), max(by_frame)
    # Indexar lo ya calculado
    have = {(row["t_s"], row["zone"]) for row in series}
    filled: list[dict[str, Any]] = list(series)
    for frame in range(min_f, max_f + 1):
        t_s = round(frame / fps, 4)
        counts = count_persons_per_zone(
            by_frame.get(frame, []), zones, class_names=None
        )
        for z in zones:
            zid = str(z.get("id") or "zona")
            if (t_s, zid) in have:
                continue
            persons = int(counts.get(zid, 0))
            area = z.get("area_m2")
            dens = None
            if area is not None and float(area) > 0:
                dens = round(persons / float(area), 4)
            filled.append(
                {
                    "t_s": t_s,
                    "zone": zid,
                    "persons": persons,
                    "density_per_m2": dens,
                }
            )
            have.add((t_s, zid))
    filled.sort(key=lambda r: (r["t_s"], r["zone"]))
    return filled


def peak_density(series: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pico de density_per_m2 (ignora null)."""
    best = None
    for row in series:
        d = row.get("density_per_m2")
        if d is None:
            continue
        if best is None or float(d) > float(best["density_per_m2"]):
            best = {
                "zone": row["zone"],
                "t_s": row["t_s"],
                "persons": row["persons"],
                "density_per_m2": float(d),
            }
    return best


def persons_per_zone_peak(series: list[dict[str, Any]]) -> dict[str, int]:
    """Máximo de personas por zona a lo largo de la serie."""
    peaks: dict[str, int] = {}
    for row in series:
        z = str(row["zone"])
        peaks[z] = max(peaks.get(z, 0), int(row["persons"]))
    return peaks


def _moving_average(
    times: list[float],
    values: list[float],
    window_s: float,
) -> list[float]:
    """Media móvil causal: promedio de valores en [t - window_s, t]."""
    out: list[float] = []
    n = len(times)
    for i in range(n):
        t = times[i]
        lo = t - window_s
        nums = [values[j] for j in range(i + 1) if times[j] >= lo]
        out.append(sum(nums) / len(nums) if nums else values[i])
    return out


def _parse_sustained(when: str) -> tuple[float, str] | None:
    m = _SUSTAINED_RE.search(when or "")
    if not m:
        return None
    return float(m.group(1)), m.group(2)


def evaluate_sustained_density_alerts(
    series: list[dict[str, Any]],
    alert_specs: list[dict[str, Any]],
    *,
    smoothing_window_s: float = 5.0,
    sustain_s: float = 10.0,
    sustain_keys: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Alertas density_per_m2 >= T SUSTAINED sustain_s (media móvil).

    sustain_keys permite resolver nombres del pack (p. ej. sustain_s → 10).
    Dispara una alerta por (zona, regla) al inicio del tramo sostenido.
    """
    sustain_keys = sustain_keys or {}
    fired: list[dict[str, Any]] = []
    by_zone: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in series:
        by_zone[str(row["zone"])].append(row)

    for spec in alert_specs:
        when = spec.get("when") or ""
        parsed = _parse_sustained(when)
        if parsed is None:
            continue
        threshold, sustain_name = parsed
        sustain = float(sustain_keys.get(sustain_name, sustain_s))
        aid = spec.get("id", "alert")
        severity = spec.get("severity", "info")
        msg_tmpl = spec.get("message", aid)

        for zid, rows in by_zone.items():
            rows = sorted(rows, key=lambda r: float(r["t_s"]))
            times = [float(r["t_s"]) for r in rows]
            vals: list[float] = []
            usable = True
            for r in rows:
                d = r.get("density_per_m2")
                if d is None:
                    usable = False
                    break
                vals.append(float(d))
            if not usable or not vals:
                continue
            smooth = _moving_average(times, vals, smoothing_window_s)
            run_start: float | None = None
            already = False
            for i, (t, s) in enumerate(zip(times, smooth)):
                if s >= threshold:
                    if run_start is None:
                        run_start = t
                        already = False
                    held = t - run_start
                    if held >= sustain - 1e-9 and not already:
                        dens_now = vals[i]
                        try:
                            message = msg_tmpl.format(
                                density_per_m2=round(dens_now, 2),
                                zone=zid,
                                sustain_s=sustain,
                            )
                        except (KeyError, ValueError):
                            message = msg_tmpl
                        fired.append(
                            {
                                "id": aid,
                                "severity": severity,
                                "message": message,
                                "t_s": round(run_start, 4),
                                "zone": zid,
                                "density_per_m2": round(dens_now, 4),
                                "sustain_s": sustain,
                            }
                        )
                        already = True
                else:
                    run_start = None
                    already = False
    return fired
