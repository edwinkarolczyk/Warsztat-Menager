import tools_autocheck


def test_status_flag_takes_precedence(monkeypatch):
    monkeypatch.setattr(tools_autocheck, "AUTOCHECK_IDS", {"1"})
    tool = {"id": "1", "autocheck": False}
    assert not tools_autocheck.should_autocheck(tool)


def test_global_list_used_when_no_flag(monkeypatch):
    monkeypatch.setattr(tools_autocheck, "AUTOCHECK_IDS", {"2"})
    tool = {"id": "2"}
    assert tools_autocheck.should_autocheck(tool)


def test_none_returns_false(monkeypatch):
    monkeypatch.setattr(tools_autocheck, "AUTOCHECK_IDS", set())
    tool = {"id": "3"}
    assert not tools_autocheck.should_autocheck(tool)
