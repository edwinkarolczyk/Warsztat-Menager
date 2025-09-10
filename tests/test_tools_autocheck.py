from pathlib import Path

import pytest

import tools_autocheck


@pytest.fixture(autouse=True)
def sample_data_dir(monkeypatch):
    """Point :mod:`tools_autocheck` to bundled fixture data."""

    path = Path(__file__).parent / "fixtures" / "tools_autocheck"
    monkeypatch.setattr(tools_autocheck, "DATA_DIR", path)
    return path


def test_entry_flag_takes_precedence():
    config = {"tools": {"auto_check_on_status_global": ["s1"]}}
    assert not tools_autocheck.should_autocheck("s1", "col", config)


def test_entry_flag_true_overrides_global():
    config = {"tools": {"auto_check_on_status_global": []}}
    assert tools_autocheck.should_autocheck("s4", "col", config)


def test_global_list_used_when_no_entry_flag():
    config = {"tools": {"auto_check_on_status_global": ["s2"]}}
    assert tools_autocheck.should_autocheck("s2", "col", config)


def test_none_returns_false():
    config = {"tools": {"auto_check_on_status_global": []}}
    assert not tools_autocheck.should_autocheck("s3", "col", config)
