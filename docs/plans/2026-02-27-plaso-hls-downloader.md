# Plaso HLS Downloader Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI that lists your historical live-class recordings and batch-downloads each course video via HLS (m3u8) into MP4 files.

**Architecture:** A small Python package with (1) an API client that calls the course list endpoint using your `access-token`, and (2) an HLS downloader that resolves an m3u8 URL from each course item and delegates the actual media fetch/remux to `ffmpeg`.

**Tech Stack:** Python 3.10+, `httpx`, `typer`, `rich`, `pytest`, system `ffmpeg`.

---

### Task 1: Scaffold Project + CLI Entry

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/plaso_dl/__init__.py`
- Create: `src/plaso_dl/cli.py`

**Step 1: Write a minimal CLI skeleton**

- Commands: `auth set-token`, `courses list`, `download course`, `download all`
- Ensure `python -m plaso_dl ...` works.

**Step 2: Manual smoke test**

Run:
```bash
python -m plaso_dl --help
```
Expected: shows commands.

---

### Task 2: Persist Config (Token, Defaults)

**Files:**
- Create: `src/plaso_dl/config.py`
- Test: `tests/test_config.py`

**Step 1: Write failing test**

```python
from plaso_dl.config import ConfigStore

def test_save_and_load_token(tmp_path):
    store = ConfigStore(base_dir=tmp_path)
    store.save_token("token123")
    assert store.load_token() == "token123"
```

**Step 2: Run to verify it fails**

Run:
```bash
pytest -q
```
Expected: FAIL (missing module/implementation).

**Step 3: Implement**

- Store config in JSON at `%APPDATA%/plaso-dl/config.json` by default.
- Allow overriding base directory for tests.

**Step 4: Run tests**

Run:
```bash
pytest -q
```
Expected: PASS.

---

### Task 3: Implement API Client for Course List

**Files:**
- Create: `src/plaso_dl/api.py`
- Create: `src/plaso_dl/models.py`
- Test: `tests/test_api_payload.py`

**Step 1: Write failing test for request building**

```python
from plaso_dl.api import build_course_list_request

def test_build_course_list_request_minimal():
    req = build_course_list_request(search="")
    assert req["method"] == "POST"
    assert "/course/api/v1/m/package/student/list/quit" in req["url"]
    assert req["json"] == {"search": ""}
```

**Step 2: Run and verify FAIL**

Run:
```bash
pytest -q
```

**Step 3: Implement**

- Endpoint (observed): `POST https://www.plaso.cn/course/api/v1/m/package/student/list/quit`
- Headers required: `access-token`, plus common headers.
- Payload at minimum: `{ "search": "" }`
- Parse response into a `CourseItem` model containing:
  - `_id`, `name`, `teacherName`, `duration`, `createTime`, `fileCommon.location`.

**Step 4: Run tests**

Run:
```bash
pytest -q
```

---

### Task 4: Resolve m3u8 URL From Course Item

**Files:**
- Create: `src/plaso_dl/resolve.py`
- Test: `tests/test_resolve.py`

**Step 1: Write failing test**

```python
from plaso_dl.resolve import build_cdn_m3u8_url

def test_build_cdn_m3u8_url():
    url = build_cdn_m3u8_url("12202/21113177_1770182849863a3_fg3")
    assert url.endswith("/liveclass/plaso/12202/21113177_1770182849863a3_fg3/a1/a.m3u8")
```

**Step 2: Implement**

- Observed media URL form: `https://filecdn-t.plaso.com/liveclass/plaso/{location}/a1/a.m3u8`

**Step 3: Run tests**

Run:
```bash
pytest -q
```

---

### Task 5: HLS Download via ffmpeg

**Files:**
- Create: `src/plaso_dl/ffmpeg.py`
- Create: `src/plaso_dl/download.py`
- Test: `tests/test_ffmpeg_cmd.py`

**Step 1: Write failing test for ffmpeg args**

```python
from plaso_dl.ffmpeg import build_ffmpeg_hls_args

def test_ffmpeg_hls_args_contains_input_and_copy():
    args = build_ffmpeg_hls_args("https://example.com/a.m3u8", "out.mp4")
    assert "-i" in args
    assert "-c" in args and "copy" in args
```

**Step 2: Implement**

- Use `ffmpeg -y -hide_banner -loglevel error -i <m3u8> -c copy -bsf:a aac_adtstoasc <out.mp4>`
- If m3u8 contains `#EXT-X-KEY`, fail with a clear error.

---

### Task 6: Wire CLI Commands End-to-End

**Files:**
- Modify: `src/plaso_dl/cli.py`

**Step 1: `auth set-token`**

- Store `access-token` into config.

**Step 2: `courses list`**

- Call API, print table (name/teacher/duration/id/location).

**Step 3: `download all`**

- For each course item, build m3u8 URL and run ffmpeg into output folder.
- Sanitize filenames.

**Step 4: Manual run**

```bash
python -m plaso_dl auth set-token "<paste-your-token>"
python -m plaso_dl courses list
python -m plaso_dl download all --out "D:/Project/plaso-dl/downloads" --limit 3
```

---

### Task 7 (Optional): Signed URL Fallback

If CDN m3u8 is blocked in some cases, detect 403/404 and add a fallback that uses a captured endpoint returning the signed `file.plaso.com` playlist URL.
