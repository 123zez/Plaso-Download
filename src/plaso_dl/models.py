from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileCommon:
    location: str
    locationPath: str | None


@dataclass(frozen=True)
class CourseItem:
    id: str
    name: str
    teacher_name: str | None
    duration_seconds: int | None
    create_time_ms: int | None
    file_common: FileCommon


@dataclass(frozen=True)
class GroupItem:
    id: int
    name: str
    active_start_ms: int | None
    active_end_ms: int | None
