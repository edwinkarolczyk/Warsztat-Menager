from __future__ import annotations

import ntpath
import os
import sys
from typing import Any, Callable, Dict, Optional

try:
    from config_manager import get_path as _config_get_path
except Exception:  # pragma: no cover - optional during bootstrap
    _config_get_path = None

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
    root_cfg = str(_read("paths.data_root") or "").strip()
    if root_cfg:
        if os.name != "nt" and len(root_cfg) >= 2 and root_cfg[1] == ":":
            root = data_path()
        else:
            root = resolve(root_cfg)
    else:
        root = data_path()
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
        "hall.machines_file": os.path.join(root, "maszyny", "maszyny.json"),
        # UWAGA: hall.background_image to zwykle obraz wskazywany ręcznie — brak twardej domyślnej
    }

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
        return resolve(val)
    fallback = _default_paths().get(key, default)
    if isinstance(fallback, str) and fallback.strip():
        return resolve(fallback)
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


def _auto_detect_base_dir() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.abspath(os.path.dirname(sys.argv[0]))
    for candidate in (
        base,
        os.path.abspath(os.path.join(base, os.pardir)),
        os.getcwd(),
    ):
        if os.path.isdir(os.path.join(candidate, "data")):
            return candidate
    return os.getcwd()


def get_base_dir() -> str:
    cfg_raw = (
        str(_config_get_path("paths.base_dir", ""))
        if _config_get_path
        else ""
    ).strip()
    if cfg_raw and os.path.isdir(cfg_raw):
        return os.path.abspath(cfg_raw)
    return _auto_detect_base_dir()


def resolve(path_or_rel: str) -> str:
    if not path_or_rel:
        return path_or_rel
    candidate = os.path.expanduser(str(path_or_rel).strip())
    if not candidate:
        return candidate
    if os.path.isabs(candidate):
        return os.path.abspath(candidate)
    if candidate.startswith("\\\\"):
        return os.path.abspath(candidate.replace("\\", "/"))
    drive, tail = ntpath.splitdrive(candidate)
    if drive:
        if os.name == "nt":
            return os.path.abspath(candidate)
        candidate = tail.lstrip("\\/")
    return os.path.abspath(os.path.join(get_base_dir(), candidate))


def data_path(*parts: str) -> str:
    return os.path.join(get_base_dir(), "data", *parts)


def prefer_config_file(key: str, default_rel: str) -> str:
    value = ""
    if _config_get_path:
        try:
            value = str(_config_get_path(key, "") or "").strip()
        except TypeError:
            value = str(_config_get_path(key) or "").strip()
        except Exception:
            value = ""
    if not value:
        try:
            value = get_path(key, "")
        except Exception:
            value = ""
    if value:
        return resolve(value)
    normalized = default_rel.replace("\\", "/").split("/")
    return data_path(*normalized)
