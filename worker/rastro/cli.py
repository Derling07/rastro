"""CLI de Rastro.

Uso:
  rastro run --pack fauna --video data/lila/coyote/DSCF0104.MP4
  rastro run --pack fauna --video clip.mp4 --mock-sam --no-spark
  rastro probe-baseten
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rastro",
        description="Rastro — sigue cosas en video sin contarlas dos veces.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Correr el motor sobre un video")
    run_p.add_argument("--pack", required=True, help="Nombre o ruta del paquete JSON")
    run_p.add_argument("--video", required=True, help="Ruta al video MP4/MOV")
    run_p.add_argument("--out", default=None, help="Carpeta de salida")
    run_p.add_argument(
        "--mock-sam",
        action="store_true",
        help="Forzar SAM simulado (útil sin META_API_KEY)",
    )
    run_p.add_argument(
        "--no-spark",
        action="store_true",
        help="No llamar a Baseten; reporte local",
    )
    run_p.add_argument("--voice", default=None, help="WAV de nota de campo (opcional)")
    run_p.add_argument(
        "--voice-public",
        action="store_true",
        help="Marca voice.is_public=true en result.json (default false)",
    )
    run_p.add_argument(
        "--hour",
        type=int,
        default=None,
        help="Hora local 0-23 para alertas (ej. persona de noche)",
    )
    run_p.add_argument("--station", default=None, help="Nombre de la estación")
    run_p.add_argument(
        "--concepts",
        default=None,
        help="Lista separada por comas de prompts/clases a correr (ahorra plata)",
    )
    run_p.add_argument("--no-annotate", action="store_true", help="No generar annotated.mp4")
    run_p.add_argument("--no-blur", action="store_true", help="No generar blurred.mp4")

    sub.add_parser("probe-baseten", help="Probar texto/imagen/audio/JSON en Baseten")

    args = parser.parse_args(argv)

    if args.cmd == "probe-baseten":
        from . import probe_baseten as pb

        return pb.main()

    if args.cmd == "run":
        from .pipeline import run_pipeline

        bundle = run_pipeline(
            pack=args.pack,
            video=args.video,
            out_dir=args.out,
            mock_sam=True if args.mock_sam else None,
            use_spark=not args.no_spark,
            voice_wav=args.voice,
            voice_public=bool(args.voice_public),
            local_hour=args.hour,
            station=args.station,
            concepts=[x.strip() for x in args.concepts.split(",")] if args.concepts else None,
            annotate=False if args.no_annotate else None,
            blur=False if args.no_blur else None,
        )
        summary = bundle["summary"]
        report = bundle["report"]
        print("=== Rastro ===")
        print(f"paquete:     {bundle['pack']}")
        print(f"video:       {bundle['video']}")
        print(f"SAM mock:    {summary['mock']}")
        print(f"ingenuo:     {summary['naive_count']}")
        print(f"únicos:      {summary['unique_count']}")
        print(f"por clase:   {summary['by_class']}")
        print(f"alertas:     {len(summary['alerts'])}")
        for a in summary["alerts"]:
            print(f"  - [{a.get('severity')}] {a.get('message')}")
        print(f"reporte:     {report.get('titulo')} ({report.get('_source')})")
        print(f"gancho:      {report.get('gancho_demo')}")
        print(f"costo SAM:   ${summary.get('est_usd_sam', 0):.4f}")
        print(f"run_id:      {bundle.get('run_id')}")
        arts = (bundle.get("result") or {}).get("artifacts") or {}
        if arts.get("annotated_video"):
            print(f"anotado:     {arts['annotated_video']}")
        if arts.get("blurred_video"):
            print(f"difuminado:  {arts['blurred_video']}")
        if bundle.get("result"):
            print(f"result.json: schema {(bundle['result'] or {}).get('schema_version')}")
        out = Path(args.out) if args.out else None
        if out is None:
            # El pipeline elige la carpeta; la leemos del run si hace falta.
            pass
        print(json.dumps({"unique": summary["unique_count"], "naive": summary["naive_count"]}, ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
