# version: 1.4
# -*- coding: utf-8 -*-
# RC1: guard przed podwójnym przyciskiem 'Zamówienia' w Magazynie.
# 1.1: po zbudowaniu istniejącego toolbara dodaje pojedynczy przycisk PZ.
# 1.2: blokada działa dla instancji panelu, więc nowy ekran Magazynu dostaje własny toolbar.
# 1.3: Planista korzysta wyłącznie z własnej kartoteki Surowców; nazwa surowca jest tworzona z rodzaju i wymiaru.
# 1.4: zapis surowca odtwarza techniczną zmienną nazwy, gdy pole Nazwa nie istnieje już w formularzu.

from functools import wraps
import tkinter as tk
from tkinter import messagebox, ttk


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
        # Pole „Nazwa” nie jest już edytowane ręcznie. Zostawiamy zmienną
        # w modelu dla zgodności danych, ale usuwamy cały pierwszy wiersz z UI.
        for child in parent.winfo_children():
            try:
                is_card = isinstance(child, ttk.LabelFrame) and child.cget("text") == "Karta surowca"
            except Exception:
                is_card = False
            if not is_card:
                continue
            for widget in child.grid_slaves(row=0):
                widget.destroy()
            break
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
        return result
    return wrapper
