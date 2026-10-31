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
    assert line == "Peak density 5.4 people/m² (NOT VERIFIED (area not calibrated)). Zone 1."
    assert ".." not in line


def test_zone_ids_use_a_place_name():
    assert zone_label("zone_1") == "Zone 1"
    assert zone_label("zona_1") == "Zone 1"
    assert public_copy("Crush risk in zone_1") == "Crush risk in Zone 1"
