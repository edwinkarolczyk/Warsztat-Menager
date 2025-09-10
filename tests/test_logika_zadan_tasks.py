import json
from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
import logika_zadan as LZ


SETTINGS = {"tools": {"collections_enabled": ["NN"], "auto_check_on_status_global": []}}


def _write(tmp_path, content):
    path = tmp_path / "zadania_narzedzia.json"
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_limit_collections(monkeypatch, tmp_path):
    data = {"collections": {str(i): {"types": []} for i in range(9)}}
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_collections(SETTINGS)


def test_limit_types(monkeypatch, tmp_path):
    data = {
        "collections": {
            "NN": {"types": [{"id": str(i), "statuses": []} for i in range(9)]}
        }
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_tool_types("NN", SETTINGS)


def test_limit_statuses(monkeypatch, tmp_path):
    data = {
        "collections": {
            "NN": {
                "types": [
                    {
                        "id": "T1",
                        "statuses": [
                            {"id": str(i), "tasks": []} for i in range(9)
                        ],
                    }
                ]
            }
        }
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_statuses("NN", "T1", SETTINGS)


def test_duplicate_type_ids(monkeypatch, tmp_path):
    data = {
        "collections": {
            "NN": {
                "types": [
                    {"id": "T1", "statuses": []},
                    {"id": "T1", "statuses": []},
                ]
            }
        }
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    with pytest.raises(LZ.ToolTasksError) as exc:
        LZ.get_tool_types("NN", SETTINGS)
    assert "Powtarzające się id typu" in str(exc.value)


def test_duplicate_status_ids(monkeypatch, tmp_path):
    data = {
        "collections": {
            "NN": {
                "types": [
                    {
                        "id": "T1",
                        "statuses": [
                            {"id": "S1", "tasks": []},
                            {"id": "S1", "tasks": []},
                        ],
                    }
                ]
            }
        }
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    with pytest.raises(LZ.ToolTasksError) as exc:
        LZ.get_statuses("NN", "T1", SETTINGS)
    assert "Powtarzające się id statusu" in str(exc.value)


def test_get_tasks_and_cache(monkeypatch, tmp_path):
    data1 = {
        "collections": {
            "NN": {
                "types": [
                    {
                        "id": "T1",
                        "name": "Old",
                        "statuses": [{"id": "S1", "tasks": ["a"]}],
                    }
                ]
            }
        }
    }
    path = _write(tmp_path, data1)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    assert LZ.get_tasks("NN", "T1", "S1", SETTINGS) == ["a"]

    data2 = {
        "collections": {
            "NN": {
                "types": [
                    {
                        "id": "T1",
                        "name": "New",
                        "statuses": [{"id": "S1", "tasks": ["b"]}],
                    }
                ]
            }
        }
    }
    path.write_text(json.dumps(data2, ensure_ascii=False, indent=2), encoding="utf-8")
    # cache still holds old values
    assert LZ.get_tool_types("NN", SETTINGS)[0]["name"] == "Old"
    LZ.invalidate_cache()
    assert LZ.get_tool_types("NN", SETTINGS)[0]["name"] == "New"


def test_legacy_types_migrated(monkeypatch, tmp_path):
    legacy = {"types": [{"id": "T1", "statuses": []}]}
    path = _write(tmp_path, legacy)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))

    class Cfg:
        def get(self, key, default=None):
            if key == "tools.collections_enabled":
                return ["NN"]
            if key == "tools.default_collection":
                return "NN"
            return default

    monkeypatch.setattr(LZ, "ConfigManager", lambda: Cfg())
    LZ.invalidate_cache()
    types = LZ.get_tool_types("NN", SETTINGS)
    assert types and types[0]["id"] == "T1"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "collections" in data and "types" not in data

