from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Callable

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from .api import list_courses, list_groups
from .auth_capture import capture_access_token
from .config import ConfigStore
from .download import download_hls_to_mp4
from .models import CourseItem, GroupItem
from .resolve import resolve_cdn_m3u8_urls
from .util import format_duration_hms, sanitize_filename


console = Console()

WELCOME_TEXT = "欢迎使用 Plaso DL 全流程助手"
INITIAL_MENU_TEXT = "1) 登录  2) 设置  3) 退出"
LOGGED_IN_MENU_TEXT = "1) 获取课程目录  2) 按班级获取课程视频  3) 设置  4) 退出"
DOWNLOAD_MENU_TEXT = "1) 单个下载  2) 多个下载  3) 全部下载  4) 更新(仅缺失)  5) 返回"


def _infer_topic(name: str) -> str:
    s = (name or "").strip()
    if not s:
        return "未分类"
    if "-" in s:
        head = s.split("-", 1)[0].strip()
        return head or "未分类"
    s = re.sub(r"\s+\d+$", "", s).strip()
    return s or "未分类"


def _group_courses_by_topic(items: list[CourseItem]) -> dict[str, list[CourseItem]]:
    grouped: dict[str, list[CourseItem]] = {}
    for it in items:
        key = _infer_topic(it.name)
        grouped.setdefault(key, []).append(it)
    return grouped


def _is_choose_all_token(raw: str) -> bool:
    s = (raw or "").strip().lower()
    return s in {"0", "a", "all", "全部"}


def _choose_topic(items: list[CourseItem]) -> list[CourseItem]:
    grouped = _group_courses_by_topic(items)
    topics = sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    table = Table(title=f"课程目录（共 {len(topics)} 门）")
    table.add_column("#", justify="right")
    table.add_column("课程")
    table.add_column("视频数", justify="right")
    for i, (topic, rows) in enumerate(topics, start=1):
        table.add_row(str(i), topic, str(len(rows)))
    console.print(table)
    console.print("输入序号选择课程；输入 0/A 加载所有课程视频。")

    raw = console.input("请选择课程: ").strip()
    if _is_choose_all_token(raw):
        return items
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(topics):
            return topics[idx - 1][1]
    console.print("无效选择，默认显示全部视频。")
    return items


def _choose_group(groups: list[GroupItem]) -> GroupItem | None:
    if not groups:
        console.print("未获取到班级目录。")
        return None
    table = Table(title=f"班级目录（共 {len(groups)} 个）")
    table.add_column("#", justify="right")
    table.add_column("班级")
    for i, g in enumerate(groups, start=1):
        table.add_row(str(i), g.name)
    console.print(table)
    raw = console.input("请选择班级序号: ").strip()
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(groups):
            return groups[idx - 1]
    console.print("无效选择。")
    return None


def _print_courses(items: list[CourseItem]) -> None:
    table = Table(title=f"Courses ({len(items)})")
    table.add_column("#", justify="right")
    table.add_column("id", overflow="fold")
    table.add_column("name")
    table.add_column("teacher")
    table.add_column("duration", justify="right")
    for idx, it in enumerate(items, start=1):
        table.add_row(
            str(idx),
            it.id,
            it.name,
            it.teacher_name or "",
            format_duration_hms(it.duration_seconds),
        )
    console.print(table)


def _launch_desktop_app(exe: str) -> None:
    cmd = f"Start-Process '{exe}' -ArgumentList '--remote-debugging-port=9222'"
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
        check=False,
    )


def _run_capture_in_new_cmd(timeout_s: int = 600) -> bool:
    store = ConfigStore()
    old_token = store.load_token()
    deadline = time.time() + max(60, timeout_s)

    while time.time() < deadline:
        try:
            token = capture_access_token(host="127.0.0.1", port=9222, timeout_s=30)
            if token and token != old_token:
                store.save_token(token)
                return True
        except TimeoutError:
            pass
        except Exception:
            time.sleep(1)
        time.sleep(0.5)
    return False


def _build_capture_start_command(timeout_s: int) -> list[str]:
    capture_cmd = (
        "python -m plaso_dl auth auto-capture "
        "--host 127.0.0.1 --port 9222 "
        f"--timeout {max(60, int(timeout_s))}"
    )
    return ["cmd", "/c", "start", "", "cmd", "/k", capture_cmd]


def _course_file_path(course: CourseItem, out_dir: Path) -> Path:
    fname = (
        sanitize_filename(f"{course.name} - {course.teacher_name or 'unknown'}")
        + ".mp4"
    )
    return out_dir / fname


