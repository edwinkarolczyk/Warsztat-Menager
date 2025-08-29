import gui_narzedzia


def test_load_config_logs(monkeypatch):
    logs = []
    dialogs = []
    monkeypatch.setattr(gui_narzedzia.logger, "log_akcja", lambda m: logs.append(m))
    monkeypatch.setattr(
        gui_narzedzia.error_dialogs,
        "show_error_dialog",
        lambda title, msg, suggestion=None: dialogs.append((title, msg)),
    )

    def bad_open(*a, **kw):
        raise OSError("boom")

    monkeypatch.setattr("builtins.open", bad_open)
    cfg = gui_narzedzia._load_config()
    assert cfg == {}
    assert any("boom" in m for m in logs)
    assert any("boom" in msg for _, msg in dialogs)


def test_save_config_logs(monkeypatch):
    logs = []
    dialogs = []
    monkeypatch.setattr(gui_narzedzia.logger, "log_akcja", lambda m: logs.append(m))
    monkeypatch.setattr(
        gui_narzedzia.error_dialogs,
        "show_error_dialog",
        lambda title, msg, suggestion=None: dialogs.append((title, msg)),
    )

    def bad_open(*a, **kw):
        raise OSError("fail")

    monkeypatch.setattr("builtins.open", bad_open)
    gui_narzedzia._save_config({"a": 1})
    assert any("fail" in m for m in logs)
    assert any("fail" in msg for _, msg in dialogs)
