# WM-VERSION: 0.1
# Plik: planista_editor_runtime.py
# version: 1.0
"""Dodawanie/edycja zleceń oraz edycja słowników Planisty."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk


def _fmt(value) -> str:
    try:
        number = float(value or 0)
    except Exception:
        return str(value or "")
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _install_order_editor() -> None:
    import gui_planista_panel as GPP
    import zlecenia_logika as ZL
    import zlecenia_progress as ZP
    from ui_context_help import SearchableCombobox, add_help_button

    Panel = GPP.PlanistaPanel
    old_build = Panel._build_orders
    if getattr(old_build, "_wm_order_editor", False):
        return

    def product_values():
        rows = []
        for rec in ZL.list_produkty():
            code = str(rec.get("kod") or "").strip()
            if not code:
                continue
            name = str(rec.get("nazwa") or code).strip()
            display = f"{name}  [{code}]"
            rows.append((display, rec))
        return rows

    def add_order(self):
        rows = product_values()
        if not rows:
            messagebox.showinfo("Planista", "Najpierw dodaj produkt w zakładce Produkty.", parent=self)
            return
        by_display = {display: rec for display, rec in rows}

        dlg = tk.Toplevel(self.root)
        dlg.title("Dodaj zlecenie")
        dlg.transient(self.root)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)

        product = tk.StringVar()
        qty = tk.StringVar(value="1")
        term = tk.StringVar(value=date.today().strftime("%d-%m-%y"))
        cut = tk.StringVar(value=_fmt(ZL.DEFAULT_CUT_MM))
        internal = tk.StringVar()
        notes = tk.StringVar()
        reserve = tk.BooleanVar(value=True)

        labels = (
            ("Produkt", 0),
            ("Ilość", 1),
            ("Termin", 2),
            ("Rzaz [mm]", 3),
            ("Zlecenie wewnętrzne", 4),
            ("Uwagi", 5),
        )
        for text, row in labels:
            ttk.Label(frm, text=text).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)

        combo = SearchableCombobox(frm, textvariable=product, state="normal")
        combo.set_values([display for display, _ in rows])
        combo.grid(row=0, column=1, sticky="ew", pady=3)
        add_help_button(frm, "Wybierz produkt z kartoteki Produkty. Zlecenie zapisze aktualną wersję produktu i na jej podstawie policzy półprodukty oraz surowce.", row=0, column=2, padx=(4, 0))
        ttk.Entry(frm, textvariable=qty).grid(row=1, column=1, sticky="ew", pady=3)
        add_help_button(frm, "Podaj liczbę sztuk produktu do wykonania. Planista automatycznie wyliczy zapotrzebowanie wynikające z BOM.", row=1, column=2, padx=(4, 0))
        tk.Entry(frm, textvariable=term, state="readonly", readonlybackground="#2e7d32", fg="white", justify="center").grid(row=2, column=1, sticky="ew", pady=3)
        ttk.Button(frm, text="📅", command=lambda: GPP._open_date_calendar(dlg, term), width=3).grid(row=2, column=2, sticky="w", padx=(4, 0))
        ttk.Entry(frm, textvariable=cut).grid(row=3, column=1, sticky="ew", pady=3)
        add_help_button(frm, "Rzaz jest doliczany do materiału dla każdej wykonywanej sztuki półproduktu liniowego.", row=3, column=2, padx=(4, 0))
        ttk.Entry(frm, textvariable=internal).grid(row=4, column=1, sticky="ew", pady=3)
        ttk.Entry(frm, textvariable=notes).grid(row=5, column=1, sticky="ew", pady=3)
        ttk.Checkbutton(frm, text="Rezerwuj dostępny materiał", variable=reserve).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 3))
        add_help_button(frm, "Po zapisaniu WM zarezerwuje dostępne półprodukty i surowce dla tego zlecenia. Braki pozostaną widoczne jako zapotrzebowanie.", row=6, column=2, padx=(4, 0))

        def save():
            rec = by_display.get(product.get().strip())
            if not rec:
                messagebox.showerror("Dodaj zlecenie", "Wybierz produkt z listy.", parent=dlg)
                return
            try:
                qty_value = float(qty.get().replace(",", "."))
                cut_value = float(cut.get().replace(",", "."))
                if qty_value <= 0:
                    raise ValueError("Ilość musi być większa od zera.")
                if cut_value < 0:
                    raise ValueError("Rzaz nie może być ujemny.")
                ZL.create_zlecenie(
                    str(rec.get("kod")),
                    qty_value,
                    uwagi=notes.get().strip(),
                    autor=self.login or "system",
                    zlec_wew=internal.get().strip() or None,
                    reserve=bool(reserve.get()),
                    version=rec.get("version"),
                    termin=GPP._iso_date(term.get()),
                    rzaz_mm=cut_value,
                )
            except Exception as exc:
                messagebox.showerror("Dodaj zlecenie", str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        buttons = ttk.Frame(frm)
        buttons.grid(row=7, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Anuluj", command=dlg.destroy).pack(side="right")
        ttk.Button(buttons, text="Dodaj zlecenie", command=save).pack(side="right", padx=(0, 6))
        frm.columnconfigure(1, weight=1)

    def edit_order(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie do edycji.", parent=self)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Edytuj zlecenie {order.get('id')}")
        dlg.transient(self.root)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)

        qty = tk.StringVar(value=_fmt(order.get("ilosc", 0)))
        term = tk.StringVar(value=GPP._display_date(order.get("termin")) or date.today().strftime("%d-%m-%y"))
        cut = tk.StringVar(value=_fmt(order.get("rzaz_mm", ZL.DEFAULT_CUT_MM)))
        internal = tk.StringVar(value=str(order.get("zlec_wew") or ""))
        notes = tk.StringVar(value=str(order.get("uwagi") or ""))

        ttk.Label(frm, text=f"Produkt: {order.get('produkt')}   |   Zlecenie: {order.get('id')}", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        fields = (("Ilość", qty, 1), ("Rzaz [mm]", cut, 3), ("Zlecenie wewnętrzne", internal, 4), ("Uwagi", notes, 5))
        for label, var, row in fields:
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
            ttk.Entry(frm, textvariable=var).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Label(frm, text="Termin").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=3)
        tk.Entry(frm, textvariable=term, state="readonly", readonlybackground="#2e7d32", fg="white", justify="center").grid(row=2, column=1, sticky="ew", pady=3)
        ttk.Button(frm, text="📅", command=lambda: GPP._open_date_calendar(dlg, term), width=3).grid(row=2, column=2, sticky="w", padx=(4, 0))
        add_help_button(frm, "Zmiana ilości lub rzazu przeliczy tylko pozostałą do wykonania część zlecenia i odświeży rezerwacje. Już rozliczone wykonanie nie jest cofane.", row=1, column=2, padx=(4, 0))

        def save():
            try:
                qty_value = float(qty.get().replace(",", "."))
                cut_value = float(cut.get().replace(",", "."))
                if qty_value < 0 or cut_value < 0:
                    raise ValueError("Ilość i rzaz nie mogą być ujemne.")
                ZP.update_zlecenie(
                    order["id"],
                    ilosc=qty_value,
                    termin=GPP._iso_date(term.get()),
                    rzaz_mm=cut_value,
                    zlec_wew=internal.get().strip(),
                    uwagi=notes.get().strip(),
                    kto=self.login or "system",
                )
            except Exception as exc:
                messagebox.showerror("Edytuj zlecenie", str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        buttons = ttk.Frame(frm)
        buttons.grid(row=6, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Anuluj", command=dlg.destroy).pack(side="right")
        ttk.Button(buttons, text="Zapisz zmiany", command=save).pack(side="right", padx=(0, 6))
        frm.columnconfigure(1, weight=1)

    def build_orders(self, parent):
        old_build(self, parent)
        frames = [child for child in parent.winfo_children() if isinstance(child, ttk.Frame)]
        if not frames:
            return
        bar = frames[-1]
        children = list(bar.winfo_children())
        before = children[0] if children else None
        add_btn = ttk.Button(bar, text="Dodaj zlecenie", command=self.add_order)
        edit_btn = ttk.Button(bar, text="Edytuj zlecenie", command=self.edit_order)
        pack_args = {"side": "left", "padx": (0, 6)}
        if before is not None:
            pack_args["before"] = before
        add_btn.pack(**pack_args)
        add_help_button(bar, "Tworzy nowe zlecenie na podstawie wybranego produktu i jego aktualnego BOM. Planista wyliczy półprodukty, surowce oraz rezerwacje.", command_only=False).pack(side="left", padx=(0, 6), before=before if before is not None else None)
        edit_btn.pack(side="left", padx=(0, 6), before=before if before is not None else None)
        add_help_button(bar, "Edytuje ilość, termin, rzaz, numer wewnętrzny i uwagi wybranego zlecenia. Zmiany wpływające na zapotrzebowanie są automatycznie przeliczane.", command_only=False).pack(side="left", padx=(0, 10), before=before if before is not None else None)

    Panel.add_order = add_order
    Panel.edit_order = edit_order
    build_orders._wm_order_editor = True
    build_orders._wm_original = old_build
    Panel._build_orders = build_orders


def _install_operations_editor() -> None:
    import gui_magazyn_bom as GMB
    import planista_operations_runtime as POR
    from ui_context_help import add_help_button

    UI = GMB.MagazynBOM
    old_build = UI._build_operations_dictionary
    if getattr(old_build, "_wm_edit_operation", False):
        return

    def select_operation(self, _event=None):
        selection = self.tree_operations.selection()
        if not selection:
            return
        values = POR._load_operations()
        idx = int(selection[0])
        if 0 <= idx < len(values):
            self._editing_operation_original = values[idx]
            self.operation_name.set(values[idx])

    def edit_operation(self):
        old_name = str(getattr(self, "_editing_operation_original", "") or "").strip()
        new_name = self.operation_name.get().strip()
        if not old_name:
            GMB._msg_error(self, "Operacje technologiczne", "Zaznacz operację do edycji.")
            return
        if not new_name:
            GMB._msg_error(self, "Operacje technologiczne", "Nazwa operacji nie może być pusta.")
            return
        values = POR._load_operations()
        if old_name not in values:
            GMB._msg_error(self, "Operacje technologiczne", "Operacja została zmieniona w innym miejscu. Odśwież listę.")
            return
        if new_name.casefold() != old_name.casefold() and any(x.casefold() == new_name.casefold() for x in values):
            GMB._msg_error(self, "Operacje technologiczne", "Taka operacja już istnieje.")
            return
        values[values.index(old_name)] = new_name
        fresh = GMB.WarehouseModel()
        for code, rec in list(fresh.polprodukty.items()):
            if not isinstance(rec, dict):
                continue
            operations = list(rec.get("czynnosci") or [])
            changed = False
            for idx, value in enumerate(operations):
                if str(value).casefold() == old_name.casefold():
                    operations[idx] = new_name
                    changed = True
            if changed:
                updated = dict(rec)
                updated["czynnosci"] = operations
                fresh.add_or_update_polprodukt(updated)
        POR._save_operations(values)
        self.model.polprodukty = fresh.polprodukty
        self._editing_operation_original = ""
        self.operation_name.set("")
        self._refresh_operations_tree()
        self._refresh_pp_operations()
        if hasattr(self, "_load_polprodukty"):
            self._load_polprodukty()

    def build_operations(self, parent):
        old_build(self, parent)
        self._editing_operation_original = ""
        self.tree_operations.bind("<<TreeviewSelect>>", self._select_operation_for_edit, add="+")
        top = next((child for child in parent.winfo_children() if isinstance(child, ttk.Frame)), None)
        if top is not None:
            ttk.Button(top, text="Zapisz zmianę", command=self._edit_operation).grid(row=1, column=3, padx=(8, 0))
            add_help_button(top, "Zmienia nazwę zaznaczonej operacji i aktualizuje wszystkie półprodukty, które jej używają. Powiązania technologiczne nie zostaną utracone.", row=1, column=4, padx=(4, 0))

    UI._select_operation_for_edit = select_operation
    UI._edit_operation = edit_operation
    build_operations._wm_edit_operation = True
    UI._build_operations_dictionary = build_operations


def _install_raw_kind_editor() -> None:
    import gui_magazyn_bom as GMB
    from ui_context_help import add_help_button

    UI = GMB.MagazynBOM
    old_build = UI._build_raw_kinds
    if getattr(old_build, "_wm_edit_raw_kind", False):
        return

    def select_kind(self, _event=None):
        selection = self.tree_raw_kinds.selection()
        if not selection:
            return
        idx = int(selection[0])
        if not (0 <= idx < len(self.model.raw_kinds)):
            return
        rec = self.model.raw_kinds[idx]
        self._editing_raw_kind_original = str(rec.get("nazwa") or "")
        self.raw_kind_name.set(self._editing_raw_kind_original)
        self.raw_kind_mode.set("Fi" if str(rec.get("pole") or "").casefold() == "fi" else "Wymiar")

    def edit_kind(self):
        old_name = str(getattr(self, "_editing_raw_kind_original", "") or "").strip()
        new_name = self.raw_kind_name.get().strip()
        mode = "fi" if self.raw_kind_mode.get() == "Fi" else "wymiar"
        if not old_name:
            GMB._msg_error(self, "Rodzaje surowców", "Zaznacz rodzaj surowca do edycji.")
            return
        if not new_name:
            GMB._msg_error(self, "Rodzaje surowców", "Nazwa rodzaju nie może być pusta.")
            return

        fresh = GMB.WarehouseModel()
        target = next((item for item in fresh.raw_kinds if str(item.get("nazwa") or "").casefold() == old_name.casefold()), None)
        if target is None:
            GMB._msg_error(self, "Rodzaje surowców", "Rodzaj został zmieniony w innym miejscu. Odśwież listę.")
            return
        if new_name.casefold() != old_name.casefold() and any(str(item.get("nazwa") or "").casefold() == new_name.casefold() for item in fresh.raw_kinds):
            GMB._msg_error(self, "Rodzaje surowców", "Taki rodzaj surowca już istnieje.")
            return

        records = []
        for item in fresh.raw_kinds:
            if item is target:
                records.append({"nazwa": new_name, "pole": mode})
            else:
                records.append(dict(item))
        fresh.save_raw_kinds(records)

        for code, rec in list(fresh.surowce.items()):
            if not isinstance(rec, dict) or str(rec.get("rodzaj") or "").casefold() != old_name.casefold():
                continue
            updated = dict(rec)
            updated["rodzaj"] = new_name
            size = str(updated.get("rozmiar") or updated.get("wymiar") or updated.get("fi") or "").strip()
            updated.pop("fi", None)
            updated.pop("wymiar", None)
            updated.update(GMB._raw_dimension_fields(new_name, size, mode))
            fresh.add_or_update_surowiec(updated)

        self.model.raw_kinds = fresh.raw_kinds
        self.model.surowce = fresh.surowce
        self._kind_dimension_modes = {
            str(item["nazwa"]): str(item.get("pole") or "wymiar").casefold()
            for item in fresh.raw_kinds
            if isinstance(item, dict) and item.get("nazwa")
        }
        self.s_kind_combo.configure(values=tuple(self._kind_dimension_modes))
        self._editing_raw_kind_original = ""
        self.raw_kind_name.set("")
        self._refresh_raw_kinds_tree()
        self._load_surowce()
        self._refresh_raw_selector()

    def build_raw_kinds(self, parent):
        old_build(self, parent)
        self._editing_raw_kind_original = ""
        self.tree_raw_kinds.bind("<<TreeviewSelect>>", self._select_raw_kind_for_edit, add="+")
        top = next((child for child in parent.winfo_children() if isinstance(child, ttk.Frame)), None)
        if top is not None:
            ttk.Button(top, text="Zapisz zmianę", command=self._edit_raw_kind).grid(row=1, column=4, padx=(8, 0))
            add_help_button(top, "Zmienia nazwę lub typ wymiaru zaznaczonego rodzaju. Surowce używające tego rodzaju zostaną automatycznie zaktualizowane.", row=1, column=5, padx=(4, 0))

    UI._select_raw_kind_for_edit = select_kind
    UI._edit_raw_kind = edit_kind
    build_raw_kinds._wm_edit_raw_kind = True
    UI._build_raw_kinds = build_raw_kinds


def install_planista_editor_runtime() -> None:
    _install_order_editor()
    _install_operations_editor()
    _install_raw_kind_editor()


__all__ = ["install_planista_editor_runtime"]
