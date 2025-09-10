import json
import os
from pathlib import Path
import sys
import threading

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
import logika_zadan as LZ
from config_manager import ConfigManager


def _write(tmp_path, content):
    path = tmp_path / "zadania_narzedzia.json"
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_duplicate_type_ids(monkeypatch, tmp_path, caplog):
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
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    with caplog.at_level("WARNING"):
        assert LZ.get_tool_types_list(collection="NN") == []
    assert "Powtarzające się id typu" in caplog.text


def test_duplicate_status_ids(monkeypatch, tmp_path, caplog):
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
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    with caplog.at_level("WARNING"):
        assert LZ.get_statuses_for_type("T1", collection="NN") == []
    assert "Powtarzające się id statusu" in caplog.text


def test_migrate_plain_list(monkeypatch, tmp_path):
    ConfigManager.refresh()
    data = [{"id": "T1", "statuses": []}]
    path = tmp_path / "zadania_narzedzia.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    types = LZ.get_tool_types_list(collection="NN")
    assert types and types[0]["id"] == "T1"
    with path.open(encoding="utf-8") as fh:
        stored = json.load(fh)
    assert "collections" in stored
    assert stored["collections"]["NN"]["types"][0]["id"] == "T1"


def test_cache_invalidation(monkeypatch, tmp_path):
    data1 = {
        "collections": {
            "NN": {
                "types": [
                    {"id": "T1", "statuses": [{"id": "S1", "tasks": ["A"]}]}
                ]
            }
        }
    }
    path = _write(tmp_path, data1)
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    assert LZ.get_tasks("T1", "S1", "NN") == ["A"]
    mtime = os.path.getmtime(path)
    data2 = {
        "collections": {
            "NN": {
                "types": [
                    {"id": "T1", "statuses": [{"id": "S1", "tasks": ["B"]}]}
                ]
            }
        }
    }
    path.write_text(json.dumps(data2, ensure_ascii=False, indent=2), encoding="utf-8")
    orig_getmtime = os.path.getmtime
    monkeypatch.setattr(os.path, "getmtime", lambda _p: mtime)
    assert LZ.get_tasks("T1", "S1", "NN") == ["A"]
    monkeypatch.setattr(os.path, "getmtime", orig_getmtime)
    LZ.invalidate_cache()
    assert LZ.get_tasks("T1", "S1", "NN") == ["B"]


def test_concurrent_access(monkeypatch, tmp_path):
    data = {
        "collections": {
            "NN": {
                "types": [
                    {"id": "T1", "statuses": []}
                ]
            }
        }
    }
    path = _write(tmp_path, data)
    monkeypatch.setattr(LZ, "_TASKS_PATH", str(path))
    LZ.invalidate_cache()
    results = []

    def worker():
        results.append(LZ.get_tool_types("NN"))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(r == [{"id": "T1", "name": "T1"}] for r in results)
