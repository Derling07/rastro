#!/usr/bin/env python3
"""Offline scorer: ground_truth.json vs outputs/<run_id>/result.json.

Never calls Meta/Baseten. Never prints API keys.

Reads OUTPUT_SCHEMA v1.1 result.json (flat unique_count / naive_count + nested
counts). Keeps legacy summary.json + schema 1.0 / mock flag support.

Mock runs (is_mock/mock true, or demo-mock-* folders) are never scored as real:
they are flagged SKIPPED_MOCK unless --allow-mock or fixture_map is used.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GT = Path(__file__).resolve().parent / "ground_truth.json"
DEFAULT_TOLERANCE = 0


@dataclass
class ClipScore:
    clip_id: str
    status: str  # PASS | FAIL | SKIPPED | SKIPPED_MOCK | ERROR
    gt_unique: int | None
    pred_unique: int | None
    pred_naive: int | None
    abs_error: float | None
    naive_error_vs_gt: float | None
    rastro_better_than_naive: bool | None
    source: str | None
    notes: str = ""
    is_mock: bool | None = None
    schema_version: str | None = None
    run_id: str | None = None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def payload_is_mock(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    if payload.get("is_mock") is True:
        return True
    if payload.get("mock") is True:
        return True
    return False


def folder_looks_mock(folder: Path) -> bool:
    name = folder.name.lower()
    return name.startswith("demo-mock") or "-mock-" in name or name.endswith("-mock")


def extract_counts(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    """Return (unique, naive) from result.json schema 1.1 / 1.0 or legacy summary.

    v1.1 prefers flat unique_count / naive_count (CORE aliases) when present,
    else nested counts.{unique,naive}. Legacy summary uses unique_count only.
    """
    # v1.1 flat aliases (preferred when both exist — keep in sync with nested)
    flat_u = payload.get("unique_count")
    flat_n = payload.get("naive_count")
    nested = payload.get("counts") if isinstance(payload.get("counts"), dict) else None

    unique: int | None = None
    naive: int | None = None

    if flat_u is not None:
        unique = int(flat_u)
    elif nested is not None and nested.get("unique") is not None:
        unique = int(nested["unique"])

    if flat_n is not None:
        naive = int(flat_n)
    elif nested is not None and nested.get("naive") is not None:
        naive = int(nested["naive"])

    return unique, naive


def _parse_created(payload: dict[str, Any]) -> float:
    raw = payload.get("created_at")
    if not raw or not isinstance(raw, str):
        return 0.0
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _video_stem(payload: dict[str, Any]) -> str | None:
    sid = payload.get("source_video_id")
    if isinstance(sid, str) and sid:
        return Path(sid).stem
    video = payload.get("video")
    if isinstance(video, dict) and video.get("path"):
        return Path(str(video["path"])).stem
    if isinstance(video, str) and video:
        return Path(video).stem
    return None


def _payload_matches_clip(payload: dict[str, Any], clip_id: str, folder: Path) -> bool:
    if clip_id in folder.name:
        return True
    stem = _video_stem(payload)
    if stem and (stem == clip_id or clip_id in stem):
        return True
    run_id = payload.get("run_id")
    if isinstance(run_id, str) and clip_id in run_id:
        return True
    return False


def _candidate_score(folder: Path, payload: dict[str, Any], allow_mock: bool) -> tuple:
    """Higher tuple = better candidate. Mocks sort last unless allow_mock."""
    is_mock = payload_is_mock(payload) or folder_looks_mock(folder)
    if is_mock and not allow_mock:
        # Still discoverable for SKIPPED_MOCK reporting, but lose to real.
        mock_rank = 0
    else:
        mock_rank = 1 if not is_mock else 0
    has_result = 1 if (folder / "result.json").is_file() else 0
    # Prefer demo-real / real / fauna-* over miscellaneous
    name = folder.name.lower()
    name_rank = 0
    if name.startswith("demo-real") or name == "demo-real-coyote":
        name_rank = 3
    elif name.startswith("real") or "/real" in str(folder):
        name_rank = 2
    elif name.startswith("fauna"):
        name_rank = 2
    elif "coyote" in name and not is_mock:
        name_rank = 1
    created = _parse_created(payload)
    pack = payload.get("pack") if isinstance(payload.get("pack"), dict) else {}
    ver = str(pack.get("version") or "0")
    return (mock_rank, has_result, name_rank, created, ver)


def iter_run_folders(outputs_dir: Path) -> list[Path]:
    if not outputs_dir.exists():
        return []
    if outputs_dir.is_file():
        return []
    folders: list[Path] = []
    # Direct children that look like runs
    for p in sorted(outputs_dir.iterdir()):
        if not p.is_dir():
            continue
        if (p / "result.json").is_file() or (p / "summary.json").is_file():
            folders.append(p)
        else:
            # one level of nesting (outputs/real/<clip>)
            for child in sorted(p.iterdir()):
                if child.is_dir() and (
                    (child / "result.json").is_file() or (child / "summary.json").is_file()
                ):
                    folders.append(child)
    return folders


def find_run_payload(
    outputs_dir: Path,
    clip_id: str,
    *,
    allow_mock: bool = False,
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any]]:
    """Locate best result.json / summary.json for a clip.

    Returns (payload, source_path, meta) where meta may include
    matched_mock_only=True when only mock runs matched.
    """
    meta: dict[str, Any] = {"matched_mock_only": False, "candidates": []}

    if outputs_dir.is_file() and outputs_dir.name.endswith(".json"):
        payload = load_json(outputs_dir)
        return payload, str(outputs_dir), meta

    if not outputs_dir.exists():
        return None, None, meta

    # Single-run directory (has result.json at this path)
    if (outputs_dir / "result.json").is_file() or (outputs_dir / "summary.json").is_file():
        folders = [outputs_dir]
    else:
        folders = iter_run_folders(outputs_dir)

    real_hits: list[tuple[tuple, Path, dict[str, Any], str]] = []
    mock_hits: list[tuple[tuple, Path, dict[str, Any], str]] = []

    for folder in folders:
        result = folder / "result.json"
        summary = folder / "summary.json"
        path: Path | None = None
        if result.is_file():
            path = result
        elif summary.is_file():
            path = summary
        if path is None:
            continue
        payload = load_json(path)
        if not _payload_matches_clip(payload, clip_id, folder):
            continue
        is_mock = payload_is_mock(payload) or folder_looks_mock(folder)
        rank = _candidate_score(folder, payload, allow_mock=allow_mock)
        entry = (rank, folder, payload, str(path))
        meta["candidates"].append(
            {"path": str(path), "is_mock": is_mock, "run_id": payload.get("run_id")}
        )
        if is_mock and not allow_mock:
            mock_hits.append(entry)
        else:
            real_hits.append(entry)

    if real_hits:
        real_hits.sort(key=lambda x: x[0], reverse=True)
        _, _, payload, src = real_hits[0]
        return payload, src, meta

    if mock_hits:
        meta["matched_mock_only"] = True
        mock_hits.sort(key=lambda x: x[0], reverse=True)
        _, _, payload, src = mock_hits[0]
        # Return payload so caller can flag SKIPPED_MOCK with counts visible
        return payload, src, meta

    return None, None, meta


def score_clip(
    clip: dict[str, Any],
    payload: dict[str, Any] | None,
    source: str | None,
    *,
    tolerance: int,
    mock_only: bool = False,
    allow_mock: bool = False,
) -> ClipScore:
    clip_id = clip["id"]
    status_gt = clip.get("status", "VERIFIED")
    gt = clip.get("true_unique_count")

    schema_v = None
    run_id = None
    is_mock = None
    if payload is not None:
        schema_v = str(payload.get("schema_version")) if payload.get("schema_version") else None
        run_id = str(payload.get("run_id")) if payload.get("run_id") else None
        is_mock = payload_is_mock(payload)

    if status_gt == "NOT VERIFIED" or gt is None:
        return ClipScore(
            clip_id=clip_id,
            status="SKIPPED",
            gt_unique=None if gt is None else int(gt),
            pred_unique=None,
            pred_naive=None,
            abs_error=None,
            naive_error_vs_gt=None,
            rastro_better_than_naive=None,
            source=source,
            notes="GT not verified — excluded from MAE / exact-match",
            is_mock=is_mock,
            schema_version=schema_v,
            run_id=run_id,
        )

    if mock_only and not allow_mock:
        unique, naive = extract_counts(payload) if payload else (None, None)
        return ClipScore(
            clip_id=clip_id,
            status="SKIPPED_MOCK",
            gt_unique=int(gt),
            pred_unique=unique,
            pred_naive=naive,
            abs_error=None,
            naive_error_vs_gt=None,
            rastro_better_than_naive=None,
            source=source,
            notes="Only mock run matched — not scored as real (pass --allow-mock to force)",
            is_mock=True,
            schema_version=schema_v,
            run_id=run_id,
        )

    if payload is None:
        return ClipScore(
            clip_id=clip_id,
            status="ERROR",
            gt_unique=int(gt),
            pred_unique=None,
            pred_naive=None,
            abs_error=None,
            naive_error_vs_gt=None,
            rastro_better_than_naive=None,
            source=None,
            notes="No result.json / summary.json found for clip",
        )

    if is_mock and not allow_mock:
        unique, naive = extract_counts(payload)
        return ClipScore(
            clip_id=clip_id,
            status="SKIPPED_MOCK",
            gt_unique=int(gt),
            pred_unique=unique,
            pred_naive=naive,
            abs_error=None,
            naive_error_vs_gt=None,
            rastro_better_than_naive=None,
            source=source,
            notes="Payload is_mock/mock=true — not scored as real",
            is_mock=True,
            schema_version=schema_v,
            run_id=run_id,
        )

    unique, naive = extract_counts(payload)
    if unique is None:
        return ClipScore(
            clip_id=clip_id,
            status="ERROR",
            gt_unique=int(gt),
            pred_unique=None,
            pred_naive=naive,
            abs_error=None,
            naive_error_vs_gt=None,
            rastro_better_than_naive=None,
            source=source,
            notes="Payload missing counts.unique / unique_count",
            is_mock=is_mock,
            schema_version=schema_v,
            run_id=run_id,
        )

    abs_err = abs(unique - int(gt))
    naive_err = abs(naive - int(gt)) if naive is not None else None
    better = None
    if naive_err is not None:
        better = abs_err < naive_err or (abs_err == 0 and naive_err > 0)

    passed = abs_err <= tolerance
    return ClipScore(
        clip_id=clip_id,
        status="PASS" if passed else "FAIL",
        gt_unique=int(gt),
        pred_unique=unique,
        pred_naive=naive,
        abs_error=float(abs_err),
        naive_error_vs_gt=float(naive_err) if naive_err is not None else None,
        rastro_better_than_naive=better,
        source=source,
        notes=f"tolerance={tolerance}; schema={schema_v or 'legacy'}",
        is_mock=bool(is_mock) if is_mock is not None else False,
        schema_version=schema_v,
        run_id=run_id,
    )


def aggregate(scores: list[ClipScore]) -> dict[str, Any]:
    scored = [s for s in scores if s.status in ("PASS", "FAIL")]
    n = len(scored)
    mae = sum(s.abs_error or 0.0 for s in scored) / n if n else None
    exact = sum(1 for s in scored if (s.abs_error or 0) == 0) / n if n else None
    pass_rate = sum(1 for s in scored if s.status == "PASS") / n if n else None
    naive_mae = None
    with_naive = [s for s in scored if s.naive_error_vs_gt is not None]
    if with_naive:
        naive_mae = sum(s.naive_error_vs_gt or 0.0 for s in with_naive) / len(with_naive)
    better_count = sum(1 for s in scored if s.rastro_better_than_naive is True)
    return {
        "n_scored": n,
        "n_skipped": sum(1 for s in scores if s.status == "SKIPPED"),
        "n_skipped_mock": sum(1 for s in scores if s.status == "SKIPPED_MOCK"),
        "n_error": sum(1 for s in scores if s.status == "ERROR"),
        "n_pass": sum(1 for s in scores if s.status == "PASS"),
        "n_fail": sum(1 for s in scores if s.status == "FAIL"),
        "mae": mae,
        "naive_mae": naive_mae,
        "exact_match_rate": exact,
        "pass_rate": pass_rate,
        "rastro_strictly_better_than_naive": better_count,
    }


def score_run(
    gt_path: Path,
    outputs_dir: Path,
    *,
    tolerance: int = DEFAULT_TOLERANCE,
    fixture_map: dict[str, Path] | None = None,
    allow_mock: bool = False,
) -> dict[str, Any]:
    gt = load_json(gt_path)
    scores: list[ClipScore] = []
    for clip in gt.get("clips", []):
        clip_id = clip["id"]
        payload = None
        source = None
        mock_only = False
        if fixture_map and clip_id in fixture_map:
            path = fixture_map[clip_id]
            payload = load_json(path)
            source = str(path)
            # Fixtures are intentional mocks for unit tests — treat as allow_mock
            scores.append(
                score_clip(
                    clip,
                    payload,
                    source,
                    tolerance=tolerance,
                    mock_only=False,
                    allow_mock=True,
                )
            )
            continue
        else:
            payload, source, meta = find_run_payload(
                outputs_dir, clip_id, allow_mock=allow_mock
            )
            mock_only = bool(meta.get("matched_mock_only"))
        scores.append(
            score_clip(
                clip,
                payload,
                source,
                tolerance=tolerance,
                mock_only=mock_only,
                allow_mock=allow_mock,
            )
        )

    return {
        "ground_truth": str(gt_path),
        "outputs_dir": str(outputs_dir),
        "tolerance": tolerance,
        "allow_mock": allow_mock,
        "clips": [asdict(s) for s in scores],
        "aggregate": aggregate(scores),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score Rastro unique counts vs hand GT (offline).")
    parser.add_argument("--gt", type=Path, default=DEFAULT_GT, help="Path to ground_truth.json")
    parser.add_argument(
        "--outputs",
        type=Path,
        default=ROOT / "outputs" / "real",
        help="Directory with run folders (each with result.json or summary.json)",
    )
    parser.add_argument("--tolerance", type=int, default=DEFAULT_TOLERANCE)
    parser.add_argument(
        "--allow-mock",
        action="store_true",
        help="Allow scoring is_mock/demo-mock runs as if real (default: skip/flag)",
    )
    parser.add_argument("--json-out", type=Path, default=None, help="Optional path to write full report")
    args = parser.parse_args(argv)

    # Refuse to run if someone tries to pass secrets via env into this script's prints
    for key in ("META_API_KEY", "BASETEN_API_KEY", "MODEL_API_KEY"):
        # We never read or print these; existence is fine.
        _ = key

    report = score_run(
        args.gt, args.outputs, tolerance=args.tolerance, allow_mock=args.allow_mock
    )
    agg = report["aggregate"]
    print("Rastro eval score (offline)")
    print(f"  GT:       {report['ground_truth']}")
    print(f"  outputs:  {report['outputs_dir']}")
    print(f"  tolerance:{report['tolerance']}")
    print(f"  allow_mock:{report['allow_mock']}")
    print()
    for c in report["clips"]:
        line = (
            f"  {c['clip_id']:28} {c['status']:12} "
            f"gt={c['gt_unique']} pred={c['pred_unique']} naive={c['pred_naive']} "
            f"abs_err={c['abs_error']} mock={c.get('is_mock')}"
        )
        print(line)
        if c.get("notes"):
            print(f"             note: {c['notes']}")
        if c.get("source"):
            print(f"             source: {c['source']}")
    print()
    print("Aggregate (VERIFIED non-mock clips only):")
    for k, v in agg.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {args.json_out}")

    # Exit 1 if any FAIL or ERROR on scored set
    if agg["n_fail"] or agg["n_error"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
