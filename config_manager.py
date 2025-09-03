"""
Config Manager – warstwy: defaults → global → local → secrets
Wersja: 1.0.1

Funkcje:
- Ładowanie i scalanie warstw configu
- Walidacja wg settings_schema.json
- Zapis z backupem i audytem zmian
- Import/eksport (eksport bez sekretów)
- Rollback przez katalogi w backup_wersji (utrzymujemy ostatnie 10)
"""

from __future__ import annotations
import json, os, shutil, datetime
import logging
from typing import Any, Dict, List

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
    def __init__(self):
        self.schema = self._load_json_or_raise(
            SCHEMA_PATH, msg_prefix="Brak pliku schematu"
        )
        self._schema_idx: Dict[str, Dict[str, Any]] = {
            opt["key"]: opt for opt in self.schema.get("options", [])
        }
        self.defaults = self._load_json(DEFAULTS_PATH) or {}
        self.global_cfg = self._load_json(GLOBAL_PATH) or {}
        self.local_cfg = self._load_json(LOCAL_PATH) or {}
        self.secrets = self._load_json(SECRETS_PATH) or {}
        self._ensure_dirs()
        self.merged = self._merge_all()
        self._validate_all()

        # Settings for unsaved changes handling
        self.warn_on_unsaved = self.get("warn_on_unsaved", True)
        self.autosave_draft = self.get("autosave_draft", False)
        self.autosave_draft_interval_sec = self.get(
            "autosave_draft_interval_sec", 15
        )

    # ========== I/O pomocnicze ==========
    def _ensure_dirs(self):
        os.makedirs(AUDIT_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)

    def _load_json(self, path: str) -> Dict[str, Any] | None:
        try:
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
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
        os.replace(tmp, path)

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
        for key, value in flatten(self.merged).items():
            if key not in idx:
                # klucz spoza schematu – dopuszczamy (forward‑compat), ale można by zalogować
                continue
            self._validate_value(idx[key], value)

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
            if value not in opt.get("enum", []):
                raise ConfigError(f"{opt['key']}: {value} nie w {opt.get('enum')}")
        elif t == "array":
            if not isinstance(value, list):
                raise ConfigError(
                    f"{opt['key']}: oczekiwano listy, dostano {type(value).__name__}"
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
        # backup aktualnych warstw z timestampem
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        bdir = os.path.join(BACKUP_DIR, stamp)
        os.makedirs(bdir, exist_ok=True)
        for path in (GLOBAL_PATH, LOCAL_PATH, SECRETS_PATH):
            if os.path.exists(path):
                shutil.copy2(path, os.path.join(bdir, os.path.basename(path)))
        self._prune_rollbacks()
        # zapis
        if self.global_cfg is not None:
            self._save_json(GLOBAL_PATH, self.global_cfg)
        if self.local_cfg is not None:
            self._save_json(LOCAL_PATH, self.local_cfg)
        if self.secrets is not None:
            self._save_json(SECRETS_PATH, self.secrets)

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
            subdirs = sorted(
                [
                    d
                    for d in os.listdir(BACKUP_DIR)
                    if os.path.isdir(os.path.join(BACKUP_DIR, d))
                ]
            )
            if len(subdirs) > ROLLBACK_KEEP:
                for d in subdirs[:-ROLLBACK_KEEP]:
                    shutil.rmtree(os.path.join(BACKUP_DIR, d), ignore_errors=True)
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
