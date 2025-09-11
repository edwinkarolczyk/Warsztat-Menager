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
import json, os, shutil, datetime, time
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

from utils.path_utils import cfg_path

# Ścieżki domyślne (katalog główny aplikacji)
SCHEMA_PATH = cfg_path("settings_schema.json")
DEFAULTS_PATH = cfg_path("config.defaults.json")
GLOBAL_PATH = cfg_path("config.json")
LOCAL_PATH = cfg_path("config.local.json")
SECRETS_PATH = cfg_path("secrets.json")
AUDIT_DIR = cfg_path("audit")
BACKUP_DIR = cfg_path("backup_wersji")
ROLLBACK_KEEP = 10

# Initialize module logger
logger = logging.getLogger(__name__)


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

    @classmethod
    def _ensure_defaults_from_schema(
        cls, cfg: Dict[str, Any], schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Uzupełnia brakujące klucze domyślnymi wartościami ze schematu."""

        def apply_default(key: str | None, default: Any) -> None:
            if key and default is not None and key not in cfg:
                print(f"[WM-DBG] [SETTINGS] default injected: {key}={default}")
                cfg[key] = default

        for field in cls._iter_schema_fields(schema):
            apply_default(field.get("key"), field.get("default"))
        return cfg
    # >>> WM PATCH END

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
        self.global_cfg = self._load_json(self.config_path) or {}

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

        self.global_cfg = self._ensure_defaults_from_schema(
            self.global_cfg, self.schema
        )
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
        return cls(config_path=config_path, schema_path=schema_path)

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
        set_by_key(target, key, value)
        self.merged = self._merge_all()
        self._audit_change(key, before_val=before_val, after_val=value, who=who)

    def save_all(self):
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
