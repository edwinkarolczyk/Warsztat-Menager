# version: 1.5
# -*- coding: utf-8 -*-
# RC1: guard przed podwójnym przyciskiem 'Zamówienia' w Magazynie.
# 1.1: po zbudowaniu istniejącego toolbara dodaje pojedynczy przycisk PZ.
# 1.2: blokada działa dla instancji panelu, więc nowy ekran Magazynu dostaje własny toolbar.
# 1.3: Planista korzysta wyłącznie z własnej kartoteki Surowców; nazwa surowca jest tworzona z rodzaju i wymiaru.
# 1.4: zapis surowca odtwarza techniczną zmienną nazwy, gdy pole Nazwa nie istnieje już w formularzu.
# 1.5: nie usuwa wiersza Rodzaj w nowej karcie surowca; porządkuje kolumny Magazynu bez zmiany danych.

from functools import wraps
import tkinter as tk
from tkinter import messagebox, ttk


_MAGAZYN_DISPLAY_COLUMNS = (
    "id",
    "nazwa",
    "rozmiar",
    "stan",
    "rezerwacje",
    "dostepne",
    "jednostka",
    "lokalizacja",
    "zadania",
    "typ",
    "sekcja",
)

_MAGAZYN_COLUMN_WIDTHS = {
    "id": 95,
    "nazwa": 240,
    "rozmiar": 130,
    "stan": 90,
    "rezerwacje": 110,
    "dostepne": 95,
    "jednostka": 80,
    "lokalizacja": 130,
    "zadania": 190,
    "typ": 100,
    "sekcja": 110,
}


def _generated_raw_name(kind, size):
    kind = str(kind or "").strip()
    size = str(size or "").strip()
    return f"{kind} - {size}" if kind and size else kind or size


def _ensure_generated_raw_name(raw_vars, owner, kind, size):
    """Utrzymaj techniczną nazwę nawet po usunięciu pola Nazwa z formularza."""
    name = _generated_raw_name(kind, size)
    name_var = raw_vars.get("nazwa")
    if name_var is None:
        name_var = tk.StringVar(master=owner)
        raw_vars["nazwa"] = name_var
    name_var.set(name)
    return name


def _catalog_raw_materials_only(model):
    """Źródłem listy surowców Planisty jest wyłącznie zakładka Surowce."""
    out = {}
    for key, rec in getattr(model, "surowce", {}).items():
        if not isinstance(rec, dict):
            continue
        item_id = str(rec.get("id") or rec.get("kod") or key).strip()
        if item_id:
            out[item_id] = {**rec, "id": item_id, "kod": item_id}
    return out


def _remove_manual_raw_name_row(owner, parent):
    """Usuń wyłącznie stare ręczne pole Nazwa, nigdy wiersz Rodzaj."""
    raw_vars = getattr(owner, "s_vars", None)
    if not isinstance(raw_vars, dict) or "nazwa" not in raw_vars:
        # Nowy formularz Planisty nie ma technicznej zmiennej Nazwa w UI.
        # Jego pierwszy wiersz to Rodzaj i musi pozostać widoczny.
        return False

    for child in parent.winfo_children():
        try:
            is_card = (
                isinstance(child, ttk.LabelFrame)
                and child.cget("text") == "Karta surowca"
            )
        except Exception:
            is_card = False
        if not is_card:
            continue

        row_widgets = list(child.grid_slaves(row=0))
        has_name_label = False
        for widget in row_widgets:
            try:
                if str(widget.cget("text") or "").strip().casefold() == "nazwa":
                    has_name_label = True
                    break
            except Exception:
                continue
        if not has_name_label:
            return False

        for widget in row_widgets:
            widget.destroy()
        return True
    return False


