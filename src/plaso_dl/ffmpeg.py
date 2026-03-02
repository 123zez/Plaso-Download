from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional
from threading import Event


class FfmpegNotFoundError(RuntimeError):
    pass


class FfprobeNotFoundError(RuntimeError):
    pass


class FfmpegRunError(RuntimeError):
    pass

class FfmpegCancelledError(RuntimeError):
    pass


def ensure_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FfmpegNotFoundError("ffmpeg not found in PATH")
    return ffmpeg


def ensure_ffprobe() -> str:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe
    ffmpeg = ensure_ffmpeg()
    if ffmpeg.lower().endswith("ffmpeg.exe"):
        probe_candidate = ffmpeg[:-10] + "ffprobe.exe"
        if Path(probe_candidate).exists():
            return probe_candidate
    raise FfprobeNotFoundError("ffprobe not found in PATH")


def build_ffmpeg_hls_args(m3u8_url: str, out_path: str) -> list[str]:
    return [
        ensure_ffmpeg(),
        "-y",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-rw_timeout",
        "15000000",
        "-reconnect",
        "1",
        "-reconnect_streamed",
        "1",
        "-reconnect_delay_max",
        "5",
        "-http_persistent",
        "0",
        "-i",
        m3u8_url,
        "-c",
        "copy",
        "-bsf:a",
        "aac_adtstoasc",
        out_path,
    ]


def run_ffmpeg(
    args: list[str], 
    *, 
    progress_cb: Callable[[float], None] | None = None,
    cancel_event: Optional[Event] = None,
    pause_event: Optional[Event] = None
) -> None:
    p = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        # For Windows process control
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )

    logs: list[str] = []
    assert p.stdout is not None
    
    # We need a non-blocking way to read stdout or check events
    import os
    import fcntl # Not available on Windows, we'll use a thread or polling
    
    # Simple polling for Windows/Cross-platform
    while True:
        # Check cancellation
        if cancel_event and cancel_event.is_set():
            p.terminate()
            p.wait()
            raise FfmpegCancelledError("Download cancelled by user")

        # Check pause
        if pause_event and pause_event.is_set():
            # FFmpeg doesn't have a clean pause, so we might need to rely 
            # on the OS or just wait. On Windows, we can't easily SIGSTOP.
            # We'll just loop here until unpaused.
            time.sleep(0.5)
            continue

        line = p.stdout.readline()
        if not line:
            if p.poll() is not None:
                break
            continue
            
        line = line.strip()
        if "=" in line:
            parts = line.split("=", 1)
            if len(parts) == 2:
                k, v = parts
                if k == "out_time_ms" and progress_cb is not None:
                    try:
                        progress_cb(float(v) / 1_000_000.0)
                    except Exception:
                        pass
        else:
            logs.append(line)

    code = p.wait()
    if code == 0:
        return
    if code < 0: # Terminated
        raise FfmpegCancelledError("Process terminated")
        
    tail = "\n".join(logs[-12:]) if logs else "(no stderr)"
    raise FfmpegRunError(f"ffmpeg failed with code {code}:\n{tail}")

import sys

def run_ffmpeg_to_file(
    m3u8_url: str,
    out_path: Path,
    *,
    progress_cb: Callable[[float], None] | None = None,
    cancel_event: Optional[Event] = None,
    pause_event: Optional[Event] = None
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    args = build_ffmpeg_hls_args(m3u8_url, str(out_path))
    run_ffmpeg(args, progress_cb=progress_cb, cancel_event=cancel_event, pause_event=pause_event)


def build_ffmpeg_concat_args(list_file_path: str, out_path: str) -> list[str]:
    return [
        ensure_ffmpeg(),
        "-y",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_file_path,
        "-c",
        "copy",
        out_path,
    ]


def run_ffmpeg_concat_files(parts: list[Path], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = out_path.parent / f".{out_path.stem}.concat.txt"
    lines: list[str] = []
    for p in parts:
        escaped = str(p).replace("'", "''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        args = build_ffmpeg_concat_args(str(list_file), str(out_path))
        run_ffmpeg(args)
    finally:
        list_file.unlink(missing_ok=True)


def probe_media_duration_seconds(file_path: Path) -> float | None:
    ffprobe = ensure_ffprobe()
    args = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    r = subprocess.run(args, check=False, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    text = r.stdout.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
