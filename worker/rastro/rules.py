"""Motor de reglas determinista: cruces, alertas, densidades.

IMPORTANTE: los números los calcula este código, NO el LLM.
Así los conteos se pueden auditar en el demo.
"""

from __future__ import annotations

from typing import Any

from .types import Box, Event, Track


def point_side(line: list[list[float]], x: float, y: float) -> float:
    """Signo del lado de un punto respecto a una línea (coords normalizadas 0..1).

    line = [[x1,y1],[x2,y2]]. Devuelve >0, <0 o ~0.
    """
    (x1, y1), (x2, y2) = line
    return (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)


def line_crossings(
    tracks: list[Track],
    lines: list[dict[str, Any]],
    *,
    fps: float,
) -> list[Event]:
    """Detecta cuándo el centro de una pista cruza una línea del paquete."""
    events: list[Event] = []
    if not lines:
        return events
    for track in tracks:
        if len(track.detections) < 2:
            continue
        for line_spec in lines:
            line = line_spec["line"]
            lid = line_spec.get("id", "line")
            prev_side = None
            for det in track.detections:
                # Normalizamos el centro a 0..1 usando w/h de la caja.
                box = det.box
                nx, ny = box.cx / box.w, box.cy / box.h
                side = point_side(line, nx, ny)
                if prev_side is not None and side * prev_side < 0:
                    direction = "A_to_B" if prev_side < 0 else "B_to_A"
                    events.append(
                        Event(
                            kind="line_cross",
                            t_s=det.frame / fps,
                            payload={
                                "track_id": track.track_id,
                                "class": track.class_name,
                                "line_id": lid,
                                "direction": direction,
                                "frame": det.frame,
                            },
                        )
                    )
                if abs(side) > 1e-9:
                    prev_side = side
    return events


def _format_message(tmpl: str, **fields: Any) -> str:
    """Arma el mensaje de alerta. 'class' es nombre de campo del paquete."""
    try:
        return tmpl.format(**fields)
    except KeyError:
        return tmpl


def _first_t_s(tracks: list[Track], class_name: str | None, fps: float) -> float:
    """Segundo del video de la primera detección de la clase (o 0)."""
    cands = [t for t in tracks if class_name is None or t.class_name == class_name]
    if not cands or fps <= 0:
        return 0.0
    t0 = min(cands, key=lambda t: t.start_frame)
    return round(t0.start_frame / fps, 4)


def evaluate_alerts(
    tracks: list[Track],
    by_class: dict[str, int],
    alert_specs: list[dict[str, Any]],
    *,
    fps: float,
    local_hour: int | None = None,
    station: str = "demo",
) -> list[dict[str, Any]]:
    """Evalúa las reglas de alerta del paquete (subset simple del DSL).

    Cada alerta incluye `t_s` (segundo del video) para CORE/web.
    """
    fired: list[dict[str, Any]] = []
    for spec in alert_specs:
        when = spec.get("when", "")
        aid = spec.get("id", "alert")
        msg_tmpl = spec.get("message", aid)
        severity = spec.get("severity", "info")

        if "persona" in when and "local_hour" in when:
            if "persona" not in by_class or by_class["persona"] < 1:
                continue
            if local_hour is None:
                continue
            night = True
            if "NOT IN" in when and ".." in when:
                try:
                    rng = when.split("NOT IN", 1)[1].strip()
                    a, b = rng.split("..")
                    lo, hi = int(a.strip()), int(b.strip())
                    night = not (lo <= local_hour <= hi)
                except Exception:
                    night = local_hour < 6 or local_hour > 18
            if night:
                fired.append(
                    {
                        "id": aid,
                        "severity": severity,
                        "message": _format_message(
                            msg_tmpl,
                            station=station,
                            **{"class": "persona"},
                            unique_count=by_class["persona"],
                        ),
                        "local_hour": local_hour,
                        "t_s": _first_t_s(tracks, "persona", fps),
                    }
                )
            continue

        if "unique_count" in when:
            cls = None
            if "class ==" in when:
                cls = when.split("class ==", 1)[1].split("AND")[0].strip().strip("'\"")
            if cls and by_class.get(cls, 0) >= 1:
                fired.append(
                    {
                        "id": aid,
                        "severity": severity,
                        "message": _format_message(
                            msg_tmpl,
                            station=station,
                            **{"class": cls},
                            unique_count=by_class[cls],
                        ),
                        "t_s": _first_t_s(tracks, cls, fps),
                    }
                )
            continue

    return fired


def boxes_near_edge(box: Box, edge_px: float = 80.0) -> bool:
    return (
        box.x1 <= edge_px
        or box.y1 <= edge_px
        or (box.w - box.x2) <= edge_px
        or (box.h - box.y2) <= edge_px
    )



# --- Tránsito: matriz de giros N/S/E/O (compatible con web/src/lib/transito.ts) ---

CARDINALS = ("N", "S", "E", "O")

# Etiquetas por defecto (tráfico por la derecha, CR): origen→destino.
_DEFAULT_TURN_LABELS: dict[str, str] = {
    "N->S": "recto",
    "S->N": "recto",
    "E->O": "recto",
    "O->E": "recto",
    "N->E": "izquierda",
    "E->S": "izquierda",
    "S->O": "izquierda",
    "O->N": "izquierda",
    "N->O": "derecha",
    "O->S": "derecha",
    "S->E": "derecha",
    "E->N": "derecha",
}


