"""Carga y valida paquetes JSON por sector.

Un paquete describe QUÉ seguir (targets), CÓMO deduplicar, qué alertas
lanzar y cómo redactar el reporte. El motor no cambia de código al
cambiar de paquete: solo lee otro JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# dedup es opcional: el modo image_sample (multitudes) no sigue individuos.
REQUIRED_KEYS = (
    "id",
    "version",
    "targets",
    "sampling",
    "metrics",
    "alerts",
    "privacy",
)


@dataclass
class Pack:
    """Paquete de sector ya cargado en memoria."""

    path: Path
    data: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.data["id"])

    @property
    def targets(self) -> list[dict[str, str]]:
        return list(self.data["targets"])

    @property
    def sampling(self) -> dict[str, Any]:
        return dict(self.data["sampling"])

    @property
    def dedup(self) -> dict[str, Any]:
        return dict(self.data.get("dedup") or {})

    @property
    def alerts(self) -> list[dict[str, Any]]:
        return list(self.data.get("alerts", []))

    @property
    def privacy(self) -> dict[str, Any]:
        return dict(self.data.get("privacy", {}))

    @property
    def geometry(self) -> dict[str, Any]:
        return dict(self.data.get("geometry", {}))

    @property
    def density(self) -> dict[str, Any]:
        return dict(self.data.get("density") or {})

    @property
    def report(self) -> dict[str, Any]:
        return dict(self.data.get("report", {}))

    @property
    def station_defaults(self) -> dict[str, Any]:
        return dict(self.data.get("station_defaults", {}))

    @property
    def tracking_enabled(self) -> bool:
        """False en image_sample / privacy.tracking=false."""
        mode = str(self.sampling.get("mode") or "video_track")
        if mode == "image_sample":
            return False
        if self.privacy.get("tracking") is False:
            return False
        return True


def _default_packs_dir() -> Path:
    # worker/rastro/pack.py -> repo root = parents[2]
    return Path(__file__).resolve().parents[2] / "packs"


def load_pack(name_or_path: str | Path, packs_dir: Path | None = None) -> Pack:
    """Carga un paquete por nombre corto ('fauna') o por ruta a un .json.

    Ejemplo:
        load_pack("fauna")
        load_pack("/ruta/a/packs/fauna.json")
    """
    raw = Path(name_or_path)
    if raw.suffix == ".json" and raw.exists():
        path = raw
    else:
        base = packs_dir or _default_packs_dir()
        # acepta "fauna" o "fauna.json"
        stem = raw.name.removesuffix(".json")
        path = base / f"{stem}.json"
        if not path.exists():
            # aceptar también el id interno del paquete (p. ej. "fauna-camtrap")
            import json as _json
            for cand in sorted(base.glob("*.json")):
                try:
                    if _json.loads(cand.read_text(encoding="utf-8")).get("id") == stem:
                        path = cand
                        break
                except Exception:
                    continue
        if not path.exists():
            raise FileNotFoundError(
                f"No encontré el paquete '{name_or_path}'. "
                f"Busqué en {path}."
            )

    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        raise ValueError(
            f"El paquete {path} le faltan campos: {', '.join(missing)}"
        )
    if not isinstance(data["targets"], list) or not data["targets"]:
        raise ValueError(f"El paquete {path} necesita al menos un target.")

    mode = str((data.get("sampling") or {}).get("mode") or "video_track")
    if mode not in ("video_track", "image_sample"):
        raise ValueError(
            f"El paquete {path} tiene sampling.mode inválido: {mode!r}. "
            "Usá 'video_track' o 'image_sample'."
        )

    return Pack(path=path, data=data)
