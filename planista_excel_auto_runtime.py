# WM-VERSION: 0.1
# Plik: planista_excel_auto_runtime.py
# version: 1.1
"""Bezpieczny automat zewnętrznego planu Excel.

Oryginalny plik jest otwierany wyłącznie na czas binarnego skopiowania.
Całe parsowanie odbywa się na krótkotrwałej kopii tymczasowej.
Stan automatu jest przechowywany pod aktywnym WM_ROOT/data/planista.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable, Iterator

from config_manager import ConfigManager


AUTO_STATE_FILE = "excel_auto_state.json"
DEFAULT_INTERVAL_MS = 60_000
DEFAULT_INTERVAL_MINUTES = 1
MIN_INTERVAL_MINUTES = 1
MAX_INTERVAL_MINUTES = 60


def normalize_interval_minutes(value: Any) -> int:
    try:
        minutes = int(str(value).strip())
    except (TypeError, ValueError):
        minutes = DEFAULT_INTERVAL_MINUTES
    return max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, minutes))


def interval_ms(value: Any) -> int:
    return normalize_interval_minutes(value) * 60_000


def _planista_dir() -> Path:
    path = Path(ConfigManager().path_data()) / "planista"
    path.mkdir(parents=True, exist_ok=True)
    return path


def auto_state_path() -> Path:
    return _planista_dir() / AUTO_STATE_FILE


def _default_state() -> dict[str, Any]:
    return {
        "enabled": False,
        "source_path": "",
        "interval_minutes": DEFAULT_INTERVAL_MINUTES,
        "auto_accept": False,
        "auto_print": False,
        "pending_print_order_ids": [],
    }


def load_auto_state() -> dict[str, Any]:
    path = auto_state_path()
    if not path.is_file():
        return _default_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_state()
    if not isinstance(raw, dict):
        return _default_state()

    pending = raw.get("pending_print_order_ids")
    pending = pending if isinstance(pending, list) else []
    pending = list(dict.fromkeys(str(value).strip() for value in pending if str(value).strip()))

    return {
        "enabled": bool(raw.get("enabled")),
        "source_path": str(raw.get("source_path") or "").strip(),
        "interval_minutes": normalize_interval_minutes(raw.get("interval_minutes")),
        "auto_accept": bool(raw.get("auto_accept")),
        "auto_print": bool(raw.get("auto_print")),
        "pending_print_order_ids": pending,
    }


def save_auto_state(
    *,
    enabled: bool | None = None,
    source_path: str | None = None,
    interval_minutes: Any | None = None,
    auto_accept: bool | None = None,
    auto_print: bool | None = None,
    pending_print_order_ids: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Zapisz podane ustawienia, zachowując pozostałe pola istniejącego stanu."""
    state = load_auto_state()
    if enabled is not None:
        state["enabled"] = bool(enabled)
    if source_path is not None:
        state["source_path"] = str(source_path or "").strip()
    if interval_minutes is not None:
        state["interval_minutes"] = normalize_interval_minutes(interval_minutes)
    if auto_accept is not None:
        state["auto_accept"] = bool(auto_accept)
    if auto_print is not None:
        state["auto_print"] = bool(auto_print)
    if pending_print_order_ids is not None:
        state["pending_print_order_ids"] = list(
            dict.fromkeys(
                str(value).strip()
                for value in pending_print_order_ids
                if str(value).strip()
            )
        )

    path = auto_state_path()
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)
    return state


@contextmanager
def detached_excel_copy(source: str | Path) -> Iterator[Path]:
    """Skopiuj źródło, zamknij je i udostępnij parserowi wyłącznie kopię."""
    source_path = Path(source).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(f"Nie znaleziono pliku Excel: {source_path}")

    fd, temp_name = tempfile.mkstemp(
        prefix="WM_plan_excel_",
        suffix=source_path.suffix or ".xlsx",
    )
    os.close(fd)
    temp_path = Path(temp_name)

    try:
        # Uchwyt do oryginału istnieje tylko podczas kopiowania bajtów.
        with source_path.open("rb") as source_file, temp_path.open("wb") as temp_file:
            shutil.copyfileobj(source_file, temp_file, length=1024 * 1024)
            temp_file.flush()
        yield temp_path
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def parse_from_detached_copy(
    source: str | Path,
    parser: Callable[[Path], Any],
) -> Any:
    """Uruchom parser dopiero po zamknięciu oryginalnego pliku."""
    with detached_excel_copy(source) as copy_path:
        return parser(copy_path)
