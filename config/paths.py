# version: 1.0
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.path_utils import get_app_root as _resolve_app_root
try:
    from core import root_paths as _root_paths
except Exception:  # pragma: no cover - fallback na starszy start
    _root_paths = None


def get_app_root() -> Path:
    """
    Zwraca katalog główny aplikacji.
    Logika jest scentralizowana w core.path_utils.get_app_root().
    """

    if _root_paths is not None:
        return _root_paths.get_app_root()
    return _resolve_app_root()


def get_data_root(cfg: Optional[Dict[str, Any]]) -> Path:
    """Resolve data root using config dictionary or environment override."""

    env_root = os.getenv("WM_DATA_ROOT")
    if env_root:
        return Path(env_root)
    if _root_paths is not None:
        return _root_paths.get_data_root()

    cfg = cfg or {}
    paths = cfg.get("paths") or {}
    system = cfg.get("system") or {}
    value = paths.get("data_root") or system.get("data_root")
    if isinstance(value, str) and value.strip():
        return Path(_expand_path(value.strip()))
    return Path(_data_root())


def get_logs_dir(cfg: Optional[Dict[str, Any]]) -> Path:
    """Resolve logs directory using config dictionary."""

    cfg = cfg or {}
    paths = cfg.get("paths") or {}
    value = paths.get("logs_dir") or os.path.join(_anchor_root(), "logs")
    return Path(_expand_path(str(value)))


def get_backup_dir(cfg: Optional[Dict[str, Any]]) -> Path:
    """Resolve backup directory using config dictionary."""

    cfg = cfg or {}
    paths = cfg.get("paths") or {}
    system = cfg.get("system") or {}
    value = (
        paths.get("backup_dir")
        or system.get("backup_root")
        or os.path.join(_anchor_root(), "backup")
    )
    return Path(_expand_path(str(value)))

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

_DEFAULT_BASE_DIR = get_app_root()
if _root_paths is not None:
    _DEFAULT_ANCHOR = os.path.normpath(str(_root_paths.get_root_anchor()))
else:
    _DEFAULT_ANCHOR = os.path.normpath(str(_DEFAULT_BASE_DIR))


def _is_abs(path: str) -> bool:
    return (
        os.path.isabs(path)
        or path.startswith("\\\\")
        or (len(path) > 1 and path[1] == ":")
    )


def _raw_anchor_value() -> str:
    anchor = _read("paths.anchor_root")
    if isinstance(anchor, str) and anchor.strip():
        return anchor.strip()
    data_raw = _read("paths.data_root")
    if isinstance(data_raw, str) and data_raw.strip():
        candidate = data_raw.strip()
        try:
            norm_candidate = os.path.normpath(candidate)
        except Exception:
            norm_candidate = candidate
        if os.path.basename(norm_candidate).lower() == "data":
            return os.path.dirname(norm_candidate)
        return norm_candidate
    if _root_paths is not None:
        return str(_root_paths.get_root_anchor())
    return _DEFAULT_ANCHOR


def _anchor_root() -> str:
    raw = _raw_anchor_value()
    if "<root>" in raw:
        raw = raw.replace("<root>", _DEFAULT_ANCHOR)
    try:
        expanded = os.path.expanduser(raw)
    except Exception:
        expanded = raw
    if _is_abs(expanded):
        return os.path.normpath(expanded)
    return os.path.normpath(os.path.join(_DEFAULT_ANCHOR, expanded))


def _expand_path(value: str, anchor: Optional[str] = None) -> str:
    if not isinstance(value, str):
        return value
    anchor_root = anchor or _anchor_root()
    candidate = value.replace("<root>", anchor_root)
    try:
        expanded = os.path.expanduser(candidate)
    except Exception:
        expanded = candidate
    if _is_abs(expanded):
        return os.path.normpath(expanded)
    return os.path.normpath(os.path.join(anchor_root, expanded))


def _data_root() -> str:
    data_raw = _read("paths.data_root")
    if isinstance(data_raw, str) and data_raw.strip():
        return _expand_path(data_raw.strip())
    if _root_paths is not None:
        return str(_root_paths.get_data_root())
    return os.path.join(_anchor_root(), "data")

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
    data_base = _data_root()
    anchor = _anchor_root()
    return {
        "paths.data_root": data_base,
        "paths.logs_dir": os.path.join(anchor, "logs"),
        "paths.backup_dir": os.path.join(anchor, "backup"),
        "paths.assets_dir": os.path.join(anchor, "assets"),
        "paths.layout_dir": os.path.join(data_base, "layout"),
        "paths.warehouse_dir": os.path.join(data_base, "magazyn"),
        "paths.products_dir": os.path.join(data_base, "produkty"),
        "paths.tools_dir": os.path.join(data_base, "narzedzia"),
        "paths.orders_dir": os.path.join(data_base, "zlecenia"),

        # Pliki:
        "warehouse.stock_source": os.path.join(data_base, "magazyn", "magazyn.json"),
        "warehouse.reservations_file": os.path.join(
            data_base, "magazyn", "rezerwacje.json"
        ),
        "bom.file": os.path.join(data_base, "produkty", "bom.json"),
        "tools.types_file": os.path.join(data_base, "narzedzia", "typy_narzedzi.json"),
        "tools.statuses_file": os.path.join(
            data_base, "narzedzia", "statusy_narzedzi.json"
        ),
        "tools.task_templates_file": os.path.join(
            data_base, "narzedzia", "szablony_zadan.json"
        ),
        "hall.machines_file": os.path.join(data_base, "layout", "maszyny.json"),
        # UWAGA: hall.background_image to zwykle obraz wskazywany ręcznie — brak twardej domyślnej
    }


