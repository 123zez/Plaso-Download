# Guided Launcher Automation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a one-entry guided launcher that automates app startup, token capture, course listing, and interactive download/settings workflow.

**Architecture:** Add a new interactive launcher module that orchestrates existing API/download functions, persists launcher settings, and uses a simple menu loop. Reuse current downloader pipeline, but extend it with configurable per-course part concurrency and post-download duration verification feedback.

**Tech Stack:** Python, Typer/Rich (existing), subprocess on Windows, httpx/ffmpeg pipeline (existing)

---

### Task 1: Add persisted launcher settings

**Files:**
- Modify: `src/plaso_dl/config.py`
- Test: `tests/test_config.py`

Add `download_dir` and `part_workers` to config schema with backward-compatible load/save defaults.

### Task 2: Support configurable per-course part concurrency

**Files:**
- Modify: `src/plaso_dl/download.py`
- Test: `tests/test_download_verify.py`

Extend `download_hls_to_mp4(...)` to accept `part_workers` and use bounded worker pool when multiple playlist parts are detected.

### Task 3: Build guided launcher module

**Files:**
- Create: `src/plaso_dl/launcher.py`

Implement menu-driven flow:
- Welcome and launch desktop app with remote debug port
- Auto-capture token workflow
- Fetch course list and cache for session
- Menu: Download / Settings / Exit
- Download submenu: single / multiple / all / update-missing
- Return to menu after each operation

### Task 4: Add simple executable entry

**Files:**
- Create: `start_plaso_dl.py`

Provide one-file entrypoint for non-CLI users to run interactive workflow directly.

### Task 5: Validate behavior

**Files:**
- Modify: `tests/test_download_verify.py` (if needed)
- Run: full test suite and smoke command checks
