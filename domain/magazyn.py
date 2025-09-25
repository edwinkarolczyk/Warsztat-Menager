"""Helpers for warehouse domain paths and persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path, PureWindowsPath
from typing import Any, Dict, Iterable, Mapping

from config.paths import get_path

_DEFAULT_WAREHOUSE_DIR = Path("data") / "magazyn"
_DEFAULT_STATES_FILE = _DEFAULT_WAREHOUSE_DIR / "stany.json"
_DEFAULT_RESERVATIONS_FILE = _DEFAULT_WAREHOUSE_DIR / "rezerwacje.json"
_DEFAULT_STOCK_FILE = _DEFAULT_WAREHOUSE_DIR / "magazyn.json"


def _coerce_path(value: str | os.PathLike[str] | None, fallback: Path) -> Path:
    """Return ``value`` coerced to :class:`Path` with sane fallback."""

    if not value:
        return fallback
    if isinstance(value, os.PathLike):
        return Path(value)
    text = str(value)
    if "\\" in text:
        return Path(PureWindowsPath(text))
    return Path(text)


def warehouse_dir(base_dir: str | os.PathLike[str] | None = None) -> Path:
    """Return directory containing warehouse related files."""

    if base_dir:
        return _coerce_path(base_dir, _DEFAULT_WAREHOUSE_DIR)

    stock_file = get_path("warehouse.stock_source")
    if stock_file:
        return _coerce_path(stock_file, _DEFAULT_STOCK_FILE).parent

    path = get_path("paths.warehouse_dir")
    return _coerce_path(path, _DEFAULT_WAREHOUSE_DIR)


def stock_file_path() -> str:
    """Return path to the main warehouse JSON file."""

    path = get_path("warehouse.stock_source")
    stock = _coerce_path(path, _DEFAULT_STOCK_FILE)
    return str(stock)


def states_file_path(base_dir: str | os.PathLike[str] | None = None) -> str:
    """Return path to ``stany.json`` using configuration overrides."""

    if base_dir:
        return str(_coerce_path(base_dir, _DEFAULT_WAREHOUSE_DIR) / "stany.json")

    path = get_path("warehouse.states_file")
    if path:
        return str(_coerce_path(path, _DEFAULT_STATES_FILE))

    directory = warehouse_dir()
    return str(directory / "stany.json")


def reservations_file_path(base_dir: str | os.PathLike[str] | None = None) -> str:
    """Return path to ``rezerwacje.json`` honoring configuration overrides."""

    if base_dir:
        return str(_coerce_path(base_dir, _DEFAULT_WAREHOUSE_DIR) / "rezerwacje.json")

    path = get_path("warehouse.reservations_file")
    if path:
        return str(_coerce_path(path, _DEFAULT_RESERVATIONS_FILE))

    directory = warehouse_dir()
    return str(directory / "rezerwacje.json")


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def save_states(
    states: Mapping[str, Any] | Iterable[tuple[str, Any]],
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> str:
    """Persist simplified warehouse ``states`` to the configured location."""

    path = states_file_path(base_dir)
    _ensure_parent(path)
    if isinstance(states, Mapping):
        data: Dict[str, Any] = dict(states)
    else:
        data = dict(states)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return path


def save_reservations(
    reservations: Mapping[str, Any] | Iterable[tuple[str, Any]],
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> str:
    """Persist ``reservations`` to the configured ``rezerwacje`` file."""

    path = reservations_file_path(base_dir)
    _ensure_parent(path)
    if isinstance(reservations, Mapping):
        data: Dict[str, Any] = dict(reservations)
    else:
        data = dict(reservations)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return path


def load_states(*, base_dir: str | os.PathLike[str] | None = None) -> Dict[str, Any]:
    """Load and return states dictionary from ``stany.json``."""

    path = states_file_path(base_dir)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def load_reservations(
    *, base_dir: str | os.PathLike[str] | None = None
) -> Dict[str, Any]:
    """Load reservations mapping from ``rezerwacje.json``."""

    path = reservations_file_path(base_dir)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        return {}
    return {}

__all__ = [
    "warehouse_dir",
    "stock_file_path",
    "states_file_path",
    "reservations_file_path",
    "save_states",
    "save_reservations",
    "load_states",
    "load_reservations",
]
