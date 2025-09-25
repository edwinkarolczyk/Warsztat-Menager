"""Utilities for resolving application paths from configuration settings."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Optional
import os

from utils.path_utils import cfg_path

# Application root (directory with config.json)
_APP_ROOT = Path(cfg_path("")).resolve()
_DEFAULT_DATA_ROOT = (_APP_ROOT / "data").resolve()

# Globals mutated via ``bind_settings``
_STATE: MutableMapping[str, Any] | None = None
_DATA_ROOT: Path | None = None
_FALLBACK_DATA_ROOT: Path | None = None

# Cache for already resolved keys to avoid repeated normalization
_CACHE: dict[str, Path] = {}

# Known prefixes that may need trimming when normalising Windows styled paths.
# Each tuple is (name, keep_after_match). When keep_after_match is False the
# prefix is removed entirely, otherwise the matching segment is kept.
_KNOWN_PREFIXES: tuple[tuple[str, bool], ...] = (
    ("warsztat-menager", False),
    ("warsztat manager", False),
    ("warsztat", False),
    ("wm", False),
    ("data", True),
    ("logi", True),
    ("logs", True),
    ("backup_wersji", True),
    ("backup", True),
    ("layout", True),
    ("magazyn", True),
    ("produkty", True),
    ("polprodukty", True),
    ("narzedzia", True),
    ("tools", True),
    ("zamowienia", True),
    ("zlecenia", True),
    ("orders", True),
    ("profiles", True),
)

# Keys treated as directories that should be auto-created by ``ensure_core_tree``.
_CORE_DIR_KEYS: tuple[str, ...] = (
    "paths.data_root",
    "paths.logs_dir",
    "paths.backup_dir",
    "paths.layout_dir",
    "paths.warehouse_dir",
    "paths.products_dir",
    "paths.tools_dir",
    "paths.orders_dir",
)

# Keys that point to files – their parent directories are ensured.
_FILE_PARENT_KEYS: tuple[str, ...] = (
    "warehouse.stock_source",
    "warehouse.reservations_file",
    "bom.file",
    "hall.machines_file",
    "tools.types_file",
)


def bind_settings(settings_state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Bind settings mapping used to resolve paths."""

    if not isinstance(settings_state, MutableMapping):
        raise TypeError("settings_state must be a mutable mapping")

    global _STATE, _DATA_ROOT, _CACHE
    _STATE = settings_state
    _CACHE = {}
    _DATA_ROOT = _compute_data_root()
    return settings_state


def ensure_core_tree() -> None:
    """Ensure directories used by the application exist."""

    for key in _CORE_DIR_KEYS:
        path = get_path(key, default=None)
        if path:
            Path(path).mkdir(parents=True, exist_ok=True)

    for key in _FILE_PARENT_KEYS:
        path = get_path(key, default=None)
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)


_MISSING = object()


def get_path(key: str, default: Optional[str] = _MISSING) -> Optional[str]:
    """Return resolved absolute path for the configuration *key*.

    When *default* is provided and the key is unset, ``default`` is returned.
    """

    if not key:
        raise ValueError("Key must be a non-empty string")

    if key in _CACHE:
        return str(_CACHE[key])

    value = _lookup(key)
    if value in (None, ""):
        if default is not _MISSING:
            return default
        raise KeyError(f"Missing value for setting: {key}")

    path = _normalise_path(key, value)
    _CACHE[key] = path
    return str(path)


def join_path(base_key: str, *additional: str) -> str:
    """Join *additional* segments onto path resolved from *base_key*."""

    base = Path(get_path(base_key))
    return str(base.joinpath(*additional))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _lookup(key: str) -> Any:
    if _STATE is not None:
        if key in _STATE:
            return _STATE[key]
        current: Any = _STATE
        for part in key.split('.'):
            if isinstance(current, Mapping) and part in current:
                current = current[part]
            else:
                break
        else:
            return current

    try:
        from config_manager import ConfigManager

        cfg = ConfigManager()
        return cfg.get(key)
    except Exception:
        return None


