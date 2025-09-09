import json

import pytest

import tools
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
    monkeypatch.setattr(tools, "collections_paths", {})
    LZ._TOOLS_TEMPLATES_CACHE = None
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_tool_types()


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
    monkeypatch.setattr(tools, "collections_paths", {})
    LZ._TOOLS_TEMPLATES_CACHE = None
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_statuses(None, "T1")


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
    monkeypatch.setattr(tools, "collections_paths", {})
    LZ._TOOLS_TEMPLATES_CACHE = None
    assert LZ.get_tasks(None, "T1", "S1") == ["a", "b"]


def test_duplicate_ids(monkeypatch, tmp_path):
    data = {
        "types": [
            {"id": "T1", "statuses": []},
            {"id": "T1", "statuses": []},
        ]
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    monkeypatch.setattr(tools, "collections_paths", {})
    LZ._TOOLS_TEMPLATES_CACHE = None
    with pytest.raises(LZ.ToolTasksError):
        LZ.get_tool_types()


def test_variant_b(monkeypatch, tmp_path):
    c1 = {
        "types": [
            {
                "id": "T1",
                "statuses": [
                    {"id": "S1", "tasks": ["a"], "autocheck": True}
                ],
            }
        ]
    }
    c2 = {
        "types": [
            {
                "id": "T2",
                "statuses": [
                    {"id": "S2", "tasks": ["b"]}
                ],
            }
        ]
    }
    p1 = tmp_path / "c1.json"
    p2 = tmp_path / "c2.json"
    p1.write_text(json.dumps(c1, ensure_ascii=False, indent=2), encoding="utf-8")
    p2.write_text(json.dumps(c2, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(tools, "collections_paths", {"C1": str(p1), "C2": str(p2)})
    LZ._TOOLS_TEMPLATES_CACHE = None
    cols = sorted(LZ.get_collections(), key=lambda x: x["id"])
    assert cols == [{"id": "C1", "name": "C1"}, {"id": "C2", "name": "C2"}]
    assert LZ.get_tasks("C1", "T1", "S1") == ["a"]
    assert LZ.should_autocheck("C1", "T1", "S1") is True


def test_cache_invalidation(monkeypatch, tmp_path):
    data = {
        "types": [
            {
                "id": "T1",
                "statuses": [
                    {"id": "S1", "tasks": []}
                ],
            }
        ]
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(path))
    monkeypatch.setattr(tools, "collections_paths", {})
    LZ._TOOLS_TEMPLATES_CACHE = None
    assert LZ.get_tool_types() == [{"id": "T1", "name": "T1"}]
    path.write_text(json.dumps({"types": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    assert LZ.get_tool_types() == [{"id": "T1", "name": "T1"}]
    LZ.load_tools_templates(force=True)
    assert LZ.get_tool_types() == []
