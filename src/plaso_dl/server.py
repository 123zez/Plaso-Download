import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from threading import Event

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .api import list_courses, list_groups, login_with_password
from .config import ConfigStore, Config
from .download import download_hls_to_mp4
from .resolve import resolve_cdn_m3u8_urls
from .util import sanitize_filename

app = FastAPI(title="Plaso DL API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if getattr(sys, 'frozen', False):
    STATIC_DIR = Path(sys._MEIPASS) / "plaso_dl" / "static"
else:
    STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

class LoginRequest(BaseModel):
    account: str
    password: str

class SettingsUpdate(BaseModel):
    download_dir: str
    part_workers: int
    batch_workers: int

class DownloadItem(BaseModel):
    id: str
    name: str
    location: str
    duration: Optional[int]

class DownloadRequest(BaseModel):
    items: List[DownloadItem]

# Task Manager
class TaskState:
    def __init__(self, course_id: str, name: str):
        self.course_id = course_id
        self.name = name
        self.cancel_event = Event()
        self.pause_event = Event()
        self.status = "queued"
        self.progress = 0
        self.msg = ""

class DownloadManager:
    def __init__(self):
        self.tasks: Dict[str, TaskState] = {}
        self.queue = asyncio.Queue()

    def add_task(self, item: DownloadItem):
        if item.id not in self.tasks:
            self.tasks[item.id] = TaskState(item.id, item.name)
            self.queue.put_nowait(item)

    def pause_task(self, course_id: str):
        if course_id in self.tasks:
            self.tasks[course_id].pause_event.set()
            self.tasks[course_id].status = "paused"

    def resume_task(self, course_id: str):
        if course_id in self.tasks:
            self.tasks[course_id].pause_event.clear()
            self.tasks[course_id].status = "downloading"

    def cancel_task(self, course_id: str):
        if course_id in self.tasks:
            self.tasks[course_id].cancel_event.set()
            self.tasks[course_id].status = "cancelled"

manager = DownloadManager()
websocket_clients: List[WebSocket] = []

def get_config():
    return ConfigStore().load()

@app.get("/")
async def read_index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/config")
async def get_current_config():
    cfg = get_config()
    return {
        "download_dir": cfg.download_dir,
        "part_workers": cfg.part_workers,
        "batch_workers": cfg.batch_workers,
        "is_logged_in": cfg.access_token is not None
    }

@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    ConfigStore().save_settings(
        download_dir=settings.download_dir,
        part_workers=settings.part_workers,
        batch_workers=settings.batch_workers
    )
    return {"status": "ok"}

@app.post("/api/login")
async def login(req: LoginRequest):
    try:
        token = login_with_password(req.account, req.password)
        ConfigStore().save_token(token)
        return {"status": "ok", "token": token}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/api/logout")
async def logout(delete_config: bool = False):
    store = ConfigStore()
    if delete_config:
        if store.path.exists():
            store.path.unlink()
    else:
        store.save_token("")
    return {"status": "ok"}

@app.get("/api/courses")
async def get_courses(group_id: Optional[int] = None):
    cfg = get_config()
    if not cfg.access_token:
        raise HTTPException(status_code=401, detail="Not logged in")
    items = list_courses(cfg.access_token, group_id=group_id)
    return [{"id": it.id, "name": it.name, "teacher": it.teacher_name, "duration": it.duration_seconds, "location": it.file_common.location} for it in items]

@app.get("/api/groups")
async def get_groups_list():
    cfg = get_config()
    if not cfg.access_token:
        raise HTTPException(status_code=401, detail="Not logged in")
    groups = list_groups(cfg.access_token)
    return [{"id": g.id, "name": g.name} for g in groups]

@app.post("/api/download")
async def start_download(req: DownloadRequest):
    for item in req.items:
        manager.add_task(item)
    return {"status": "queued"}

@app.post("/api/download/pause/{course_id}")
async def pause_download(course_id: str):
    manager.pause_task(course_id)
    await broadcast_progress({"type": "progress", "course_id": course_id, "status": "paused", "msg": "已暂停"})
    return {"status": "ok"}

@app.post("/api/download/resume/{course_id}")
async def resume_download(course_id: str):
    manager.resume_task(course_id)
    await broadcast_progress({"type": "progress", "course_id": course_id, "status": "downloading", "msg": "继续传输"})
    return {"status": "ok"}

@app.post("/api/download/cancel/{course_id}")
async def cancel_download(course_id: str):
    manager.cancel_task(course_id)
    await broadcast_progress({"type": "progress", "course_id": course_id, "status": "cancelled", "msg": "已取消"})
    return {"status": "ok"}

async def broadcast_progress(data: dict):
    if not websocket_clients: return
    message = json.dumps(data)
    for ws in websocket_clients[:]:
        try: await ws.send_text(message)
        except: websocket_clients.remove(ws)

async def download_worker():
    while True:
        item = await manager.queue.get()
        try:
            state = manager.tasks[item.id]
            state.status = "downloading"
            await run_download_task(item, state)
        finally:
            manager.queue.task_done()

async def run_download_task(item: DownloadItem, state: TaskState):
    cfg = get_config()
    out_dir = Path(cfg.download_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (sanitize_filename(item.name) + ".mp4")
    
    if out_path.exists() and state.status != "downloading": # Don't skip if we are resuming
         pass 

    try:
        urls = resolve_cdn_m3u8_urls(item.location)
        loop = asyncio.get_running_loop()
        def cb(sec: float):
            prog = Math.round((sec / (item.duration or 1)) * 100) if item.duration else 0
            state.progress = prog
            asyncio.run_coroutine_threadsafe(broadcast_progress({"type": "progress", "course_id": item.id, "completed": sec, "total": item.duration or 0, "status": state.status}), loop)

        actual_s, ok = await loop.run_in_executor(None, lambda: download_hls_to_mp4(urls, out_path, expected_duration_s=item.duration, progress_cb=cb, cancel_event=state.cancel_event, pause_event=state.pause_event))
        await broadcast_progress({"type": "progress", "course_id": item.id, "status": "ok" if ok else "warn", "msg": "完成" if ok else "时长异常", "completed": actual_s or 0, "total": item.duration or 0})
    except Exception as e:
        status = "cancelled" if "cancelled" in str(e).lower() else "error"
        await broadcast_progress({"type": "progress", "course_id": item.id, "status": status, "msg": str(e)})

import math as Math

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.append(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in websocket_clients: websocket_clients.remove(websocket)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(download_worker())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
