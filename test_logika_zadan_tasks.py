import json
import os

import pytest

import logika_zadan as LZ


def _write(tmp_path, content):
    path = tmp_path / "zadania_narzedzia.json"
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_limit_types(monkeypatch, tmp_path, caplog):
    data = {
        "types": [
            {"id": str(i), "statuses": []} for i in range(9)
        ]
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    with caplog.at_level("WARNING"):
        assert LZ.get_tool_types_list() == []
    assert "Przekroczono maksymalną liczbę typów" in caplog.text


def test_limit_statuses(monkeypatch, tmp_path, caplog):
    data = {
        "types": [
            {
                "id": "T1",
                "statuses": [{"id": str(i), "tasks": []} for i in range(9)],
            }
        ]
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    with caplog.at_level("WARNING"):
        assert LZ.get_statuses_for_type("T1") == []
    assert "Przekroczono maksymalną liczbę statusów" in caplog.text


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
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    assert LZ.get_tasks_for("T1", "S1") == ["a", "b"]


def test_force_reload(monkeypatch, tmp_path):
    data1 = {"types": [{"id": "T1", "name": "Old", "statuses": []}]}
    path = _write(tmp_path, data1)
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    assert LZ.get_tool_types_list() == [{"id": "T1", "name": "Old"}]

    data2 = {"types": [{"id": "T1", "name": "New", "statuses": []}]}
    prev_mtime = path.stat().st_mtime
    path.write_text(json.dumps(data2, ensure_ascii=False, indent=2), encoding="utf-8")
    os.utime(path, (prev_mtime, prev_mtime))

    assert LZ.get_tool_types_list()[0]["name"] == "Old"
    assert LZ.get_tool_types_list(force=True)[0]["name"] == "New"


def test_reload_on_mtime_change(monkeypatch, tmp_path):
    data1 = {"types": [{"id": "T1", "name": "Old", "statuses": []}]}
    path = _write(tmp_path, data1)
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    assert LZ.get_tool_types_list() == [{"id": "T1", "name": "Old"}]

    data2 = {"types": [{"id": "T1", "name": "New", "statuses": []}]}
    path.write_text(json.dumps(data2, ensure_ascii=False, indent=2), encoding="utf-8")
    prev_mtime = path.stat().st_mtime
    os.utime(path, (prev_mtime + 1, prev_mtime + 1))
    assert LZ.get_tool_types_list()[0]["name"] == "New"
