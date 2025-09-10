import types
import gui_magazyn


def test_add_and_pz_buttons_create_windows(monkeypatch):
    created = []

    class DummyAddDialog:
        def __init__(self, root, config, profiles, on_saved=None):
            self.top = object()
            created.append(self)

    class DummyPZDialog:
        def __init__(self, root, config, profiles, on_saved=None):
            created.append(self)

    monkeypatch.setattr(gui_magazyn, "MagazynAddDialog", DummyAddDialog)
    monkeypatch.setattr(gui_magazyn, "MagazynPZDialog", DummyPZDialog)

    panel = object.__new__(gui_magazyn.PanelMagazyn)
    root = types.SimpleNamespace(wait_window=lambda _win: None)
    panel.winfo_toplevel = lambda: root
    panel.config = None
    panel.profiles = None
    panel._reload_data = lambda *a, **k: None

    gui_magazyn.PanelMagazyn._act_dodaj(panel)
    gui_magazyn.PanelMagazyn._act_przyjecie(panel)

    assert len(created) == 2