def _download_one(
    course: CourseItem,
    out_dir: Path,
    part_workers: int,
    *,
    progress_cb: Callable[[float], None] | None = None,
) -> tuple[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = _course_file_path(course, out_dir)
    if out_path.exists():
        return ("skip", f"Skip exists: {out_path.name}")

    urls = resolve_cdn_m3u8_urls(course.file_common.location)
    actual_s, ok = download_hls_to_mp4(
        urls,
        out_path,
        expected_duration_s=course.duration_seconds,
        tolerance_s=60,
        part_workers=part_workers,
        progress_cb=progress_cb,
    )
    if course.duration_seconds is not None and actual_s is not None and not ok:
        return (
            "warn",
            f"Saved with mismatch: {out_path.name} "
            f"expected={format_duration_hms(course.duration_seconds)} "
            f"actual={format_duration_hms(int(actual_s))}",
        )
    return ("ok", f"Saved: {out_path.name}")


def _select_courses(items: list[CourseItem], raw: str) -> list[CourseItem]:
    picks: list[CourseItem] = []
    by_id = {x.id: x for x in items}
    for token in [x.strip() for x in raw.split(",") if x.strip()]:
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(items):
                picks.append(items[idx - 1])
            continue
        c = by_id.get(token)
        if c is not None:
            picks.append(c)
    seen: set[str] = set()
    uniq: list[CourseItem] = []
    for c in picks:
        if c.id in seen:
            continue
        seen.add(c.id)
        uniq.append(c)
    return uniq


def _download_many(
    courses: list[CourseItem], out_dir: Path, part_workers: int, batch_workers: int
) -> None:
    if not courses:
        console.print("未选择课程。")
        return

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    )
    success = 0
    skipped = 0
    warned = 0
    failed: list[tuple[str, str]] = []

    with progress:
        task_id = progress.add_task("总体进度", total=len(courses))
        with ThreadPoolExecutor(max_workers=max(1, min(batch_workers, 6))) as ex:
            futures: dict[Any, tuple[CourseItem, int, float]] = {}
            for c in courses:
                per_total = float(c.duration_seconds or 100)
                per_task: Any = progress.add_task(c.name, total=per_total)

                def _mk_cb(tid: Any, total: float):
                    def _cb(sec: float) -> None:
                        progress.update(tid, completed=min(sec, total))

                    return _cb

                fut = ex.submit(
                    _download_one,
                    c,
                    out_dir,
                    part_workers,
                    progress_cb=_mk_cb(per_task, per_total),
                )
                futures[fut] = (c, per_task, per_total)

            for fut in as_completed(futures):
                c, per_task, per_total = futures[fut]
                try:
                    status, _msg = fut.result()
                    progress.update(per_task, completed=per_total)
                    if status == "skip":
                        skipped += 1
                        console.print(f"[cyan]{c.name}: 已存在，跳过[/cyan]")
                    elif status == "warn":
                        warned += 1
                        console.print(
                            f"[yellow]{c.name}: 下载完成（时长异常）[/yellow]"
                        )
                    else:
                        success += 1
                        console.print(f"[green]{c.name}: 下载成功[/green]")
                except Exception as e:
                    failed.append((c.name, str(e)))
                    console.print(f"[red]{c.name}: 下载失败[/red]")
                progress.update(task_id, advance=1)

    console.print("\n[bold]下载总结[/bold]")
    console.print(f"成功: {success}")
    console.print(f"跳过: {skipped}")
    console.print(f"警告(时长异常): {warned}")
    console.print(f"失败: {len(failed)}")
    if failed:
        table = Table(title="失败详情")
        table.add_column("课程")
        table.add_column("错误", overflow="fold")
        for name, err in failed:
            table.add_row(name, err)
        console.print(table)


