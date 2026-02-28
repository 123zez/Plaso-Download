from pathlib import Path
import json

from plaso_dl.config import ConfigStore


def test_save_and_load_token(tmp_path: Path) -> None:
    store = ConfigStore(base_dir=tmp_path)
    store.save_token("token123")
    assert store.load_token() == "token123"


def test_default_launcher_settings(tmp_path: Path) -> None:
    store = ConfigStore(base_dir=tmp_path)
    cfg = store.load()
    assert cfg.download_dir == "downloads"
    assert cfg.part_workers == 3
    assert cfg.batch_workers == 2


def test_backward_compatible_load_old_config_shape(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"access_token": "t"}), encoding="utf-8")
    cfg = ConfigStore(base_dir=tmp_path).load()
    assert cfg.access_token == "t"
    assert cfg.download_dir == "downloads"
    assert cfg.part_workers == 3
    assert cfg.batch_workers == 2
