# version: 1.0
"""
Config Manager – warstwy: defaults → global → local → secrets
Wersja: 1.0.2

Funkcje:
- Ładowanie i scalanie warstw configu
- Walidacja wg settings_schema.json
- Zapis z backupem i audytem zmian
- Import/eksport (eksport bez sekretów)
- Rollback przez katalogi w backup (utrzymujemy ostatnie 10)
"""

# Sekcje config:
# - general: nazwa_warsztatu, language, domyślne moduły startowe
# - paths: data_root, logs_dir, backup_dir, assets_dir
# - backup: keep_last, auto_on_exit
# - ui: theme, font_size, language, debug_enabled
# - jarvis: enabled, allow_ai, auto_interval_sec, notify.refresh_ms
# - modules: konfiguracje poszczególnych modułów (service, warehouse, tools…)
# - hall: ustawienia layoutu hali i siatki
# - local: fullscreen_on_start, ui_scale
# - profiles: konfiguracja pól profili użytkowników

from __future__ import annotations

import datetime
import inspect
import json
import logging
import os
import ntpath
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from core.bootstrap import bootstrap_paths
from core.path_utils import resolve_root_path
from core import root_paths as wm_root_paths
from utils.path_utils import cfg_path

log = logging.getLogger(__name__)


def _wm_root_env_active() -> bool:
    """Czy centralny ROOT jest już ustawiony w runtime."""

    return bool(
        os.environ.get("WM_ROOT")
        or os.environ.get("WM_DATA_ROOT")
        or os.environ.get("WM_CONFIG_FILE")
    )


def _force_runtime_root_into_env() -> None:
    """Ujednolica ENV na podstawie core.root_paths, bez pytania użytkownika."""

    try:
        if not os.environ.get("WM_ROOT"):
            os.environ["WM_ROOT"] = str(wm_root_paths.get_root_anchor())
        if not os.environ.get("WM_DATA_ROOT"):
            os.environ["WM_DATA_ROOT"] = str(wm_root_paths.get_data_root())
        if not os.environ.get("WM_CONFIG_FILE"):
            os.environ["WM_CONFIG_FILE"] = str(wm_root_paths.path_config())
    except Exception:
        pass


def _runtime_root() -> str | None:
    _force_runtime_root_into_env()
    env_root = os.environ.get("WM_ROOT")
    if env_root:
        return _norm(env_root)
    try:
        return _norm(str(wm_root_paths.get_root_anchor()))
    except Exception:
        return None


def _runtime_data_root() -> str | None:
    _force_runtime_root_into_env()
    env_data = os.environ.get("WM_DATA_ROOT")
    if env_data:
        return _norm(env_data)
    root = _runtime_root()
    return _norm(os.path.join(root, "data")) if root else None


def _runtime_config_file() -> str | None:
    _force_runtime_root_into_env()
    env_cfg = os.environ.get("WM_CONFIG_FILE")
    if env_cfg:
        return _norm(env_cfg)
    root = _runtime_root()
    return _norm(os.path.join(root, "config.json")) if root else None


def _wm_root_anchor() -> str | None:
    """Zwraca aktywny WM_ROOT, jeśli centralny resolver jest dostępny."""

    env_root = os.environ.get("WM_ROOT")
    if env_root:
        return _norm(env_root)
    if _wm_root_env_active():
        return _runtime_root()
    return None


def _wm_data_root() -> str | None:
    env_data = os.environ.get("WM_DATA_ROOT")
    if env_data:
        return _norm(env_data)
    if _wm_root_env_active():
        return _runtime_data_root()
    return None


def _wm_config_file() -> str | None:
    env_cfg = os.environ.get("WM_CONFIG_FILE")
    if env_cfg:
        return _norm(env_cfg)
    if _wm_root_env_active():
        return _runtime_config_file()
    return None


# --- R-ROOT-ALL: centralny dostęp do katalogu danych ---
_DEFAULT_ROOT = _wm_root_anchor() or os.path.normcase(
    os.path.abspath(os.path.normpath(os.path.join(os.getcwd(), "data", "..")))
)
_MAP: dict[str, tuple[str, ...]] = {
    # MODUŁY DANYCH
    "machines": ("data", "maszyny", "maszyny.json"),
    "tools_index": ("data", "narzedzia", "narzedzia.json"),
    "tools_item_dir": ("data", "narzedzia"),
    "warehouse_stock": ("data", "magazyn", "magazyn.json"),
    "bom": ("data", "produkty", "bom.json"),
    "orders": ("data", "zlecenia", "zlecenia.json"),
    "tools_defs": ("data", "narzedzia", "szablony_zadan.json"),
    # UI / MEDIA
    "machines_bg": ("assets", "hala_bg.png"),
    # INNE
    "profiles": ("data", "profiles.json"),
    "audit_log_dir": ("logs",),
}

# zachowujemy dotychczasową nazwę mapy dla kompatybilności
_RROOT_MAP: dict[str, tuple[str, ...]] = _MAP

# Standardowa mapa plików relatywnych (względem paths.data_root)
PATH_MAP = {
    "machines": "maszyny/maszyny.json",
    "warehouse": "magazyn/magazyn.json",
    "bom": "produkty/bom.json",
    "tools.dir": "narzedzia",
    "tools.types": "narzedzia/typy_narzedzi.json",
    "tools.statuses": "narzedzia/statusy_narzedzi.json",
    "tools.tasks": "narzedzia/szablony_zadan.json",
    "tools.zadania": "narzedzia/szablony_zadan.json",
    "orders": "zlecenia/zlecenia.json",
    "root.logs": "logs",
    "root.backup": "backup",
    "data.profiles": "profiles.json",
}

RESOLVE_MAP = {
    "machines": ("maszyny", "maszyny.json"),
    "warehouse": ("magazyn", "magazyn.json"),
    "warehouse_stock": ("magazyn", "magazyn.json"),
    "bom": ("produkty", "bom.json"),
    "tools": ("narzedzia", "narzedzia.json"),
    "tools.dir": ("narzedzia", ""),
    "tools_dir": ("narzedzia", ""),
    "tools_defs": ("narzedzia", "szablony_zadan.json"),
    "tools.types": ("narzedzia", "typy_narzedzi.json"),
    "tools.statuses": ("narzedzia", "statusy_narzedzi.json"),
    "tools.tasks": ("narzedzia", "szablony_zadan.json"),
    "tools_templates": ("narzedzia", "szablony_zadan.json"),
    "tools_types": ("narzedzia", "typy_narzedzi.json"),
    "tools_statuses": ("narzedzia", "statusy_narzedzi.json"),
    "orders": ("zlecenia", "zlecenia.json"),
    "orders_dir": ("zlecenia", ""),
    "tools.zadania": ("narzedzia", "szablony_zadan.json"),
    "profiles": ("", "profiles.json"),
}

RELATIVE_ALIAS_KEYS = {
    "tools": "tools_dir",
    "tools.dir": "tools_dir",
    "tools_defs": "tools_defs",
    "tools.types": "tools_defs",
    "tools.statuses": "tools_defs",
    "tools.tasks": "tools_defs",
    "tools_templates": "tools_defs",
    "tools_types": "tools_defs",
    "tools_statuses": "tools_defs",
    "orders": "orders_dir",
    "warehouse": "warehouse",
    "warehouse_stock": "warehouse",
}

DEFAULTS = {
    "paths": {
        "anchor_root": _DEFAULT_ROOT,
        "data_root": _wm_data_root() or os.path.join(_DEFAULT_ROOT, "data"),
        "logs_dir": os.path.join(_DEFAULT_ROOT, "logs"),
        "backup_dir": os.path.join(_DEFAULT_ROOT, "backup"),
        "assets_dir": os.path.join(_DEFAULT_ROOT, "assets"),
        "layout_dir": os.path.join(_DEFAULT_ROOT, "data", "layout"),
    },
    "relative": {
        "machines": "maszyny/maszyny.json",
        "tools_dir": "narzedzia",
        "orders_dir": "zlecenia",
        "warehouse": "magazyn/magazyn.json",
        "profiles": "profiles.json",
        "bom": "produkty/bom.json",
        "tools_defs": "narzedzia",
    },
}

SETTING_ALIASES = {
    "system.theme": "ui.theme",
    "system.language": "ui.language",
    "system.start_on_dashboard": "ui.start_on_dashboard",
    "system.auto_check_updates": "ui.auto_check_updates",
    "system.debug_enabled": "ui.debug_enabled",
    "system.log_level": "ui.log_level",
    "paths.assets_user": "paths.assets_dir",
}

_ALIAS_REVERSE = {target: source for source, target in SETTING_ALIASES.items()}


def get_machines_path(cfg: dict | None = None) -> str:
    """Return the canonical absolute path to the machines data file."""

    cfg = cfg or {}
    data = _wm_data_root()
    if data:
        return _norm(os.path.join(data, "maszyny", "maszyny.json"))
    path = resolve_rel(cfg, "machines")
    if path:
        return _norm(path)
    return _norm(os.path.join(get_root(cfg), "data", "maszyny", "maszyny.json"))


def get_profiles_path(cfg: dict | None = None) -> str:
    """Return the canonical absolute path to the profiles JSON file."""

    cfg = cfg or {}
    data = _wm_data_root()
    if data:
        return _norm(os.path.join(data, "profiles.json"))
    path = resolve_rel(cfg, "profiles")
    if path:
        return _norm(path)
    return _norm(os.path.join(get_root(cfg), "data", "profiles.json"))


