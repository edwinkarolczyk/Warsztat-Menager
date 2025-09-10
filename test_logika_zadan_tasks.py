import json

import pytest

import logika_zadan as LZ


class DummyCfg:
    def __init__(self, enabled=None, default=None):
        self.enabled = enabled or ["NN"]
        self.default = default or self.enabled[0]

    def get(self, key, default=None):
        if key == "tools.collections_enabled":
            return list(self.enabled)
        if key == "tools.default_collection":
            return self.default
        return default


def _write(tmp_path, content):
    path = tmp_path / "zadania_narzedzia.json"
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_limit_types(monkeypatch, tmp_path):
    data = {
        "collections": {
            "NN": {
                "types": [{"id": str(i), "statuses": []} for i in range(9)]
            }
        }
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    monkeypatch.setattr(LZ, "ConfigManager", lambda: DummyCfg())
    LZ._TOOL_TASKS_CACHE = None
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_tool_types_list(collection="NN")


def test_limit_statuses(monkeypatch, tmp_path):
    data = {
        "collections": {
            "NN": {
                "types": [
                    {
                        "id": "T1",
                        "statuses": [{"id": str(i), "tasks": []} for i in range(9)],
                    }
                ]
            }
        }
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    monkeypatch.setattr(LZ, "ConfigManager", lambda: DummyCfg())
    LZ._TOOL_TASKS_CACHE = None
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_statuses_for_type("T1", collection="NN")


def test_get_tasks(monkeypatch, tmp_path):
    data = {
        "collections": {
            "NN": {
                "types": [
                    {
                        "id": "T1",
                        "statuses": [
                            {"id": "S1", "tasks": ["a", "b"]},
                        ],
                    }
                ]
            }
        }
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    monkeypatch.setattr(LZ, "ConfigManager", lambda: DummyCfg())
    LZ._TOOL_TASKS_CACHE = None
    assert LZ.get_tasks_for("T1", "S1", collection="NN") == ["a", "b"]


def test_force_reload(monkeypatch, tmp_path):
    data1 = {
        "collections": {
            "NN": {"types": [{"id": "T1", "name": "Old", "statuses": []}]}
        }
    }
    path = _write(tmp_path, data1)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    monkeypatch.setattr(LZ, "ConfigManager", lambda: DummyCfg())
    LZ._TOOL_TASKS_CACHE = None
    assert LZ.get_tool_types_list(collection="NN") == [{"id": "T1", "name": "Old"}]

    data2 = {
        "collections": {
            "NN": {"types": [{"id": "T1", "name": "New", "statuses": []}]}
        }
    }
    path.write_text(json.dumps(data2, ensure_ascii=False, indent=2), encoding="utf-8")

    assert LZ.get_tool_types_list(collection="NN")[0]["name"] == "Old"
    assert (
        LZ.get_tool_types_list(collection="NN", force=True)[0]["name"]
        == "New"
    )
    LZ._TOOL_TASKS_CACHE = None


def test_save_creates_file(monkeypatch, tmp_path):
    path = tmp_path / "zadania_narzedzia.json"
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))

    class Cfg:
        def get(self, key, default=None):
            mapping = {
                "tools.collections_enabled": ["A", "B"],
                "tools.default_collection": "A",
            }
            return mapping.get(key, default)

    monkeypatch.setattr(LZ, "ConfigManager", Cfg)
    LZ._TOOL_TASKS_CACHE = None
    LZ.save_tool_tasks({"collections": {}})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data["collections"].keys()) == {"A", "B"}


def test_legacy_format_migrated(monkeypatch, tmp_path):
    data = {"types": [{"id": "T1", "statuses": []}]}
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    monkeypatch.setattr(LZ, "ConfigManager", lambda: DummyCfg())
    LZ._TOOL_TASKS_CACHE = None
    types_list = LZ.get_tool_types_list(collection="NN")
    assert types_list[0]["id"] == "T1"
    migrated = json.loads(path.read_text(encoding="utf-8"))
    assert "collections" in migrated

