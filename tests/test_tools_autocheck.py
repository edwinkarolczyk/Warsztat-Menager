import json

import pytest

import tools_autocheck


@pytest.fixture
def write_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(tools_autocheck, "DATA_DIR", tmp_path)

    def _write(collection_id: str, status_id: str, payload) -> None:
        path = tmp_path / collection_id
        path.mkdir(exist_ok=True)
        (path / f"{status_id}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    return _write


def test_entry_flag_takes_precedence(write_entry):
    config = {"tools": {"auto_check_on_status_global": ["s1"]}}
    write_entry("col", "s1", {"auto_check_on_entry": False})
    assert not tools_autocheck.should_autocheck("s1", "col", config)


def test_global_list_used_when_no_entry_flag(write_entry):
    config = {"tools": {"auto_check_on_status_global": ["s2"]}}
    assert tools_autocheck.should_autocheck("s2", "col", config)


def test_none_returns_false(write_entry):
    config = {"tools": {"auto_check_on_status_global": []}}
    assert not tools_autocheck.should_autocheck("s3", "col", config)
