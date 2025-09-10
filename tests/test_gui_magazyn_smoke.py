import types
import sys
import gui_magazyn


def test_add_and_pz_buttons_create_windows(monkeypatch):
    created = []

    class DummyToplevel:
        def __init__(self, *args, **kwargs):
            created.append(self)

        def title(self, *args, **kwargs):
            pass

    monkeypatch.setattr(
        gui_magazyn,
        "tk",
        types.SimpleNamespace(Toplevel=DummyToplevel),
    )
    monkeypatch.setattr(gui_magazyn, "apply_theme", lambda *a, **k: None)
    class DummyDialog:
        def __init__(self, master, config, profiles=None, preselect_id=None, on_saved=None):
            self.top = gui_magazyn.tk.Toplevel(master)

    monkeypatch.setattr(gui_magazyn, "MagazynAddDialog", DummyDialog)
    dummy_mod = types.SimpleNamespace(MagazynPZDialog=DummyDialog)
    monkeypatch.setitem(sys.modules, "gui_magazyn_pz", dummy_mod)

    panel = object.__new__(gui_magazyn.PanelMagazyn)
    panel.root = types.SimpleNamespace(wait_window=lambda *_: None)
    panel.config = {}
    panel.profiles = {}

    gui_magazyn.PanelMagazyn._act_dodaj(panel)
    gui_magazyn.PanelMagazyn._act_przyjecie(panel)

    assert len(created) == 2
