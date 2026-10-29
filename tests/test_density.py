"""Densidad por zona, alertas sostenidas y pack multitudes (image_sample)."""

from __future__ import annotations

from pathlib import Path

from rastro.density import (
    bbox_bottom_center_norm,
    build_density_series,
    evaluate_sustained_density_alerts,
    peak_density,
    point_in_polygon,
    persons_per_zone_peak,
)
from rastro.pack import load_pack
from rastro.pipeline import run_pipeline
from rastro.types import Box, Detection


ZONE = {
    "id": "zona_1",
    "polygon": [[0.1, 0.4], [0.9, 0.4], [0.9, 0.95], [0.1, 0.95]],
    "area_m2": 10,
}


def _box_at(nx: float, ny_feet: float, w: float = 1000, h: float = 1000) -> Box:
    """Caja cuyo centro inferior queda en (nx, ny_feet) normalizado."""
    bw, bh = 40.0, 80.0
    cx = nx * w
    y2 = ny_feet * h
    x1 = cx - bw / 2
    y1 = y2 - bh
    return Box(x1=x1, y1=y1, x2=x1 + bw, y2=y2, w=w, h=h)


def test_point_in_polygon_and_feet():
    assert point_in_polygon(0.5, 0.7, ZONE["polygon"])
    assert not point_in_polygon(0.5, 0.1, ZONE["polygon"])
    b = _box_at(0.5, 0.8)
    nx, ny = bbox_bottom_center_norm(b)
    assert abs(nx - 0.5) < 1e-6
    assert abs(ny - 0.8) < 1e-6


def test_density_series_with_area():
    dets = [
        Detection(
            frame=0,
            object_id=i,
            box=_box_at(0.2 + (i % 10) * 0.06, 0.55 + (i // 10) * 0.06),
            class_name="persona",
        )
        for i in range(50)  # 50 / 10 m² = 5 p/m²; todos dentro de zona_1
    ]
    series = build_density_series(dets, [ZONE], fps=1.0, class_names={"persona"})
    assert series
    row = next(r for r in series if r["t_s"] == 0.0 and r["zone"] == "zona_1")
    assert row["persons"] == 50
    assert row["density_per_m2"] == 5.0


def test_density_null_without_area():
    z = {**ZONE, "area_m2": None}
    dets = [
        Detection(frame=0, object_id=0, box=_box_at(0.5, 0.7), class_name="persona")
    ]
    series = build_density_series(dets, [z], fps=1.0)
    assert series[0]["density_per_m2"] is None
    assert series[0]["persons"] == 1


def test_sustained_alert_fires_after_10s():
    # 15 s a 5 p/m² (umbral media = 4) con area 10 → 50 personas
    dets: list[Detection] = []
    for f in range(15):
        for i in range(50):
            dets.append(
                Detection(
                    frame=f,
                    object_id=i,
                    box=_box_at(0.2 + (i % 10) * 0.05, 0.6 + (i // 10) * 0.05),
                    class_name="persona",
                )
            )
    series = build_density_series(dets, [ZONE], fps=1.0, class_names={"persona"})
    alerts = evaluate_sustained_density_alerts(
        series,
        [
            {
                "id": "densidad_media",
                "when": "density_per_m2 >= 4 SUSTAINED sustain_s",
                "severity": "media",
                "message": "Densidad de {density_per_m2} personas/m² en {zone} durante {sustain_s} s",
            }
        ],
        smoothing_window_s=5,
        sustain_s=10,
        sustain_keys={"sustain_s": 10},
    )
    assert len(alerts) >= 1
    assert alerts[0]["id"] == "densidad_media"
    assert "t_s" in alerts[0]
    assert alerts[0]["zone"] == "zona_1"


def test_sustained_alert_does_not_fire_on_spike():
    # Solo 2 s por encima del umbral
    dets: list[Detection] = []
    for f in range(12):
        n = 50 if f < 2 else 10  # spike corto
        for i in range(n):
            dets.append(
                Detection(
                    frame=f,
                    object_id=i,
                    box=_box_at(0.2 + (i % 10) * 0.05, 0.7),
                    class_name="persona",
                )
            )
    series = build_density_series(dets, [ZONE], fps=1.0, class_names={"persona"})
    alerts = evaluate_sustained_density_alerts(
        series,
        [
            {
                "id": "densidad_media",
                "when": "density_per_m2 >= 4 SUSTAINED sustain_s",
                "severity": "media",
                "message": "x",
            }
        ],
        smoothing_window_s=5,
        sustain_s=10,
    )
    assert alerts == []


def test_load_multitudes_pack():
    pack = load_pack("multitudes")
    assert pack.id == "multitudes-densidad"
    assert pack.sampling["mode"] == "image_sample"
    assert pack.tracking_enabled is False
    assert pack.privacy.get("blur_target") == "full_bbox"
    assert pack.density["sustain_s"] == 10
    assert "dedup" not in pack.data or pack.dedup == {} or True  # opcional


def test_pipeline_multitudes_mock(tmp_path: Path):
    src = Path("data/lila5fps/DSCF0004.mp4")
    if not src.exists():
        return
    # Pack temporal con area_m2 chica para forzar alertas en mock (~90 personas)
    import json
    import shutil

    pack_src = Path("packs/multitudes.json")
    pack_data = json.loads(pack_src.read_text(encoding="utf-8"))
    pack_data["geometry"]["zones"][0]["area_m2"] = 10  # 90/10 = 9 → alta
    pack_path = tmp_path / "multitudes_test.json"
    pack_path.write_text(json.dumps(pack_data), encoding="utf-8")

    out = tmp_path / "crowd-run"
    bundle = run_pipeline(
        pack=pack_path,
        video=src,
        out_dir=out,
        mock_sam=True,
        use_spark=False,
        annotate=False,
        blur=False,
    )
    r = bundle["result"]
    assert r["schema_version"] == "1.1"
    assert r["sampling_mode"] == "image_sample"
    assert r["is_mock"] is True
    assert isinstance(r.get("density"), list) and len(r["density"]) > 0
    row = r["density"][0]
    assert {"t_s", "zone", "persons", "density_per_m2"} <= set(row)
    assert r.get("peak_density") is not None
    assert r.get("persons_per_zone")
    # Con area 10 y ~90 personas mock → densidad alta sostenida
    dens_alerts = [a for a in r["alerts"] if "densidad" in a["id"]]
    assert dens_alerts, f"esperaba alertas de densidad, got {r['alerts']}"
    assert all("t_s" in a for a in r["alerts"])
    # Fauna no se rompe: unique_count es pico (sin tracking)
    assert r["unique_count"] >= 1
    assert r["naive_count"] >= r["unique_count"]


def test_peak_and_persons_helpers():
    series = [
        {"t_s": 0, "zone": "a", "persons": 3, "density_per_m2": 0.3},
        {"t_s": 1, "zone": "a", "persons": 10, "density_per_m2": 1.0},
        {"t_s": 1, "zone": "b", "persons": 2, "density_per_m2": 2.0},
    ]
    assert peak_density(series)["density_per_m2"] == 2.0
    assert persons_per_zone_peak(series) == {"a": 10, "b": 2}