def _compute_data_root() -> Path:
    value = _lookup("paths.data_root")
    if value in (None, ""):
        return _DEFAULT_DATA_ROOT
    return _ensure_path("paths.data_root", value, base=_APP_ROOT, drop_first_anchor=False)


def _data_root() -> Path:
    global _DATA_ROOT, _FALLBACK_DATA_ROOT
    if _STATE is not None:
        if _DATA_ROOT is None:
            _DATA_ROOT = _compute_data_root()
        return _DATA_ROOT

    if _FALLBACK_DATA_ROOT is None:
        value = _lookup("paths.data_root")
        if value in (None, ""):
            _FALLBACK_DATA_ROOT = _DEFAULT_DATA_ROOT
        else:
            _FALLBACK_DATA_ROOT = _ensure_path(
                "paths.data_root", value, base=_APP_ROOT, drop_first_anchor=False
            )
    return _FALLBACK_DATA_ROOT


def _normalise_path(key: str, value: Any) -> Path:
    base = _base_for_key(key)
    return _ensure_path(key, value, base=base)


def _base_for_key(key: str) -> Path:
    if key == "paths.data_root":
        return _APP_ROOT

    prefix = key.split('.', 1)[0]
    if prefix == "paths":
        return _data_root()
    if prefix in {"warehouse", "bom", "tools", "hall", "orders", "profiles"}:
        return _data_root()
    return _APP_ROOT


def _ensure_path(
    key: str,
    value: Any,
    *,
    base: Optional[Path],
    drop_first_anchor: bool = False,
) -> Path:
    text = _stringify(value)
    if text is None:
        raise KeyError(f"Missing value for setting: {key}")

    text = os.path.expanduser(os.path.expandvars(text)).strip()
    if not text:
        raise KeyError(f"Missing value for setting: {key}")

    if _is_posix_absolute(text):
        return Path(text).resolve()

    if _is_windows_absolute(text):
        if not _should_rebase_windows(text):
            return Path(text)
        parts = _split_windows_parts(text)
        parts = _trim_known_prefixes(parts, drop_first_anchor or _is_data_base(base))
        base = base or _APP_ROOT
        if not parts:
            return base.resolve()
        return (base.joinpath(*parts)).resolve()

    rel_path = Path(text)
    if rel_path.is_absolute():
        return rel_path.resolve()

    if drop_first_anchor and rel_path.parts and rel_path.parts[0].lower() == "data":
        rel_path = Path(*rel_path.parts[1:])
    elif _is_data_base(base) and rel_path.parts and rel_path.parts[0].lower() == "data":
        rel_path = Path(*rel_path.parts[1:])

    base = base or _APP_ROOT
    return (base / rel_path).resolve()


def _stringify(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (str, Path)):
        return str(value)
    return str(value)


def _is_posix_absolute(text: str) -> bool:
    return Path(text).is_absolute()


def _is_windows_absolute(text: str) -> bool:
    text = text.replace("\\", "/")
    return len(text) >= 3 and text[1] == ":" and text[2] == "/"


def _should_rebase_windows(text: str) -> bool:
    lowered = text.lower().replace("\\", "/")
    return (
        lowered.startswith("c:/wm/")
        or "warsztat-menager" in lowered
        or lowered.startswith("c:/warsztat/")
    )


def _split_windows_parts(text: str) -> list[str]:
    normalised = text.replace("\\", "/")
    rest = normalised[2:]
    rest = rest.lstrip("/")
    parts = [p for p in rest.split("/") if p]
    return parts


def _trim_known_prefixes(parts: Iterable[str], drop_data: bool) -> list[str]:
    result = list(parts)
    lower = [p.lower() for p in result]
    for name, keep in _KNOWN_PREFIXES:
        if name in lower:
            idx = lower.index(name)
            if keep:
                result = result[idx:]
            else:
                result = result[idx + 1 :]
            lower = [p.lower() for p in result]
            break
    if drop_data and result and result[0].lower() == "data":
        result = result[1:]
    return result


def _is_data_base(base: Optional[Path]) -> bool:
    if base is None:
        return False
    try:
        return base.resolve() == _data_root().resolve()
    except Exception:
        return False
