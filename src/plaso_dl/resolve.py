from __future__ import annotations

import re
import time
import httpx


def build_cdn_m3u8_url(location: str, *, slot: str = "s1") -> str:
    location = location.strip().lstrip("/")
    return f"https://filecdn-t.plaso.com/liveclass/plaso/{location}/{slot}/a.m3u8"


def build_cdn_m3u8_candidates(location: str) -> list[str]:
    return [
        build_cdn_m3u8_url(location, slot="s1"),
        build_cdn_m3u8_url(location, slot="a1"),
    ]


def _parse_duration_seconds(m3u8_text: str) -> float:
    vals = re.findall(r"#EXTINF:([0-9.]+)", m3u8_text)
    return sum(float(v) for v in vals)


def _pick_slots(duration_by_slot: dict[str, float]) -> list[str]:
    if not duration_by_slot:
        return ["s1"]

    meaningful = {k: v for k, v in duration_by_slot.items() if v >= 60.0}
    if not meaningful:
        best = max(duration_by_slot.items(), key=lambda kv: kv[1])[0]
        return [best]

    families: dict[str, list[tuple[int, float]]] = {"s": [], "a": []}
    for slot, dur in meaningful.items():
        p = slot[:1]
        idx = slot[1:]
        if p in families and idx.isdigit():
            families[p].append((int(idx), dur))

    best_family: list[str] = []
    best_total = 0.0
    for p in ("s", "a"):
        parts = sorted(families[p], key=lambda x: x[0])
        if len(parts) < 2:
            continue
        slots = [f"{p}{i}" for i, _ in parts]
        total = sum(d for _, d in parts)
        if total > best_total:
            best_total = total
            best_family = slots

    if best_family:
        return best_family

    s1 = meaningful.get("s1")
    a1 = meaningful.get("a1")
    if s1 is not None and a1 is not None and a1 <= s1 * 1.2:
        return ["s1"]

    best = max(meaningful.items(), key=lambda kv: kv[1])[0]
    return [best]


def _build_probe_slots(max_slots: int = 12, max_chunk_groups: int = 20) -> list[str]:
    slots: list[str] = []
    for prefix in ("s", "a"):
        for i in range(1, max_slots + 1):
            slots.append(f"{prefix}{i}")
        for g in range(0, max_chunk_groups + 1):
            slots.append(f"{prefix}{g * 100 + 1}")
    seen: set[str] = set()
    uniq: list[str] = []
    for s in slots:
        if s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    return uniq


def resolve_cdn_m3u8_urls(
    location: str,
    *,
    timeout_s: float = 10.0,
    max_slots: int = 12,
    max_chunk_groups: int = 20,
    probe_rounds: int = 2,
    probe_interval_s: float = 1.0,
) -> list[str]:
    duration_by_slot: dict[str, float] = {}
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        slots = _build_probe_slots(
            max_slots=max_slots, max_chunk_groups=max_chunk_groups
        )
        rounds = max(1, probe_rounds)
        for round_idx in range(rounds):
            for slot in slots:
                url = build_cdn_m3u8_url(location, slot=slot)
                try:
                    r = client.get(url)
                except Exception:
                    continue
                if r.status_code != 200 or "#EXTM3U" not in r.text:
                    continue
                dur = _parse_duration_seconds(r.text)
                prev = duration_by_slot.get(slot)
                if prev is None or dur > prev:
                    duration_by_slot[slot] = dur
            if round_idx < rounds - 1:
                time.sleep(max(0.0, probe_interval_s))

    selected_slots = _pick_slots(duration_by_slot)
    return [build_cdn_m3u8_url(location, slot=s) for s in selected_slots]


def resolve_cdn_m3u8_url(location: str, *, timeout_s: float = 10.0) -> str:
    return resolve_cdn_m3u8_urls(location, timeout_s=timeout_s)[0]
