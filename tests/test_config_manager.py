import json
import shutil
from pathlib import Path

import pytest

import config_manager as cm


@pytest.fixture
def make_manager(tmp_path, monkeypatch):
    def _make_manager(
        defaults=None,
        global_cfg=None,
        local_cfg=None,
        secrets=None,
        schema=None,
        rollback_keep=None,
    ):
        defaults = defaults or {}
        global_cfg = global_cfg or {}
        local_cfg = local_cfg or {}
        secrets = secrets or {}
        schema = schema or {"config_version": 1, "options": []}

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

        data_map = {
            paths["schema"]: schema,
            paths["defaults"]: defaults,
            paths["global"]: global_cfg,
            paths["local"]: local_cfg,
            paths["secrets"]: secrets,
        }
        for path, data in data_map.items():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        monkeypatch.setattr(cm, "SCHEMA_PATH", str(paths["schema"]))
        monkeypatch.setattr(cm, "DEFAULTS_PATH", str(paths["defaults"]))
        monkeypatch.setattr(cm, "GLOBAL_PATH", str(paths["global"]))
        monkeypatch.setattr(cm, "LOCAL_PATH", str(paths["local"]))
        monkeypatch.setattr(cm, "SECRETS_PATH", str(paths["secrets"]))
        monkeypatch.setattr(cm, "AUDIT_DIR", str(paths["audit"]))
        monkeypatch.setattr(cm, "BACKUP_DIR", str(paths["backup"]))
        if rollback_keep is not None:
            monkeypatch.setattr(cm, "ROLLBACK_KEEP", rollback_keep)

        return cm.ConfigManager.refresh(), paths

    return _make_manager


def test_load_and_merge_overrides(make_manager):
    schema = {
        "config_version": 1,
        "options": [
            {"key": "a", "type": "int"},
            {"key": "b.x", "type": "int"},
            {"key": "c", "type": "int"},
            {"key": "secret", "type": "string", "scope": "secret"},
        ],
    }
    defaults = {"a": 1, "b": {"x": 1}}
    global_cfg = {"b": {"x": 2}, "c": 3}
    local_cfg = {"c": 4}
    secrets = {"secret": "s"}

    mgr, _ = make_manager(
        defaults=defaults,
        global_cfg=global_cfg,
        local_cfg=local_cfg,
        secrets=secrets,
        schema=schema,
    )

    assert mgr.merged == {"a": 1, "b": {"x": 2}, "c": 4, "secret": "s"}


def test_set_and_save_all_persistence(make_manager):
    schema = {
        "config_version": 1,
        "options": [{"key": "foo", "type": "int"}],
    }
    defaults = {"foo": 1}

    mgr, paths = make_manager(defaults=defaults, schema=schema)
    mgr.set("foo", 5, who="tester")
    assert mgr.get("foo") == 5

    mgr.save_all()

    with open(paths["global"], encoding="utf-8") as f:
        assert json.load(f)["foo"] == 5

    reloaded = cm.ConfigManager.refresh()
    assert reloaded.get("foo") == 5


def test_audit_and_prune_rollbacks(make_manager):
    schema = {
        "config_version": 1,
        "options": [{"key": "foo", "type": "int"}],
    }
    defaults = {"foo": 1}

    mgr, paths = make_manager(defaults=defaults, schema=schema, rollback_keep=2)

    mgr.set("foo", 2, who="tester")

    audit_file = Path(paths["audit"]) / "config_changes.jsonl"
    with open(audit_file, encoding="utf-8") as f:
        rec = json.loads(f.readline())
    assert rec["key"] == "foo"
    assert rec["before"] == 1
    assert rec["after"] == 2
    assert rec["user"] == "tester"

    for name in [
        "config_20200101_000000.json",
        "config_20200102_000000.json",
        "config_20200103_000000.json",
    ]:
        (Path(paths["backup"]) / name).touch()

    mgr.save_all()

    files = sorted(f.name for f in Path(paths["backup"]).iterdir() if f.is_file())
    assert len(files) == 2
    assert "config_20200101_000000.json" not in files
    assert "config_20200102_000000.json" not in files


