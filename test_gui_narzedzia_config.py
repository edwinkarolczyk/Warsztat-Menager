import json
import types

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


def test_panel_refreshes_after_config_change(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.json"
    with open(gui_narzedzia.CONFIG_PATH, encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg["typy_narzedzi"] = ["Specjalny"]
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(gui_narzedzia, "CONFIG_PATH", str(cfg_path))

    class DummyVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, val):
            self.value = val

        def trace_add(self, *_):
            pass

    class DummyWidget:
        def __init__(self, *args, **kwargs):
            pass

        def pack(self, *args, **kwargs):
            pass

        def grid(self, *args, **kwargs):
            pass

        def config(self, *args, **kwargs):
            pass

        configure = config

        def bind(self, *args, **kwargs):
            pass

        def delete(self, *args, **kwargs):
            pass

        def get_children(self):
            return []

        def heading(self, *args, **kwargs):
            pass

        def column(self, *args, **kwargs):
            pass

        def insert(self, *args, **kwargs):
            pass

        def tag_configure(self, *args, **kwargs):
            pass

    dummy_tk = types.SimpleNamespace(StringVar=DummyVar)
    dummy_ttk = types.SimpleNamespace(
        Frame=DummyWidget,
        Label=DummyWidget,
        Entry=DummyWidget,
        Button=DummyWidget,
        Treeview=DummyWidget,
    )

    monkeypatch.setattr(gui_narzedzia, "tk", dummy_tk)
    monkeypatch.setattr(gui_narzedzia, "ttk", dummy_ttk)
    monkeypatch.setattr(gui_narzedzia, "apply_theme", lambda *a, **k: None)
    monkeypatch.setattr(gui_narzedzia, "clear_frame", lambda *a, **k: None)
    monkeypatch.setattr(gui_narzedzia, "_load_all_tools", lambda: [])

    gui_narzedzia.panel_narzedzia(DummyWidget(), DummyWidget())
    assert "Specjalny" in gui_narzedzia._types_from_config()
