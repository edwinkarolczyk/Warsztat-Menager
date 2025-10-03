"""
Config Manager – warstwy: defaults → global → local → secrets
Wersja: 1.0.2

Funkcje:
- Ładowanie i scalanie warstw configu
- Walidacja wg settings_schema.json
- Zapis z backupem i audytem zmian
- Import/eksport (eksport bez sekretów)
- Rollback przez katalogi w backup_wersji (utrzymujemy ostatnie 10)
"""

from __future__ import annotations

import datetime
import inspect
import json
import logging
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

from utils.path_utils import cfg_path

log = logging.getLogger(__name__)

# Standardowa mapa plików relatywnych (względem paths.data_root)
PATH_MAP = {
    "machines": "maszyny/maszyny.json",
    "warehouse": "magazyn/magazyn.json",
    "bom": "produkty/bom.json",
    "tools.dir": "narzedzia",
    "tools.types": "narzedzia/typy_narzedzi.json",
    "tools.statuses": "narzedzia/statusy_narzedzi.json",
    "tools.tasks": "narzedzia/szablony_zadan.json",
    "tools.zadania": "zadania_narzedzia.json",
    "orders": "zlecenia/zlecenia.json",
    "root.logs": "logs",
    "root.backup": "backup",
}

DEFAULTS = {
    "paths": {
        "data_root": "C:/wm/data",
        "logs_dir": "C:/wm/data/logs",
        "backup_dir": "C:/wm/data/backup",
        "layout_dir": "C:/wm/data/layout",
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


def _norm(p: str) -> str:
    return os.path.normpath(p).replace("\\", "/")


def get_root(cfg: dict) -> str:
    return ((cfg.get("paths") or {}).get("data_root") or "").strip()


def resolve_rel(cfg: dict, what: str) -> str | None:
    """Zwróć ścieżkę absolutną względem ``paths.data_root`` lub wpisu w ``paths``."""

    cfg = cfg or {}
    paths_cfg = (cfg.get("paths") or {})
    root = (paths_cfg.get("data_root") or DEFAULTS["paths"]["data_root"]).strip()
    relative_cfg = (cfg.get("relative") or {})

    try:
        from config.paths import get_path as _get_path  # lazy import to avoid cycles

        override_root = (_get_path("paths.data_root") or "").strip()
        if override_root:
            root = override_root
    except Exception:
        pass

    rel = {
        "machines": relative_cfg.get("machines") or DEFAULTS["relative"]["machines"],
        "tools_dir": relative_cfg.get("tools_dir")
        or DEFAULTS["relative"]["tools_dir"],
        "orders_dir": relative_cfg.get("orders_dir")
        or DEFAULTS["relative"]["orders_dir"],
        "warehouse": relative_cfg.get("warehouse")
        or DEFAULTS["relative"]["warehouse"],
        "profiles": relative_cfg.get("profiles")
        or DEFAULTS["relative"]["profiles"],
        "bom": relative_cfg.get("bom") or DEFAULTS["relative"]["bom"],
        "tools_defs": relative_cfg.get("tools_defs")
        or DEFAULTS["relative"]["tools_defs"],
    }

    def _is_windows_abs(val: str) -> bool:
        return val.startswith("\\\\") or (len(val) > 1 and val[1] == ":")

    def _abs_path(base: str, value: str | None) -> str | None:
        if not value:
            return None
        if os.path.isabs(value) or _is_windows_abs(value):
            return os.path.normpath(value)
        base_path = base or DEFAULTS["paths"]["data_root"]
        if base_path:
            return os.path.normpath(os.path.join(base_path, value))
        return os.path.normpath(value)

    def _normalized(val: str | None) -> str:
        return (val or "").replace("\\", "/")

    join_map = {
        "machines": rel["machines"],
        "warehouse": rel["warehouse"],
        "bom": rel["bom"],
        "profiles": rel["profiles"],
        "tools_dir": rel["tools_dir"],
        "orders_dir": rel["orders_dir"],
        "tools_defs": rel["tools_defs"],
        "tools.dir": rel["tools_dir"],
        "tools.types": os.path.join(rel["tools_defs"], "typy_narzedzi.json"),
        "tools.statuses": os.path.join(rel["tools_defs"], "statusy_narzedzi.json"),
        "tools.tasks": os.path.join(rel["tools_defs"], "szablony_zadan.json"),
        "tools.zadania": "zadania_narzedzia.json",
        "orders": os.path.join(rel["orders_dir"], "zlecenia.json"),
    }

    if what in ("machines",) and not relative_cfg.get("machines"):
        legacy_rel = ((cfg.get("machines") or {}).get("rel_path") or "").strip()
        if legacy_rel and root:
            legacy_abs = os.path.join(root, legacy_rel)
            if os.path.exists(legacy_abs):
                return os.path.normpath(legacy_abs)

    value = join_map.get(what)
    if value:
        result = _abs_path(root, value)
        if result:
            return result

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
            result = _abs_path(root, PATH_MAP.get("root.logs", "logs"))
            if result:
                return result
        result = _abs_path(root, logs_dir)
        if result:
            return result
    if what == "root.backup":
        backup_dir = paths_cfg.get("backup_dir") or PATH_MAP.get("root.backup", "backup")
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
            rel_backup = rel_backup or PATH_MAP.get("root.backup", "backup")
            result = _abs_path(root, rel_backup)
            if result:
                return result
        if _normalized(backup_dir) == _normalized(default_backup):
            result = _abs_path(root, PATH_MAP.get("root.backup", "backup"))
            if result:
                return result
        result = _abs_path(root, backup_dir)
        if result:
            return result

    if what == "root":
        return os.path.normpath(root) if root else None

    return None


def try_migrate_if_missing(src_abs: str, dst_abs: str):
    """Copy legacy file if destination is missing."""

    if os.path.exists(dst_abs):
        return False
    if os.path.exists(src_abs):
        os.makedirs(os.path.dirname(dst_abs) or ".", exist_ok=True)
        shutil.copy2(src_abs, dst_abs)
        return True
    return False


def normalize_config(cfg: dict) -> dict:
    """Czyścimy puste legacy i utrzymujemy sekcje."""

    cfg = dict(cfg or {})
    cfg.setdefault("paths", {})
    cfg.setdefault("settings", {})
    cfg.setdefault("machines", {})
    if "rel_path" in cfg["machines"] and not cfg["machines"]["rel_path"]:
        cfg["machines"].pop("rel_path", None)
    return cfg


def _is_subpath(child: str, parent: str) -> bool:
    try:
        return os.path.commonpath(
            [os.path.abspath(child), os.path.abspath(parent)]
        ) == os.path.abspath(parent)
    except Exception:
        return False


def resolve_under_root(cfg: dict, rel_key_path: tuple[str, ...]) -> str | None:
    """
    Zwraca ścieżkę absolutną jako join(paths.data_root, rel_path),
    gdzie rel_path = cfg[rel_key_path...]. Jeśli brak danych – None.
    """

    root = ((cfg.get("paths") or {}).get("data_root") or "").strip()
    cur = cfg
    for k in rel_key_path:
        cur = (cur.get(k) if isinstance(cur, dict) else None) or {}
    rel = (cur or "").strip() if isinstance(cur, str) else ""
    if not (root and rel):
        return None
    return os.path.join(root, rel)


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
        new_rel = ((cfg.get("machines") or {}).get("rel_path") or "").strip()

        if root and legacy_abs and not new_rel and _is_subpath(legacy_abs, root):
            rel = _norm(os.path.relpath(legacy_abs, root))
            cfg.setdefault("machines", {})["rel_path"] = rel
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
BACKUP_DIR = cfg_path("backup_wersji")
ROLLBACK_KEEP = 10

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
            existing = get_by_key(cfg, key, sentinel)
            if existing is not sentinel:
                continue
            if key in cfg:
                value = cfg.pop(key)
                set_by_key(cfg, key, value)
                continue
            value = self._coerce_default_for_field(field)
            print(f"[WM-DBG] [SETTINGS] default injected: {key}={value}")
            set_by_key(cfg, key, value)
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

        self.schema_path = schema_path or SCHEMA_PATH
        self.config_path = config_path or GLOBAL_PATH

        self.schema = self._load_json_or_raise(
            self.schema_path, msg_prefix="Brak pliku schematu"
        )
        self._schema_idx: Dict[str, Dict[str, Any]] = {}
        for field in self._iter_schema_fields(self.schema):
            key = field.get("key")
            if key and key not in self._schema_idx:
                self._schema_idx[key] = field
        self.defaults = self._load_json(DEFAULTS_PATH) or {}
        raw_cfg = self._load_json(self.config_path) or {}
        normalized_cfg = normalize_config(raw_cfg)
        if normalized_cfg != raw_cfg:
            try:
                with open(self.config_path, "w", encoding="utf-8") as wf:
                    json.dump(normalized_cfg, wf, ensure_ascii=False, indent=2)
                log.info("[CFG] Normalized config to 1-root model.")
            except Exception as e:
                log.warning("[CFG] Failed to persist normalized config: %r", e)
        self.global_cfg = normalized_cfg
        migrated = False
        if _migrate_legacy_paths(self.global_cfg):
            migrated = True
        if _migrate_legacy_keys(self.global_cfg):
            migrated = True
        if migrated:
            try:
                save_method = getattr(self, "save", None)
                if callable(save_method):
                    save_method(self.global_cfg)
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

        ensure_key("ui.theme", "dark")
        ensure_key("ui.language", "pl")
        ensure_key("backup.keep_last", 10)

        if healed:
            self._save_json(self.config_path, self.global_cfg)
            for key, val in healed:
                self._audit_change(key, before_val=None, after_val=val, who="auto-heal")
        # >>> WM PATCH END

        self._schema_defaults_injected: set[str] = set()
        self.global_cfg = self._ensure_defaults_from_schema(
            self.global_cfg, self.schema
        )
        self._ensure_magazyn_defaults(self.schema, self.global_cfg)
        self.local_cfg = self._load_json(LOCAL_PATH) or {}
        self.secrets = self._load_json(SECRETS_PATH) or {}
        self._ensure_dirs()
        self.merged = self._merge_all()
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

    # ========== I/O pomocnicze ==========
    def _ensure_dirs(self):
        os.makedirs(AUDIT_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)

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
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        LOCK_PATH = path + ".lock"
        with open(LOCK_PATH, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
        try:
            os.replace(tmp, path)
        finally:
            try:
                os.remove(LOCK_PATH)
            except Exception:
                pass

    # ========== scalanie i indeks schematu ==========
    def _merge_all(self) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for src in (self.defaults, self.global_cfg, self.local_cfg, self.secrets):
            if not src:
                continue
            merged = deep_merge(merged, src)
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
    def get(self, key: str, default: Any = None) -> Any:
        return get_by_key(self.merged, key, default)

    def load(self) -> Dict[str, Any]:
        """Backward-compatible snapshot accessor returning current config."""

        try:
            getter = getattr(self, "get", None)
            if callable(getter):
                signature = inspect.signature(getter)
                if len(signature.parameters) == 0:
                    value = getter()
                    if isinstance(value, dict):
                        return value
        except Exception:
            pass

        try:
            to_dict = getattr(self, "to_dict", None)
            if callable(to_dict):
                value = to_dict()
                if isinstance(value, dict):
                    return value
        except Exception:
            pass

        try:
            reader = getattr(self, "read", None)
            if callable(reader):
                value = reader()
                if isinstance(value, dict):
                    return value
        except Exception:
            pass

        if hasattr(self, "merged") and isinstance(self.merged, dict):
            return json.loads(json.dumps(self.merged))

        import os

        path = getattr(self, "config_path", "config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                try:
                    return json.load(fh)
                except Exception:
                    return {}
        return {}

    def is_schema_default(self, key: str) -> bool:
        """Zwraca True, jeśli wartość została wstrzyknięta z domyślnego schematu."""

        return key in self._schema_defaults_injected

    def set(self, key: str, value: Any, who: str = "system"):
        idx = self._schema_idx
        opt = idx.get(key)
        if opt:
            self._validate_value(opt, value)
            scope = opt.get("scope", "global")
            target = {
                "global": self.global_cfg,
                "local": self.local_cfg,
                "secret": self.secrets,
            }.get(scope, self.global_cfg)
        else:
            # klucz spoza schematu → zapis do global
            target = self.global_cfg
        before_val = get_by_key(self.merged, key)
        self._schema_defaults_injected.discard(key)
        set_by_key(target, key, value)
        self.merged = self._merge_all()
        self._audit_change(key, before_val=before_val, after_val=value, who=who)

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
        migrate_dotted_keys(self.global_cfg)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"config_{stamp}.json"
        config_path = Path(self.config_path)
        print(f"[WM-DBG] backup_dir={backup_dir}")
        if config_path.exists():
            shutil.copy2(config_path, backup_path)
        else:
            self._save_json(str(backup_path), self.global_cfg or {})
        print(f"[WM-DBG] writing backup: {backup_path}")
        if self.global_cfg is not None:
            self._save_json(str(config_path), self.global_cfg)
            print(f"[WM-DBG] writing config: {config_path}")
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
        os.makedirs(AUDIT_DIR, exist_ok=True)
        path = os.path.join(AUDIT_DIR, "config_changes.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _prune_rollbacks(self):
        try:
            files = sorted(
                f
                for f in os.listdir(BACKUP_DIR)
                if os.path.isfile(os.path.join(BACKUP_DIR, f))
                and f.startswith("config_")
            )
            if len(files) > ROLLBACK_KEEP:
                for f in files[:-ROLLBACK_KEEP]:
                    try:
                        os.remove(os.path.join(BACKUP_DIR, f))
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
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
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
