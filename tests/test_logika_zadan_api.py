import json
from pathlib import Path

import logika_zadan as LZ


def test_get_collections_and_default_collection(monkeypatch, tmp_path):
    data = {"collections": {"C1": {"types": []}, "C2": {"types": []}}}
    path = tmp_path / "zadania_narzedzia.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    assert LZ.get_collections() == [
        {"id": "C1", "name": "C1"},
        {"id": "C2", "name": "C2"},
    ]
    cfg = {
        "tools.collections_enabled": ["C1", "C2"],
        "tools.default_collection": "C2",
    }
    assert LZ.get_default_collection(cfg) == "C2"


def test_get_tool_types_statuses_and_tasks(monkeypatch, tmp_path):
    data = {
        "collections": {
            "C1": {
                "types": [
                    {
                        "id": "T1",
                        "statuses": [{"id": "S1", "tasks": ["A", "B"]}],
                    }
                ]
            }
        }
    }
    path = tmp_path / "zadania_narzedzia.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    assert LZ.get_tool_types("C1") == [{"id": "T1", "name": "T1"}]
    assert LZ.get_statuses("T1", "C1") == [{"id": "S1", "name": "S1"}]
    assert LZ.get_tasks("T1", "S1", "C1") == ["A", "B"]


def test_should_autocheck_respects_global_status():
    cfg = {"tools": {"auto_check_on_status_global": ["S1"]}}
    assert LZ.should_autocheck("S1", "C1", cfg)
    assert not LZ.should_autocheck("S2", "C1", cfg)
