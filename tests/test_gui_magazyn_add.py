import types

import gui_magazyn_add as gma


class DummyVar:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


def test_on_save_persists_selected_values(monkeypatch):
    saved = {}

    def fake_load():
        return {"items": {}, "meta": {"order": []}}

    def fake_save(data):
        saved.update(data)

    monkeypatch.setattr(gma, "magazyn_io", types.SimpleNamespace(load=fake_load, save=fake_save))
    monkeypatch.setattr(gma.LM, "append_history", lambda *a, **k: None)
    monkeypatch.setattr(gma, "bump_material_seq_if_matches", lambda *a, **k: None)

    dlg = object.__new__(gma.MagazynAddDialog)
    dlg.vars = {
        "id": DummyVar("M1"),
        "nazwa": DummyVar("Element"),
        "kategoria": DummyVar("kat"),
        "typ": DummyVar("stal"),
        "jednostka": DummyVar("szt"),
        "stan": DummyVar("1"),
        "min_poziom": DummyVar("0"),
    }
    dlg.master = types.SimpleNamespace(winfo_toplevel=lambda: types.SimpleNamespace(login="u"))
    dlg.config = {"magazyn.require_reauth": False}
    dlg.win = types.SimpleNamespace(destroy=lambda: None)
    dlg.on_saved = None

    gma.MagazynAddDialog.on_save(dlg)

    item = saved["items"]["M1"]
    assert item["kategoria"] == "kat"
    assert item["typ"] == "stal"
    assert item["jednostka"] == "szt"
