from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from .api import list_courses
from .config import ConfigStore
from .download import download_hls_to_mp4
from .models import CourseItem
from .resolve import resolve_cdn_m3u8_urls
from .util import format_duration_hms, sanitize_filename


app = typer.Typer(add_completion=False, no_args_is_help=True)
auth_app = typer.Typer(no_args_is_help=True)
courses_app = typer.Typer(no_args_is_help=True)
download_app = typer.Typer(no_args_is_help=True)

app.add_typer(auth_app, name="auth")
app.add_typer(courses_app, name="courses")
app.add_typer(download_app, name="download")

console = Console()


def _require_token() -> str:
    token = ConfigStore().load_token()
    if not token:
        raise typer.BadParameter("Missing token. Run: plaso-dl auth set-token <token>")
    return token


@auth_app.command("set-token")
def set_token(token: str) -> None:
    """Save access-token from the desktop app."""
    ConfigStore().save_token(token)
    console.print("Token saved.")


@courses_app.command("list")
def courses_list(
    search: str = typer.Option("", help="Search keyword"),
    limit: int = typer.Option(0, help="Limit number of items (0 = no limit)"),
) -> None:
    token = _require_token()
    items = list_courses(token, search=search)
    if limit and limit > 0:
        items = items[:limit]

    table = Table(title=f"Courses ({len(items)})")
    table.add_column("id", overflow="fold")
    table.add_column("name")
    table.add_column("teacher")
    table.add_column("duration", justify="right")
    table.add_column("location", overflow="fold")
    for it in items:
        table.add_row(
            it.id,
            it.name,
            it.teacher_name or "",
            format_duration_hms(it.duration_seconds),
            it.file_common.location,
        )
    console.print(table)


@download_app.command("course")
def download_course(
    course_id: str = typer.Option(..., "--id", help="Course _id"),
    out: Path = typer.Option(Path("downloads"), help="Output directory"),
) -> None:
    store = ConfigStore()
    cfg = store.load()
    token = _require_token()
    items = list_courses(token)
    match = next((x for x in items if x.id == course_id), None)
    if not match:
        raise typer.BadParameter("Course id not found in list")

    m3u8_urls = resolve_cdn_m3u8_urls(match.file_common.location)
    fname = (
        sanitize_filename(f"{match.name} - {match.teacher_name or 'unknown'}") + ".mp4"
    )
    out_path = out / fname
    console.print(f"Downloading: {match.name}")
    if len(m3u8_urls) > 1:
        console.print(f"Detected {len(m3u8_urls)} playlist parts, merging...")
    actual_s, ok = download_hls_to_mp4(
        m3u8_urls,
        out_path,
        expected_duration_s=match.duration_seconds,
        tolerance_s=60,
        part_workers=cfg.part_workers,
    )
    if match.duration_seconds is not None and actual_s is not None:
        console.print(
            f"Duration check expected={format_duration_hms(match.duration_seconds)} actual={format_duration_hms(int(actual_s))}"
        )
    if not ok:
        console.print(
            "Warning: duration mismatch > 1 minute, possible missing segments"
        )
    console.print(f"Saved: {out_path}")


@download_app.command("all")
def download_all(
    out: Path = typer.Option(Path("downloads"), help="Output directory"),
    search: str = typer.Option("", help="Search keyword"),
    limit: int = typer.Option(0, help="Limit number of items (0 = no limit)"),
    workers: int = typer.Option(
        0, help="Parallel downloads for batch (0 = use settings)"
    ),
) -> None:
    store = ConfigStore()
    cfg = store.load()
    token = _require_token()
    items = list_courses(token, search=search)
    if limit and limit > 0:
        items = items[:limit]

    out.mkdir(parents=True, exist_ok=True)

    def _job(course: CourseItem) -> tuple[str, str]:
        fname = (
            sanitize_filename(f"{course.name} - {course.teacher_name or 'unknown'}")
            + ".mp4"
        )
        out_path = out / fname
        if out_path.exists():
            return ("skip", f"Skip exists: {out_path.name}")
        m3u8_urls = resolve_cdn_m3u8_urls(course.file_common.location)
        actual_s, ok = download_hls_to_mp4(
            m3u8_urls,
            out_path,
            expected_duration_s=course.duration_seconds,
            tolerance_s=60,
            part_workers=cfg.part_workers,
        )
        if course.duration_seconds is not None and actual_s is not None and not ok:
            return (
                "warn",
                f"Saved with mismatch: {out_path.name} expected={format_duration_hms(course.duration_seconds)} actual={format_duration_hms(int(actual_s))}",
            )
        return ("ok", f"Saved: {out_path.name}")

    if workers <= 0:
        workers = cfg.batch_workers
    workers = max(1, min(workers, 6))
    success = 0
    skipped = 0
    warned = 0
    failed: list[tuple[str, str]] = []
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    )
    with progress:
        task_id = progress.add_task("Downloading courses", total=len(items))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_job, it): it for it in items}
            for fut in as_completed(futures):
                try:
                    status, msg = fut.result()
                    if status == "skip":
                        skipped += 1
                        console.print(f"[cyan]{msg}[/cyan]")
                    elif status == "warn":
                        warned += 1
                        console.print(f"[yellow]{msg}[/yellow]")
                    else:
                        success += 1
                        console.print(msg)
                except Exception as e:
                    course = futures[fut]
                    failed.append((course.name, str(e)))
                    console.print(f"[red]Failed: {course.name}[/red]")
                progress.update(task_id, advance=1)

    console.print("\n[bold]Download Summary[/bold]")
    console.print(f"Success: {success}")
    console.print(f"Skipped: {skipped}")
    console.print(f"Warnings: {warned}")
    console.print(f"Failed: {len(failed)}")
    if failed:
        table = Table(title="Failed Details")
        table.add_column("course")
        table.add_column("error", overflow="fold")
        for name, err in failed:
            table.add_row(name, err)
        console.print(table)
