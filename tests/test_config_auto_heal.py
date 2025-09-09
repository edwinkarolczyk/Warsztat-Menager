import json
from pathlib import Path

import config_manager as cm
from config_manager import get_by_key, set_by_key


def test_auto_heals_and_persists_defaults(tmp_path, monkeypatch):
    schema = {
        "config_version": 1,
        "options": [
            {"key": "ui.theme", "type": "string"},
            {"key": "ui.language", "type": "string"},
            {"key": "backup.keep_last", "type": "int"},
        ],
    }

    paths = {
        "schema": tmp_path / "settings_schema.json",
        "defaults": tmp_path / "config.defaults.json",
        "global": tmp_path / "config.json",
        "local": tmp_path / "config.local.json",
        "secrets": tmp_path / "secrets.json",
        "audit": tmp_path / "audit",
        "backup": tmp_path / "backup_wersji",
    }
    paths["audit"].mkdir()
    paths["backup"].mkdir()

    for p, data in {
        paths["schema"]: schema,
        paths["defaults"]: {},
        paths["global"]: {},
        paths["local"]: {},
        paths["secrets"]: {},
    }.items():
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    monkeypatch.setattr(cm, "SCHEMA_PATH", str(paths["schema"]))
    monkeypatch.setattr(cm, "DEFAULTS_PATH", str(paths["defaults"]))
    monkeypatch.setattr(cm, "GLOBAL_PATH", str(paths["global"]))
    monkeypatch.setattr(cm, "LOCAL_PATH", str(paths["local"]))
    monkeypatch.setattr(cm, "SECRETS_PATH", str(paths["secrets"]))
    monkeypatch.setattr(cm, "AUDIT_DIR", str(paths["audit"]))
    monkeypatch.setattr(cm, "BACKUP_DIR", str(paths["backup"]))

    real_save = cm.ConfigManager._save_json
    calls: list[Path] = []

    def spy(self, path, data):
        calls.append(Path(path))
        real_save(self, path, data)

    monkeypatch.setattr(cm.ConfigManager, "_save_json", spy)

    mgr = cm.ConfigManager.refresh()

    assert get_by_key(mgr.global_cfg, "ui.theme") == "dark"
    assert get_by_key(mgr.global_cfg, "ui.language") == "pl"
    assert get_by_key(mgr.global_cfg, "backup.keep_last") == 10
    assert calls == [paths["global"]]

    set_by_key(mgr.global_cfg, "ui.language", "en")
    assert get_by_key(mgr.global_cfg, "ui.language") == "en"

    calls.clear()
    cm.ConfigManager.refresh()
    assert calls == []
