import os
import sys
import types

import importlib

import gui_settings


def test_open_tools_config_invalidates_cache(monkeypatch):
    called = {"n": 0, "path": None, "wait": 0}

    def invalidate():
        called["n"] += 1

    monkeypatch.setattr(
        gui_settings, "LZ", types.SimpleNamespace(invalidate_cache=invalidate)
    )
    monkeypatch.setattr(gui_settings, "_ensure_topmost", lambda win: None)

    class DummyDialog:
        def __init__(self, master=None, *, path="", on_save=None):
            self.on_save = on_save
            called["path"] = path
            dummy_holder["instance"] = self

    dummy_holder = {}
    monkeypatch.setattr(gui_settings, "ToolsConfigDialog", DummyDialog)

    dummy_self = gui_settings.SettingsPanel.__new__(gui_settings.SettingsPanel)
    dummy_self.master = types.SimpleNamespace(winfo_toplevel=lambda: None)
    dummy_self.wait_window = lambda win: called.__setitem__("wait", called["wait"] + 1)
    dummy_self.cfg = types.SimpleNamespace(get=lambda key, default=None: None)

    def reload_section():
        called.setdefault("reload", 0)
        called["reload"] += 1

    dummy_self._reload_tools_section = reload_section

    gui_settings.SettingsPanel._open_tools_config(dummy_self)

    dummy_holder["instance"].on_save()

    assert called["n"] == 1
    assert called["wait"] == 1
    assert called["path"] == os.path.join("data", "zadania_narzedzia.json")
    assert called.get("reload") == 1


def test_dialog_save_invalidates_cache(monkeypatch, tmp_path):
    dummy_module = types.ModuleType("tkinter")

    class DummyToplevel:
        def __init__(self, *a, **k):
            pass

        def title(self, *a, **k):
            pass

        def resizable(self, *a, **k):
            pass

        def destroy(self):
            pass

    class DummyText:
        def __init__(self, *a, **k):
            self.value = ""

        def pack(self, *a, **k):
            pass

        def insert(self, *a, **k):
            self.value = a[1]

        def get(self, *a, **k):
            return self.value

    class DummyFrame:
        def __init__(self, *a, **k):
            pass

        def pack(self, *a, **k):
            pass

    class DummyButton:
        def __init__(self, *a, **k):
            pass

        def pack(self, *a, **k):
            pass

    dummy_ttk = types.ModuleType("tkinter.ttk")
    dummy_ttk.Frame = DummyFrame
    dummy_ttk.Button = DummyButton
    dummy_messagebox = types.ModuleType("tkinter.messagebox")
    dummy_messagebox.showerror = lambda *a, **k: None
    dummy_module.Toplevel = DummyToplevel
    dummy_module.Text = DummyText
    dummy_module.BOTH = "both"
    dummy_module.END = "end"
    dummy_module.LEFT = "left"
    dummy_module.X = "x"
    dummy_module.ttk = dummy_ttk
    dummy_module.messagebox = dummy_messagebox

    monkeypatch.setitem(sys.modules, "tkinter", dummy_module)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", dummy_ttk)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", dummy_messagebox)

    gui_tools_config = importlib.reload(importlib.import_module("gui_tools_config"))

    import logika_zadan

    called = {"inv": 0, "cb": 0}

    def invalidate():
        called["inv"] += 1

    def cb():
        called["cb"] += 1

    monkeypatch.setattr(logika_zadan, "invalidate_cache", invalidate)

    path = tmp_path / "zadania_narzedzia.json"
    dlg = gui_tools_config.ToolsConfigDialog(path=str(path), on_save=cb)
    dlg._save()

    assert called["inv"] == 1
    assert called["cb"] == 1

