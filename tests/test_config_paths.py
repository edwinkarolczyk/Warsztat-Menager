from __future__ import annotations

from pathlib import Path

import pytest

from config.paths import bind_settings, ensure_core_tree, get_path, join_path
from utils.path_utils import cfg_path


@pytest.fixture(autouse=True)
def reset_settings():
    # Rebind to clean dict before each test
    state: dict[str, str] = {}
    bind_settings(state)
    return state


def test_windows_defaults_are_rebased(tmp_path, reset_settings):
    state = reset_settings
    state.update(
        {
            "paths.data_root": "C:\\wm\\data",
            "warehouse.stock_source": "C:\\wm\\data\\magazyn\\magazyn.json",
        }
    )
    bind_settings(state)

    data_root = Path(get_path("paths.data_root"))
    assert data_root == Path(cfg_path("data")).resolve()

    stock_path = Path(get_path("warehouse.stock_source"))
    assert stock_path == data_root / "magazyn" / "magazyn.json"


def test_absolute_paths_preserved(tmp_path, reset_settings):
    data_root = tmp_path / "app_data"
    state = reset_settings
    state.update(
        {
            "paths.data_root": str(data_root),
            "warehouse.stock_source": str(data_root / "magazyn" / "magazyn.json"),
        }
    )
    bind_settings(state)

    assert Path(get_path("paths.data_root")) == data_root
    assert Path(get_path("warehouse.stock_source")) == data_root / "magazyn" / "magazyn.json"


def test_windows_path_with_custom_data_root(tmp_path, reset_settings):
    data_root = tmp_path / "storage"
    state = reset_settings
    state.update(
        {
            "paths.data_root": str(data_root),
            "warehouse.stock_source": "C:/wm/data/magazyn/magazyn.json",
        }
    )
    bind_settings(state)

    resolved = Path(get_path("warehouse.stock_source"))
    assert resolved == data_root / "magazyn" / "magazyn.json"


def test_join_path_uses_base_directory(tmp_path, reset_settings):
    data_root = tmp_path / "root"
    state = reset_settings
    state.update(
        {
            "paths.data_root": str(data_root),
            "paths.orders_dir": "zamowienia",
        }
    )
    bind_settings(state)

    target = Path(join_path("paths.orders_dir", "2025", "ZZ_0001.json"))
    assert target == data_root / "zamowienia" / "2025" / "ZZ_0001.json"


def test_ensure_core_tree_creates_directories(tmp_path, reset_settings):
    data_root = tmp_path / "warehouse"
    state = reset_settings
    state.update(
        {
            "paths.data_root": str(data_root),
            "paths.orders_dir": "zamowienia",
            "warehouse.stock_source": "C:/wm/data/magazyn/magazyn.json",
        }
    )
    bind_settings(state)

    ensure_core_tree()

    assert (data_root / "zamowienia").is_dir()
    assert (data_root / "magazyn").is_dir()


def test_get_path_returns_default_when_missing(reset_settings):
    state = reset_settings
    bind_settings(state)
    assert get_path("hall.background_image", "") == ""