def test_validate_dict_value_type(make_manager):
    schema = {
        "config_version": 1,
        "options": [
            {
                "key": "progi_alertow_surowce",
                "type": "dict",
                "value_type": "float",
            },
            {
                "key": "jednostki_miary",
                "type": "dict",
                "value_type": "string",
            },
        ],
    }
    defaults = {
        "progi_alertow_surowce": {"stal": 10.0},
        "jednostki_miary": {"szt": "sztuka"},
    }

    mgr, paths = make_manager(defaults=defaults, schema=schema)
    assert mgr.get("progi_alertow_surowce") == {"stal": 10.0}
    assert mgr.get("jednostki_miary") == {"szt": "sztuka"}

    for bad_defaults in [
        {"progi_alertow_surowce": 1},
        {"progi_alertow_surowce": {"stal": "dużo"}},
        {"jednostki_miary": {"szt": 1}},
    ]:
        shutil.rmtree(paths["audit"], ignore_errors=True)
        shutil.rmtree(paths["backup"], ignore_errors=True)
        with pytest.raises(cm.ConfigError):
            make_manager(defaults=bad_defaults, schema=schema)


def test_secret_admin_pin_masked(make_manager):
    schema = {
        "config_version": 1,
        "options": [{"key": "secrets.admin_pin", "type": "string"}],
    }
    defaults = {"secrets": {"admin_pin": ""}}

    mgr, paths = make_manager(defaults=defaults, schema=schema)
    mgr.set("secrets.admin_pin", "1234", who="tester")
    mgr.save_all()

    with open(paths["global"], encoding="utf-8") as f:
        data = json.load(f)
    assert data["secrets"]["admin_pin"] == "1234"

    reloaded = cm.ConfigManager.refresh()
    assert reloaded.get("secrets.admin_pin") == "1234"

    audit_file = Path(paths["audit"]) / "config_changes.jsonl"
    with open(audit_file, encoding="utf-8") as f:
        rec = json.loads(f.readline())
    assert rec["before"] == "***"
    assert rec["after"] == "***"


def test_refresh_with_custom_paths(tmp_path):
    schema = {"config_version": 1, "options": [{"key": "a", "type": "int"}]}
    cfg_data = {"a": 5}
    schema_path = tmp_path / "schema.json"
    cfg_path = tmp_path / "custom.json"
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg_data, f, ensure_ascii=False, indent=2)

    mgr = cm.ConfigManager.refresh(
        config_path=str(cfg_path), schema_path=str(schema_path)
    )
    try:
        assert mgr.get("a") == 5
    finally:
        cm.ConfigManager.refresh()


def test_backup_cloud_persistence(make_manager):
    schema = {
        "config_version": 1,
        "options": [
            {"key": "backup.cloud.url", "type": "string"},
            {"key": "backup.cloud.username", "type": "string"},
            {"key": "backup.cloud.password", "type": "string"},
            {"key": "backup.cloud.folder", "type": "string"},
        ],
    }
    defaults = {
        "backup": {
            "cloud": {
                "url": "",
                "username": "",
                "password": "",
                "folder": "",
            }
        }
    }

    mgr, paths = make_manager(defaults=defaults, schema=schema)
    assert mgr.get("backup.cloud.url") == ""
    assert mgr.get("backup.cloud.username") == ""
    assert mgr.get("backup.cloud.password") == ""
    assert mgr.get("backup.cloud.folder") == ""

    mgr.set("backup.cloud.url", "https://example.com")
    mgr.set("backup.cloud.username", "alice")
    mgr.set("backup.cloud.password", "secret")
    mgr.set("backup.cloud.folder", "/remote")
    mgr.save_all()

    with open(paths["global"], encoding="utf-8") as f:
        data = json.load(f)
    assert data["backup"]["cloud"]["url"] == "https://example.com"
    assert data["backup"]["cloud"]["username"] == "alice"
    assert data["backup"]["cloud"]["password"] == "secret"
    assert data["backup"]["cloud"]["folder"] == "/remote"

    reloaded = cm.ConfigManager.refresh()
    assert reloaded.get("backup.cloud.url") == "https://example.com"
    assert reloaded.get("backup.cloud.username") == "alice"
    assert reloaded.get("backup.cloud.password") == "secret"
    assert reloaded.get("backup.cloud.folder") == "/remote"
