# WM-VERSION: 0.1
# Plik: planista_safety_runtime.py
# version: 1.1
"""Spójność danych i bezpieczne zachowanie modułu Planista.

Warstwa runtime utrzymuje poprawki w jednym miejscu bez dublowania logiki kartotek.
"""
from __future__ import annotations

from pathlib import Path
import copy
import tkinter as tk
from tkinter import messagebox, ttk

from config_manager import ConfigManager


def _active_data_dir() -> Path:
    value = ConfigManager().path_data()
    return Path(value) if value else Path("data")


def _sync_bom_root() -> Path:
    """BOM ma zawsze korzystać z tego samego aktywnego data root co WM."""
    import bom

    root = _active_data_dir()
    bom.DATA_DIR = root
    return root


def _reservation_state(order: dict) -> tuple[bool, str]:
    """Zwraca (czy pełna rezerwacja, opis stanu)."""
    raw_need = order.get("zapotrzebowanie_surowce") or {}
    raw_reserved = order.get("rezerwacje_surowce") or {}
    plan = order.get("plan_polprodukty") or {}
    semi_reserved = order.get("rezerwacje_polprodukty") or {}

    needed = []
    reserved = []
    for code, rec in raw_need.items():
        if not isinstance(rec, dict):
            continue
        qty = max(0.0, float(rec.get("ilosc", 0) or 0))
        if qty > 1e-9:
            needed.append(qty)
            reserved.append(max(0.0, float(raw_reserved.get(code, 0) or 0)))
    for code, rec in plan.items():
        if not isinstance(rec, dict):
            continue
        qty = max(0.0, float(rec.get("z_magazynu", 0) or 0))
        if qty > 1e-9:
            needed.append(qty)
            reserved.append(max(0.0, float(semi_reserved.get(code, 0) or 0)))

    if not needed:
        return True, "nie dotyczy"
    full = all(have + 1e-9 >= need for need, have in zip(needed, reserved))
    if full:
        return True, "pełne"
    if any(value > 1e-9 for value in reserved):
        return False, "częściowe"
    return False, "brak"


def _set_reservation_state(order: dict) -> dict:
    full, label = _reservation_state(order)
    order["materialy_zarezerwowane"] = bool(full)
    order["status_rezerwacji"] = label
    return order


def _restore_reservations(mapping: dict, user: str, context: str) -> None:
    import logika_magazyn as LM

    for code, qty in (mapping or {}).items():
        amount = max(0.0, float(qty or 0))
        if amount <= 1e-9:
            continue
        try:
            LM.rezerwuj(code, amount, user, kontekst=context)
        except Exception:
            # Nie maskujemy pierwotnego wyjątku przeliczenia.
            pass


def _install_bom_root_guard() -> None:
    import bom

    if getattr(bom, "_wm_dynamic_root_installed", False):
        return
    for name in (
        "get_produkt",
        "get_polprodukt",
        "compute_bom_for_prd",
        "compute_sr_for_pp",
        "compute_sr_for_prd",
    ):
        original = getattr(bom, name, None)
        if not callable(original) or getattr(original, "_wm_dynamic_root", False):
            continue

        def make_wrapper(fn):
            def wrapped(*args, **kwargs):
                _sync_bom_root()
                return fn(*args, **kwargs)
            wrapped._wm_dynamic_root = True
            wrapped._wm_original = fn
            wrapped.__name__ = getattr(fn, "__name__", "wrapped")
            return wrapped

        setattr(bom, name, make_wrapper(original))
    bom._wm_dynamic_root_installed = True
    _sync_bom_root()


def _install_progress_guard() -> None:
    import zlecenia_logika as ZL
    import zlecenia_progress as ZP

    if not getattr(ZP._replan_remaining, "_wm_safe_replan", False):
        original_replan = ZP._replan_remaining

        def safe_replan(order, kto="system"):
            # Najpierw sprawdź, czy BOM w ogóle daje się rozwinąć, zanim zwolnimy
            # istniejące rezerwacje tego zlecenia.
            _sync_bom_root()
            remaining = max(0.0, float(order.get("ilosc", 0) or 0) - float(order.get("wykonano", 0) or 0))
            if remaining > 0:
                ZL.build_production_plan(
                    order["produkt"],
                    remaining,
                    cut_mm=float(order.get("rzaz_mm", ZL.DEFAULT_CUT_MM) or 0),
                    version=order.get("version"),
                    overrides=ZP._remaining_overrides(order, remaining),
                )
            old_pp = dict(order.get("rezerwacje_polprodukty") or {})
            old_raw = dict(order.get("rezerwacje_surowce") or {})
            snapshot = copy.deepcopy(order)
            try:
                result = original_replan(order, kto)
                return _set_reservation_state(result)
            except Exception:
                order.clear()
                order.update(snapshot)
                _restore_reservations(old_pp, kto, f"rollback-przeliczenie:{order.get('id')}")
                _restore_reservations(old_raw, kto, f"rollback-przeliczenie:{order.get('id')}")
                raise

        safe_replan._wm_safe_replan = True
        safe_replan._wm_original = original_replan
        ZP._replan_remaining = safe_replan

    # Jeden kanoniczny mechanizm aktualizacji i rozliczenia. Stare wejścia ZL
    # delegują do bezpieczniejszej implementacji ZP.
    ZL.update_zlecenie = ZP.update_zlecenie
    ZL.report_wykonano = ZP.report_wykonano

    if not getattr(ZL.create_zlecenie, "_wm_reservation_state", False):
        original_create = ZL.create_zlecenie

        def create_with_state(*args, **kwargs):
            _sync_bom_root()
            order, shortages = original_create(*args, **kwargs)
            _set_reservation_state(order)
            try:
                ZL._write_json(ZL._order_path(order["id"]), order)
            except Exception:
                pass
            return order, shortages

        create_with_state._wm_reservation_state = True
        create_with_state._wm_original = original_create
        ZL.create_zlecenie = create_with_state


