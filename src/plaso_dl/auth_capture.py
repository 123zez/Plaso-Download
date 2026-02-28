from __future__ import annotations

import json
import time
import urllib.request
from urllib.parse import urlparse
from typing import Any

import websocket


def extract_access_token(headers: dict[str, Any]) -> str | None:
    for k, v in headers.items():
        if str(k).lower() == "access-token":
            s = str(v).strip()
            return s or None
    return None


def extract_token_from_event(evt: dict[str, Any]) -> str | None:
    method = evt.get("method")
    if method not in (
        "Network.requestWillBeSent",
        "Network.requestWillBeSentExtraInfo",
    ):
        return None

    params = evt.get("params")
    if not isinstance(params, dict):
        return None

    headers: Any = None
    if method == "Network.requestWillBeSent":
        req = params.get("request")
        if isinstance(req, dict):
            headers = req.get("headers")
    else:
        headers = params.get("headers")

    if not isinstance(headers, dict):
        return None
    return extract_access_token(headers)


def _is_course_api_url(url: str) -> bool:
    try:
        u = urlparse(url)
    except Exception:
        return False
    if u.netloc.lower() != "www.plaso.cn":
        return False
    return u.path.startswith("/course/api/v1/") or u.path.startswith(
        "/liveclassgo/api/v1/"
    )


def _read_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def _pick_target_ws(host: str, port: int) -> str:
    targets = _read_json(f"http://{host}:{port}/json/list")
    if not isinstance(targets, list):
        raise RuntimeError("Unexpected DevTools target list response")

    preferred = None
    fallback = None
    for t in targets:
        if not isinstance(t, dict):
            continue
        ws = t.get("webSocketDebuggerUrl")
        if not isinstance(ws, str):
            continue
        url = str(t.get("url", ""))
        if "PlasoCloud/resources/app/index.html" in url:
            preferred = ws
            break
        if fallback is None:
            fallback = ws

    if preferred:
        return preferred
    if fallback:
        return fallback
    raise RuntimeError("No debuggable target found on remote debugging endpoint")


def capture_access_token(
    *, host: str = "127.0.0.1", port: int = 9222, timeout_s: int = 180
) -> str:
    ws_url = _pick_target_ws(host, port)
    ws = websocket.create_connection(ws_url, timeout=5)
    try:
        msg_id = 1
        ws.send(json.dumps({"id": msg_id, "method": "Network.enable", "params": {}}))
        msg_id += 1

        start = time.time()
        request_url_by_id: dict[str, str] = {}
        while True:
            if time.time() - start > timeout_s:
                raise TimeoutError(
                    "Timed out waiting for access-token in network traffic"
                )

            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            if not isinstance(raw, str):
                continue
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError:
                continue

            method = evt.get("method")
            params = evt.get("params") if isinstance(evt.get("params"), dict) else {}

            if method == "Network.requestWillBeSent":
                request = params.get("request")
                if isinstance(request, dict):
                    rid = params.get("requestId")
                    url = request.get("url")
                    if isinstance(rid, str) and isinstance(url, str):
                        request_url_by_id[rid] = url
                    if isinstance(url, str) and _is_course_api_url(url):
                        token = extract_token_from_event(evt)
                        if token:
                            return token

            if method == "Network.requestWillBeSentExtraInfo":
                rid = params.get("requestId")
                if isinstance(rid, str):
                    url = request_url_by_id.get(rid, "")
                    if _is_course_api_url(url):
                        token = extract_token_from_event(evt)
                        if token:
                            return token
    finally:
        ws.close()
