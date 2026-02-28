from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, cast

import httpx

from .models import CourseItem, FileCommon, GroupItem


PLASO_BASE = "https://www.plaso.cn"
LIVECLASS_HISTORY_PATH = "/liveclassgo/api/v1/history/listRecord"
COURSE_LIST_PATH = "/course/api/v1/m/package/student/list"
COURSE_LIST_PATH_FALLBACK = "/course/api/v1/m/package/student/list/quit"
GROUP_LIST_PATH = "/gt/servlet/oldgroup/getSimplifiedGroupsInfo"
LOGIN_PATH = "/custom/usr/doLogin"


def _to_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _parse_course_item(raw: dict[str, Any]) -> CourseItem:
    fc = raw.get("fileCommon")
    if not isinstance(fc, dict):
        fc = {}

    if not fc.get("location") and raw.get("location") is not None:
        fc["location"] = raw.get("location")

    file_common = FileCommon(
        location=str(fc.get("location", "")),
        locationPath=(
            str(fc.get("locationPath")) if fc.get("locationPath") is not None else None
        ),
    )

    return CourseItem(
        id=str(raw.get("_id", "")),
        name=str(
            raw.get("shortDesc")
            or raw.get("name")
            or raw.get("title")
            or raw.get("courseName")
            or raw.get("className")
            or ""
        ),
        teacher_name=(
            str(raw.get("teacherName")) if raw.get("teacherName") is not None else None
        ),
        duration_seconds=_to_int(raw.get("duration")),
        create_time_ms=_to_int(raw.get("createTime")),
        file_common=file_common,
    )


def parse_course_list_from_list(raw_list: list[Any]) -> list[CourseItem]:
    items: list[CourseItem] = []
    for raw in raw_list:
        if isinstance(raw, dict):
            items.append(_parse_course_item(raw))
    return items


def parse_course_list(obj: dict[str, Any]) -> list[CourseItem]:
    raw_list = obj.get("list")
    if not isinstance(raw_list, list):
        rec = obj.get("records")
        if isinstance(rec, list):
            raw_list = rec
        else:
            data = obj.get("data")
            if isinstance(data, dict) and isinstance(data.get("list"), list):
                raw_list = data.get("list")
            else:
                return []
    if not isinstance(raw_list, list):
        return []
    return parse_course_list_from_list(cast(list[Any], raw_list))


def parse_group_list(raw_list: list[Any]) -> list[GroupItem]:
    out: list[GroupItem] = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        gid = _to_int(raw.get("id"))
        if gid is None:
            continue
        name = str(raw.get("groupName") or raw.get("name") or "").strip()
        if not name:
            name = f"group-{gid}"
        out.append(
            GroupItem(
                id=gid,
                name=name,
                active_start_ms=_to_int(raw.get("activeStartMs")),
                active_end_ms=_to_int(raw.get("activeEndMs")),
            )
        )
    return out


def build_course_list_request(
    search: str = "",
    *,
    endpoint: str = "history",
    page_no: int = 1,
    page_size: int = 200,
    group_id: int | None = None,
) -> dict[str, Any]:
    if endpoint == "history":
        path = LIVECLASS_HISTORY_PATH
        now_ms = int(time.time() * 1000)
        payload = {
            "dateFrom": now_ms - 5 * 365 * 24 * 3600 * 1000,
            "dateTo": now_ms + 24 * 3600 * 1000,
            "indexStart": max(0, (page_no - 1) * page_size),
            "pageSize": page_size,
        }
        if group_id is not None:
            payload["groupId"] = int(group_id)
    elif endpoint == "course_list":
        path = COURSE_LIST_PATH
        payload = {"search": search, "pageNo": page_no, "pageSize": page_size}
    else:
        path = COURSE_LIST_PATH_FALLBACK
        payload = {"search": search, "pageNo": page_no, "pageSize": page_size}

    return {
        "method": "POST",
        "url": f"{PLASO_BASE}{path}",
        "json": payload,
    }


