from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# -----------------------------------------------------------------------------
#  Centralny helper ścieżek:
#   - bind_settings(state)  -> zbindowanie referencji do słownika ustawień
#   - set_getter(fn)        -> albo dostawca ustawień (fn: key -> value)
#   - get_path(key, default)-> odczyt ścieżki z ustawień + fallback do domyślnej
#   - join_path(key, *rest) -> dobudowanie ścieżki wzgl. wartości klucza
#   - ensure_core_tree()    -> tworzy standardowe podkatalogi w data_root
# -----------------------------------------------------------------------------

_SETTINGS_STATE: Optional[Dict[str, Any]] = None
_SETTINGS_GETTER: Optional[Callable[[str], Any]] = None

_DEFAULT_BASE_DIR = Path(__file__).resolve().parent.parent

def bind_settings(state: Dict[str, Any]) -> None:
    """Zbindowanie referencji do słownika ustawień (np. tego samego, który
    modyfikuje UI Ustawień)."""
    global _SETTINGS_STATE, _SETTINGS_GETTER
    _SETTINGS_STATE = state
    _SETTINGS_GETTER = None

def set_getter(getter: Callable[[str], Any]) -> None:
    """Alternatywnie: ustaw funkcję pobierającą ustawienia (gdy nie masz
    bezpośredniej referencji do słownika)."""
    global _SETTINGS_STATE, _SETTINGS_GETTER
    _SETTINGS_STATE = None
    _SETTINGS_GETTER = getter

# --- domyślne wartości (zależne od data_root) --------------------------------

def _default_paths() -> Dict[str, str]:
    root = _read("paths.data_root") or r"C:\wm\data"
    return {
        "paths.data_root": root,
        "paths.logs_dir": os.path.join(root, "logs"),
        "paths.backup_dir": os.path.join(root, "backup"),
        "paths.layout_dir": os.path.join(root, "layout"),
        "paths.warehouse_dir": os.path.join(root, "magazyn"),
        "paths.products_dir": os.path.join(root, "produkty"),
        "paths.tools_dir": os.path.join(root, "narzedzia"),
        "paths.orders_dir": os.path.join(root, "zlecenia"),

        # Pliki:
        "warehouse.stock_source": os.path.join(root, "magazyn", "magazyn.json"),
        "warehouse.reservations_file": os.path.join(root, "magazyn", "rezerwacje.json"),
        "bom.file": os.path.join(root, "produkty", "bom.json"),
        "tools.types_file": os.path.join(root, "narzedzia", "typy_narzedzi.json"),
        "tools.statuses_file": os.path.join(root, "narzedzia", "statusy_narzedzi.json"),
        "tools.task_templates_file": os.path.join(root, "narzedzia", "szablony_zadan.json"),
        "hall.machines_file": os.path.join(root, "layout", "maszyny.json"),
        # UWAGA: hall.background_image to zwykle obraz wskazywany ręcznie — brak twardej domyślnej
    }


def _read_base_dir() -> Path:
    base = _read("paths.base_dir")
    if isinstance(base, str) and base.strip():
        try:
            return Path(base).expanduser().resolve()
        except Exception:
            return Path(base).expanduser()
    data_root = _read("paths.data_root")
    if isinstance(data_root, str) and data_root.strip():
        try:
            return Path(data_root).expanduser().resolve().parent
        except Exception:
            return Path(data_root).expanduser().parent
    return _DEFAULT_BASE_DIR

def _read(key: str) -> Any:
    if _SETTINGS_GETTER:
        try:
            return _SETTINGS_GETTER(key)
        except Exception:
            return None
    if _SETTINGS_STATE is not None:
        return _SETTINGS_STATE.get(key)
    return None

# --- API publiczne ------------------------------------------------------------

def get_path(key: str, default: Optional[str] = None) -> str:
    """Zwraca ścieżkę z ustawień. Jeśli brak – oddaje sensowny fallback z _default_paths()."""
    val = _read(key)
    if isinstance(val, str) and val.strip():
        return val
    fallback = _default_paths().get(key, default)
    return str(fallback) if fallback is not None else ""

def join_path(key: str, *rest: str) -> str:
    """Buduje ścieżkę wzg. wartości klucza (np. join_path('paths.orders_dir','2025','ZZ001.json'))."""
    base = get_path(key)
    return os.path.join(base, *rest) if base else os.path.join(*rest)

def ensure_core_tree() -> None:
    """Tworzy podstawowe katalogi (logs/backup/produkty/magazyn/narzedzia/layout/zlecenia) w data_root."""
    defaults = _default_paths()
    dirs = [
        "paths.logs_dir",
        "paths.backup_dir",
        "paths.products_dir",
        "paths.warehouse_dir",
        "paths.tools_dir",
        "paths.layout_dir",
        "paths.orders_dir",
    ]
    for dkey in dirs:
        try:
            os.makedirs(defaults[dkey], exist_ok=True)
        except Exception:
            pass


def get_base_dir() -> str:
    """Zwraca katalog bazowy WM (folder root aplikacji)."""

    return str(_read_base_dir())


def resolve(*parts: str) -> str:
    """Buduje ścieżkę względem katalogu bazowego WM."""

    base = _read_base_dir()
    return str(base.joinpath(*parts))


def data_path(*parts: str) -> str:
    """Buduje ścieżkę w katalogu ``data`` względem folderu WM."""

    base = _read_base_dir()
    return str(base.joinpath("data", *parts))
