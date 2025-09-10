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
    monkeypatch.setattr(
        gui_magazyn, "MagazynAddDialog", lambda master, *a, **k: DummyToplevel()
    )
    monkeypatch.setattr(
        gui_magazyn, "MagazynPZDialog", lambda master, *a, **k: DummyToplevel()
    )

    panel = object.__new__(gui_magazyn.PanelMagazyn)

    gui_magazyn.PanelMagazyn._act_dodaj(panel)
    gui_magazyn.PanelMagazyn._act_przyjecie(panel)

    assert len(created) == 2
