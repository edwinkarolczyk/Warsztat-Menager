import json

import pytest

import logika_zadan as LZ


def _write(tmp_path, content):
    path = tmp_path / "zadania_narzedzia.json"
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_limit_types(monkeypatch, tmp_path):
    data = {
        "collections": {
            "C": {"types": [{"id": str(i), "statuses": []} for i in range(9)]}
        }
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ._TOOLS_TEMPLATES_CACHE = None
    settings = {"tools": {"collections_enabled": ["C"]}}
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_tool_types("C", settings)


def test_limit_statuses(monkeypatch, tmp_path):
    data = {
        "collections": {
            "C": {
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
    LZ._TOOLS_TEMPLATES_CACHE = None
    settings = {"tools": {"collections_enabled": ["C"]}}
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_statuses("C", "T1", settings)


def test_get_tasks(monkeypatch, tmp_path):
    data = {
        "collections": {
            "C": {
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
    LZ._TOOLS_TEMPLATES_CACHE = None
    settings = {"tools": {"collections_enabled": ["C"]}}
    assert LZ.get_tasks("C", "T1", "S1", settings) == ["a", "b"]


def test_force_reload(monkeypatch, tmp_path):
    data1 = {
        "collections": {
            "C": {"types": [{"id": "T1", "name": "Old", "statuses": []}]}
        }
    }
    path = _write(tmp_path, data1)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ._TOOLS_TEMPLATES_CACHE = None
    settings = {"tools": {"collections_enabled": ["C"]}}
    assert LZ.get_tool_types("C", settings) == [{"id": "T1", "name": "Old"}]

    data2 = {
        "collections": {
            "C": {"types": [{"id": "T1", "name": "New", "statuses": []}]}
        }
    }
    path.write_text(json.dumps(data2, ensure_ascii=False, indent=2), encoding="utf-8")

    assert LZ.get_tool_types("C", settings)[0]["name"] == "Old"
    LZ.load_tools_templates(force=True)
    assert LZ.get_tool_types("C", settings)[0]["name"] == "New"
    LZ._TOOLS_TEMPLATES_CACHE = None
