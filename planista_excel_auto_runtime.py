# WM-VERSION: 0.1
# Plik: planista_excel_auto_runtime.py
# version: 1.0
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


def _planista_dir() -> Path:
    path = Path(ConfigManager().path_data()) / "planista"
    path.mkdir(parents=True, exist_ok=True)
    return path


def auto_state_path() -> Path:
    return _planista_dir() / AUTO_STATE_FILE


def load_auto_state() -> dict[str, Any]:
    path = auto_state_path()
    if not path.is_file():
        return {"enabled": False, "source_path": ""}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"enabled": False, "source_path": ""}
    if not isinstance(raw, dict):
        return {"enabled": False, "source_path": ""}
    return {
        "enabled": bool(raw.get("enabled")),
        "source_path": str(raw.get("source_path") or "").strip(),
    }


def save_auto_state(*, enabled: bool, source_path: str) -> dict[str, Any]:
    state = {
        "enabled": bool(enabled),
        "source_path": str(source_path or "").strip(),
    }
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
