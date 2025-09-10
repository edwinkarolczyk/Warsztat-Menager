import sys
import types

import gui_settings


def test_open_tools_config_invalidates_cache(monkeypatch):
    called = {"n": 0}

    def invalidate():
        called["n"] += 1

    monkeypatch.setattr(
        gui_settings, "LZ", types.SimpleNamespace(invalidate_cache=invalidate)
    )
    monkeypatch.setattr(
        gui_settings,
        "messagebox",
        types.SimpleNamespace(showerror=lambda *a, **k: None, showwarning=lambda *a, **k: None),
    )

    dummy_module = types.SimpleNamespace()

    class DummyWin:
        def __init__(self, master=None, on_save=None):
            self.on_save = on_save
            dummy_module.instance = self

        def transient(self, parent):  # pragma: no cover - no-op
            pass

        def attributes(self, *args, **kwargs):  # pragma: no cover - no-op
            pass

        def grab_set(self):  # pragma: no cover - no-op
            pass

    dummy_module.ToolsConfigWindow = DummyWin
    monkeypatch.setitem(sys.modules, "gui_tools_config", dummy_module)

    dummy_self = types.SimpleNamespace(
        master=types.SimpleNamespace(winfo_toplevel=lambda: None)
    )

    gui_settings.SettingsPanel._open_tools_config(dummy_self)

    dummy_module.instance.on_save()

    assert called["n"] == 1