def _read_base_dir() -> Path:
    base = _read("paths.base_dir")
    if isinstance(base, str) and base.strip():
        try:
            return Path(_expand_path(base.strip())).expanduser().resolve()
        except Exception:
            return Path(_expand_path(base.strip())).expanduser()
    return Path(_anchor_root())

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
        return _expand_path(val.strip())
    fallback = _default_paths().get(key, default)
    if isinstance(fallback, str):
        return _expand_path(fallback)
    if fallback is not None:
        return str(fallback)
    return ""

def join_path(key: str, *rest: str) -> str:
    """Buduje ścieżkę wzg. wartości klucza (np. join_path('paths.orders_dir','2025','ZZ001.json'))."""
    base = get_path(key)
    return os.path.join(base, *rest) if base else os.path.join(*rest)

def ensure_core_tree() -> None:
    """Tworzy podstawowe katalogi (logs/backup/assets/produkty/magazyn/narzedzia/layout/zlecenia)."""
    defaults = _default_paths()
    dirs = [
        "paths.logs_dir",
        "paths.backup_dir",
        "paths.assets_dir",
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

    base = Path(_data_root())
    return str(base.joinpath(*parts))


def _as_path(value: Any) -> Path:
    path = value if isinstance(value, Path) else Path(str(value))
    try:
        return path.expanduser().resolve()
    except Exception:
        return path.expanduser()


def _call_accessor(cfg: Any, *names: str) -> Any:
    for name in names:
        attr = getattr(cfg, name, None)
        if attr is None:
            continue
        if callable(attr):
            try:
                result = attr()
            except TypeError:
                result = attr
        else:
            result = attr
        if result is not None:
            return result
    raise AttributeError(f"Brak accessorów {names} w obiekcie {type(cfg)!r}")


def _project_root(cfg: Any) -> Path:
    try:
        return _as_path(_call_accessor(cfg, "project_root"))
    except AttributeError:
        return _as_path(p_config(cfg).parent)


def _D(cfg: Any) -> Path:
    return _as_path(_call_accessor(cfg, "path_data"))


def p_config(cfg: Any) -> Path:
    return _as_path(
        _call_accessor(cfg, "path_config", "config_path", "get_config_path")
    )


def p_settings_schema(cfg: Any) -> Path:
    if hasattr(cfg, "path_settings_schema"):
        try:
            return _as_path(_call_accessor(cfg, "path_settings_schema"))
        except AttributeError:
            pass
    return _project_root(cfg) / "settings_schema.json"


def p_profiles(cfg: Any) -> Path:
    return _D(cfg) / "profiles.json"


def p_users(cfg: Any) -> Path:
    return _D(cfg) / "uzytkownicy.json"


def p_assign_orders(cfg: Any) -> Path:
    return _D(cfg) / "assign_orders.json"


def p_assign_tools(cfg: Any) -> Path:
    return _D(cfg) / "assign_tools.json"


def p_presence(cfg: Any) -> Path:
    return _D(cfg) / "presence.json"


def p_tools_defs(cfg: Any) -> Path:
    try:
        base = _D(cfg)
    except Exception:
        try:
            cfg_dict = cfg if isinstance(cfg, dict) else None
            base = get_data_root(cfg_dict)
        except Exception:
            base = get_data_root(None)
        return Path(base) / "zadania_narzedzia.json"
    return base / "zadania_narzedzia.json"


def p_tools_types(cfg: Any) -> Path:
    return _D(cfg) / "narzedzia" / "typy_narzedzi.json"


def p_tools_statuses(cfg: Any) -> Path:
    return _D(cfg) / "narzedzia" / "statusy_narzedzi.json"


def p_tools_templates(cfg: Any) -> Path:
    return _D(cfg) / "narzedzia" / "szablony_zadan.json"


def p_tools_data(cfg: Any) -> Path:
    return _D(cfg) / "narzedzia.json"


def p_manifest_moduly(cfg: Any) -> Path:
    return _D(cfg) / "moduly_manifest.json"