def cardinal_from_line_id(line_id: str | None) -> str | None:
    """Extrae N/S/E/O de ids como acceso_N, approach_S, N, line-E."""
    if not line_id:
        return None
    s = str(line_id).strip().upper()
    if s in CARDINALS:
        return s
    # acceso_N / approach_S / line_E / from-O
    for sep in ("_", "-", ":"):
        if sep in s:
            tail = s.rsplit(sep, 1)[-1]
            if tail in CARDINALS:
                return tail
    return None


def access_lines_from_geometry(geometry: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Normaliza geometry.lines + geometry.approaches a líneas con cardinal.

    FRONT espera ids acceso_N/S/E/O; el plan usa approaches[].id = N/S/E/O.
    Cada ítem: {id, line, cardinal}.
    """
    geometry = geometry or {}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(raw_id: Any, line: Any) -> None:
        if not isinstance(line, list) or len(line) < 2:
            return
        card = cardinal_from_line_id(str(raw_id) if raw_id is not None else None)
        if card is None:
            return
        lid = str(raw_id) if raw_id is not None else f"acceso_{card}"
        # Preferir id canónico acceso_X si el pack ya lo trae; si no, conservar.
        if lid.upper() in CARDINALS:
            lid = f"acceso_{lid.upper()}"
        key = card
        if key in seen:
            return
        seen.add(key)
        out.append({"id": lid, "line": line, "cardinal": card})

    for spec in geometry.get("lines") or []:
        if not isinstance(spec, dict):
            continue
        _add(spec.get("id"), spec.get("line"))

    for spec in geometry.get("approaches") or []:
        if not isinstance(spec, dict):
            continue
        _add(spec.get("id"), spec.get("line"))

    return out


def turn_label(movement: str, turning_rules: dict[str, Any] | None = None) -> str:
    """Etiqueta del giro (recto/izquierda/derecha) desde pack.turning_rules o default."""
    rules = turning_rules or {}
    if movement in rules and isinstance(rules[movement], str):
        return str(rules[movement])
    if "_" in rules and isinstance(rules["_"], str) and rules["_"] != "por_orientacion":
        return str(rules["_"])
    return _DEFAULT_TURN_LABELS.get(movement, "por_orientacion")


def turning_movements(
    tracks: list[Track],
    access_lines: list[dict[str, Any]],
    *,
    fps: float,
    turning_rules: dict[str, Any] | None = None,
) -> list[Event]:
    """Emite events kind=turn con movement 'N->S' (entrada->salida).

    Por pista: primer cruce de acceso = entrada, último distinto = salida.
    Compatible con web parseMovement / buildTurnMatrix (kind turn + movement).
    """
    events: list[Event] = []
    if not access_lines or fps <= 0:
        return events

    # Reusar detector de cruces; line_id conserva el id del acceso.
    crosses = line_crossings(tracks, access_lines, fps=fps)
    by_track: dict[str, list[Event]] = {}
    track_class: dict[str, str] = {}
    for ev in crosses:
        tid = str(ev.payload.get("track_id") or "")
        if not tid:
            continue
        by_track.setdefault(tid, []).append(ev)
        track_class[tid] = str(ev.payload.get("class") or "")

    for tid, evs in by_track.items():
        evs_sorted = sorted(evs, key=lambda e: (e.t_s, e.payload.get("frame") or 0))
        cards: list[tuple[str, Event]] = []
        for ev in evs_sorted:
            card = cardinal_from_line_id(str(ev.payload.get("line_id") or ""))
            if card is None:
                # access_lines ya trae cardinal; fallback por id
                continue
            cards.append((card, ev))
        if len(cards) < 2:
            continue
        entry_card, _entry_ev = cards[0]
        exit_card, exit_ev = cards[-1]
        if entry_card == exit_card:
            # Buscar el último cardinal distinto del de entrada
            exit_card = None
            exit_ev = None
            for c, ev in reversed(cards):
                if c != entry_card:
                    exit_card, exit_ev = c, ev
                    break
            if exit_card is None or exit_ev is None:
                continue
        movement = f"{entry_card}->{exit_card}"
        label = turn_label(movement, turning_rules)
        events.append(
            Event(
                kind="turn",
                t_s=float(exit_ev.t_s),
                payload={
                    "track_id": tid,
                    "class": track_class.get(tid) or "",
                    "movement": movement,
                    "label": label,
                    "entry": entry_card,
                    "exit": exit_card,
                },
            )
        )
    events.sort(key=lambda e: e.t_s)
    return events


def matriz_giros_from_events(events: list[dict[str, Any]] | list[Event]) -> dict[str, int]:
    """Agrega conteos origen→destino desde events[].movement (kind=turn)."""
    out: dict[str, int] = {}
    for raw in events:
        if isinstance(raw, Event):
            d = raw.to_dict()
        else:
            d = raw
        kind = d.get("kind")
        if kind is not None and str(kind) != "turn":
            continue
        mov = d.get("movement")
        if not isinstance(mov, str):
            continue
        m = mov.strip().upper()
        parts = m.split("->")
        if len(parts) != 2:
            continue
        a, b = parts[0].strip(), parts[1].strip()
        if a not in CARDINALS or b not in CARDINALS:
            continue
        key = f"{a}->{b}"
        out[key] = out.get(key, 0) + 1
    return out
