import os
import sys
import types

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

