"""Pruebas de cruces de línea y alertas."""

from __future__ import annotations

from rastro.rules import evaluate_alerts, line_crossings, point_side  # noqa: F401 — extras in new tests
from rastro.types import Box, Detection, Track


def test_point_side_signs():
    line = [[0.0, 0.5], [1.0, 0.5]]  # horizontal a mitad de altura
    assert point_side(line, 0.5, 0.2) > 0 or point_side(line, 0.5, 0.2) < 0
    # Puntos a distintos lados deben tener signos opuestos.
    s1 = point_side(line, 0.5, 0.2)
    s2 = point_side(line, 0.5, 0.8)
    assert s1 * s2 < 0


def test_line_crossing_event():
    # Pista que cruza una línea vertical en x=0.5
    dets = []
    for i, x in enumerate([0.2, 0.3, 0.4, 0.6, 0.7]):
        # Convertimos coords normalizadas a píxeles (w=1000).
        px = x * 1000
        dets.append(
            Detection(
                frame=i,
                object_id=0,
                box=Box(x1=px, y1=400, x2=px + 50, y2=480, w=1000, h=1000),
                class_name="auto",
            )
        )
    track = Track(track_id="auto-1", class_name="auto", detections=dets)
    lines = [{"id": "N", "line": [[0.5, 0.0], [0.5, 1.0]]}]
    events = line_crossings([track], lines, fps=10.0)
    assert len(events) == 1
    assert events[0].kind == "line_cross"
    assert events[0].payload["line_id"] == "N"


def test_persona_noche_alert():
    alerts = evaluate_alerts(
        tracks=[],
        by_class={"persona": 1},
        alert_specs=[
            {
                "id": "persona_noche",
                "when": "class == 'persona' AND local_hour NOT IN 6..18",
                "severity": "alta",
                "message": "Persona detectada de noche en la estación {station}",
            }
        ],
        fps=10.0,
        local_hour=22,
        station="norte",
    )
    assert len(alerts) == 1
    assert "noche" in alerts[0]["message"]


def test_persona_de_dia_no_alerta():
    alerts = evaluate_alerts(
        tracks=[],
        by_class={"persona": 1},
        alert_specs=[
            {
                "id": "persona_noche",
                "when": "class == 'persona' AND local_hour NOT IN 6..18",
                "severity": "alta",
                "message": "Persona detectada de noche en la estación {station}",
            }
        ],
        fps=10.0,
        local_hour=10,
        station="norte",
    )
    assert alerts == []


def test_cardinal_from_line_id():
    from rastro.rules import cardinal_from_line_id

    assert cardinal_from_line_id("acceso_N") == "N"
    assert cardinal_from_line_id("S") == "S"
    assert cardinal_from_line_id("approach_E") == "E"
    assert cardinal_from_line_id("foo") is None


def test_turning_movement_N_to_S():
    """Pista que entra por N y sale por S → movement N->S, kind turn."""
    from rastro.rules import access_lines_from_geometry, turning_movements

    # Centro se mueve de arriba (N) hacia abajo (S), cruzando ambas líneas.
    dets = []
    for i, y in enumerate([0.05, 0.15, 0.4, 0.6, 0.85, 0.95]):
        py = y * 1000
        dets.append(
            Detection(
                frame=i,
                object_id=0,
                box=Box(x1=480, y1=py, x2=520, y2=py + 40, w=1000, h=1000),
                class_name="auto",
            )
        )
    track = Track(track_id="auto-1", class_name="auto", detections=dets)
    geom = {
        "approaches": [
            {"id": "N", "line": [[0.40, 0.10], [0.60, 0.10]]},
            {"id": "S", "line": [[0.40, 0.90], [0.60, 0.90]]},
            {"id": "E", "line": [[0.90, 0.40], [0.90, 0.60]]},
            {"id": "O", "line": [[0.10, 0.40], [0.10, 0.60]]},
        ]
    }
    access = access_lines_from_geometry(geom)
    assert {a["cardinal"] for a in access} == {"N", "S", "E", "O"}
    turns = turning_movements([track], access, fps=10.0)
    assert len(turns) == 1
    d = turns[0].to_dict()
    assert d["kind"] == "turn"
    assert d["movement"] == "N->S"
    assert d["label"] == "recto"
    assert d["track_id"] == "auto-1"


def test_matriz_giros_from_events():
    from rastro.rules import matriz_giros_from_events

    events = [
        {"kind": "turn", "movement": "N->S"},
        {"kind": "turn", "movement": "N->S"},
        {"kind": "turn", "movement": "N->E"},
        {"kind": "line_cross", "movement": "O->E"},  # ignorado: no es turn
        {"kind": "individual"},
    ]
    m = matriz_giros_from_events(events)
    assert m == {"N->S": 2, "N->E": 1}