def _norm(path: str) -> str:
    if not path:
        return ""
    normalized = os.path.normpath(path)
    if _is_absolute_path(normalized) or os.path.isabs(normalized):
        return os.path.normcase(normalized)
    return os.path.normcase(os.path.abspath(normalized))


def _looks_like_windows_path(path: str) -> bool:
    if not path:
        return False
    normalized = path.replace("\\", "/")
    head = normalized.split("/", 1)[0]
    if len(head) == 2 and head[1] == ":" and head[0].isalpha():
        return True
    return normalized.startswith("//")


def _safe_makedirs(path: Path | str | None) -> None:
    if not path:
        return
    path_str = str(path)
    if not path_str.strip():
        return
    if path_str.endswith(":"):
        logger.debug(
            "[WM-DBG][CFG] refusing to mkdir on drive-only path: %s", path_str
        )
        return
    if os.name != "nt" and _looks_like_windows_path(path_str):
        return
    try:
        os.makedirs(path_str, exist_ok=True)
    except FileExistsError:
        pass


def _normalize_user_path(path_str: str) -> Path:
    """
    Normalizuje ścieżki pochodzące z ustawień.

    - jeśli ma drive (np. ``C:`` albo ``C:\\smth``) → traktuj jako absolutną,
    - jeśli jest względna → doklej do ``_DEFAULT_ROOT``,
    - odrzuca wpisy typu ``C:`` (sam dysk, bez katalogu).
    """

    trimmed = str(path_str or "").strip()
    base_root = Path(_DEFAULT_ROOT)
    candidate = Path(trimmed) if trimmed else base_root
    if candidate.drive and candidate.root == "":
        logger.debug("[WM-DBG][CFG] invalid path (drive only): %s", path_str)
        raise ValueError(f"Nieprawidłowa ścieżka: {path_str}")
    if candidate.is_absolute():
        return candidate.expanduser().resolve()
    return (base_root / candidate).expanduser().resolve()


def _is_absolute_path(path: str) -> bool:
    """Return ``True`` when ``path`` points to an absolute location."""

    if not path:
        return False
    if os.path.isabs(path):
        return True
    if path.startswith("\\\\"):
        return True
    if len(path) > 1 and path[1] == ":":
        return True
    return False


def _absolute_with_root(path: str | None, root: str) -> str:
    base = _norm(root)
    if not path:
        return base
    resolved = resolve_root_path(base, str(path))
    return _norm(resolved)


def get_root(cfg: dict | None = None) -> str:
    cfg = cfg or {}
    forced_root = _wm_root_anchor()
    # WM_ROOT / core.root_paths jest nadrzędną prawdą runtime.
    # Stare wpisy paths.anchor_root / paths.data_root z configu nie mogą
    # nadpisywać folderu wybranego przez użytkownika.
    if forced_root:
        return _norm(forced_root)
    paths = cfg.get("paths") or {}

    try:
        raw_anchor = paths.get("anchor_root")
        anchor_candidate: str | None = None
        if isinstance(raw_anchor, str) and raw_anchor.strip():
            anchor_candidate = raw_anchor.strip()

        raw = paths.get("data_root") or cfg.get("data_root") or _DEFAULT_ROOT
        if isinstance(raw, str) and raw.strip():
            data_candidate = raw.strip()
            placeholder_base = anchor_candidate or _DEFAULT_ROOT
            if "<root>" in data_candidate:
                data_candidate = data_candidate.replace("<root>", placeholder_base)
            data_norm = _norm(data_candidate)

            anchor_value = anchor_candidate or data_norm
            if not anchor_candidate and os.path.basename(data_norm).lower() == "data":
                anchor_value = os.path.dirname(data_norm)
            if isinstance(anchor_value, str) and "<root>" in anchor_value:
                anchor_value = anchor_value.replace("<root>", _DEFAULT_ROOT)
            return _norm(anchor_value)
    except Exception:
        pass
    return _norm(_DEFAULT_ROOT)


def _machines_rel_value(cfg: dict) -> str:
    """Return stripped machines relative path supporting both legacy keys."""

    machines = cfg.get("machines") or {}
    rel = machines.get("rel_path") or machines.get("relative_path") or ""
    return rel.strip() if isinstance(rel, str) else ""


def _set_machines_rel(cfg: dict, value: str) -> None:
    """Store machines relative path under the canonical key."""

    machines = cfg.setdefault("machines", {})
    machines["rel_path"] = value
    if "relative_path" in machines:
        machines.pop("relative_path", None)


def _resolve_rel_legacy(cfg: dict, what: str) -> str | None:
    """Zwróć ścieżkę absolutną względem ``paths.data_root`` lub wpisu w ``paths``."""

    cfg = cfg or {}
    paths_cfg = (cfg.get("paths") or {})
    root = (
        _wm_data_root() or paths_cfg.get("data_root") or DEFAULTS["paths"]["data_root"]
    ).strip()
    relative_cfg = (cfg.get("relative") or {})

    try:
        from config.paths import get_path as _get_path  # lazy import to avoid cycles

        override_root = (_get_path("paths.data_root") or "").strip()
        if override_root and not paths_cfg.get("data_root"):
            root = override_root
    except Exception:
        pass

    def _is_windows_abs(val: str) -> bool:
        return val.startswith("\\\\") or (len(val) > 1 and val[1] == ":")

    def _abs_path(base: str, value: str | None) -> str | None:
        if not value:
            return None
        if os.path.isabs(value) or _is_windows_abs(value):
            return _norm(value)
        base_path = base or DEFAULTS["paths"]["data_root"]
        if base_path:
            return _norm(os.path.join(base_path, value))
        return _norm(value)

    def _normalized(val: str | None) -> str:
        return (val or "").replace("\\", "/")

    override_value = (relative_cfg.get(what) or "").strip()
    alias_key = RELATIVE_ALIAS_KEYS.get(what)
    if not override_value and alias_key:
        override_value = (relative_cfg.get(alias_key) or "").strip()

    if override_value:
        entry = RESOLVE_MAP.get(what)
        candidate = override_value
        if entry and alias_key and alias_key != what:
            _, fname = entry
            if fname and not os.path.splitext(override_value)[1]:
                candidate = os.path.join(override_value, fname)
        result = _abs_path(root, candidate)
        if result:
            return result

    if what in ("machines",) and not relative_cfg.get("machines"):
        legacy_rel = _machines_rel_value(cfg)
        if legacy_rel and root:
            legacy_abs = os.path.join(root, legacy_rel)
            return _norm(legacy_abs)

    entry = RESOLVE_MAP.get(what)
    if entry:
        subdir, fname = entry
        rel_path = os.path.join(subdir, fname) if subdir else fname
        if rel_path:
            result = _abs_path(root, rel_path)
            if result:
                return result
        if root:
            return _norm(root)

    if what == "root.logs":
        logs_dir = paths_cfg.get("logs_dir") or PATH_MAP.get("root.logs", "logs")
        default_root = DEFAULTS["paths"].get("data_root", "")
        default_logs = DEFAULTS["paths"].get("logs_dir", "")
        if (
            logs_dir
            and default_root
            and _normalized(logs_dir).startswith(_normalized(default_root))
        ):
            rel_logs = _normalized(logs_dir)[len(_normalized(default_root)) :].lstrip("/")
            rel_logs = rel_logs or PATH_MAP.get("root.logs", "logs")
            result = _abs_path(root, rel_logs)
            if result:
                return result
        if _normalized(logs_dir) == _normalized(default_logs):
            if _is_absolute_path(default_logs):
                return _norm(default_logs)
            result = _abs_path(root, PATH_MAP.get("root.logs", "logs"))
            if result:
                return result
        result = _abs_path(root, logs_dir)
        if result:
            return result
    if what == "root.backup":
        backup_dir = (
            paths_cfg.get("backup_dir")
            or PATH_MAP.get("root.backup", "backup")
        )
        default_root = DEFAULTS["paths"].get("data_root", "")
        default_backup = DEFAULTS["paths"].get("backup_dir", "")
        if (
            backup_dir
            and default_root
            and _normalized(backup_dir).startswith(_normalized(default_root))
        ):
            rel_backup = _normalized(backup_dir)[
                len(_normalized(default_root)) :
            ].lstrip("/")
            rel_backup = rel_backup or PATH_MAP.get(
                "root.backup", "backup"
            )
            result = _abs_path(root, rel_backup)
            if result:
                return result
        if _normalized(backup_dir) == _normalized(default_backup):
            if _is_absolute_path(default_backup):
                return _norm(default_backup)
            result = _abs_path(
                root, PATH_MAP.get("root.backup", "backup")
            )
            if result:
                return result
        result = _abs_path(root, backup_dir)
        if result:
            return result

    if what == "root":
        return _norm(root) if root else None

    if root:
        return _norm(os.path.join(root, what))
    return None


def _resolve_rroot_map(cfg: dict | None, key: str, *, dir_only: bool = False) -> str | None:
    mapping = _RROOT_MAP.get(key)
    if not mapping:
        return None
    parts = list(mapping)
    if dir_only and parts:
        last = parts[-1]
        if os.path.splitext(last)[1]:
            parts = parts[:-1]
    root = _wm_root_anchor() or get_root(cfg)
    if not parts:
        return root
    return _norm(os.path.join(root, *parts))


def resolve_rel(cfg: dict | None, what: str, *extra: str) -> str | None:
    cfg = cfg or {}
    base = _resolve_rel_legacy(cfg, what)
    if extra:
        base_dir: str | None = base
        if base_dir and os.path.splitext(base_dir)[1]:
            base_dir = os.path.dirname(base_dir)
        if not base_dir:
            base_dir = _resolve_rroot_map(cfg, what, dir_only=True)
        if not base_dir:
            base_dir = get_root(cfg)
        return _norm(os.path.join(base_dir, *extra))
    if base:
        return base
    mapped = _resolve_rroot_map(cfg, what)
    if mapped:
        return mapped
    return base