def _settings_menu() -> None:
    store = ConfigStore()
    cfg = store.load()
    console.print("\n[bold]设置[/bold]")
    console.print(f"当前伯索程序路径: {cfg.plaso_exe_path}")
    console.print(f"当前下载目录: {cfg.download_dir}")
    console.print(f"当前单视频分片并发: {cfg.part_workers}")
    console.print(f"当前批量下载并发: {cfg.batch_workers}")

    raw_exe = console.input("伯索程序路径 (回车保持不变): ").strip()
    raw_dir = console.input("下载目录 (回车保持不变): ").strip()
    raw_workers = console.input("分片并发 1-8 (回车保持不变): ").strip()
    raw_batch_workers = console.input("批量下载并发 1-6 (回车保持不变): ").strip()

    plaso_exe_path = raw_exe or cfg.plaso_exe_path
    download_dir = raw_dir or cfg.download_dir
    part_workers = cfg.part_workers
    batch_workers = cfg.batch_workers
    if raw_workers:
        try:
            part_workers = int(raw_workers)
        except ValueError:
            console.print("并发输入无效，保持原值。")
            part_workers = cfg.part_workers
    if raw_batch_workers:
        try:
            batch_workers = int(raw_batch_workers)
        except ValueError:
            console.print("批量并发输入无效，保持原值。")
            batch_workers = cfg.batch_workers

    store.save_settings(
        plaso_exe_path=plaso_exe_path,
        download_dir=download_dir,
        part_workers=part_workers,
        batch_workers=batch_workers,
    )
    console.print("设置已保存。")


def _download_menu(items: list[CourseItem]) -> None:
    cfg = ConfigStore().load()
    out_dir = Path(cfg.download_dir)
    while True:
        console.print("\n[bold]下载菜单[/bold]")
        console.print(DOWNLOAD_MENU_TEXT)
        choice = console.input("请选择: ").strip()

        if choice == "1":
            raw = console.input("输入课程序号或课程 id: ").strip()
            selected = _select_courses(items, raw)
            if not selected:
                console.print("未选择有效课程。")
                continue
            status, msg = _download_one(selected[0], out_dir, cfg.part_workers)
            if status == "warn":
                console.print(f"[yellow]{msg}[/yellow]")
            elif status == "skip":
                console.print(f"[cyan]{msg}[/cyan]")
            else:
                console.print(msg)
        elif choice == "2":
            raw = console.input("输入多个序号/id（逗号分隔）: ").strip()
            selected = _select_courses(items, raw)
            _download_many(selected, out_dir, cfg.part_workers, cfg.batch_workers)
        elif choice == "3":
            _download_many(items, out_dir, cfg.part_workers, cfg.batch_workers)
        elif choice == "4":
            missing = [x for x in items if not _course_file_path(x, out_dir).exists()]
            console.print(f"待补下载课程数量: {len(missing)}")
            _download_many(missing, out_dir, cfg.part_workers, cfg.batch_workers)
        elif choice == "5":
            return
        else:
            console.print("无效选项。")


def main() -> None:
    console.print(f"[bold green]{WELCOME_TEXT}[/bold green]")
    token: str | None = None
    selected_items: list[CourseItem] | None = None

    while True:
        if token is None:
            console.print("\n[bold]开始菜单[/bold]")
            console.print(INITIAL_MENU_TEXT)
        else:
            console.print("\n[bold]登录后菜单[/bold]")
            console.print(LOGGED_IN_MENU_TEXT)
        choice = console.input("请选择: ").strip()
        if choice == "1" and token is None:
            cfg = ConfigStore().load()
            if not Path(cfg.plaso_exe_path).exists():
                console.print("[red]伯索程序路径不存在，请先到设置里修改路径。[/red]")
                continue
            console.print("步骤 1/3: 启动伯索云学堂桌面端并开启远程调试...")
            _launch_desktop_app(cfg.plaso_exe_path)
            console.print(
                "步骤 2/3: 自动抓取 token（请在伯索中进入历史课堂并点开任意回放）..."
            )
            ok = _run_capture_in_new_cmd(timeout_s=600)
            if not ok:
                console.print("[red]Token 抓取超时，请重试。[/red]")
                continue
            new_token = ConfigStore().load_token()
            if not new_token:
                console.print("[red]Token 抓取失败。[/red]")
                continue
            console.print("[green]登录成功（已获取 token）。[/green]")
            token = new_token
            selected_items = None
        elif choice == "1" and token is not None:
            console.print("正在获取课程视频列表...")
            all_items = list_courses(token)
            selected_items = _choose_topic(all_items)
            _print_courses(selected_items)
            _download_menu(selected_items)
        elif choice == "2" and token is not None:
            console.print("正在获取班级目录...")
            groups = list_groups(token)
            picked = _choose_group(groups)
            if picked is None:
                continue
            console.print(f"正在加载班级视频列表: {picked.name}")
            selected_items = list_courses(token, group_id=picked.id)
            _print_courses(selected_items)
            _download_menu(selected_items)
        elif choice == "3":
            _settings_menu()
        elif choice == "4" and token is not None:
            console.print("已退出。")
            return
        elif choice == "3" and token is None:
            console.print("已退出。")
            return
        else:
            console.print("无效选项。")
