from rastro.pack import load_pack


def test_load_fauna_pack():
    pack = load_pack("fauna")
    assert pack.id == "fauna-camtrap"
    assert any(t["class"] == "coyote" for t in pack.targets)
    coyote = next(t for t in pack.targets if t["class"] == "coyote")
    assert coyote["prompt"] == "coyote"
    assert "animal" in coyote.get("fallbacks", [])
    assert pack.dedup["reentry_window_s"] == 20
    assert "center_dist_factor" in pack.dedup
    assert "person" in pack.privacy["blur"]
    assert pack.privacy.get("identity") is False