def _raw_refs(model, code: str) -> list[str]:
    refs = []
    for pp_code, rec in model.polprodukty.items():
        if not isinstance(rec, dict):
            continue
        raw = rec.get("surowiec") if isinstance(rec.get("surowiec"), dict) else {}
        raw_code = str(raw.get("kod") or raw.get("id") or "").strip()
        if raw_code == str(code):
            refs.append(str(rec.get("nazwa") or pp_code))
    return refs


def _semi_refs(model, code: str) -> list[str]:
    import gui_magazyn_bom as GMB

    refs = []
    for symbol, rec in model.produkty.items():
        if not isinstance(rec, dict):
            continue
        for item in GMB._product_bom(rec):
            if str(item.get("kod") or "") == str(code):
                refs.append(str(rec.get("nazwa") or symbol))
                break
    return refs


def _active_order_refs(symbol: str) -> list[str]:
    import zlecenia_logika as ZL

    refs = []
    for order in ZL.list_zlecenia():
        if str(order.get("produkt") or "") != str(symbol):
            continue
        if str(order.get("status") or "").casefold() in {"zakończone", "anulowane"}:
            continue
        refs.append(str(order.get("id") or "?"))
    return refs


def _install_catalog_guards() -> None:
    import gui_magazyn_bom as GMB

    Model = GMB.WarehouseModel
    if not getattr(Model, "_wm_planista_safety", False):
        # Półprodukt ma wybierać wyłącznie rekordy z kartoteki Surowce.
        def inventory_raw_materials(self):
            out = {}
            for key, rec in self.surowce.items():
                if not isinstance(rec, dict):
                    continue
                item_id = str(rec.get("id") or rec.get("kod") or key).strip()
                if item_id:
                    out[item_id] = {**rec, "id": item_id, "kod": item_id}
            return out
        Model.inventory_raw_materials = inventory_raw_materials

        old_add_raw = Model.add_or_update_surowiec
        def add_raw(self, record):
            rec = dict(record)
            kind = str(rec.get("rodzaj") or rec.get("typ") or "").strip()
            size = str(rec.get("rozmiar") or rec.get("wymiar") or rec.get("fi") or "").strip()
            if kind and size:
                rec["nazwa"] = f"{kind} - {size}"
            return old_add_raw(self, rec)
        Model.add_or_update_surowiec = add_raw

        old_del_raw = Model.delete_surowiec
        def del_raw(self, code):
            refs = _raw_refs(self, code)
            if refs:
                raise ValueError("Nie można usunąć surowca. Używają go półprodukty: " + ", ".join(refs[:8]))
            return old_del_raw(self, code)
        Model.delete_surowiec = del_raw

        old_del_semi = Model.delete_polprodukt
        def del_semi(self, code):
            refs = _semi_refs(self, code)
            if refs:
                raise ValueError("Nie można usunąć półproduktu. Używają go produkty: " + ", ".join(refs[:8]))
            return old_del_semi(self, code)
        Model.delete_polprodukt = del_semi

        old_del_product = Model.delete_produkt
        def del_product(self, symbol):
            refs = _active_order_refs(symbol)
            if refs:
                raise ValueError("Nie można usunąć produktu. Ma aktywne zlecenia: " + ", ".join(refs[:8]))
            return old_del_product(self, symbol)
        Model.delete_produkt = del_product

        old_add_product = Model.add_or_update_produkt
        def add_product(self, record):
            rec = dict(record)
            current = self.produkty.get(str(rec.get("symbol") or ""), {})
            rec.setdefault("version", current.get("version", "1.0"))
            rec.setdefault("revision", current.get("revision", current.get("rewizja", 1)))
            rec.setdefault("is_default", current.get("is_default", True))
            return old_add_product(self, rec)
        Model.add_or_update_produkt = add_product
        Model._wm_planista_safety = True

    UI = GMB.MagazynBOM
    if not getattr(UI, "_wm_delete_errors", False):
        # Model zgłasza zależności jako ValueError; UI ma je pokazać zamiast
        # pozostawić wyjątek w callbacku Tk.
        for method_name in ("_delete_surowiec", "_delete_polprodukt", "_delete_produkt"):
            original = getattr(UI, method_name, None)
            if not callable(original):
                continue
            def make_delete_wrapper(fn, title):
                def wrapped(self, *args, **kwargs):
                    try:
                        return fn(self, *args, **kwargs)
                    except ValueError as exc:
                        messagebox.showerror(title, str(exc), parent=self)
                        return None
                return wrapped
            setattr(UI, method_name, make_delete_wrapper(original, "Planista — zależności"))
        UI._wm_delete_errors = True


