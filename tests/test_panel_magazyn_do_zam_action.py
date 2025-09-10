import gui_magazyn as gm


def test_act_do_zam_opens_dialog(monkeypatch):
    created = []

    class DummyDialog:
        def __init__(self, parent, config, preselect_id=None, on_saved=None):
            self.args = (parent, config, preselect_id, on_saved)
            self.top = object()
            created.append(self)

    monkeypatch.setattr(gm, "MagazynOrderDialog", DummyDialog)

    class DummyTree:
        def selection(self):
            return ["item1"]

        def item(self, *_a, **_k):
            return ("X123",)

    class DummyRoot:
        def __init__(self):
            self.waited = None

        def wait_window(self, win):
            self.waited = win

    panel = object.__new__(gm.PanelMagazyn)
    panel.tree = DummyTree()
    panel.root = DummyRoot()
    panel.config = {"cfg": 1}
    panel._reload_data = lambda: None

    gm.PanelMagazyn._act_do_zam(panel)

    dlg = created[0]
    assert dlg.args == (panel.root, panel.config, "X123", panel._reload_data)
    assert panel.root.waited is dlg.top
