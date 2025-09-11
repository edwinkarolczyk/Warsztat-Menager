import tkinter as tk
import pytest

import gui_magazyn_pz as gmpz
import logika_magazyn as LM
import magazyn_io


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def magazyn(tmp_path, monkeypatch):
    monkeypatch.setattr(LM, "MAGAZYN_PATH", str(tmp_path / "magazyn.json"))
    monkeypatch.setattr(magazyn_io, "MAGAZYN_PATH", str(tmp_path / "magazyn.json"))
    monkeypatch.setattr(magazyn_io, "HISTORY_PATH", str(tmp_path / "magazyn_history.json"))
    monkeypatch.setattr(magazyn_io, "PRZYJECIA_PATH", str(tmp_path / "przyjecia.json"))
    LM.load_magazyn()
    yield


def test_dialog_smoke_open(root, magazyn, monkeypatch):
    monkeypatch.setattr(gmpz, "apply_theme", lambda *a, **k: None)
    LM.upsert_item({
        "id": "MAT-1",
        "nazwa": "Test",
        "typ": "materiał",
        "jednostka": "mb",
        "stan": 0,
        "min_poziom": 0,
    })
    dlg = gmpz.MagazynPZDialog(root, config={"magazyn.require_reauth": False})
    assert dlg.top.winfo_exists()
    dlg.top.destroy()


def test_record_pz_updates_stock(magazyn):
    items = [
        {
            "id": "PROFIL",
            "nazwa": "Profil 20x20x2 stal",
            "typ": "materiał",
            "jednostka": "mb",
            "stan": 0,
            "min_poziom": 0,
        },
        {
            "id": "RURA",
            "nazwa": "Rura fi=30, ścianka=2",
            "typ": "materiał",
            "jednostka": "mb",
            "stan": 0,
            "min_poziom": 0,
        },
        {
            "id": "PP",
            "nazwa": "Półprodukt nowa nazwa",
            "typ": "półprodukt",
            "jednostka": "szt",
            "stan": 0,
            "min_poziom": 0,
        },
    ]
    for it in items:
        LM.upsert_item(it)

    gmpz.record_pz("PROFIL", 1.5, user="test")
    gmpz.record_pz("RURA", 0.75, user="test")
    gmpz.record_pz("PP", 5, user="test")

    assert LM.get_item("PROFIL")["stan"] == 1.5
    assert LM.get_item("RURA")["stan"] == 0.75
    assert LM.get_item("PP")["stan"] == 5


def test_fractional_szt_prompts_rounding(root, magazyn, monkeypatch):
    monkeypatch.setattr(gmpz, "apply_theme", lambda *a, **k: None)
    LM.upsert_item({
        "id": "PP",
        "nazwa": "Półprodukt",
        "typ": "półprodukt",
        "jednostka": "szt",
        "stan": 0,
        "min_poziom": 0,
    })

    calls = {}

    def fake_askyesno(title, msg, parent=None):
        calls["msg"] = msg
        return True

    monkeypatch.setattr(gmpz.messagebox, "askyesno", fake_askyesno)

    dlg = gmpz.MagazynPZDialog(
        root,
        config={"magazyn.require_reauth": False},
        preselect_id="PP",
    )
    dlg._vars["qty"].set("1.5")
    dlg._submit()
    dlg.top.destroy()

    assert "zaokrągl" in calls["msg"].lower()
    assert LM.get_item("PP")["stan"] == 2.0