def _install_catalog_cache() -> None:
    import gui_planista_panel as GPP

    if getattr(GPP.PlanistaPanel._load_catalog, "_wm_cached_catalog", False):
        return

    def cached_load_catalog(self, label):
        import gui_magazyn_bom as GMB

        _sync_bom_root()
        host = self._catalog_hosts[label]
        cache = getattr(self, "_wm_catalog_editors", None)
        if cache is None:
            cache = self._wm_catalog_editors = {}
        editor = cache.get(label)
        try:
            if editor is None or not editor.winfo_exists():
                GMB.DATA_DIR = _active_data_dir()
                editor = GMB.MagazynBOM(host)
                editor.pack(fill="both", expand=True)
                inner = next((child for child in editor.winfo_children() if isinstance(child, ttk.Notebook)), None)
                if inner is not None:
                    wanted = self._CATALOG_TABS[label]
                    tabs = list(inner.tabs())
                    if 0 <= wanted < len(tabs):
                        inner.select(tabs[wanted])
                        for idx, tab_id in enumerate(tabs):
                            if idx != wanted:
                                inner.hide(tab_id)
                cache[label] = editor
            else:
                # Odśwież źródła bez niszczenia formularza i bez utraty wpisanych danych.
                for name in ("_load_surowce", "_load_polprodukty", "_load_produkty", "_refresh_raw_selector", "_refresh_semi_selector", "_refresh_raw_kinds_tree"):
                    fn = getattr(editor, name, None)
                    if callable(fn):
                        try:
                            fn()
                        except Exception:
                            pass
        except Exception as exc:
            for child in host.winfo_children():
                child.destroy()
            ttk.Label(host, text=f"Nie udało się otworzyć kartoteki {label}:\n{exc}", justify="left").pack(anchor="nw", padx=12, pady=12)

    cached_load_catalog._wm_cached_catalog = True
    GPP.PlanistaPanel._load_catalog = cached_load_catalog


def _install_orders_help() -> None:
    """Dołącz pomoc do istniejącego paska Zleceń bez przejmowania budowy tabeli."""
    import gui_planista_panel as GPP
    from ui_context_help import add_help_button

    current_build = GPP.PlanistaPanel._build_orders
    if getattr(current_build, "_wm_help", False):
        return

    help_by_text = {
        "Ustaw / zmień termin": "Ustawia termin realizacji wybranego zlecenia. Termin jest synchronizowany z powiązaną dyspozycją.",
        "Ilość / rzaz / półprodukty…": "Zmienia ilość produktu, rzaz i ewentualne korekty półproduktów. Po zapisie WM ponownie liczy zapotrzebowanie i rezerwacje.",
        "Wykonano…": "Rozlicza łączną wykonaną ilość zlecenia. WM zużywa odpowiednią część zarezerwowanych półproduktów i surowców.",
        "Pokaż zapotrzebowanie": "Pokazuje półprodukty i surowce potrzebne do realizacji zlecenia. W tym miejscu zobaczysz również wykryte braki materiałowe.",
        "Drukuj małe zlecenie": "Przygotowuje skrócony wydruk wybranego zlecenia produkcyjnego. Wydruk otwierany jest z bieżących danych Planisty.",
    }

    def build_orders(self, parent):
        # Jedynym właścicielem Treeview, kolumn, nagłówków i szerokości pozostaje
        # gui_planista_panel.PlanistaPanel._build_orders. Runtime dopina tylko pomoc.
        current_build(self, parent)
        bars = [child for child in parent.winfo_children() if isinstance(child, ttk.Frame)]
        if not bars:
            return
        buttons = bars[-1]
        for widget in list(buttons.winfo_children()):
            if not isinstance(widget, ttk.Button):
                continue
            try:
                text = str(widget.cget("text") or "")
            except Exception:
                continue
            help_text = help_by_text.get(text)
            if not help_text:
                continue
            help_button = add_help_button(buttons, help_text, command_only=False)
            help_button.pack(side="left", padx=(2, 4), after=widget)

    build_orders._wm_help = True
    build_orders._wm_original = current_build
    GPP.PlanistaPanel._build_orders = build_orders


def install_planista_safety_runtime() -> None:
    _install_bom_root_guard()
    _install_progress_guard()
    _install_catalog_guards()
    _install_catalog_cache()
    _install_orders_help()


__all__ = ["install_planista_safety_runtime", "_reservation_state", "_sync_bom_root"]