def _install_planista_raw_material_fix():
    """Instaluje małą poprawkę zgodności bez zmiany formatu zapisanych JSON-ów."""
    try:
        import gui_magazyn_bom as gb
    except Exception:
        return

    model_cls = getattr(gb, "WarehouseModel", None)
    view_cls = getattr(gb, "MagazynBOM", None)
    if model_cls is None or view_cls is None or getattr(view_cls, "_wm_raw_catalog_fix", False):
        return

    def inventory_raw_materials(self):
        return _catalog_raw_materials_only(self)

    model_cls.inventory_raw_materials = inventory_raw_materials

    original_build_surowce = view_cls._build_surowce
    original_save_surowiec = view_cls._save_surowiec

    @wraps(original_build_surowce)
    def build_surowce(self, parent):
        result = original_build_surowce(self, parent)
        # Stary formularz miał ręczne pole „Nazwa” w wierszu 0. Nowy formularz
        # ma w tym miejscu „Rodzaj”, więc nie wolno usuwać wiersza po numerze.
        _remove_manual_raw_name_row(self, parent)
        return result

    @wraps(original_save_surowiec)
    def save_surowiec(self):
        kind = self.s_vars["rodzaj"].get().strip()
        size = self.s_vars["rozmiar"].get().strip()
        if not kind or not size:
            gb._msg_error(self, "Surowce", "Wymagane pola: rodzaj i wymiar surowca.")
            return
        _ensure_generated_raw_name(self.s_vars, self, kind, size)
        return original_save_surowiec(self)

    def raw_display(self, item_id, rec):
        name = str(rec.get("nazwa") or "").strip()
        if not name:
            kind = str(rec.get("rodzaj") or rec.get("typ") or "").strip()
            size = str(rec.get("rozmiar") or rec.get("wymiar") or rec.get("fi") or "").strip()
            name = _generated_raw_name(kind, size) or str(item_id)
        return f"{name}  [{item_id}]"

    view_cls._build_surowce = build_surowce
    view_cls._save_surowiec = save_surowiec
    view_cls._raw_display = raw_display
    view_cls._wm_raw_catalog_fix = True


_install_planista_raw_material_fix()


def _apply_magazyn_column_layout(owner):
    """Ustaw czytelną kolejność kolumn bez zmiany formatu rekordów Magazynu."""
    tree = getattr(owner, "tree", None)
    if tree is None:
        return False
    try:
        available = tuple(str(column) for column in tree["columns"])
    except Exception:
        return False
    if not available:
        return False

    ordered = [column for column in _MAGAZYN_DISPLAY_COLUMNS if column in available]
    ordered.extend(column for column in available if column not in ordered)
    try:
        tree.configure(displaycolumns=tuple(ordered))
        for column, width in _MAGAZYN_COLUMN_WIDTHS.items():
            if column in available:
                anchor = "center" if column in {
                    "stan", "rezerwacje", "dostepne", "jednostka"
                } else "w"
                tree.column(column, width=width, anchor=anchor)
    except Exception:
        return False
    return True


def _schedule_magazyn_column_layout(owner):
    if owner is None:
        return
    try:
        owner.after_idle(lambda: _apply_magazyn_column_layout(owner))
    except Exception:
        pass


def _open_selected_pz(owner):
    try:
        import gui_magazyn as gm
        if hasattr(gm, "_can") and not gm._can(owner, "pz"):
            messagebox.showwarning("Uprawnienia", "Brak uprawnień do przyjęcia PZ.")
            return
    except Exception:
        pass

    item_id = ""
    getter = getattr(owner, "_selected_item_id", None)
    if callable(getter):
        try:
            item_id = str(getter() or "").strip()
        except Exception:
            item_id = ""
    if not item_id:
        messagebox.showinfo("PZ", "Najpierw wybierz pozycję w Magazynie.")
        return

    try:
        from gui_magazyn_pz import open_pz_dialog
        open_pz_dialog(owner, item_id, on_saved=lambda _id=None: owner.refresh())
    except Exception as exc:
        messagebox.showerror("PZ", f"Nie udało się otworzyć przyjęcia PZ:\n{exc}")


def _append_pz_button(toolbar, owner):
    if getattr(owner, "_wm_pz_toolbar_button", None) is not None:
        return
    try:
        button = ttk.Button(
            toolbar,
            text="PZ / Przyjęcie",
            command=lambda: _open_selected_pz(owner),
            style="WM.Side.TButton",
        )
        button.pack(side="right", padx=(0, 6))
        owner._wm_pz_toolbar_button = button
    except Exception:
        pass


def ensure_magazyn_toolbar_once(build_fn):
    @wraps(build_fn)
    def wrapper(*args, **kwargs):
        owner = args[1] if len(args) >= 2 else kwargs.get("owner")
        if owner is not None and getattr(owner, "_wm_magazyn_toolbar_built", False):
            return
        result = build_fn(*args, **kwargs)
        if owner is not None:
            owner._wm_magazyn_toolbar_built = True
        if len(args) >= 2:
            _append_pz_button(args[0], owner)
        _schedule_magazyn_column_layout(owner)
        return result
    return wrapper