def _apply_root_defaults(cfg: dict) -> dict:
    """Uzupełnia konfigurację o ścieżki relatywne względem <root>."""

    try:
        paths = cfg.setdefault("paths", {})
        anchor = _wm_root_anchor() or get_root(cfg)
        data_root = _wm_data_root() or os.path.join(anchor, "data")
        paths["anchor_root"] = anchor
        paths["data_root"] = data_root
        paths["logs_dir"] = os.path.join(anchor, "logs")
        paths["backup_dir"] = os.path.join(anchor, "backup")
        paths["assets_dir"] = os.path.join(anchor, "assets")
        paths["layout_dir"] = os.path.join(data_root, "layout")

        hall = cfg.get("hall") or {}
        machines = cfg.setdefault("machines", {})
        if hall.get("machines_file") and not machines.get("file"):
            machines["file"] = get_machines_path(cfg)
            logger.info(
                "[CFG-MIGRATE] hall.machines_file → machines.file = %s",
                machines["file"],
            )
        machines.setdefault("file", get_machines_path(cfg))

        cfg.setdefault("tools", {}).setdefault("index", resolve_rel(cfg, "tools_index"))
        cfg.setdefault("warehouse", {}).setdefault(
            "stock_source", resolve_rel(cfg, "warehouse_stock")
        )
        cfg.setdefault("bom", {}).setdefault("file", resolve_rel(cfg, "bom"))
        cfg.setdefault("orders", {}).setdefault("file", resolve_rel(cfg, "orders"))
        cfg.setdefault("profiles", {}).setdefault("file", resolve_rel(cfg, "profiles"))
        tools_section = cfg.setdefault("tools", {})
        tools_section.setdefault("definitions_path", resolve_rel(cfg, "tools.zadania"))

        ui = cfg.setdefault("ui", {})
        ui.setdefault("machines_bg", ui.get("machines_bg", ""))
    except Exception as exc:  # pragma: no cover - log i kontynuuj
        logger.warning("[CFG-MIGRATE] Wyjątek migracji ścieżek: %s", exc)
    return cfg


def _prepare_loaded_config(cfg: dict | None) -> dict:
    """Deep copy + aplikacja migracji ścieżek względem <root>."""

    snapshot = json.loads(json.dumps(cfg or {}))
    return _apply_root_defaults(snapshot)


def try_migrate_if_missing(src_abs: str, dst_abs: str):
    """Copy legacy file if destination is missing."""

    if os.path.exists(dst_abs):
        return False
    if os.path.exists(src_abs):
        os.makedirs(os.path.dirname(dst_abs) or ".", exist_ok=True)
        shutil.copy2(src_abs, dst_abs)
        return True
    return False


def migrate_user_files(cfg: dict | None = None) -> list[str]:
    """Migrate user-maintained files to ``<root>/data`` if missing there."""

    cfg = cfg or {}
    moved: list[str] = []
    try:
        root = _wm_root_anchor() or get_root(cfg)
        if not root:
            return moved
        data_dir = _wm_data_root() or os.path.join(root, "data")
        os.makedirs(data_dir, exist_ok=True)

        repo_data_dir = cfg_path("data")
        targets: list[tuple[str, str]] = []

        if repo_data_dir:
            targets.append(
                (
                    os.path.join(repo_data_dir, "zadania_narzedzia.json"),
                    os.path.join(data_dir, "zadania_narzedzia.json"),
                )
            )
            targets.append(
                (
                    os.path.join(repo_data_dir, "profiles.json"),
                    os.path.join(data_dir, "profiles.json"),
                )
            )

        direct_profiles = cfg_path("profiles.json")
        if direct_profiles:
            targets.append(
                (direct_profiles, os.path.join(data_dir, "profiles.json"))
            )

        for src, dst in targets:
            try:
                if try_migrate_if_missing(src, dst):
                    moved.append(os.path.basename(dst))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("[CFG] Migracja pliku %s nie powiodła się: %s", src, exc)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[CFG] Migracja plików użytkownika nie powiodła się: %s", exc)
    return moved


def migrate_legacy_machines_files(cfg: dict | None = None) -> bool:
    """Merge legacy ``data/maszyny.json`` into the canonical machines file."""

    cfg = cfg or {}
    try:
        target_path = get_machines_path(cfg)
        legacy_path = resolve_rel(cfg, r"maszyny.json")
        if not legacy_path:
            return False

        norm_target = os.path.normcase(os.path.abspath(target_path)) if target_path else ""
        norm_legacy = os.path.normcase(os.path.abspath(legacy_path))
        if not os.path.exists(legacy_path) or norm_target == norm_legacy:
            return False

        from utils_json import normalize_rows, safe_read_json
        from utils_maszyny import merge_unique, sort_machines

        legacy_doc = safe_read_json(legacy_path, default=[], ensure=False)
        target_doc = safe_read_json(target_path, default=[], ensure=False)

        def _rows(doc: Any) -> list[dict]:
            rows = normalize_rows(doc, "maszyny")
            if rows:
                return rows
            return normalize_rows(doc, None)

        legacy_rows = _rows(legacy_doc)
        target_rows = _rows(target_doc)

        merged_rows = merge_unique(target_rows, legacy_rows)
        merged_rows = sort_machines(merged_rows)

        os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as handle:
            json.dump(merged_rows, handle, ensure_ascii=False, indent=2)

        timestamp = time.strftime("%Y%m%d%H%M%S")
        backup_path = legacy_path + ".bak"
        if os.path.exists(backup_path):
            backup_path = f"{legacy_path}.{timestamp}.bak"
        shutil.move(legacy_path, backup_path)

        log.info(
            "[WM-DBG][MACH] merged legacy file: %s → %s (rows=%d)",
            legacy_path,
            target_path,
            len(merged_rows),
        )
        return True
    except Exception as exc:  # pragma: no cover - defensive logging
        log.warning("[CFG-MIGRATE] migrate_legacy_machines_files failed: %s", exc)
        return False


def normalize_config(cfg: dict) -> dict:
    """Czyścimy puste legacy i utrzymujemy sekcje."""

    cfg = dict(cfg or {})
    cfg.setdefault("paths", {})
    cfg.setdefault("settings", {})
    machines = cfg.setdefault("machines", {})
    rel_candidate = _machines_rel_value(cfg)
    if rel_candidate:
        machines["rel_path"] = rel_candidate
    else:
        machines.pop("rel_path", None)
    machines.pop("relative_path", None)
    _apply_setting_aliases(cfg)
    _migrate_profiles_config(cfg)
    load_tool_vocab(cfg)
    return cfg


