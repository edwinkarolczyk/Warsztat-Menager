import json

import tools_autocheck


def _write_entry(tmp_path, collection_id, status_id, payload):
    path = tmp_path / collection_id
    path.mkdir()
    (path / f"{status_id}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def test_entry_flag_takes_precedence(tmp_path, monkeypatch):
    config = {"tools": {"auto_check_on_status_global": ["s1"]}}
    _write_entry(tmp_path, "col", "s1", {"auto_check_on_entry": False})
    monkeypatch.setattr(tools_autocheck, "DATA_DIR", tmp_path)
    assert not tools_autocheck.should_autocheck("s1", "col", config)


def test_global_list_used_when_no_entry_flag(tmp_path, monkeypatch):
    config = {"tools": {"auto_check_on_status_global": ["s2"]}}
    monkeypatch.setattr(tools_autocheck, "DATA_DIR", tmp_path)
    assert tools_autocheck.should_autocheck("s2", "col", config)


def test_none_returns_false(tmp_path, monkeypatch):
    config = {"tools": {"auto_check_on_status_global": []}}
    monkeypatch.setattr(tools_autocheck, "DATA_DIR", tmp_path)
    assert not tools_autocheck.should_autocheck("s3", "col", config)
