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
        "2020-01-01_00-00-00",
        "2020-01-02_00-00-00",
        "2020-01-03_00-00-00",
    ]:
        (Path(paths["backup"]) / name).mkdir()

    mgr.save_all()

    subdirs = sorted(d.name for d in Path(paths["backup"]).iterdir() if d.is_dir())
    assert len(subdirs) == 2
    assert "2020-01-01_00-00-00" not in subdirs
    assert "2020-01-02_00-00-00" not in subdirs


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
