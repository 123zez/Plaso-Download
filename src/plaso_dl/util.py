from __future__ import annotations

import re


_INVALID_FILENAME_CHARS = re.compile(r"[\\/:*?\"<>|]+")


def sanitize_filename(name: str, max_len: int = 180) -> str:
    s = name.strip()
    s = _INVALID_FILENAME_CHARS.sub("_", s)
    s = re.sub(r"\s+", " ", s)
    if not s:
        s = "untitled"
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s


def format_duration_hms(seconds: int | None) -> str:
    if seconds is None:
        return ""
    if seconds < 0:
        seconds = 0
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
