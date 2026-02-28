from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_dir


@dataclass(frozen=True)
class Config:
    access_token: str | None = None
    download_dir: str = "downloads"
    part_workers: int = 3
    batch_workers: int = 2


class ConfigStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path(user_config_dir("plaso-dl"))
        self._base_dir = base_dir
        self._path = base_dir / "config.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> Config:
        if not self._path.exists():
            return Config()
        data = json.loads(self._path.read_text(encoding="utf-8"))
        token = data.get("access_token")
        if token is not None and not isinstance(token, str):
            token = None
        download_dir = data.get("download_dir")
        if not isinstance(download_dir, str) or not download_dir.strip():
            download_dir = "downloads"
        part_workers = data.get("part_workers")
        if not isinstance(part_workers, int):
            part_workers = 3
        part_workers = max(1, min(part_workers, 8))
        batch_workers = data.get("batch_workers")
        if not isinstance(batch_workers, int):
            batch_workers = 2
        batch_workers = max(1, min(batch_workers, 6))
        return Config(
            access_token=token,
            download_dir=download_dir,
            part_workers=part_workers,
            batch_workers=batch_workers,
        )

    def save(self, cfg: Config) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                {
                    "access_token": cfg.access_token,
                    "download_dir": cfg.download_dir,
                    "part_workers": cfg.part_workers,
                    "batch_workers": cfg.batch_workers,
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        try:
            os.chmod(self._path, 0o600)
        except Exception:
            # Best-effort on Windows.
            pass

    def save_token(self, token: str) -> None:
        old = self.load()
        self.save(
            Config(
                access_token=token.strip() or None,
                download_dir=old.download_dir,
                part_workers=old.part_workers,
                batch_workers=old.batch_workers,
            )
        )

    def load_token(self) -> str | None:
        return self.load().access_token

    def save_settings(
        self,
        *,
        download_dir: str,
        part_workers: int,
        batch_workers: int,
    ) -> None:
        old = self.load()
        self.save(
            Config(
                access_token=old.access_token,
                download_dir=download_dir.strip() or "downloads",
                part_workers=max(1, min(part_workers, 8)),
                batch_workers=max(1, min(batch_workers, 6)),
            )
        )
