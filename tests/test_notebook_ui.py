"""The field notebook says what the product is, in the pages a judge opens."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "src"


def _text(*parts: str) -> str:
    return "\n".join((WEB.joinpath(*part.split("/")).read_text(encoding="utf-8")) for part in parts)


def test_pages_explain_the_three_steps_and_the_viewfinder():
    shell = (WEB / "components/notebook/Shell.tsx").read_text(encoding="utf-8")
    assert "Pick a module" in shell
    assert "Watch the video" in shell
    assert "Read the count and the alerts" in shell
    css = (WEB / "app/globals.css").read_text(encoding="utf-8")
    assert "--paper:" in css
    assert "--viewfinder:" in css
    assert "@keyframes" not in css
    cameras = (WEB / "components/cameras/Cameras.tsx").read_text(encoding="utf-8")
    assert "Simulated camera" in cameras
    assert "does not notify authorities" in cameras


def test_alert_card_separates_the_engine_count_from_the_summary():
    card = (WEB / "components/notebook/AlertCard.tsx").read_text(encoding="utf-8")
    assert "Muse Spark summary" in card
    assert "Engine count" in card
    assert "The summary cannot change this number." in card
    assert "Example data" in card
    assert "not_sure" in card
    studio = (WEB / "components/studio/Studio.tsx").read_text(encoding="utf-8")
    assert "clip=DSCF0112" in studio
    assert "Mock mode." in studio and "Live keys." in studio


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
