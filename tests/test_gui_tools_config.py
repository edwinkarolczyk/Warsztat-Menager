import json
import pytest
import gui_tools_config as gtc
import logika_zadan as LZ


def _sample_data():
    return {
        "types": [
            {
                "id": "t1",
                "name": "T1",
                "statuses": [
                    {"id": "s1", "name": "S1", "tasks": ["a"], "auto_check_on_entry": True}
                ],
            }
        ]
    }


def test_validate_structure_limits():
    gtc.validate_structure(_sample_data())
    dup_type = {"types": [{"id": "t1", "statuses": []}, {"id": "t1", "statuses": []}]}
    with pytest.raises(ValueError):
        gtc.validate_structure(dup_type)
    dup_status = {"types": [{"id": "t1", "statuses": [{"id": "s1", "tasks": []}, {"id": "s1", "tasks": []}]}]}
    with pytest.raises(ValueError):
        gtc.validate_structure(dup_status)
    too_many_tasks = {"types": [{"id": "t1", "statuses": [{"id": "s1", "tasks": [str(i) for i in range(9)]}]}]}
    with pytest.raises(ValueError):
        gtc.validate_structure(too_many_tasks)


def test_save_collection_variant_a(monkeypatch, tmp_path):
    data = _sample_data()
    monkeypatch.setattr(gtc, "collections_paths", None)
    monkeypatch.setattr(gtc, "DEFAULT_PATH", str(tmp_path / "tools.json"))
    LZ._TOOL_TASKS_CACHE = [1]
    gtc.save_collection("NN", data)
    saved = json.loads((tmp_path / "tools.json").read_text(encoding="utf-8"))
    assert saved["NN"] == data
    assert LZ._TOOL_TASKS_CACHE is None


def test_save_collection_variant_b_callable(monkeypatch, tmp_path):
    data = _sample_data()
    def fake_paths(coll):
        return tmp_path / f"{coll}.json"
    monkeypatch.setattr(gtc, "collections_paths", fake_paths)
    LZ._TOOL_TASKS_CACHE = [1]
    gtc.save_collection("ST", data)
    saved = json.loads((tmp_path / "ST.json").read_text(encoding="utf-8"))
    assert saved == data
    assert LZ._TOOL_TASKS_CACHE is None
