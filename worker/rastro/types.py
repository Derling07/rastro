"""Tipos compartidos del motor (pistas, eventos, resúmenes)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Box:
    """Caja en píxeles del video (x1,y1)-(x2,y2), más el tamaño del frame."""

    x1: float
    y1: float
    x2: float
    y2: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)

    def iou(self, other: "Box") -> float:
        """Intersection-over-Union entre dos cajas (0 = nada, 1 = iguales)."""
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        if inter <= 0:
            return 0.0
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0


@dataclass
class Detection:
    """Una detección de SAM en un frame concreto."""

    frame: int
    object_id: int  # ID que SAM da DENTRO de una petición
    box: Box
    class_name: str
    confidence: float | None = None
    chunk_index: int = 0


@dataclass
class Track:
    """Una trayectoria = un individuo a lo largo del video."""

    track_id: str
    class_name: str
    detections: list[Detection] = field(default_factory=list)

    @property
    def start_frame(self) -> int:
        return min(d.frame for d in self.detections)

    @property
    def end_frame(self) -> int:
        return max(d.frame for d in self.detections)

    @property
    def dwell_frames(self) -> int:
        return self.end_frame - self.start_frame + 1

    def last_box(self) -> Box:
        return self.detections[-1].box


@dataclass
class Event:
    """Algo que pasó: un individuo nuevo, un cruce de línea, una alerta."""

    kind: str
    t_s: float
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "t_s": self.t_s, **self.payload}


@dataclass
class RunSummary:
    """Resumen que le pasamos al agente Spark."""

    pack_id: str
    video: str
    fps: float
    naive_count: int
    unique_count: int
    by_class: dict[str, int]
    events: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    tracks: list[dict[str, Any]]
    notes: list[str] = field(default_factory=list)
    mock: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
