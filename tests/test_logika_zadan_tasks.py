import json
from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
import logika_zadan as LZ


def _write(tmp_path, content):
    path = tmp_path / "zadania_narzedzia.json"
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


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
    LZ._TOOL_TASKS_CACHE = None
    with pytest.raises(LZ.ToolTasksError) as exc:
        LZ.get_tool_types_list(collection="NN")
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
    LZ._TOOL_TASKS_CACHE = None
    with pytest.raises(LZ.ToolTasksError) as exc:
        LZ.get_statuses_for_type("T1", collection="NN")
    assert "Powtarzające się id statusu" in str(exc.value)
