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

    dummy_module = types.SimpleNamespace()

    class DummyDialog:
        def __init__(self, master=None, *, path="", on_save=None):
            self.on_save = on_save
            called["path"] = path
            dummy_module.instance = self

    dummy_module.ToolsConfigDialog = DummyDialog
    monkeypatch.setitem(sys.modules, "gui_tools_config", dummy_module)

    dummy_self = types.SimpleNamespace(
        master=types.SimpleNamespace(winfo_toplevel=lambda: None),
        wait_window=lambda win: called.__setitem__("wait", called["wait"] + 1),
    )

    gui_settings.SettingsPanel._open_tools_config(dummy_self)

    dummy_module.instance.on_save()

    assert called["n"] == 1
    assert called["wait"] == 1
    assert called["path"] == os.path.join("data", "zadania_narzedzia.json")


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

