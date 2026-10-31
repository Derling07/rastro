"""Visible names drop file names and prefer the longer pack id."""

from rastro.agent import crowd_line
from rastro.display_names import finish_sentence, public_copy, zone_label


def test_longer_pack_id_is_replaced_before_the_short_one():
    assert public_copy("fauna-camtrap") == "Wildlife camera"
    assert public_copy("transito-giros") == "Intersection"
    assert "camtrap" not in public_copy("Report fauna-camtrap")
    assert public_copy("seen on transito-giros") == "seen on Intersection"


def test_finish_sentence_adds_a_period_only_when_missing():
    assert finish_sentence("Zone 1") == "Zone 1."
    assert finish_sentence("Zone 1.") == "Zone 1."
    assert finish_sentence("Already done!") == "Already done!"
    line = crowd_line(5.4, "zone_1")
    assert line == "Peak density 5.4 people/m² (NOT VERIFIED: area not calibrated). Zone 1."
    assert ".." not in line


def test_density_text_has_no_nested_parentheses():
    line = crowd_line(5.4, "zone_1")
    depth = 0
    for char in line:
        if char == "(":
            depth += 1
            assert depth == 1
        elif char == ")":
            assert depth == 1
            depth -= 1
    assert depth == 0
    assert line.count("(NOT VERIFIED: area not calibrated)") == 1


def test_density_mark_is_written_once_on_each_side():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    mark = "(NOT VERIFIED: area not calibrated)"
    python_hits = [
        path.relative_to(root).as_posix()
        for path in (root / "worker").rglob("*.py")
        if mark in path.read_text(encoding="utf-8")
    ]
    web_hits = [
        path.relative_to(root).as_posix()
        for path in (root / "web" / "src").rglob("*.ts*")
        if mark in path.read_text(encoding="utf-8")
    ]
    assert python_hits == ["worker/rastro/display_names.py"]
    assert web_hits == ["web/src/lib/labels.ts"]


def test_zone_ids_use_a_place_name():
    assert zone_label("zone_1") == "Zone 1"
    assert zone_label("zona_1") == "Zone 1"
    assert public_copy("Crush risk in zone_1") == "Crush risk in Zone 1"