def _headers(access_token: str) -> dict[str, str]:
    return {
        "accept": "*/*",
        "accept-language": "zh-CN",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "access-token": access_token,
        "device": "pc",
        "platform": "plaso",
        "pragma": "no-cache",
        "version": "5.64.114",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) plaso_client/1.07.137 Chrome/89.0.4389.128 Electron/12.0.18 Safari/537.36",
    }


def _preview_headers() -> dict[str, str]:
    return _headers("previewToken")


def extract_access_token_from_login_response(data: dict[str, Any]) -> str | None:
    if not isinstance(data, dict):
        return None
    if data.get("code") != 0:
        return None
    obj = data.get("obj")
    if not isinstance(obj, dict):
        return None
    token = obj.get("access_token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def login_with_password(
    login_name: str, password_plain: str, *, timeout_s: float = 30.0
) -> str:
    login_name = login_name.strip()
    password_plain = password_plain.strip()
    if not login_name or not password_plain:
        raise RuntimeError("账号或密码为空")

    payload = {
        "rawName": login_name,
        "name": login_name,
        "passwd": hashlib.md5(password_plain.encode("utf-8")).hexdigest(),
        "loginName": login_name,
        "clientVersion": "5.64.114",
        "deviceId": f"windows-{uuid.uuid4()}",
        "deviceName": "PC",
        "role": 1,
        "version": "12.0.18_5.64.114",
        "systemInfo": "10.0.26200 ia32 1.07.137",
        "osInfo": "Windows_NT",
    }
    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(
            f"{PLASO_BASE}{LOGIN_PATH}",
            headers=_preview_headers(),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("登录响应格式异常")

    token = extract_access_token_from_login_response(data)
    if token:
        return token

    raise RuntimeError(f"登录失败: code={data.get('code')!r}, msg={data.get('msg')!r}")


def list_courses(
    access_token: str,
    *,
    search: str = "",
    timeout_s: float = 30.0,
    group_id: int | None = None,
) -> list[CourseItem]:
    with httpx.Client(timeout=timeout_s) as client:
        last_error: Exception | None = None

        for endpoint in ("history", "course_list", "course_list_quit"):
            req = build_course_list_request(
                search=search, endpoint=endpoint, group_id=group_id
            )
            r = client.request(
                req["method"],
                req["url"],
                headers=_headers(access_token),
                json=req["json"],
            )
            r.raise_for_status()

            try:
                data = r.json()
            except json.JSONDecodeError as e:
                ctype = r.headers.get("content-type", "")
                snippet = r.text[:300].replace("\n", " ")
                last_error = RuntimeError(
                    f"Non-JSON response from course API {req['url']}. status={r.status_code}, content-type={ctype}, body={snippet!r}"
                )
                continue

            if not isinstance(data, dict):
                last_error = RuntimeError(
                    f"Unexpected non-dict response from {req['url']}: {type(data).__name__}"
                )
                continue

            obj = data.get("obj")

            if isinstance(obj, list):
                return parse_course_list_from_list(obj)
            if isinstance(obj, dict):
                return parse_course_list(obj)
            top_list = data.get("list")
            if isinstance(top_list, list):
                return parse_course_list_from_list(top_list)

            msg = data.get("msg")
            code = data.get("code")
            last_error = RuntimeError(
                f"Unexpected response shape from {req['url']}. code={code!r}, msg={msg!r}, keys={list(data.keys())!r}, obj_type={type(obj).__name__ if obj is not None else None!r}, obj_preview={str(obj)[:220]!r}"
            )

        assert last_error is not None
        raise last_error


def list_groups(access_token: str, *, timeout_s: float = 30.0) -> list[GroupItem]:
    now_ms = int(time.time() * 1000)
    payload = {
        "dateFrom": now_ms - 5 * 365 * 24 * 3600 * 1000,
        "dateTo": now_ms + 24 * 3600 * 1000,
    }
    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(
            f"{PLASO_BASE}{GROUP_LIST_PATH}",
            headers=_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, dict):
        return []
    obj = data.get("obj")
    if isinstance(obj, list):
        return parse_group_list(obj)
    info = data.get("info")
    if isinstance(info, dict) and isinstance(info.get("list"), list):
        return parse_group_list(cast(list[Any], info.get("list")))
    return []
