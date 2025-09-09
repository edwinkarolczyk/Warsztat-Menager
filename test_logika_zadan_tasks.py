import json

import pytest

import logika_zadan as LZ


def _write(tmp_path, content):
    path = tmp_path / "zadania_narzedzia.json"
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_limit_types(monkeypatch, tmp_path):
    data = {
        "types": [
            {"id": str(i), "statuses": []} for i in range(9)
        ]
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ._TOOL_TASKS_CACHE = None
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_tool_types_list()


def test_limit_statuses(monkeypatch, tmp_path):
    data = {
        "types": [
            {
                "id": "T1",
                "statuses": [{"id": str(i), "tasks": []} for i in range(9)],
            }
        ]
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ._TOOL_TASKS_CACHE = None
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_statuses_for_type("T1")


def test_get_tasks(monkeypatch, tmp_path):
    data = {
        "types": [
            {
                "id": "T1",
                "statuses": [
                    {"id": "S1", "tasks": ["a", "b"]},
                ],
            }
        ]
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ._TOOL_TASKS_CACHE = None
    assert LZ.get_tasks_for("T1", "S1") == ["a", "b"]


def test_force_reload(monkeypatch, tmp_path):
    data1 = {"types": [{"id": "T1", "name": "Old", "statuses": []}]}
    path = _write(tmp_path, data1)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    LZ._TOOL_TASKS_CACHE = None
    assert LZ.get_tool_types_list() == [{"id": "T1", "name": "Old"}]

    data2 = {"types": [{"id": "T1", "name": "New", "statuses": []}]}
    path.write_text(json.dumps(data2, ensure_ascii=False, indent=2), encoding="utf-8")

    assert LZ.get_tool_types_list()[0]["name"] == "Old"
    assert LZ.get_tool_types_list(force=True)[0]["name"] == "New"
    LZ._TOOL_TASKS_CACHE = None
