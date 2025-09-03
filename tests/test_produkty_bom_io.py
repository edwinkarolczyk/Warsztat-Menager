import json
import os
import tkinter as tk
from pathlib import Path

from tkinter import ttk

import pytest

import ustawienia_produkty_bom as upb


if not os.environ.get("DISPLAY"):
    pytest.skip("Wymagane środowisko z wyświetlaczem", allow_module_level=True)


def _find_widgets(root, cls):
    widgets = []
    if isinstance(root, cls):
        widgets.append(root)
    for child in root.winfo_children():
        widgets.extend(_find_widgets(child, cls))
    return widgets


def test_save_and_load_polprodukty(tmp_path, monkeypatch):
    monkeypatch.setattr(upb, "DATA_DIR", tmp_path / "produkty")
    monkeypatch.setattr(upb, "POL_DIR", tmp_path / "polprodukty")
    monkeypatch.setattr(upb, "SURO_PATH", tmp_path / "magazyn" / "surowce.json")
    upb._ensure_dirs()

    pp_dir = Path(upb.POL_DIR)
    pp_dir.mkdir(parents=True, exist_ok=True)
    (pp_dir / "PP1.json").write_text(
        json.dumps({"kod": "PP1", "nazwa": "Polprodukt A"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    sr_dir = Path(upb.SURO_PATH).parent
    sr_dir.mkdir(parents=True, exist_ok=True)
    Path(upb.SURO_PATH).write_text(
        json.dumps([
            {"kod": "SR1", "nazwa": "Surowiec 1"}
        ], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    root = tk.Tk()
    root.withdraw()
    frm = upb.make_tab(root)

    entries = _find_widgets(frm, ttk.Entry)
    kod_entry, nazwa_entry = entries[0], entries[1]
    kod_entry.insert(0, "PROD1")
    nazwa_entry.insert(0, "Produkt 1")

    tv = _find_widgets(frm, ttk.Treeview)[0]
    tv.insert("", "end", values=("PP1", "Polprodukt A", "2", "", "SR1", "1"))

    save_btn = [b for b in _find_widgets(frm, ttk.Button) if b.cget("text") == "Zapisz"][0]
    save_btn.invoke()

    prod_file = Path(upb.DATA_DIR) / "PROD1.json"
    data = json.loads(prod_file.read_text(encoding="utf-8"))
    assert data == {
        "kod": "PROD1",
        "nazwa": "Produkt 1",
        "polprodukty": [
            {
                "kod": "PP1",
                "ilosc_na_szt": 2,
                "czynnosci": [],
                "surowiec": {"typ": "SR1", "dlugosc": 1},
            }
        ],
    }

    # clear and reload
    for iid in tv.get_children():
        tv.delete(iid)
    lb = _find_widgets(frm, tk.Listbox)[0]
    lb.selection_set(0)
    lb.event_generate("<<ListboxSelect>>")
    items = tv.get_children()
    assert len(items) == 1
    assert tv.item(items[0], "values") == ("PP1", "Polprodukt A", "2", "", "SR1", "1")

    root.destroy()


def test_only_one_default_version(tmp_path, monkeypatch):
    monkeypatch.setattr(upb, "DATA_DIR", tmp_path / "produkty")
    monkeypatch.setattr(upb, "POL_DIR", tmp_path / "polprodukty")
    monkeypatch.setattr(upb, "SURO_PATH", tmp_path / "magazyn" / "surowce.json")
    upb._ensure_dirs()

    pp_dir = Path(upb.POL_DIR)
    pp_dir.mkdir(parents=True, exist_ok=True)
    (pp_dir / "PP1.json").write_text(
        json.dumps({"kod": "PP1", "nazwa": "Polprodukt A"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    sr_dir = Path(upb.SURO_PATH).parent
    sr_dir.mkdir(parents=True, exist_ok=True)
    Path(upb.SURO_PATH).write_text(
        json.dumps([{"kod": "SR1", "nazwa": "Surowiec 1"}], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # existing default version
    prod_dir = Path(upb.DATA_DIR)
    prod_dir.mkdir(parents=True, exist_ok=True)
    existing = {
        "kod": "PROD1",
        "nazwa": "Produkt 1 stary",
        "version": "1.0",
        "bom_revision": 1,
        "effective_from": None,
        "effective_to": None,
        "is_default": True,
        "polprodukty": [
            {
                "kod": "PP1",
                "ilosc_na_szt": 1,
                "czynnosci": [],
                "surowiec": {"typ": "SR1", "dlugosc": 1},
            }
        ],
    }
    (prod_dir / "PROD1_v1.json").write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    root = tk.Tk()
    root.withdraw()
    frm = upb.make_tab(root)

    entries = _find_widgets(frm, ttk.Entry)
    entries[0].insert(0, "PROD1")
    entries[1].insert(0, "Produkt 1 nowy")

    tv = _find_widgets(frm, ttk.Treeview)[0]
    tv.insert("", "end", values=("PP1", "Polprodukt A", "1", "", "SR1", "1"))

    monkeypatch.setattr(upb.messagebox, "showinfo", lambda *a, **k: None)
    save_btn = [b for b in _find_widgets(frm, ttk.Button) if b.cget("text") == "Zapisz"][0]
    save_btn.invoke()

    new_path = prod_dir / "PROD1.json"
    old_path = prod_dir / "PROD1_v1.json"
    new_data = json.loads(new_path.read_text(encoding="utf-8"))
    old_data = json.loads(old_path.read_text(encoding="utf-8"))

    assert new_data["is_default"] is True
    assert old_data.get("is_default") is False

    root.destroy()
