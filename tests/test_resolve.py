from plaso_dl.resolve import (
    _build_probe_slots,
    _pick_slots,
    build_cdn_m3u8_candidates,
    build_cdn_m3u8_url,
)


def test_build_cdn_m3u8_url() -> None:
    url = build_cdn_m3u8_url("12202/21113177_1770182849863a3_fg3")
    assert url.endswith("/liveclass/plaso/12202/21113177_1770182849863a3_fg3/s1/a.m3u8")


def test_build_cdn_m3u8_candidates_prefers_s1_then_a1() -> None:
    urls = build_cdn_m3u8_candidates("12202/21113177_1770182849863a3_fg3")
    assert urls[0].endswith("/s1/a.m3u8")
    assert urls[1].endswith("/a1/a.m3u8")


def test_pick_slots_prefers_multi_part_family() -> None:
    slots = _pick_slots({"s1": 3000.0, "a1": 1400.0, "a2": 1500.0})
    assert slots == ["a1", "a2"]


def test_pick_slots_prefers_s1_when_both_full() -> None:
    slots = _pick_slots({"s1": 15563.8, "a1": 15570.5})
    assert slots == ["s1"]


def test_build_probe_slots_contains_hundred_series() -> None:
    slots = _build_probe_slots(max_slots=2, max_chunk_groups=3)
    assert "s1" in slots
    assert "s101" in slots
    assert "s201" in slots
    assert "s301" in slots
    assert len(slots) == len(set(slots))
