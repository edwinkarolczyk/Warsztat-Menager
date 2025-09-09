import json

import logika_zadan as LZ


def _write(path, content):
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


def test_old_schema_wrapped_as_nn(monkeypatch, tmp_path):
    data = {"types": [{"id": "T1", "statuses": []}]}
    tasks = tmp_path / "zadania_narzedzia.json"
    _write(tasks, data)
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(tasks))
    monkeypatch.setattr(LZ, "cfg_path", lambda name: str(tmp_path / name))
    LZ._TOOL_TASKS_CACHE = None
    types = LZ.get_tool_types_list()
    assert types == [{"id": "T1", "name": "T1"}]
    assert list(LZ._load_tool_tasks().keys()) == ["NN"]


def test_variant_b_requires_config(monkeypatch, tmp_path):
    default = {"types": [{"id": "A", "statuses": []}]}
    alt = {"types": [{"id": "B", "statuses": []}]}
    default_path = tmp_path / "default.json"
    alt_path = tmp_path / "alt.json"
    _write(default_path, default)
    _write(alt_path, alt)

    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(LZ, "cfg_path", lambda name: str(tmp_path / name))
    monkeypatch.setattr(LZ, "TOOL_TASKS_PATH", str(default_path))

    LZ._TOOL_TASKS_CACHE = None
    # without collections_paths only default is used
    assert LZ.get_tool_types_list() == [{"id": "A", "name": "A"}]

    cfg.write_text(
        json.dumps(
            {"tools": {"collections_paths": {"NN": "default.json", "B": "alt.json"}}},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    LZ._TOOL_TASKS_CACHE = None
    # with collections_paths mapping we can access other collection
    assert LZ.get_tool_types_list("B") == [{"id": "B", "name": "B"}]
