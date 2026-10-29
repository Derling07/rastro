"""Genera supabase/seed_packs.sql desde packs/*.json (sin red, sin claves).

Uso: python supabase/seed_packs.py  -> luego ORION lo pega/aplica en Supabase.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SECTORS = {"fauna": "fauna", "transito": "transito", "multitud": "multitudes"}


def q(s):
    return "null" if s is None else "'" + str(s).replace("'", "''") + "'"


def build() -> str:
    rows = []
    for f in sorted((REPO / "packs").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        sector = next((v for k, v in SECTORS.items() if k in f.stem or k in d["id"]), None)
        rows.append(f"({q(d['id'])}, {q(d.get('version'))}, {q(sector)}, {q(d.get('description'))}, "
                    f"{q(json.dumps(d, ensure_ascii=False))}::jsonb)")
    return ("insert into public.packs (id, version, sector, description, config) values\n  "
            + ",\n  ".join(rows)
            + "\non conflict (id) do update set version = excluded.version, sector = excluded.sector,\n"
              "  description = excluded.description, config = excluded.config, updated_at = now();\n")


if __name__ == "__main__":
    out = REPO / "supabase" / "seed_packs.sql"
    out.write_text(build(), encoding="utf-8")
    print(f"escrito {out}")