def _extract_strings(value: Any) -> list[str]:
    """Return flattened list of string values found within *value*."""

    result: list[str] = []

    def _walk(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            text = node.strip()
            if text:
                result.append(text)
            return
        if isinstance(node, (list, tuple, set)):
            for item in node:
                _walk(item)
            return
        if isinstance(node, dict):
            for item in node.values():
                _walk(item)

    _walk(value)
    return result


def _dedupe_strings(items: Iterable[str]) -> list[str]:
    """Return a list of unique, case-insensitive strings preserving order."""

    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(text)
    return out


def load_tool_vocab(cfg: dict | None = None, *, include_files: bool = True) -> dict[str, list[str]]:
    """Merge tool vocabulary from new keys, legacy config and optional files."""

    cfg = cfg or {}
    tools_cfg = cfg.get("tools")
    if not isinstance(tools_cfg, dict):
        tools_cfg = {}
        cfg["tools"] = tools_cfg

    mapping = {
        "types": {
            "legacy": ["typy_narzedzi"],
            "rel": "tools.types",
        },
        "statuses": {
            "legacy": [
                "statusy_narzedzi",
                "statusy_narzedzi_nowe",
                "statusy_narzedzi_stare",
            ],
            "rel": "tools.statuses",
        },
        "task_templates": {
            "legacy": ["szablony_zadan_narzedzia"],
            "rel": "tools.tasks",
        },
    }

    result: dict[str, list[str]] = {}

    for key, meta in mapping.items():
        seeds: list[str] = []
        seeds.extend(_extract_strings(tools_cfg.get(key)))
        for legacy_key in meta["legacy"]:
            seeds.extend(_extract_strings(cfg.get(legacy_key)))

        if include_files:
            try:
                path = resolve_rel(cfg, meta["rel"])
            except Exception:
                path = None
            if path and os.path.exists(path):
                try:
                    from utils_json import safe_read_json

                    doc = safe_read_json(path, default=None, ensure=False)
                except Exception:
                    doc = None
                seeds.extend(_extract_strings(doc))

        merged = _dedupe_strings(seeds)
        tools_cfg[key] = merged

        for legacy_key in meta["legacy"]:
            if legacy_key in cfg:
                cfg.pop(legacy_key, None)

        result[key] = merged

    cfg["tools"] = tools_cfg
    return result


def _apply_setting_aliases(cfg: dict) -> None:
    """Ensure aliased system.* keys are mirrored under their ui.* targets."""

    system_cfg = cfg.get("system") if isinstance(cfg.get("system"), dict) else {}
    if not isinstance(system_cfg, dict):
        system_cfg = {}
    ui_cfg = cfg.setdefault("ui", {})
    if not isinstance(ui_cfg, dict):
        ui_cfg = {}
        cfg["ui"] = ui_cfg

    for alias, target in SETTING_ALIASES.items():
        source_field = alias.split(".")[-1]
        target_field = target.split(".")[-1]
        if source_field in system_cfg and target_field not in ui_cfg:
            ui_cfg[target_field] = system_cfg[source_field]
        system_cfg.pop(source_field, None)

    if system_cfg:
        cfg["system"] = system_cfg
    elif "system" in cfg:
        # zachowujemy pusty dict jeśli inne klucze już usunięte przez migrację
        cfg["system"] = system_cfg


def _migrate_profiles_config(cfg: dict) -> None:
    profiles = cfg.get("profiles")
    if not isinstance(profiles, dict):
        return

    legacy_editable = profiles.pop("fields_editable_by_user", None)
    if legacy_editable is None:
        legacy_editable = cfg.pop("profiles.fields_editable_by_user", None)
    if legacy_editable is not None and "editable_fields" not in profiles:
        if isinstance(legacy_editable, (list, tuple, set)):
            profiles["editable_fields"] = list(legacy_editable)
        elif isinstance(legacy_editable, str):
            profiles["editable_fields"] = [legacy_editable]
        else:
            profiles["editable_fields"] = []

    legacy_pin = profiles.pop("allow_pin_change", None)
    if legacy_pin is None:
        legacy_pin = cfg.pop("profiles.allow_pin_change", None)
    pin_cfg = profiles.setdefault("pin", {}) if isinstance(profiles, dict) else {}
    if isinstance(pin_cfg, dict):
        if legacy_pin is not None and "change_allowed" not in pin_cfg:
            pin_cfg["change_allowed"] = bool(legacy_pin)
        pin_cfg.setdefault("change_allowed", False)
        pin_cfg.setdefault("min_length", 4)
        profiles["pin"] = pin_cfg

    legacy_avatar_dir = profiles.pop("avatar_dir", None)
    if legacy_avatar_dir is None:
        legacy_avatar_dir = cfg.pop("profiles.avatar_dir", None)
    avatar_cfg = profiles.get("avatar")
    if not isinstance(avatar_cfg, dict):
        avatar_cfg = {}
    if legacy_avatar_dir is not None and "directory" not in avatar_cfg:
        avatar_cfg["directory"] = legacy_avatar_dir
    avatar_cfg.setdefault("directory", avatar_cfg.get("directory", ""))
    avatar_cfg.setdefault("enabled", bool(avatar_cfg.get("enabled", False)))
    profiles["avatar"] = avatar_cfg

    editable = profiles.get("editable_fields")
    if not isinstance(editable, list):
        if isinstance(editable, str):
            values = [part.strip() for part in editable.split("\n") if part.strip()]
            profiles["editable_fields"] = values
        elif isinstance(editable, (set, tuple)):
            profiles["editable_fields"] = list(editable)
        elif editable is None:
            profiles["editable_fields"] = []
        else:
            profiles["editable_fields"] = [str(editable)]

    profiles.setdefault("editable_fields", profiles.get("editable_fields", []))

    fields_clean: list[str] = []
    for field in profiles.get("editable_fields", []):
        text = str(field or "").strip()
        if text and text not in fields_clean:
            fields_clean.append(text)
    profiles["editable_fields"] = fields_clean

    if isinstance(profiles.get("avatar"), dict):
        avatar = profiles["avatar"]
        avatar["enabled"] = bool(avatar.get("enabled", False))
        avatar["directory"] = str(avatar.get("directory", "") or "")


def _is_subpath(child: str, parent: str) -> bool:
    try:
        return os.path.commonpath(
            [os.path.abspath(child), os.path.abspath(parent)]
        ) == os.path.abspath(parent)
    except Exception:
        return False


def resolve_under_root(cfg: dict, rel_key_path: tuple[str, ...]) -> str | None:
    """Zwraca ścieżkę absolutną względem ``paths.data_root``."""

    paths_cfg = (cfg.get("paths") or {})
    anchor = get_root(cfg)
    raw_root = str(paths_cfg.get("data_root") or "").strip()
    if raw_root:
        root = resolve_root_path(anchor, raw_root)
    else:
        root = resolve_root_path(anchor, "data")
    cur = cfg
    for k in rel_key_path:
        cur = (cur.get(k) if isinstance(cur, dict) else None) or {}
    rel = (cur or "").strip() if isinstance(cur, str) else ""
    if not (root and rel):
        return None
    return resolve_root_path(root, rel)


def _migrate_legacy_paths(cfg: dict) -> bool:
    """
    Migracje relatywne (bez zmian UI):
    - hall.machines_file (ABS) → machines.rel_path (REL), jeśli:
      * machines.rel_path jest puste ORAZ
      * hall.machines_file wskazuje do środka paths.data_root.
    """

    changed = False
    try:
        root = ((cfg.get("paths") or {}).get("data_root") or "").strip()
        legacy_abs = ((cfg.get("hall") or {}).get("machines_file") or "").strip()
        new_rel = _machines_rel_value(cfg)

        if root and legacy_abs and not new_rel and _is_subpath(legacy_abs, root):
            rel = _norm(os.path.relpath(legacy_abs, root))
            _set_machines_rel(cfg, rel)
            changed = True
            log.info(
                "[CFG-MIGRATE] hall.machines_file → machines.rel_path = %s",
                rel,
            )
    except Exception as e:
        log.warning("[CFG-MIGRATE] Wyjątek migracji: %r", e)
    return changed


def _migrate_legacy_keys(cfg: dict) -> bool:
    """
    Migruje stare klucze konfiguracji do nowych. Zwraca True, jeśli coś zmieniono.
    Na razie: hall.machines_file -> machines.file
    """

    changed = False
    try:
        legacy = (cfg.get("hall") or {}).get("machines_file")
        newval = (cfg.get("machines") or {}).get("file")
        if legacy and not newval:
            cfg.setdefault("machines", {})["file"] = legacy
            changed = True
            log.info(
                "[CFG-MIGRATE] Skopiowano hall.machines_file → machines.file: %s",
                legacy,
            )
    except Exception as e:
        log.warning("[CFG-MIGRATE] Wyjątek podczas migracji: %r", e)
    return changed

# Ścieżki domyślne (katalog główny aplikacji)
SCHEMA_PATH = cfg_path("settings_schema.json")
DEFAULTS_PATH = cfg_path("config.defaults.json")
GLOBAL_PATH = cfg_path("config.json")
LOCAL_PATH = cfg_path("config.local.json")
SECRETS_PATH = cfg_path("secrets.json")
MAG_DICT_PATH = cfg_path("data/magazyn/slowniki.json")
AUDIT_DIR = cfg_path("audit")
ROLLBACK_KEEP = 10
BACKUP_DIR: str | None = None

# Initialize module logger
logger = log


class ConfigError(Exception):
    pass


class ConfigManager:
    """Caches loaded configuration and allows explicit refresh.

    Regular instantiation (``ConfigManager()``) returns the cached instance
    to avoid reloading configuration files multiple times during a session.
    Use ``ConfigManager.refresh()`` to force a reload.
    """

    _instance: "ConfigManager | None" = None
    _initialized: bool = False

    # >>> WM PATCH START: ensure defaults from schema
    @staticmethod
    def _iter_schema_fields(schema: Dict[str, Any]) -> "Iterable[Dict[str, Any]]":
        """Yield all field definitions from ``schema`` including nested subtabs."""

        def from_tabs(tabs: list[Dict[str, Any]]):
            for tab in tabs:
                for group in tab.get("groups", []):
                    for field in group.get("fields", []):
                        if field.get("deprecated"):
                            continue
                        yield field
                yield from from_tabs(tab.get("subtabs", []))

        yield from from_tabs(schema.get("tabs", []))
        for opt in schema.get("options", []):
            if opt.get("deprecated"):
                continue
            yield opt

    @staticmethod
    def _coerce_default_for_field(field: Dict[str, Any]) -> Any:
        """Return a sane default coerced to the field's type."""

        default = field.get("default")
        ftype = field.get("type")

        if ftype == "bool":
            if isinstance(default, bool):
                return default
            if isinstance(default, str):
                return default.lower() in {"1", "true", "yes", "on"}
            return bool(default) if default is not None else False

        if ftype == "int":
            try:
                return int(default)
            except (TypeError, ValueError):
                return 0

        if ftype == "float":
            try:
                return float(default)
            except (TypeError, ValueError):
                return 0.0

        if ftype in ("enum", "select"):
            allowed = (
                field.get("allowed")
                or field.get("values")
                or field.get("enum")
                or []
            )
            if default in allowed:
                return default
            return allowed[0] if allowed else None

        return default

    def _ensure_defaults_from_schema(
        self, cfg: Dict[str, Any], schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Uzupełnia brakujące klucze domyślnymi wartościami ze schematu."""

        sentinel = object()

        for field in self._iter_schema_fields(schema):
            key = field.get("key")
            default = field.get("default")
            if not key or default is None:
                continue
            storage_key = SETTING_ALIASES.get(key, key)
            existing = get_by_key(cfg, key, sentinel)
            if existing is sentinel and storage_key != key:
                existing = get_by_key(cfg, storage_key, sentinel)
            if existing is not sentinel:
                continue
            if key in cfg and storage_key != key:
                value = cfg.pop(key)
                set_by_key(cfg, storage_key, value)
                continue
            value = self._coerce_default_for_field(field)
            print(f"[WM-DBG] [SETTINGS] default injected: {key}={value}")
            set_by_key(cfg, storage_key, value)
            self._schema_defaults_injected.add(key)

        migrate_dotted_keys(cfg)
        return cfg
    # >>> WM PATCH END

    @classmethod
    def _ensure_magazyn_defaults(
        cls, schema: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Zapewnia domyślne ustawienia magazynu zdefiniowane w schemacie.

        W pliku ``settings_schema.json`` mogą być zdefiniowane domyślne wartości
        dla pól ``magazyn.kategorie``, ``magazyn.typy_materialu`` oraz
        ``magazyn.jednostki``. Funkcja kopiuje je do ``config`` jeśli brakują.
        """

        magazyn_cfg = config.setdefault("magazyn", {})
        added: Dict[str, Any] = {}
        field_idx = {f.get("key"): f for f in cls._iter_schema_fields(schema)}
        for key in ("kategorie", "typy_materialu", "jednostki"):
            current = magazyn_cfg.get(key)
            if isinstance(current, list):
                continue
            field = field_idx.get(f"magazyn.{key}")
            if not field or field.get("default") is None:
                continue
            value = cls._coerce_default_for_field(field)
            magazyn_cfg[key] = value
            added[key] = value
        if added:
            logger.info("Dodano domyślne ustawienia magazynu: %s", added)
        return config

    def _ensure_magazyn_slowniki(self, schema: Dict[str, Any]) -> None:
        """Ensure ``data/magazyn/slowniki.json`` exists with default values."""

        if os.path.exists(MAG_DICT_PATH):
            return

        field_idx = {f.get("key"): f for f in self._iter_schema_fields(schema)}
        defaults: Dict[str, Any] = {}
        for key in ("kategorie", "typy_materialu", "jednostki"):
            field = field_idx.get(f"magazyn.{key}")
            if field and field.get("default") is not None:
                defaults[key] = self._coerce_default_for_field(field)
            else:
                defaults[key] = []

        os.makedirs(os.path.dirname(MAG_DICT_PATH), exist_ok=True)
        self._save_json(MAG_DICT_PATH, defaults)
        logger.info(
            "[INFO] Zainicjalizowano data/magazyn/slowniki.json domyślnymi wartościami"
        )

    def _ensure_paths_defaults(self) -> None:
        paths_cfg = self.global_cfg.setdefault("paths", {})
        config_dir = Path(self._config_path_value).resolve().parent
        fallback_anchor = _norm(str(config_dir))

        raw_anchor = paths_cfg.get("anchor_root")
        raw_data_root = paths_cfg.get("data_root")

        anchor_norm = fallback_anchor
        if isinstance(raw_anchor, str) and raw_anchor.strip():
            anchor_norm = _absolute_with_root(raw_anchor.strip(), fallback_anchor)
        elif isinstance(raw_data_root, str) and raw_data_root.strip():
            data_candidate = _absolute_with_root(raw_data_root.strip(), fallback_anchor)
            if os.path.basename(data_candidate).lower() == "data":
                anchor_norm = os.path.dirname(data_candidate)
            else:
                anchor_norm = data_candidate

        paths_cfg["anchor_root"] = _norm(anchor_norm)
        self._anchor_root = paths_cfg["anchor_root"]

        if isinstance(raw_data_root, str) and raw_data_root.strip():
            data_resolved = _absolute_with_root(raw_data_root.strip(), self._anchor_root)
        else:
            data_resolved = os.path.join(self._anchor_root, "data")
        paths_cfg["data_root"] = _norm(data_resolved)
        if paths_cfg["data_root"] == self._anchor_root:
            paths_cfg["data_root"] = _norm(os.path.join(self._anchor_root, "data"))

        if paths_cfg.get("backup_wersji") and not paths_cfg.get("backup_dir"):
            paths_cfg["backup_dir"] = paths_cfg["backup_wersji"]

        defaults = {
            "logs_dir": os.path.join(self._anchor_root, "logs"),
            "backup_dir": os.path.join(self._anchor_root, "backup"),
            "assets_dir": os.path.join(self._anchor_root, "assets"),
        }
        for key, fallback in defaults.items():
            candidate = paths_cfg.get(key) or fallback
            paths_cfg[key] = _absolute_with_root(candidate, self._anchor_root)
            if not _is_subpath(paths_cfg[key], self._anchor_root):
                paths_cfg[key] = _absolute_with_root(fallback, self._anchor_root)

        self._root_dir = Path(self._anchor_root)
        self._root = self._anchor_root
        self._data_root = Path(paths_cfg["data_root"])
        self._root_config_path = Path(os.path.join(self._root, "config.json"))

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        config_path: str | None = None,
        schema_path: str | None = None,
    ):
        if self.__class__._initialized:
            return
        _force_runtime_root_into_env()

        self.schema_path = schema_path or SCHEMA_PATH
        self._config_path_value = config_path or GLOBAL_PATH
        self._config_path_input = config_path
        self._config_path: Path | None = None
        self._project_root: Path | None = None
        self._anchor_root: str | None = None
        self._root: str | None = None
        self._root_dir: Path | None = None
        self._data_root: Path | None = None
        self._root_config_path: Path | None = None
        self._root_paths_migrated: bool = False
        self._merged: Dict[str, Any] = {}

        self.schema = self._load_json_or_raise(
            self.schema_path, msg_prefix="Brak pliku schematu"
        )
        self._schema_idx: Dict[str, Dict[str, Any]] = {}
        for field in self._iter_schema_fields(self.schema):
            key = field.get("key")
            if key and key not in self._schema_idx:
                self._schema_idx[key] = field
        self.defaults = self._load_json(DEFAULTS_PATH) or {}
        load_tool_vocab(self.defaults, include_files=False)
        raw_cfg = self._load_json(self._config_path_value) or {}
        normalized_cfg = normalize_config(raw_cfg)
        normalized_cfg, config_path_obj = self._init_config_storage(normalized_cfg)
        self._config_path_value = str(config_path_obj)
        self._config_path = config_path_obj
        self.global_cfg = normalized_cfg
        migrated = bool(self._root_paths_migrated)
        if _migrate_legacy_paths(self.global_cfg):
            migrated = True
        if _migrate_legacy_keys(self.global_cfg):
            migrated = True
        if migrate_legacy_machines_files(self.global_cfg):
            migrated = True
        if migrated:
            try:
                save_method = getattr(self, "save", None)
                if callable(save_method):
                    save_method(self.global_cfg)
            except Exception:
                pass
        self.global_cfg = bootstrap_paths(self.global_cfg)
        try:
            self.global_cfg = _apply_root_defaults(self.global_cfg)
        except Exception:
            pass
        self._ensure_magazyn_slowniki(self.schema)

        # >>> WM PATCH START: auto-heal critical keys
        healed: list[tuple[str, Any]] = []

        def ensure_key(dotted: str, default: Any):
            if get_by_key(self.global_cfg, dotted, None) is None:
                set_by_key(self.global_cfg, dotted, default)
                print(f"[WM-DBG] auto-heal: {dotted}={default}")
                healed.append((dotted, default))

        def default_for(dotted: str, fallback: Any) -> Any:
            try:
                return get_by_key(self.defaults, dotted, fallback)
            except Exception:
                return fallback

        ensure_key("ui.theme", default_for("ui.theme", "dark"))
        ensure_key("ui.language", default_for("ui.language", "pl"))
        ensure_key(
            "ui.start_on_dashboard",
            default_for("ui.start_on_dashboard", True),
        )
        ensure_key(
            "ui.auto_check_updates",
            default_for("ui.auto_check_updates", True),
        )
        ensure_key(
            "ui.debug_enabled",
            default_for("ui.debug_enabled", True),
        )
        ensure_key(
            "ui.log_level",
            default_for("ui.log_level", "debug"),
        )
        default_anchor = _norm(DEFAULTS["paths"].get("anchor_root", _DEFAULT_ROOT))
        ensure_key("paths.anchor_root", default_anchor)

        default_data = DEFAULTS["paths"].get("data_root", default_anchor)
        default_data_norm = _absolute_with_root(str(default_data), default_anchor)
        if default_data_norm == default_anchor:
            default_data_norm = _norm(os.path.join(default_anchor, "data"))
        ensure_key("paths.data_root", default_data_norm)

        default_logs = DEFAULTS["paths"].get("logs_dir", os.path.join(default_anchor, "logs"))
        ensure_key(
            "paths.logs_dir",
            _absolute_with_root(str(default_logs), default_anchor),
        )
        default_backup = DEFAULTS["paths"].get(
            "backup_dir", os.path.join(default_anchor, "backup")
        )
        ensure_key(
            "paths.backup_dir",
            _absolute_with_root(str(default_backup), default_anchor),
        )
        ensure_key("backup.keep_last", 10)
        ensure_key("updates.auto_pull", True)

        if healed:
            self._save_json(self._config_path_value, self.global_cfg)
            for key, val in healed:
                self._audit_change(key, before_val=None, after_val=val, who="auto-heal")
        self._ensure_paths_defaults()
        self._user_files_migrated = migrate_user_files(self.global_cfg)
        if self._user_files_migrated:
            log.info(
                "[CFG] Przeniesiono pliki użytkownika: %s",
                ", ".join(self._user_files_migrated),
            )
        # >>> WM PATCH END

        self._schema_defaults_injected: set[str] = set()
        self.global_cfg = self._ensure_defaults_from_schema(
            self.global_cfg, self.schema
        )
        self._ensure_magazyn_defaults(self.schema, self.global_cfg)
        self.local_cfg = self._load_json(LOCAL_PATH) or {}
        self.secrets = self._load_json(SECRETS_PATH) or {}
        self._ensure_dirs()
        self._merged = self._merge_all()
        print(f"[WM-DBG][SETTINGS] require_reauth={self.get('magazyn.require_reauth', True)}")
        self._validate_all()

        # Settings for unsaved changes handling
        self.warn_on_unsaved = self.get("warn_on_unsaved", True)
        self.autosave_draft = self.get("autosave_draft", False)
        self.autosave_draft_interval_sec = self.get(
            "autosave_draft_interval_sec", 15
        )

        self._save_debounce_seconds = 10.0
        self._last_save_ts = 0.0
        self._pending_save = False
        self._save_lock = threading.Lock()
        self._debounce_timer: threading.Timer | None = None

        logger.info("ConfigManager initialized")
        self.__class__._initialized = True

    @classmethod
    def refresh(
        cls,
        config_path: str | None = None,
        schema_path: str | None = None,
    ) -> "ConfigManager":
        """Reset cached instance and reload configuration."""
        cls._instance = None
        cls._initialized = False
        inst = cls(config_path=config_path, schema_path=schema_path)
        inst._ensure_magazyn_defaults(inst.schema, inst.global_cfg)
        return inst

    # >>> PATCH START: alias merged dla backup/migracji
    @property
    def merged(self) -> dict:
        """Scalona konfiguracja (domyślna + użytkownika)."""

        return (
            getattr(self, "config", None)
            or getattr(self, "_effective", None)
            or getattr(self, "_merged", {})
        )
    # <<< PATCH END

    # ========== I/O pomocnicze ==========
    @staticmethod
    def _derive_root_dir(data_root: str) -> Path:
        try:
            candidate = Path(_norm(data_root)).expanduser()
        except Exception:
            return Path(_norm(data_root))
        if candidate.name.lower() == "data" and candidate.parent:
            return candidate.parent
        return candidate

    def _init_config_storage(
        self, cfg: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Path]:
        project_config_path = Path(self._config_path_value).resolve()
        if getattr(self, "_config_path_input", None):
            self._project_root = project_config_path.parent
            self._root_dir = project_config_path.parent
            try:
                self._data_root = Path(get_root(cfg)).expanduser()
            except Exception:
                self._data_root = project_config_path.parent
            self._config_path = project_config_path
            return cfg, project_config_path

        root_candidate = self._derive_root_dir(get_root(cfg))
        try:
            root_candidate = root_candidate.expanduser()
        except Exception:
            pass

        use_user_config = True
        if os.name != "nt" and _looks_like_windows_path(str(root_candidate)):
            use_user_config = False

        root_dir = root_candidate if use_user_config else project_config_path.parent
        loaded_cfg = cfg

        if use_user_config:
            _safe_makedirs(root_dir)
            user_cfg_path = root_dir / "config.json"

            if user_cfg_path.is_file() and user_cfg_path != project_config_path:
                user_snapshot = self._load_json(str(user_cfg_path)) or {}
                if isinstance(user_snapshot, dict) and user_snapshot:
                    loaded_cfg = normalize_config(user_snapshot)

            if (
                not user_cfg_path.exists()
                and project_config_path.is_file()
                and user_cfg_path != project_config_path
            ):
                try:
                    _safe_makedirs(user_cfg_path.parent)
                    shutil.copy2(project_config_path, user_cfg_path)
                    print(
                        f"[WM-DBG][CFG] migrated project config → {user_cfg_path}"
                    )
                except Exception as exc:
                    print(f"[WM-DBG][CFG] migrate failed: {exc}")

            if (
                user_cfg_path.exists()
                and project_config_path.is_file()
                and user_cfg_path != project_config_path
            ):
                try:
                    project_snapshot = (
                        self._load_json(str(project_config_path)) or {}
                    )
                except Exception:
                    project_snapshot = {}
                try:
                    if isinstance(project_snapshot, dict) and project_snapshot:
                        if normalize_config(project_snapshot) != loaded_cfg:
                            self._write_backup("pre_migration", project_snapshot)
                except Exception as exc:
                    print(f"[WM-DBG][CFG] backup migrate failed: {exc}")
        else:
            user_cfg_path = project_config_path

        paths_cfg = loaded_cfg.get("paths")
        if not isinstance(paths_cfg, dict):
            paths_cfg = {}
        loaded_cfg["paths"] = paths_cfg
        changed_paths = self._ensure_root_directories(paths_cfg, root_dir)
        self._root_paths_migrated = self._root_paths_migrated or changed_paths

        self._root_dir = root_dir
        self._project_root = project_config_path.parent
        try:
            self._data_root = Path(get_root(loaded_cfg)).expanduser()
        except Exception:
            self._data_root = Path(get_root(loaded_cfg))
        return loaded_cfg, user_cfg_path

    def _ensure_root_directories(
        self, paths_cfg: Dict[str, Any], root_dir: Path
    ) -> bool:
        """Ensure logs/backup directories point to ``root_dir`` defaults."""

        changed = False
        root_norm = _norm(str(root_dir))

        defaults = {
            "logs_dir": os.path.join(root_norm, "logs"),
            "backup_dir": os.path.join(root_norm, "backup"),
            "assets_dir": os.path.join(root_norm, "assets"),
        }

        if paths_cfg.get("backup_wersji") and not paths_cfg.get("backup_dir"):
            paths_cfg["backup_dir"] = paths_cfg["backup_wersji"]

        for key, default_value in defaults.items():
            candidate = paths_cfg.get(key) or default_value
            normalized = _absolute_with_root(candidate, root_norm)
            if not _is_subpath(normalized, root_norm):
                normalized = _absolute_with_root(default_value, root_norm)
            if paths_cfg.get(key) != normalized:
                paths_cfg[key] = normalized
                changed = True

        root_value = paths_cfg.get("data_root")
        if root_value:
            normalized_root = _norm(root_value)
            if root_value != normalized_root:
                paths_cfg["data_root"] = normalized_root
                changed = True

        return changed

    def update_root_paths(self, data_root: str) -> None:
        """Apply ``data_root`` as the new base and refresh dependent directories."""

        if not isinstance(data_root, str) or not data_root.strip():
            return

        normalized = _norm(data_root.strip())
        paths_cfg = self.global_cfg.setdefault("paths", {})
        paths_cfg["data_root"] = normalized

        anchor_candidate = normalized
        if os.path.basename(normalized).lower() == "data":
            anchor_candidate = os.path.dirname(normalized)
        anchor_norm = _norm(anchor_candidate)
        paths_cfg["anchor_root"] = anchor_norm
        self._anchor_root = anchor_norm

        if paths_cfg["data_root"] == anchor_norm:
            paths_cfg["data_root"] = _norm(os.path.join(anchor_norm, "data"))

        paths_cfg["assets_dir"] = _norm(os.path.join(anchor_norm, "assets"))

        root_dir = Path(anchor_norm)
        self._root_dir = root_dir
        self._root = anchor_norm
        changed = self._ensure_root_directories(paths_cfg, root_dir)
        if changed:
            self._root_paths_migrated = True

        self._data_root = Path(paths_cfg["data_root"])
        self._root_config_path = Path(os.path.join(self._root, "config.json"))
        self._config_path = root_dir / "config.json"
        self._config_path_value = str(self._config_path)
        self._merged = self._merge_all()
        self._ensure_dirs()

    def _ensure_dirs(self):
        _safe_makedirs(AUDIT_DIR)
        try:
            root_dir = getattr(self, "_root_dir", None)
            if root_dir:
                _safe_makedirs(root_dir)
        except Exception as exc:
            logger.warning("[CFG] Nie udało się utworzyć katalogu root: %s", exc)
        try:
            backup_dir = self.path_backup()
            if backup_dir:
                _safe_makedirs(backup_dir)
        except Exception as exc:
            logger.warning("[CFG] Nie udało się utworzyć katalogu kopii: %s", exc)
        try:
            _safe_makedirs(self.path_data())
        except Exception as exc:
            logger.warning("[CFG] Nie udało się utworzyć katalogu danych: %s", exc)
        try:
            logs_dir = self.path_logs()
            if logs_dir:
                _safe_makedirs(logs_dir)
        except Exception as exc:
            logger.warning("[CFG] Nie udało się utworzyć katalogu logów: %s", exc)
        try:
            assets_dir = self.path_assets()
            if assets_dir:
                _safe_makedirs(assets_dir)
        except Exception as exc:
            logger.warning("[CFG] Nie udało się utworzyć katalogu assets: %s", exc)

    def _load_json(self, path: str) -> Dict[str, Any] | None:
        try:
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                content = "\n".join(
                    line for line in f if not line.lstrip().startswith("#")
                )
            return json.loads(content) if content.strip() else None
        except Exception as e:
            logger.warning("Problem z wczytaniem %s: %s", path, e)
            return None

    def _load_json_or_raise(self, path: str, msg_prefix: str = "") -> Dict[str, Any]:
        data = self._load_json(path)
        if data is None:
            raise ConfigError(f"{msg_prefix}: {path}")
        return data

    def _save_json(self, path: str, data: Dict[str, Any]):
        target = os.fspath(path)
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        lock_path = f"{target}.lock"
        with open(lock_path, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
        try:
            self._safe_write(target, payload)
        finally:
            try:
                os.remove(lock_path)
            except Exception:
                pass

    def _safe_write(self, config_target, payload: str) -> None:
        target_path = os.fspath(config_target)
        if not target_path:
            raise ValueError("Brak ścieżki docelowej do zapisu")
        target_path = os.path.expanduser(target_path)
        if _looks_like_windows_path(target_path):
            split_mod = ntpath
            join_mod = ntpath
            if os.name == "nt":
                target_path = ntpath.abspath(target_path)
        else:
            split_mod = os.path
            join_mod = os.path
            target_path = os.path.abspath(target_path)
        base_dir, file_name = split_mod.split(target_path)
        if not file_name:
            raise ValueError(f"Nieprawidłowa ścieżka docelowa: {target_path!r}")
        _safe_makedirs(base_dir)
        tmp_name = file_name + ".tmp"
        tmp_path = join_mod.join(base_dir, tmp_name) if base_dir else tmp_name
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_path, target_path)

    def _write_backup(self, label: str, content: Dict[str, Any]) -> str | None:
        import datetime
        import json

        backup_dir = Path(self.path_backup())
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            return None
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = backup_dir / f"config_{label}.{ts}.json"
        try:
            payload = json.dumps(content, ensure_ascii=False, indent=2)
            self._safe_write(str(dst), payload)
        except Exception:
            return None
        print(f"[WM-DBG][CFG] backup {label} → {dst}")
        return _norm(str(dst))

    # ========== scalanie i indeks schematu ==========
    def _merge_all(self) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for src in (self.defaults, self.global_cfg, self.local_cfg, self.secrets):
            if not src:
                continue
            merged = deep_merge(merged, src)
        for alias, target in SETTING_ALIASES.items():
            value = get_by_key(merged, target, None)
            if value is not None:
                set_by_key(merged, alias, value)
        return merged

    def _schema_index(self) -> Dict[str, Dict[str, Any]]:
        """Zwraca zbuforowany indeks schematu."""
        return self._schema_idx

    # ========== walidacja ==========
    def _validate_all(self):
        idx = self._schema_idx
        for key, opt in idx.items():
            value = get_by_key(self.merged, key, None)
            if value is None:
                continue
            self._validate_value(opt, value)

    def _validate_value(self, opt: Dict[str, Any], value: Any):
        t = opt.get("type")
        if t == "bool":
            if not isinstance(value, bool):
                raise ConfigError(
                    f"{opt['key']}: oczekiwano bool, dostano {type(value).__name__}"
                )
        elif t == "int":
            if not isinstance(value, int):
                raise ConfigError(
                    f"{opt['key']}: oczekiwano int, dostano {type(value).__name__}"
                )
            if "min" in opt and value < opt["min"]:
                raise ConfigError(f"{opt['key']}: < min {opt['min']}")
            if "max" in opt and value > opt["max"]:
                raise ConfigError(f"{opt['key']}: > max {opt['max']}")
        elif t == "enum":
            allowed = opt.get("enum") or opt.get("values") or []
            if value not in allowed:
                raise ConfigError(f"{opt['key']}: {value} nie w {allowed}")
        elif t == "array":
            if not isinstance(value, list):
                raise ConfigError(
                    f"{opt['key']}: oczekiwano listy, dostano {type(value).__name__}"
                )
        elif t in ("dict", "object"):
            if not isinstance(value, dict):
                raise ConfigError(
                    f"{opt['key']}: oczekiwano dict, dostano {type(value).__name__}"
                )
            vtype = opt.get("value_type")
            if vtype:
                for k, v in value.items():
                    if vtype == "string" and not isinstance(v, str):
                        raise ConfigError(
                            f"{opt['key']}.{k}: oczekiwano string, dostano {type(v).__name__}"
                        )
                    elif vtype == "int" and not isinstance(v, int):
                        raise ConfigError(
                            f"{opt['key']}.{k}: oczekiwano int, dostano {type(v).__name__}"
                        )
                    elif vtype == "float" and not isinstance(v, (int, float)):
                        raise ConfigError(
                            f"{opt['key']}.{k}: oczekiwano float, dostano {type(v).__name__}"
                        )
                    elif vtype == "bool" and not isinstance(v, bool):
                        raise ConfigError(
                            f"{opt['key']}.{k}: oczekiwano bool, dostano {type(v).__name__}"
                        )
        elif t in ("string", "path"):
            if not isinstance(value, str):
                raise ConfigError(f"{opt['key']}: oczekiwano string")
        else:
            # nieznane typy traktujemy jako string/opaque
            pass

    # ========== API ==========
    def _path_source(self) -> Dict[str, Any]:
        if isinstance(getattr(self, "merged", None), dict):
            return self.merged
        if isinstance(self.global_cfg, dict):
            return self.global_cfg
        return {}

    def _anchor(self) -> str:
        if isinstance(self._anchor_root, str) and self._anchor_root:
            return self._anchor_root
        source = self._path_source()
        candidate = get_by_key(source, "paths.anchor_root", None)
        if isinstance(candidate, str) and candidate.strip():
            self._anchor_root = _absolute_with_root(candidate.strip(), _DEFAULT_ROOT)
            return self._anchor_root
        root = get_root(source)
        self._anchor_root = _norm(root)
        return self._anchor_root

    def _expand(self, value: str) -> str:
        if not isinstance(value, str):
            return value
        anchor = self._anchor()
        return _absolute_with_root(value, anchor)

    def _path_from_cfg(self, dotted: str, fallback: str) -> str:
        cfg = self._path_source()
        value = get_by_key(cfg, dotted, None)
        if value is None and isinstance(cfg, dict):
            value = cfg.get(dotted)
        if isinstance(value, str) and value.strip():
            return _norm(value.strip())
        return _norm(fallback)

    def path_root(self, *parts: str) -> str:
        base = self._root or self._anchor()
        root_path = _norm(base)
        if parts:
            return _norm(os.path.join(root_path, *parts))
        return root_path

    def path_anchor(self, *parts: str) -> str:
        forced = _wm_root_anchor()
        base = forced or self._anchor()
        if parts:
            return _norm(os.path.join(base, *parts))
        return base

    def config_path(self) -> str:
        """Return absolute path to the active configuration file."""

        runtime_config = _runtime_config_file()
        if runtime_config:
            return runtime_config
        if isinstance(self._config_path, Path):
            return _norm(str(self._config_path))
        if isinstance(self._root_config_path, Path):
            return _norm(str(self._root_config_path))
        return _norm(os.path.join(self.path_root(), "config.json"))

    def get_config_path(self) -> str:
        return self.config_path()

    def path_data(self, *parts: str) -> str:
        forced = _wm_data_root()
        base = forced or self._expanded_path(
            "paths.data_root", os.path.join(self.path_root(), "data")
        )
        if parts:
            return _norm(os.path.join(base, *parts))
        return base

    def path_backup(self, *parts: str) -> str:
        forced_root = _wm_root_anchor()
        if forced_root:
            base = _norm(os.path.join(forced_root, "backup"))
        else:
            base = self._expanded_path(
                "paths.backup_dir", os.path.join(self.path_root(), "backup")
            )
        if parts:
            return _norm(os.path.join(base, *parts))
        return base

    def path_logs(self, *parts: str) -> str:
        forced_root = _wm_root_anchor()
        if forced_root:
            base = _norm(os.path.join(forced_root, "logs"))
        else:
            base = self._expanded_path(
                "paths.logs_dir", os.path.join(self.path_root(), "logs")
            )
        if parts:
            return _norm(os.path.join(base, *parts))
        return base

    def path_assets(self, *parts: str) -> str:
        forced_root = _wm_root_anchor()
        if forced_root:
            base = _norm(os.path.join(forced_root, "assets"))
        else:
            base = self._expanded_path(
                "paths.assets_dir", os.path.join(self.path_root(), "assets")
            )
        if parts:
            return _norm(os.path.join(base, *parts))
        return base

    def _expanded_path(self, dotted: str, fallback: str) -> str:
        source = self._path_source()
        value = get_by_key(source, dotted, None)
        if value is None and isinstance(source, dict):
            parts = dotted.split(".")
            if len(parts) == 2 and parts[0] == "paths":
                value = (source.get("paths") or {}).get(parts[1])
        candidate = value or fallback
        return self._expand(str(candidate))

    def get(self, key: str, default: Any = None) -> Any:
        sentinel = object()
        value = get_by_key(self.merged, key, sentinel)
        if value is sentinel:
            alias = SETTING_ALIASES.get(key)
            if alias:
                value = get_by_key(self.merged, alias, sentinel)
        if value is sentinel and key in _ALIAS_REVERSE:
            alias = _ALIAS_REVERSE.get(key)
            if alias:
                value = get_by_key(self.merged, alias, sentinel)
        if value is sentinel:
            return default
        return value

    def expanded(self, *keys: str, default: Any = None) -> Any:
        if not keys:
            return default
        if len(keys) == 1:
            dotted = str(keys[0])
        else:
            dotted = ".".join(str(part) for part in keys)
        value = self.get(dotted, default)
        if isinstance(value, str):
            return self._expand(value)
        return value

    def load(self) -> Dict[str, Any]:
        """Backward-compatible snapshot accessor returning current config."""

        def _try_prepare(value: Any) -> Dict[str, Any] | None:
            if isinstance(value, dict):
                return _prepare_loaded_config(value)
            return None

        try:
            getter = getattr(self, "get", None)
            if callable(getter):
                signature = inspect.signature(getter)
                if len(signature.parameters) == 0:
                    maybe = _try_prepare(getter())
                    if maybe is not None:
                        return maybe
        except Exception:
            pass

        try:
            to_dict = getattr(self, "to_dict", None)
            if callable(to_dict):
                maybe = _try_prepare(to_dict())
                if maybe is not None:
                    return maybe
        except Exception:
            pass

        try:
            reader = getattr(self, "read", None)
            if callable(reader):
                maybe = _try_prepare(reader())
                if maybe is not None:
                    return maybe
        except Exception:
            pass

        if isinstance(self.merged, dict):
            return _prepare_loaded_config(self.merged)

        import os

        path = getattr(self, "config_path", "config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                try:
                    return _prepare_loaded_config(json.load(fh))
                except Exception:
                    return _prepare_loaded_config({})
        return _prepare_loaded_config({})

    def is_schema_default(self, key: str) -> bool:
        """Zwraca True, jeśli wartość została wstrzyknięta z domyślnego schematu."""

        return key in self._schema_defaults_injected

    def set(self, key: str, value: Any, who: str = "system"):
        idx = self._schema_idx
        schema_key = key if key in idx else _ALIAS_REVERSE.get(key, key)
        opt = idx.get(schema_key)
        if opt:
            self._validate_value(opt, value)
            scope = opt.get("scope", "global")
            target = {
                "global": self.global_cfg,
                "local": self.local_cfg,
                "secret": self.secrets,
            }.get(scope, self.global_cfg)
        else:
            target = self.global_cfg

        storage_key = SETTING_ALIASES.get(schema_key, key)
        _sentinel = object()
        before_val = get_by_key(self.merged, storage_key, _sentinel)
        if before_val is _sentinel and storage_key != key:
            before_val = get_by_key(self.merged, key, _sentinel)
        if before_val is _sentinel:
            before_val = None

        self._schema_defaults_injected.discard(schema_key)
        self._schema_defaults_injected.discard(key)
        set_by_key(target, storage_key, value)
        if storage_key != key:
            delete_by_key(target, schema_key)
        alias_key = _ALIAS_REVERSE.get(storage_key)
        if alias_key:
            delete_by_key(target, alias_key)
        if storage_key == "paths.data_root":
            try:
                self.update_root_paths(str(value))
            except Exception:
                pass
        self._merged = self._merge_all()
        self._audit_change(key, before_val=before_val, after_val=value, who=who)

    def save(self) -> bool:
        """Bezpieczny zapis bieżącej konfiguracji na dysk."""

        try:
            persist = getattr(self, "persist", None)
            if callable(persist):
                persist()
                return True

            writer = getattr(self, "write", None)
            if callable(writer):
                writer()
                return True

            save_all = getattr(self, "save_all", None)
            if callable(save_all):
                save_all()
                return True

            if hasattr(self, "_safe_write") and self._config_path is not None:
                payload_dict = getattr(self, "global_cfg", None) or {}
                payload_json = json.dumps(payload_dict, ensure_ascii=False, indent=2)
                backup_dir = self.path_backup()
                config_target = Path(self._config_path)
                if backup_dir:
                    try:
                        os.makedirs(backup_dir, exist_ok=True)
                        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_path = os.path.join(backup_dir, f"config_{stamp}.json")
                        if config_target.exists():
                            shutil.copy2(config_target, backup_path)
                    except Exception as exc:
                        print(f"[WM-DBG][CFG] backup dir failed: {exc}")
                self._safe_write(str(config_target), payload_json)
                return True

            raise RuntimeError("No persist/write available in ConfigManager")
        except Exception as exc:
            logger.exception("[CFG] save() failed: %s", exc)
            raise

    def save_all(self):
        now = time.monotonic()
        perform_now = False
        remaining = self._save_debounce_seconds
        with self._save_lock:
            elapsed = now - self._last_save_ts
            if self._last_save_ts == 0.0 or elapsed >= self._save_debounce_seconds:
                self._last_save_ts = now
                self._pending_save = False
                perform_now = True
            else:
                remaining = max(self._save_debounce_seconds - elapsed, 0.1)
                self._pending_save = True
                timer = self._debounce_timer
                if timer is None or not timer.is_alive():
                    self._debounce_timer = threading.Timer(
                        remaining, self._flush_debounced_save
                    )
                    self._debounce_timer.daemon = True
                    self._debounce_timer.start()
        if perform_now:
            self._perform_save_all()
        else:
            print(
                f"[WM-DBG] save_all debounced; ponowny zapis za ~{remaining:.1f}s"
            )

    def _flush_debounced_save(self) -> None:
        with self._save_lock:
            if not self._pending_save:
                self._debounce_timer = None
                return
            self._pending_save = False
            self._debounce_timer = None
            self._last_save_ts = time.monotonic()
        self._perform_save_all()

    def _perform_save_all(self) -> None:
        _force_runtime_root_into_env()
        runtime_config = _runtime_config_file()
        if runtime_config:
            self._config_path = Path(runtime_config).expanduser().resolve()
            self._config_path_value = str(self._config_path)
        try:
            self.global_cfg = _apply_root_defaults(self.global_cfg)
        except Exception:
            pass
        migrate_dotted_keys(self.global_cfg)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir_str = self.path_backup()
        backup_dir_base = (
            Path(backup_dir_str)
            if backup_dir_str
            else Path(self.get_config_path()).parent
        )
        try:
            backup_dir = _normalize_user_path(str(backup_dir_base))
        except ValueError:
            backup_dir = _normalize_user_path(str(Path(self.get_config_path()).parent))
        _safe_makedirs(backup_dir)
        backup_path = backup_dir / f"config_{stamp}.json"
        backup_target = _normalize_user_path(str(backup_path))
        if isinstance(self._config_path, Path):
            config_target = self._config_path
        else:
            config_target = Path(self.get_config_path())
        config_target = _normalize_user_path(str(config_target))
        print(f"[WM-DBG] backup_dir={backup_dir}")
        payload = self.global_cfg or {}
        payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
        print(f"[WM-DBG][CFG] saving backup to {backup_target}")
        if config_target.exists():
            shutil.copy2(config_target, backup_target)
        else:
            self._safe_write(str(backup_target), payload_json)
        print(f"[WM-DBG] writing backup: {backup_target}")
        if self.global_cfg is not None:
            print(f"[WM-DBG][CFG] saving config to {config_target}")
            self._safe_write(str(config_target), payload_json)
            print(f"[WM-DBG] writing config: {config_target}")
        if self.local_cfg is not None:
            self._save_json(LOCAL_PATH, self.local_cfg)
        if self.secrets is not None:
            self._save_json(SECRETS_PATH, self.secrets)
        self._prune_rollbacks()

    def export_public(self, path: str):
        """Eksport bez sekretnych kluczy (scope=secret)."""
        public = deep_merge(self.defaults or {}, self.global_cfg or {})
        public = deep_merge(public, self.local_cfg or {})
        self._save_json(path, public)

    def import_with_dry_run(self, path: str) -> Dict[str, Any]:
        incoming = self._load_json_or_raise(path, msg_prefix="Brak pliku do importu")
        idx = self._schema_idx
        diffs: List[Dict[str, Any]] = []
        for k, v in flatten(incoming).items():
            if k in idx:
                self._validate_value(idx[k], v)
            cur = get_by_key(self.merged, k, None)
            if cur != v:
                diffs.append({"key": k, "current": cur, "new": v})
        return {"diffs": diffs, "count": len(diffs)}

    def apply_import(self, path: str, who: str = "system"):
        _ = self.import_with_dry_run(path)  # walidacja
        incoming = self._load_json_or_raise(path)
        for k, v in flatten(incoming).items():
            self.set(k, v, who=who)
        self.save_all()
        return _

    # ========== audyt i porządkowanie backupów ==========
    def _audit_change(self, key: str, before_val: Any, after_val: Any, who: str):
        if key.startswith("secrets."):
            before_val = after_val = "***"
        rec = {
            "time": datetime.datetime.now().isoformat(timespec="seconds"),
            "user": who,
            "key": key,
            "before": before_val,
            "after": after_val,
        }
        _safe_makedirs(AUDIT_DIR)
        path = os.path.join(AUDIT_DIR, "config_changes.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _prune_rollbacks(self):
        try:
            backup_dir = self.path_backup()
            if not backup_dir:
                return
            _safe_makedirs(backup_dir)
            files = sorted(
                f
                for f in os.listdir(backup_dir)
                if os.path.isfile(os.path.join(backup_dir, f))
                and f.startswith("config_")
            )
            if len(files) > ROLLBACK_KEEP:
                for f in files[:-ROLLBACK_KEEP]:
                    try:
                        os.remove(os.path.join(backup_dir, f))
                    except OSError:
                        pass
        except FileNotFoundError:
            pass


# ========== Helpers ==========


def get_path(key: str, default: Any = None) -> Any:
    """Shortcut for ``ConfigManager().get``."""

    mgr = ConfigManager()
    return mgr.get(key, default)


def set_path(key: str, value: Any, *, who: str = "system", save: bool = True) -> None:
    """Shortcut for setting a config path and optionally saving immediately."""

    mgr = ConfigManager()
    mgr.set(key, value, who=who)
    if save:
        mgr.save_all()


def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict):
            base = out.get(k) if isinstance(out.get(k), dict) else {}
            out[k] = deep_merge(base, v)
        else:
            out[k] = v
    return out


def flatten(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    res: Dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            res.update(flatten(v, key))
        else:
            res[key] = v
    return res


def get_by_key(d: Dict[str, Any], dotted: str, default: Any = None) -> Any:
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_by_key(d: Dict[str, Any], dotted: str, value: Any):
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def delete_by_key(d: Dict[str, Any], dotted: str) -> None:
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return
        cur = cur[p]
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def migrate_dotted_keys(d: Dict[str, Any]) -> None:
    """Przenieś klucze z kropkami do struktury zagnieżdżonej."""

    if not isinstance(d, dict):
        return

    sentinel = object()
    dotted_keys = [
        key for key in list(d.keys()) if isinstance(key, str) and "." in key
    ]
    for dotted in dotted_keys:
        value = d.pop(dotted)
        if get_by_key(d, dotted, sentinel) is sentinel:
            set_by_key(d, dotted, value)
