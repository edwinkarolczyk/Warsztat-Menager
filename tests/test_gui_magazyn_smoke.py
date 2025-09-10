import types
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
        def __init__(self, parent, **_):
            gui_magazyn.tk.Toplevel(parent)

    monkeypatch.setattr(gui_magazyn, "MagazynAddDialog", DummyDialog)
    monkeypatch.setattr(gui_magazyn, "MagazynPZDialog", DummyDialog)

    panel = object.__new__(gui_magazyn.PanelMagazyn)

    gui_magazyn.PanelMagazyn._act_dodaj(panel)
    gui_magazyn.PanelMagazyn._act_przyjecie(panel)

    assert len(created) == 2
