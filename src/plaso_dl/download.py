from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import httpx

from .ffmpeg import (
    probe_media_duration_seconds,
    run_ffmpeg_concat_files,
    run_ffmpeg_to_file,
)


class EncryptedHlsError(RuntimeError):
    pass


def _check_not_encrypted(m3u8_url: str, *, timeout_s: float = 20.0) -> None:
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        r = client.get(m3u8_url)
        r.raise_for_status()
        text = r.text
    if "#EXT-X-KEY" in text:
        raise EncryptedHlsError("Encrypted HLS (#EXT-X-KEY) is not supported")


def _read_m3u8_and_check(m3u8_url: str, *, timeout_s: float = 20.0) -> str:
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        r = client.get(m3u8_url)
        r.raise_for_status()
        text = r.text
    if "#EXT-X-KEY" in text:
        raise EncryptedHlsError("Encrypted HLS (#EXT-X-KEY) is not supported")
    return text


def _m3u8_duration_seconds(m3u8_text: str) -> float:
    total = 0.0
    for line in m3u8_text.splitlines():
        line = line.strip()
        if not line.startswith("#EXTINF:"):
            continue
        raw = line[8:].split(",", 1)[0].strip()
        try:
            total += float(raw)
        except ValueError:
            continue
    return total


def is_duration_within_tolerance(
    *, expected_s: int | None, actual_s: float | None, tolerance_s: int = 60
) -> bool:
    if expected_s is None or actual_s is None:
        return True
    return abs(float(expected_s) - float(actual_s)) <= float(tolerance_s)


def download_hls_to_mp4(
    m3u8_url: str | list[str],
    out_path: Path,
    *,
    expected_duration_s: int | None = None,
    tolerance_s: int = 60,
    part_workers: int = 3,
    progress_cb: Callable[[float], None] | None = None,
) -> tuple[float | None, bool]:
    urls = [m3u8_url] if isinstance(m3u8_url, str) else list(m3u8_url)
    urls = [u for u in urls if u]
    if not urls:
        raise RuntimeError("No m3u8 url found for download")

    if len(urls) == 1:
        _check_not_encrypted(urls[0])
        run_ffmpeg_to_file(urls[0], out_path, progress_cb=progress_cb)
        actual = probe_media_duration_seconds(out_path)
        return actual, is_duration_within_tolerance(
            expected_s=expected_duration_s, actual_s=actual, tolerance_s=tolerance_s
        )

    with tempfile.TemporaryDirectory(prefix="plaso-dl-") as tmp:
        tmp_dir = Path(tmp)
        parts: list[Path] = [
            tmp_dir / f"part_{idx:03d}.mp4" for idx in range(1, len(urls) + 1)
        ]

        meta = [_read_m3u8_and_check(url) for url in urls]
        part_durations = [_m3u8_duration_seconds(x) for x in meta]
        part_offsets: list[float] = []
        running = 0.0
        for d in part_durations:
            part_offsets.append(running)
            running += d

        def _download_part(idx: int, url: str) -> None:
            def _part_progress(sec: float) -> None:
                if progress_cb is None:
                    return
                progress_cb(part_offsets[idx] + sec)

            run_ffmpeg_to_file(url, parts[idx], progress_cb=_part_progress)

        worker_count = max(1, min(part_workers, len(urls), 8))
        with ThreadPoolExecutor(max_workers=worker_count) as ex:
            futures = [
                ex.submit(_download_part, idx, url) for idx, url in enumerate(urls)
            ]
            for fut in as_completed(futures):
                fut.result()

        run_ffmpeg_concat_files(parts, out_path)
    actual = probe_media_duration_seconds(out_path)
    return actual, is_duration_within_tolerance(
        expected_s=expected_duration_s, actual_s=actual, tolerance_s=tolerance_s
    )
