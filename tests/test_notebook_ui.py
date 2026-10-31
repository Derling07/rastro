"""The field notebook says what the product is, in the pages a judge opens."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "src"


def _text(*parts: str) -> str:
    return "\n".join((WEB.joinpath(*part.split("/")).read_text(encoding="utf-8")) for part in parts)


def test_pages_keep_one_numbered_guide():
    shell = (WEB / "components/notebook/Shell.tsx").read_text(encoding="utf-8")
    assert "Pick a module" not in shell
    assert "Rastro connects a count to a decision." in shell
    studio = (WEB / "components/studio/Studio.tsx").read_text(encoding="utf-8")
    assert "1 · Module" in studio
    assert "2 · Video" in studio
    assert "3 · Run" in studio
    assert "4 · Results" in studio
    assert "fauna.json" not in studio
    assert "field-note?run=" in studio
    css = (WEB / "app/globals.css").read_text(encoding="utf-8")
    assert "--paper:" in css
    assert "--viewfinder:" in css
    assert "@keyframes" not in css
    cameras = (WEB / "components/cameras/Cameras.tsx").read_text(encoding="utf-8")
    assert "Simulated camera" in cameras
    assert "does not notify authorities" in cameras
    assert "Left the zone here" in cameras
    assert "Seen inside the zone" in cameras
    assert "Safe zone" in cameras
    assert "Protected zone" in cameras
    assert ">Trigger<" not in cameras


def test_alert_card_separates_the_engine_count_from_the_summary():
    card = (WEB / "components/notebook/AlertCard.tsx").read_text(encoding="utf-8")
    assert "note.summary_label" in card
    assert "line-clamp-3" in card
    assert 'data-unsure={note.not_sure ? "true" : "false"}' in card
    assert "Saved in this demo session only. No message sent." in card
    assert "Engine count" in card
    assert "The summary cannot change this number." in card
    assert "Example data" in card
    assert "not_sure" in card
    studio = (WEB / "components/studio/Studio.tsx").read_text(encoding="utf-8")
    assert "field-note?run=" in studio
    assert "Mock mode." in studio and "Live keys." in studio


def test_density_views_use_two_states_and_save_is_shared():
    chart = (WEB / "components/DensityChart.tsx").read_text(encoding="utf-8")
    overlay = (WEB / "components/ZoneHeatOverlay.tsx").read_text(encoding="utf-8")
    levels = (WEB / "lib/multitudes.ts").read_text(encoding="utf-8")
    labels = (WEB / "lib/labels.ts").read_text(encoding="utf-8")
    cameras = (WEB / "components/cameras/Cameras.tsx").read_text(encoding="utf-8")
    assert "4 · proposed" not in chart and "4 · proposed" not in overlay
    assert "DENSITY_HIGH" in chart
    assert "medium" not in levels
    assert "b[0].length - a[0].length" in labels
    assert "saveFieldNote" in cameras
    assert "void decideNote" not in cameras
    board = (WEB / "components/studio/IdentityBoard.tsx").read_text(encoding="utf-8")
    assert "trackerLabel" in board
    assert "· id" not in board
    assert "sighting.object_id" not in board
    assert "server error (" in (WEB / "lib/saveNote.ts").read_text(encoding="utf-8")


def test_copy_does_not_claim_a_waze_partnership():
    blob = _text(
        "components/PeakHours.tsx",
        "components/notebook/AlertCard.tsx",
    ).lower()
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert "waze for cities" in readme
    assert "compatible with waze for cities" in readme
    assert "not a partnership" in readme
    for banned in ("uber", "didi", "google maps", "official partner"):
        assert banned not in readme
        assert banned not in blob
