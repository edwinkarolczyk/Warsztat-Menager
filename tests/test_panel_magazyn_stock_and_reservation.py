import types
import gui_magazyn as gm


def test_stock_low_and_reservation(monkeypatch):
    data = [
        {"id": "IT_LOW", "nazwa": "Low", "stan": 1.0, "min_poziom": 2.0, "rezerwacje": 0.0},
        {"id": "IT_RES", "nazwa": "Reservable", "stan": 10.0, "min_poziom": 2.0, "rezerwacje": 1.0},
    ]

    monkeypatch.setattr(gm.LM, "lista_items", lambda: data)
    monkeypatch.setattr(gm.LM, "sprawdz_progi", lambda: [])

    def fake_rezerwuj(item_id, ilosc, **_):
        for it in data:
            if it["id"] == item_id:
                it["rezerwacje"] = float(it.get("rezerwacje", 0)) + ilosc
                break

    def fake_zwolnij(item_id, ilosc, **_):
        for it in data:
            if it["id"] == item_id:
                it["rezerwacje"] = float(it.get("rezerwacje", 0)) - ilosc
                break

    monkeypatch.setattr(gm.LM, "rezerwuj", fake_rezerwuj)
    monkeypatch.setattr(gm.LM, "zwolnij_rezerwacje", fake_zwolnij)

    class DummyTree:
        def __init__(self):
            self.rows = []
            self.selected = None

        def delete(self, *_a):
            self.rows.clear()

        def get_children(self):
            return [r[0] for r in self.rows]

        def insert(self, _p, _i, values, tags=()):
            iid = f"item{len(self.rows)}"
            self.rows.append((iid, values))
            return iid

        def selection(self):
            return [self.selected] if self.selected else []

        def item(self, iid, *_a):
            for rid, vals in self.rows:
                if rid == iid:
                    return vals
            return ()

        def tag_configure(self, *_a, **_k):
            pass

    panel = object.__new__(gm.PanelMagazyn)
    panel.tree = DummyTree()
    panel.tree_low = DummyTree()
    panel.nb = types.SimpleNamespace(index=lambda _sel: 0, select=lambda: 0)
    panel.var_alerty = types.SimpleNamespace(set=lambda *_a, **_k: None)

    gm.PanelMagazyn._load(panel)
    low_ids = [vals[0] for _, vals in panel.tree_low.rows]
    assert "IT_LOW" in low_ids

    panel.tree.selected = panel.tree.get_children()[1]
    monkeypatch.setattr(gm.PanelMagazyn, "_ask_float", lambda *_a, **_k: 3)

    gm.PanelMagazyn._act_rezerwuj(panel)
    assert data[1]["rezerwacje"] == 4.0
    vals = [v for _, v in panel.tree.rows if v[0] == "IT_RES"][0]
    assert vals[6] == gm._fmt(4.0)

    panel.tree.selected = panel.tree.get_children()[1]
    gm.PanelMagazyn._act_zwolnij(panel)
    assert data[1]["rezerwacje"] == 1.0
    vals = [v for _, v in panel.tree.rows if v[0] == "IT_RES"][0]
    assert vals[6] == gm._fmt(1.0)
