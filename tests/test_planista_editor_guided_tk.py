"""Real Tk smoke for the approved UI-only Planista order editor."""
import sys
import types
import tkinter as tk
from tkinter import ttk

import planista_editor_runtime as editor
import planista_semi_progress_runtime as PS
import zlecenia_logika as ZL


def _widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _widgets(child)


def test_order_editor_guides_semi_operations_without_changing_order(monkeypatch):
    order = {
        "id": "000014", "produkt": "2", "version": "1.0",
        "ilosc": 10, "wykonano": 0, "status": "w trakcie",
        "plan_polprodukty": {
            "POL-003": {"nazwa": "Rurka", "potrzeba": 11},
            "POL-002": {"nazwa": "Zawleczka", "potrzeba": 11},
        },
    }
    before = repr(order)
    rows = [
        {"kod": "POL-003", "nazwa": "Rurka", "potrzeba": 11,
         "z_magazynu": 0, "do_wykonania": 11, "wykonano": 0, "pozostalo": 11},
        {"kod": "POL-002", "nazwa": "Zawleczka", "potrzeba": 11,
         "z_magazynu": 0, "do_wykonania": 11, "wykonano": 0, "pozostalo": 11},
    ]
    monkeypatch.setattr(ZL, "_order_path", lambda _id: "dummy.json")
    monkeypatch.setattr(ZL, "_read_json", lambda _path: dict(order))
    monkeypatch.setattr(PS, "semi_progress_rows", lambda _order: list(rows))
    monkeypatch.setattr(PS, "_full_semi_targets", lambda _order: {
        "POL-003": {"potrzeba": 11, "czynnosci": ["Cięcie", "Wiercenie"]},
        "POL-002": {"potrzeba": 11, "czynnosci": []},
    })
    monkeypatch.setattr(PS, "pending_semi_surplus", lambda _order, _code: 0)
    monkeypatch.setattr(PS, "proposed_product_completion", lambda _order: {
        "available": True, "complete_sets": 0, "planned": 10, "additional": 0,
    })

    fake = types.ModuleType("gui_planista_panel")
    fake._display_date = lambda _value: ""
    fake._fmt_amount = lambda qty, unit: f"{qty} {unit}"
    fake._iso_date = lambda value: value

    class Panel:
        _build_orders = lambda self, parent: None

        def __init__(self, root):
            self.root = root
            self.login = "Edwin"
            self.rola = "brygadzista"
            self.tree = ttk.Treeview(root)
            self.refresh = lambda: None

        def _selected(self):
            return order

    fake.PlanistaPanel = Panel
    monkeypatch.setitem(sys.modules, "gui_planista_panel", fake)
    editor._install_order_editor()

    root = tk.Tk()
    try:
        panel = Panel(root)
        panel.edit_order()
        root.update_idletasks()
        window = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
        widgets = list(_widgets(window))
        labels = [
            str(w.cget("text"))
            for w in widgets
            if isinstance(w, ttk.Label) and "text" in w.keys()
        ]
        assert "1. Wybierz półprodukt" in labels
        assert "2. Zgłoś wykonanie" in labels
        assert "3. Gotowy produkt" in labels
        tree = next(
            w for w in widgets
            if isinstance(w, ttk.Treeview) and "nazwa" in w["columns"]
        )
        assert tree.selection() == ("POL-003",)
        operation = next(
            w for w in widgets
            if isinstance(w, ttk.Button)
            and w.cget("text") == "Zapisz wykonanie operacji"
        )
        assert operation.winfo_manager() == "pack"
        manual = next(
            w for w in widgets
            if isinstance(w, ttk.Button)
            and w.cget("text") == "Zapisz wykonanie półproduktu"
        )
        assert manual.master.winfo_manager() == ""
        surplus = next(
            w for w in widgets
            if isinstance(w, ttk.Button)
            and w.cget("text") == "Przekaż nadwyżkę"
        )
        assert surplus.winfo_manager() == ""
        tree.selection_set("POL-002")
        tree.event_generate("<<TreeviewSelect>>")
        root.update()
        assert operation.master.winfo_manager() == ""
        assert manual.master.winfo_manager() == "pack"
        assert repr(order) == before
    finally:
        root.destroy()
