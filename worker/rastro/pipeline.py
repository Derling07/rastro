"""Orquesta una corrida completa: paquete → SAM → dedup → reglas → agente."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent import build_report
from .annotate import annotate_video
from .density import (
    build_density_series,
    evaluate_sustained_density_alerts,
    peak_density,
    persons_per_zone_peak,
)
from .pack import Pack, load_pack
from .privacy import boxes_by_frame, blur_video, should_blur
from .result_schema import (
    build_result,
    frames_from_tracks,
    make_run_id,
    source_video_id_from_path,
    write_result,
)
from .rules import (
    access_lines_from_geometry,
    evaluate_alerts,
    line_crossings,
    matriz_giros_from_events,
    turning_movements,
)
from .sam_client import (
    SamClient,
    estimate_video_cost,
    extract_frames_at_fps,
    probe_duration_s,
    _mock_image_detections,
)
from .sam_fallback import segment_image_with_fallback, segment_with_fallback
from .tracking import CountResult, count_unique
from .transit import (
    DEFAULT_BUDGET_USD,
    access_rois_from_geometry,
    crop_rect_px,
    crop_video_access,
    filter_detections_in_roi,
    frames_hitting_object_cap,
    probe_video_size,
    remap_detections_to_full,
    wants_access_crops,
)
from .types import Detection, Event, RunSummary, Track


def _probe_fps(video: Path, default: float = 10.0) -> float:
    """Intenta leer fps con ffprobe; si falla, usa el del paquete."""
    import subprocess

    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=r_frame_rate",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video),
            ],
            text=True,
        ).strip()
        if "/" in out:
            a, b = out.split("/", 1)
            return float(a) / float(b) if float(b) else default
        return float(out) or default
    except Exception:
        return default


def _run_image_sample(
    sam: SamClient,
    *,
    video: Path,
    targets: list[dict[str, Any]],
    sample_fps: float,
    out_dir: Path,
    mock: bool,
) -> tuple[list[Detection], list[dict[str, Any]]]:
    """SAM en modo imagen a sample_fps: una petición por frame, sin tracking."""
    all_dets: list[Detection] = []
    sam_meta: list[dict[str, Any]] = []
    frames_dir = out_dir / ".image_samples"
    samples: list[tuple[int, Path, float]]

    if mock:
        # Sin ffmpeg: sintetizar N muestras según duración.
        duration = probe_duration_s(video, default=10.0)
        n = max(1, int(duration * sample_fps) + 1)
        # Cap razonable para tests
        n = min(n, 120)
        samples = [(i, Path(f"(mock-frame-{i})"), round(i / sample_fps, 4)) for i in range(n)]
    else:
        samples = extract_frames_at_fps(video, frames_dir, fps=sample_fps)

    for target in targets:
        class_name = str(target["class"])
        for sample_idx, img_path, _t_s in samples:
            if mock:
                # Variar un poco la cantidad para que la media móvil tenga señal
                base = 90
                # Oscila 70–110 personas
                n_persons = base + int(15 * ((sample_idx % 7) - 3))
                dets = _mock_image_detections(
                    concept=str(target["prompt"]),
                    class_name=class_name,
                    frame=sample_idx,
                    seed=f"{video.name}:{target['prompt']}:{sample_idx}",
                    n_persons=max(1, n_persons),
                )
                result_dets = dets
                entry = {
                    "concept": str(target["prompt"]),
                    "class": class_name,
                    "n_detections": len(dets),
                    "mock": True,
                    "elapsed_s": 0.0,
                    "usage": {"images_processed": 0, "mock": True},
                    "est_usd": 0.0,
                    "chosen": True,
                    "mode": "image_sample",
                    "frame": sample_idx,
                }
                all_dets.extend(dets)
                sam_meta.append(entry)
            else:
                result, log = segment_image_with_fallback(
                    sam,
                    image_path=img_path,
                    target=target,
                    frame_index=sample_idx,
                )
                all_dets.extend(result.detections)
                sam_meta.extend(log)

    if frames_dir.exists() and not mock:
        # Limpiar frames temporales (no son artefacto público)
        try:
            shutil.rmtree(frames_dir)
        except OSError:
            pass
    return all_dets, sam_meta


def _count_image_sample(
    detections: list[Detection],
    *,
    fps: float,
) -> CountResult:
    """Sin tracking: cada detección es independiente; unique = pico por frame."""
    by_frame: dict[int, list[Detection]] = {}
    for d in detections:
        by_frame.setdefault(d.frame, []).append(d)
    peak = max((len(v) for v in by_frame.values()), default=0)
    # Pistas efímeras por frame (para annotate / frames[])
    tracks: list[Track] = []
    for frame, dets in sorted(by_frame.items()):
        for i, d in enumerate(dets):
            tracks.append(
                Track(
                    track_id=f"{d.class_name}-f{frame}-{i}",
                    class_name=d.class_name,
                    detections=[d],
                )
            )
    by_class: dict[str, int] = {}
    for t in tracks:
        # peak per class across frames
        pass
    # by_class = peak concurrent per class
    class_peak: dict[str, int] = {}
    for dets in by_frame.values():
        local: dict[str, int] = {}
        for d in dets:
            local[d.class_name] = local.get(d.class_name, 0) + 1
        for cls, n in local.items():
            class_peak[cls] = max(class_peak.get(cls, 0), n)
    return CountResult(
        tracks=tracks,
        unique_count=peak,
        naive_count=len(detections),
        by_class=class_peak,
    )



def _run_access_crops(
    sam: SamClient,
    *,
    video: Path,
    targets: list[dict[str, Any]],
    rois: list[dict[str, Any]],
    out_dir: Path,
    track_fps: float,
    budget_usd: float,
) -> tuple[list[Detection], list[dict[str, Any]], bool, list[dict[str, Any]]]:
    """Una petición SAM por acceso (recorte) para no saturar el tope de 16.

    Orden: target → accesos, para que con budget_usd se cubran primero las
    clases prioritarias en N/S/E/O (mejor matriz de giros bajo tope de costo).

    En mock no corta con ffmpeg: filtra detecciones sintéticas cuyo centro
    cae en el ROI (coords ya en frame completo). En vivo, ffmpeg crop+fps + remap.
    Respeta budget_usd: omite peticiones restantes y marca partial.
    """
    all_dets: list[Detection] = []
    sam_meta: list[dict[str, Any]] = []
    max_objects_hit: list[dict[str, Any]] = []
    partial = False
    spent = 0.0
    min_req = float(estimate_video_cost(None))
    full_w, full_h = probe_video_size(video)
    crops_dir = out_dir / "access_crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    # Pre-crop once per access (live only).
    crop_by_card: dict[str, tuple[Path, dict[str, int]]] = {}
    for i, roi in enumerate(rois):
        card = str(roi.get("cardinal") or roi.get("id") or i)
        crop_px = crop_rect_px(roi, full_w, full_h)
        crop_path = crops_dir / f"{card}_fps{track_fps:g}.mp4"
        if not bool(sam.mock):
            if not crop_path.exists() or crop_path.stat().st_size < 32:
                try:
                    crop_px = crop_video_access(
                        video,
                        roi,
                        crop_path,
                        full_w=full_w,
                        full_h=full_h,
                        fps=track_fps,
                    )
                except Exception as exc:  # noqa: BLE001
                    sam_meta.append(
                        {
                            "concept": None,
                            "class": None,
                            "n_detections": 0,
                            "mock": bool(sam.mock),
                            "access": card,
                            "chosen": False,
                            "mode": "video_track_access_crop",
                            "est_usd": 0.0,
                            "error": f"crop_failed: {exc}",
                        }
                    )
                    partial = True
                    continue
            crop_by_card[card] = (crop_path, crop_px)
        else:
            crop_by_card[card] = (video, crop_px)

    for target in targets:
        prompt = str(target.get("prompt") or target.get("class"))
        for i, roi in enumerate(rois):
            card = str(roi.get("cardinal") or roi.get("id") or i)
            if card not in crop_by_card:
                continue
            sam_video, crop_px = crop_by_card[card]
            use_crop_file = not bool(sam.mock)

            if spent + min_req > budget_usd + 1e-12:
                partial = True
                sam_meta.append(
                    {
                        "concept": prompt,
                        "class": str(target.get("class")),
                        "n_detections": 0,
                        "mock": bool(sam.mock),
                        "access": card,
                        "chosen": False,
                        "mode": "video_track_access_crop",
                        "est_usd": 0.0,
                        "skipped_budget": True,
                        "budget_usd": budget_usd,
                        "spent_usd": round(spent, 6),
                    }
                )
                continue

            result, log = segment_with_fallback(
                sam,
                video_path=str(sam_video),
                target=target,
                chunk_index=i + 1,
            )
            if use_crop_file:
                dets = remap_detections_to_full(result.detections, crop_px)
            else:
                dets = filter_detections_in_roi(result.detections, roi)
                for d in dets:
                    d.chunk_index = i + 1
            all_dets.extend(dets)

            chosen_concept = next(
                (e.get("concept") for e in log if e.get("chosen")), prompt
            )
            hits = frames_hitting_object_cap(
                result.detections,
                fps=track_fps,
                access=card,
                concept=str(chosen_concept) if chosen_concept else prompt,
            )
            if hits:
                partial = True
                max_objects_hit.extend(hits)

            for entry in log:
                e = dict(entry)
                e["access"] = card
                e["mode"] = "video_track_access_crop"
                e["crop"] = {
                    "x": crop_px["x"],
                    "y": crop_px["y"],
                    "w": crop_px["w"],
                    "h": crop_px["h"],
                }
                add = float(e.get("est_usd") or 0.0)
                if bool(sam.mock) and add <= 0.0:
                    add = min_req
                spent += add
                sam_meta.append(e)

    return all_dets, sam_meta, partial, max_objects_hit



def run_pipeline(
    *,
    pack: str | Path | Pack,
    video: Path | str,
    out_dir: Path | str | None = None,
    mock_sam: bool | None = None,
    use_spark: bool = True,
    voice_wav: Path | str | None = None,
    local_hour: int | None = None,
    station: str | None = None,
    concepts: list[str] | None = None,
    annotate: bool | None = None,
    blur: bool | None = None,
    voice_public: bool = False,
) -> dict[str, Any]:
    """Corre el motor y escribe result.json + artefactos en out_dir."""
    video = Path(video)
    if not video.exists():
        raise FileNotFoundError(f"No existe el video: {video}")

    pack_obj = pack if isinstance(pack, Pack) else load_pack(pack)
    sampling = pack_obj.sampling
    mode = str(sampling.get("mode") or "video_track")
    track_fps = float(sampling.get("fps", 10))
    native_fps = _probe_fps(video, default=track_fps)
    out_cfg = pack_obj.data.get("output") or {}
    image_mode = mode == "image_sample"

    if out_dir is None:
        run_id = make_run_id(pack_obj.id, video.stem)
        out_dir = Path("outputs") / run_id
    else:
        out_dir = Path(out_dir)
        run_id = out_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    sam = SamClient(mock=mock_sam)
    all_dets: list[Detection] = []
    sam_meta: list[dict[str, Any]] = []

    targets = pack_obj.targets
    if concepts:
        want = {c.lower() for c in concepts}
        targets = [
            t
            for t in targets
            if t["prompt"].lower() in want
            or t["class"].lower() in want
            or any(str(f).lower() in want for f in (t.get("fallbacks") or []))
        ]
        if not targets:
            raise ValueError(f"Ningún target coincide con concepts={concepts}")

    partial = False
    max_objects_hit: list[dict[str, Any]] = []
    _raw_budget = pack_obj.data.get("budget_usd")
    budget_usd = (
        float(DEFAULT_BUDGET_USD) if _raw_budget is None else float(_raw_budget)
    )
    access_rois: list[dict[str, Any]] = []
    if wants_access_crops(pack_obj.data):
        access_rois = access_rois_from_geometry(pack_obj.geometry)

    if image_mode:
        all_dets, sam_meta = _run_image_sample(
            sam,
            video=video,
            targets=targets,
            sample_fps=track_fps,
            out_dir=out_dir,
            mock=bool(sam.mock),
        )
        counted = _count_image_sample(all_dets, fps=track_fps)
    elif access_rois:
        all_dets, sam_meta, partial, max_objects_hit = _run_access_crops(
            sam,
            video=video,
            targets=targets,
            rois=access_rois,
            out_dir=out_dir,
            track_fps=track_fps,
            budget_usd=budget_usd,
        )
        dedup = pack_obj.dedup
        counted = count_unique(
            all_dets,
            fps=track_fps,
            reentry_window_s=float(dedup.get("reentry_window_s", 20)),
            reentry_edge_px=float(dedup.get("reentry_edge_px", 80)),
            iou_stitch=float(dedup.get("iou_stitch", 0.5)),
            center_dist_factor=float(dedup.get("center_dist_factor", 2.0)),
            edge_dist_factor=float(dedup.get("edge_dist_factor", 4.0)),
        )
    else:
        for target in targets:
            result, log = segment_with_fallback(
                sam, video_path=str(video), target=target
            )
            all_dets.extend(result.detections)
            hits = frames_hitting_object_cap(
                result.detections,
                fps=track_fps,
                concept=str(target.get("prompt") or target.get("class")),
            )
            if hits:
                partial = True
                max_objects_hit.extend(hits)
            for entry in log:
                sam_meta.append(entry)

        dedup = pack_obj.dedup
        counted = count_unique(
            all_dets,
            fps=track_fps,
            reentry_window_s=float(dedup.get("reentry_window_s", 20)),
            reentry_edge_px=float(dedup.get("reentry_edge_px", 80)),
            iou_stitch=float(dedup.get("iou_stitch", 0.5)),
            center_dist_factor=float(dedup.get("center_dist_factor", 2.0)),
            edge_dist_factor=float(dedup.get("edge_dist_factor", 4.0)),
        )

    events: list[Event] = []
    if not image_mode:
        for t in counted.tracks:
            events.append(
                Event(
                    kind="individual",
                    t_s=t.start_frame / track_fps,
                    payload={
                        "track_id": t.track_id,
                        "class": t.class_name,
                        "start_frame": t.start_frame,
                        "end_frame": t.end_frame,
                        "dwell_s": t.dwell_frames / track_fps,
                    },
                )
            )
        lines = pack_obj.geometry.get("lines") or []
        access_lines = access_lines_from_geometry(pack_obj.geometry)
        cross_lines = access_lines if access_lines else lines
        events.extend(line_crossings(counted.tracks, cross_lines, fps=track_fps))
        # Tránsito: events kind=turn + movement "N->S" (entrada->salida) para FRONT.
        if access_lines:
            events.extend(
                turning_movements(
                    counted.tracks,
                    access_lines,
                    fps=track_fps,
                    turning_rules=pack_obj.data.get("turning_rules") or {},
                )
            )

    defaults = pack_obj.station_defaults
    station_name = station or defaults.get("station", "demo")
    if local_hour is None:
        local_hour = datetime.now().hour

    alerts = evaluate_alerts(
        counted.tracks,
        counted.by_class,
        pack_obj.alerts,
        fps=track_fps,
        local_hour=local_hour,
        station=station_name,
    )

    # --- Densidad (multitudes / zonas con area_m2) ---
    density_series: list[dict[str, Any]] = []
    peak_dens: dict[str, Any] | None = None
    persons_peak: dict[str, int] = {}
    dens_cfg = pack_obj.density
    zones = list(pack_obj.geometry.get("zones") or [])
    metrics = set(pack_obj.data.get("metrics") or [])
    want_density = bool(dens_cfg) or bool(
        metrics & {"persons_per_zone", "density_per_m2", "peak_density"}
    )
    if want_density and zones:
        class_names = {str(t["class"]) for t in pack_obj.targets}
        # Si el pack pide blur de persona, densidad sobre esas clases
        blur_cls = set(should_blur(pack_obj.privacy))
        if blur_cls:
            class_names = class_names | blur_cls
        density_series = build_density_series(
            all_dets,
            zones,
            fps=track_fps,
            class_names=class_names,
            point=str(dens_cfg.get("point") or "bbox_bottom_center"),
        )
        peak_dens = peak_density(density_series)
        persons_peak = persons_per_zone_peak(density_series)
        smooth_s = float(dens_cfg.get("smoothing_window_s") or 5)
        sustain_s = float(dens_cfg.get("sustain_s") or 10)
        dens_alerts = evaluate_sustained_density_alerts(
            density_series,
            pack_obj.alerts,
            smoothing_window_s=smooth_s,
            sustain_s=sustain_s,
            sustain_keys={"sustain_s": sustain_s},
        )
        alerts = list(alerts) + dens_alerts

    # --- Voice Transcribe ligado a estación + hora ---
    notes: list[str] = []
    voice_payload: dict[str, Any] | None = None
    est_usd_voice = 0.0
    if voice_wav:
        from .voice_client import VoiceClient

        voice = VoiceClient(mock=mock_sam if mock_sam is not None else None)
        vres = voice.transcribe(
            voice_wav,
            mode="DIARIZATION",
            language_bias=["Spanish", "English"],
            keywords=["estación", "persona", "linterna", "coyote", station_name],
        )
        linked = (
            f"[estación={station_name} hora={local_hour:02d}:00] {vres.transcript}"
        )
        notes.append(linked)
        est_usd_voice = float(vres.est_usd or 0.0)
        voice_payload = {
            **vres.to_dict(),
            "station": station_name,
            "local_hour": local_hour,
            "linked_note": linked,
            "is_public": bool(voice_public),
        }
        (out_dir / "voice.json").write_text(
            json.dumps(voice_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary = RunSummary(
        pack_id=pack_obj.id,
        video=video.name,
        fps=track_fps,
        naive_count=counted.naive_count,
        unique_count=counted.unique_count,
        by_class=counted.by_class,
        events=[e.to_dict() for e in events],
        alerts=alerts,
        tracks=[
            {
                "track_id": t.track_id,
                "class": t.class_name,
                "start_frame": t.start_frame,
                "end_frame": t.end_frame,
                "n_dets": len(t.detections),
            }
            for t in counted.tracks
        ],
        notes=notes,
        mock=any(m.get("mock") for m in sam_meta) if sam_meta else bool(sam.mock),
    )

    report, agent_log = build_report(summary, use_spark=use_spark)
    if voice_payload:
        report.setdefault("notas_campo", notes)
        report["estacion"] = station_name
        report["hora_local"] = local_hour
    if image_mode:
        from .agent import crowd_line

        dens = None if not peak_dens else peak_dens.get("density_per_m2")
        zone = None if not peak_dens else peak_dens.get("zone")
        line = crowd_line(
            float(dens) if isinstance(dens, (int, float)) else None,
            str(zone) if zone else None,
        )
        report["titulo"] = "Crowd density"
        report["resumen"] = (
            f"{line}. This sector measures how many people are in view at once. "
            "It does not re-identify them."
        )
        report["gancho_demo"] = line
        report["especies"] = []
        report["recomendaciones"] = ["Read the peak as density, not as unique people."]
        report["count_labels"] = {
            "naive_count": "detection boxes across frames, not unique people",
            "unique_count": "peak people in one frame, not a unique-individual count",
        }
    elif "transito" not in str(pack_obj.id).lower():
        from .agent import tracking_line

        detections_total = int(sum(int(m.get("n_detections") or 0) for m in sam_meta))
        line = tracking_line(
            detections_total=detections_total,
            naive=counted.naive_count,
            unique=counted.unique_count,
            by_class=counted.by_class,
        )
        report["gancho_demo"] = line
        clases = ", ".join(f"{k}={v}" for k, v in counted.by_class.items()) or "none"
        report["resumen"] = f"{line}. Classes: {clases}."
        report["titulo"] = f"Rastro report — {pack_obj.id}"
    if peak_dens:
        report["pico_densidad"] = peak_dens
    if persons_peak:
        report["personas_por_zona"] = persons_peak
    matriz = matriz_giros_from_events(events)
    if matriz:
        report["matriz_giros"] = matriz

    # Prefijo agent_log con pasos SAM/tracking
    prepend = []
    tool_name = "sam.segment_image" if image_mode else "sam.segment_video"
    for i, m in enumerate(sam_meta, start=1):
        prepend.append(
            {
                "step": i,
                "tool": tool_name,
                "detail": (
                    f"concept={m.get('concept')} n={m.get('n_detections')} "
                    f"chosen={m.get('chosen')} mode={m.get('mode', mode)} "
                    f"est_usd={m.get('est_usd')}"
                ),
            }
        )
    prepend.append(
        {
            "step": len(prepend) + 1,
            "tool": "density.series" if image_mode else "tracking.count_unique",
            "detail": (
                f"unique={counted.unique_count} naive={counted.naive_count}"
                + (f" density_rows={len(density_series)}" if density_series else "")
            ),
        }
    )
    if access_rois:
        prepend.append(
            {
                "step": len(prepend) + 1,
                "tool": "transit.access_crops",
                "detail": (
                    f"accesses={[r.get('cardinal') for r in access_rois]} "
                    f"partial={partial} max_objects_hit={len(max_objects_hit)} "
                    f"budget_usd={budget_usd}"
                ),
            }
        )
    n_turns = sum(1 for e in events if e.kind == "turn")
    if n_turns:
        prepend.append(
            {
                "step": len(prepend) + 1,
                "tool": "rules.turning_movements",
                "detail": f"turns={n_turns} matriz={report.get('matriz_giros') or {}}",
            }
        )
    if voice_payload:
        prepend.append(
            {
                "step": len(prepend) + 1,
                "tool": "voice.transcribe",
                "detail": f"station={station_name} hour={local_hour}",
            }
        )
    base_step = len(prepend)
    for entry in agent_log:
        entry = dict(entry)
        entry["step"] = base_step + int(entry.get("step") or 1)
        prepend.append(entry)
    agent_log = prepend

    # --- Artefactos de video (anotado + blur personas) ---
    do_annotate = out_cfg.get("annotated_video", True) if annotate is None else annotate
    do_blur = out_cfg.get("blurred_video", True) if blur is None else blur
    blur_classes = set(should_blur(pack_obj.privacy))
    blur_radius = int(pack_obj.privacy.get("blur_radius") or 28)
    # blur_target: full_bbox (único soportado; sin face ID)
    _blur_target = str(pack_obj.privacy.get("blur_target") or "full_bbox")
    if _blur_target not in ("full_bbox", "bbox", "full"):
        # Cualquier otro valor se trata como full_bbox (producto: sin face ID)
        _blur_target = "full_bbox"

    annotated_name: str | None = None
    blurred_name: str | None = None
    try:
        # Para image_sample, las detecciones están indexadas a sample_fps.
        # annotate/blur mapean native_frame → sample vía native_fps.
        ann_det_fps = track_fps
        if do_annotate:
            ann_path = out_dir / "annotated.mp4"
            annotate_video(
                video,
                ann_path,
                counted.tracks,
                fps=track_fps if image_mode else track_fps,
                unique_count=counted.unique_count,
                blur_classes=blur_classes,
                blur_radius=blur_radius,
                det_fps=ann_det_fps if image_mode else None,
                native_fps=native_fps if image_mode else None,
            )
            annotated_name = "annotated.mp4"
        if do_blur and blur_classes:
            person_dets = [
                d
                for t in counted.tracks
                for d in t.detections
                if d.class_name in blur_classes
            ]
            if person_dets:
                boxes = boxes_by_frame(person_dets, class_names=blur_classes)
                blur_path = out_dir / "blurred.mp4"
                blur_video(
                    video,
                    blur_path,
                    boxes,
                    fps=track_fps,
                    blur_radius=blur_radius,
                    det_fps=ann_det_fps if image_mode else None,
                    native_fps=native_fps if image_mode else None,
                )
                blurred_name = "blurred.mp4"
    except Exception as exc:  # noqa: BLE001 — no tumbar la corrida por ffmpeg
        report["_video_artifact_error"] = str(exc)

    est_usd_sam = round(sum(float(m.get("est_usd") or 0) for m in sam_meta), 4)
    est_usd_total = round(est_usd_sam + est_usd_voice, 6)
    summary_dict = summary.to_dict()
    summary_dict["est_usd_sam"] = est_usd_sam
    summary_dict["est_usd_voice"] = est_usd_voice
    summary_dict["sam_calls"] = len(sam_meta)
    if peak_dens:
        summary_dict["peak_density"] = peak_dens
    if persons_peak:
        summary_dict["persons_per_zone"] = persons_peak

    created_at = datetime.now(timezone.utc).isoformat()
    bundle = {
        "created_at": created_at,
        "run_id": run_id,
        "pack": pack_obj.id,
        "pack_path": str(pack_obj.path),
        "video": str(video),
        "native_fps": native_fps,
        "track_fps": track_fps,
        "sampling_mode": mode,
        "sam": sam_meta,
        "summary": summary_dict,
        "report": report,
        "est_usd_sam": est_usd_sam,
        "est_usd_voice": est_usd_voice,
        "est_usd_total": est_usd_total,
    }

    (out_dir / "events.json").write_text(
        json.dumps([e.to_dict() for e in events], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "run.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "cost.json").write_text(
        json.dumps(
            {
                "est_usd_sam": est_usd_sam,
                "est_usd_voice": est_usd_voice,
                "est_usd_total": est_usd_total,
                "sam": sam_meta,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "tracks.json").write_text(
        json.dumps([asdict_track(t) for t in counted.tracks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    track_rows = [
        {
            "track_id": t.track_id,
            "class": t.class_name,
            "start_frame": t.start_frame,
            "end_frame": t.end_frame,
            "dwell_s": round(t.dwell_frames / track_fps, 3) if track_fps else 0.0,
            "n_dets": len(t.detections),
        }
        for t in counted.tracks
    ]
    frames = frames_from_tracks(counted.tracks, fps=track_fps)
    result = build_result(
        run_id=run_id,
        source_video_id=source_video_id_from_path(video),
        pack_id=pack_obj.id,
        pack_version=str(pack_obj.data.get("version") or "0"),
        pack_path=str(pack_obj.path),
        video_path=video.name,
        track_fps=track_fps,
        native_fps=native_fps,
        station=station_name,
        local_hour=local_hour,
        naive_count=counted.naive_count,
        unique_count=counted.unique_count,
        by_class=counted.by_class,
        tracks=track_rows,
        frames=frames,
        events=[e.to_dict() for e in events],
        alerts=alerts,
        voice=voice_payload,
        agent_log=agent_log,
        report=report,
        artifacts={
            "annotated_video": annotated_name,
            "blurred_video": blurred_name,
            "voice_json": "voice.json" if voice_payload else None,
            "cost_json": "cost.json",
            "tracks_json": "tracks.json",
        },
        cost={
            "est_usd_sam": est_usd_sam,
            "est_usd_voice": est_usd_voice,
            "est_usd_total": est_usd_total,
        },
        sam=sam_meta,
        is_mock=summary.mock,
        created_at=created_at,
        density=density_series or None,
        peak_density=peak_dens,
        persons_per_zone=persons_peak or None,
        sampling_mode=mode,
        partial=partial if (partial or max_objects_hit or access_rois) else None,
        max_objects_hit=(
            max_objects_hit if (partial or max_objects_hit or access_rois) else None
        ),
    )
    write_result(out_dir, result)
    bundle["result"] = result
    return bundle


def asdict_track(t) -> dict[str, Any]:
    return {
        "track_id": t.track_id,
        "class_name": t.class_name,
        "start_frame": t.start_frame,
        "end_frame": t.end_frame,
        "detections": [
            {
                "frame": d.frame,
                "object_id": d.object_id,
                "class_name": d.class_name,
                "box": {
                    "x1": d.box.x1,
                    "y1": d.box.y1,
                    "x2": d.box.x2,
                    "y2": d.box.y2,
                    "w": d.box.w,
                    "h": d.box.h,
                },
            }
            for d in t.detections
        ],
    }
