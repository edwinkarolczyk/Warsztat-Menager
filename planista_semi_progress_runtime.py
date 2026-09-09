# WM-VERSION: 0.1
# Plik: planista_semi_progress_runtime.py
# version: 1.0
"""Postęp półproduktów w zleceniu oraz powiązania Półprodukt -> Produkt."""
from __future__ import annotations

import copy
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk


_EPS = 1e-9


def _f(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _fmt(value) -> str:
    number = _f(value)
    return str(int(number)) if number.is_integer() else f"{number:.3f}".rstrip("0").rstrip(".")


def _full_semi_targets(order: dict) -> dict[str, dict]:
    """Zwróć docelowe ilości półproduktów dla całego zlecenia."""
    import bom

    qty = max(0.0, _f(order.get("ilosc")))
    product = str(order.get("produkt") or "").strip()
    overrides = order.get("korekty_polproduktow") or {}
    targets: dict[str, dict] = {}

    if product and qty > 0:
        try:
            expanded = bom.compute_bom_for_prd(product, qty, version=order.get("version"))
        except Exception:
            expanded = {}
        for code, rec in (expanded or {}).items():
            if not isinstance(rec, dict):
                continue
            code = str(code)
            target = _f(overrides.get(code, rec.get("ilosc", 0)))
            targets[code] = {
                "nazwa": str(rec.get("nazwa") or code),
                "potrzeba": max(0.0, target),
            }

    for code, value in overrides.items():
        code = str(code)
        if code not in targets:
            plan_rec = (order.get("plan_polprodukty") or {}).get(code) or {}
            targets[code] = {
                "nazwa": str(plan_rec.get("nazwa") or code),
                "potrzeba": max(0.0, _f(value)),
            }

    if not targets:
        for code, rec in (order.get("plan_polprodukty") or {}).items():
            if not isinstance(rec, dict):
                continue
            targets[str(code)] = {
                "nazwa": str(rec.get("nazwa") or code),
                "potrzeba": max(0.0, _f(rec.get("potrzeba", rec.get("wyliczone", 0)))),
            }
    return targets


def _preview_stock_baseline(order: dict, targets: dict[str, dict] | None = None) -> dict[str, float]:
    targets = targets or _full_semi_targets(order)
    saved = order.get("polprodukty_z_magazynu_baza")
    if isinstance(saved, dict):
        return {str(code): max(0.0, _f(value)) for code, value in saved.items()}

    plan = order.get("plan_polprodukty") or {}
    out = {}
    for code, target in targets.items():
        rec = plan.get(code) if isinstance(plan.get(code), dict) else {}
        out[code] = min(max(0.0, _f(target.get("potrzeba"))), max(0.0, _f(rec.get("z_magazynu"))))
    return out


def _ensure_tracking_baseline(order: dict) -> None:
    targets = _full_semi_targets(order)
    if not isinstance(order.get("polprodukty_z_magazynu_baza"), dict):
        order["polprodukty_z_magazynu_baza"] = _preview_stock_baseline(order, targets)
    order["sledzenie_polproduktow"] = True
    order.setdefault("wykonano_polprodukty", {})


def semi_progress_rows(order: dict) -> list[dict]:
    targets = _full_semi_targets(order)
    baseline = _preview_stock_baseline(order, targets)
    made = order.get("wykonano_polprodukty") or {}
    rows = []
    for code, target in targets.items():
        need = max(0.0, _f(target.get("potrzeba")))
        from_stock = min(need, max(0.0, _f(baseline.get(code))))
        to_make = max(0.0, need - from_stock)
        done = max(0.0, _f(made.get(code)))
        rows.append(
            {
                "kod": code,
                "nazwa": str(target.get("nazwa") or code),
                "potrzeba": need,
                "z_magazynu": from_stock,
                "do_wykonania": to_make,
                "wykonano": done,
                "pozostalo": max(0.0, to_make - done),
            }
        )
    return rows


def semi_shortages_for_completion(order: dict, new_product_done: float) -> list[dict]:
    """Sprawdź, czy zgłoszony postęp półproduktów wystarcza do montażu produktu."""
    if not order.get("sledzenie_polproduktow"):
        return []
    qty = max(0.0, _f(order.get("ilosc")))
    if qty <= _EPS:
        return []

    done_product = max(0.0, min(qty, _f(new_product_done)))
    ratio = done_product / qty
    made = order.get("wykonano_polprodukty") or {}
    targets = _full_semi_targets(order)
    baseline = _preview_stock_baseline(order, targets)
    shortages = []
    for code, target in targets.items():
        total_need = max(0.0, _f(target.get("potrzeba")))
        from_stock = min(total_need, max(0.0, _f(baseline.get(code))))
        # Najpierw wykorzystujemy półprodukty z magazynu; produkcja własna jest
        # wymagana dopiero ponad tę bazę.
        required_made = max(0.0, total_need * ratio - from_stock)
        reported = max(0.0, _f(made.get(code)))
        if reported + _EPS < required_made:
            shortages.append(
                {
                    "kod": code,
                    "nazwa": str(target.get("nazwa") or code),
                    "wymagane_wykonane": required_made,
                    "zgloszone_wykonane": reported,
                    "brakuje": required_made - reported,
                }
            )
    return shortages


def report_polprodukt_wykonano(zlec_id, kod_polproduktu, wykonano, kto="system"):
    """Zapisz łączny postęp wykonania jednego półproduktu w zleceniu."""
    import zlecenia_logika as ZL

    path = ZL._order_path(zlec_id)
    order = ZL._read_json(path)
    _ensure_tracking_baseline(order)
    code = str(kod_polproduktu or "").strip()
    targets = _full_semi_targets(order)
    if code not in targets:
        raise KeyError(f"Półprodukt {code} nie należy do tego zlecenia.")

    baseline = _preview_stock_baseline(order, targets)
    target_total = max(0.0, _f(targets[code].get("potrzeba")))
    from_stock = min(target_total, max(0.0, _f(baseline.get(code))))
    max_to_make = max(0.0, target_total - from_stock)
    progress = dict(order.get("wykonano_polprodukty") or {})
    old = max(0.0, _f(progress.get(code)))
    new = float(wykonano)

    if new < old - _EPS:
        raise ValueError("Nie można zmniejszyć już zgłoszonej ilości półproduktu.")
    if new < 0:
        raise ValueError("Wykonana ilość półproduktu nie może być ujemna.")
    if new > max_to_make + _EPS:
        raise ValueError(
            f"Dla półproduktu {targets[code].get('nazwa') or code} plan przewiduje do wykonania "
            f"maksymalnie {_fmt(max_to_make)} szt. Pozostała część jest pokryta z magazynu."
        )
    if abs(new - old) <= _EPS:
        return order

    progress[code] = new
    order["wykonano_polprodukty"] = progress
    if new > 0 and _f(order.get("wykonano")) <= _EPS and str(order.get("status") or "") == "nowe":
        order["status"] = "w przygotowaniu"
    order.setdefault("historia", []).append(
        {
            "kiedy": datetime.now().isoformat(timespec="seconds"),
            "kto": kto,
            "co": f"półprodukt {code}: wykonano -> {_fmt(new)}",
        }
    )
    ZL._write_json(path, order)
    return order


def _semi_product_links(model) -> dict[str, list[str]]:
    """Odwrócone powiązanie: kod półproduktu -> aktywne produkty."""
    out: dict[str, list[str]] = {}
    for symbol, rec in getattr(model, "produkty", {}).items():
        if not isinstance(rec, dict):
            continue
        product_name = str(rec.get("nazwa") or symbol)
        display = f"{product_name} [{symbol}]"
        rows = rec.get("BOM") or rec.get("bom") or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("kod") or row.get("id") or "").strip()
            if not code:
                continue
            out.setdefault(code, [])
            if display not in out[code]:
                out[code].append(display)
    return out


def _guard_quantity_change(order: dict, new_qty: float) -> None:
    if not order.get("sledzenie_polproduktow"):
        return
    candidate = copy.deepcopy(order)
    candidate["ilosc"] = float(new_qty)
    targets = _full_semi_targets(candidate)
    baseline = _preview_stock_baseline(order, targets)
    made = order.get("wykonano_polprodukty") or {}
    errors = []
    for code, value in made.items():
        reported = max(0.0, _f(value))
        if reported <= _EPS:
            continue
        target = max(0.0, _f((targets.get(str(code)) or {}).get("potrzeba")))
        from_stock = min(target, max(0.0, _f(baseline.get(str(code)))))
        max_to_make = max(0.0, target - from_stock)
        if reported > max_to_make + _EPS:
            errors.append(f"{code}: zgłoszono {_fmt(reported)}, nowy plan {_fmt(max_to_make)}")
    if errors:
        raise ValueError(
            "Nie można zmniejszyć ilości zlecenia poniżej już zgłoszonego postępu półproduktów:\n"
            + "\n".join(errors)
        )


def install_planista_semi_progress_runtime() -> None:
    import gui_magazyn_bom as GMB
    import gui_planista_panel as GPP
    import zlecenia_logika as ZL
    import zlecenia_progress as ZP
    from ui_context_help import add_help_button

    # Backend: ochrona edycji ilości po zgłoszeniu postępu półproduktów.
    current_update = ZP.update_zlecenie
    if not getattr(current_update, "_wm_semi_progress_guard", False):
        def guarded_update(zlec_id, *args, **kwargs):
            if kwargs.get("ilosc") is not None:
                order = ZL._read_json(ZL._order_path(zlec_id))
                _guard_quantity_change(order, float(kwargs["ilosc"]))
            return current_update(zlec_id, *args, **kwargs)
        guarded_update._wm_semi_progress_guard = True
        guarded_update._wm_original = current_update
        ZP.update_zlecenie = guarded_update
        ZL.update_zlecenie = guarded_update

    # Backend: po uruchomieniu śledzenia półproduktów gotowy produkt wymaga ich
    # odpowiedniego postępu, chyba że UI świadomie potwierdzi wyjątek.
    current_report = ZP.report_wykonano
    if not getattr(current_report, "_wm_semi_progress_guard", False):
        def guarded_report(zlec_id, wykonano, kto="system", allow_incomplete_semis=False):
            order = ZL._read_json(ZL._order_path(zlec_id))
            shortages = semi_shortages_for_completion(order, float(wykonano))
            if shortages and not allow_incomplete_semis:
                details = "\n".join(
                    f"{row['nazwa']}: brakuje zgłosić {_fmt(row['brakuje'])} szt."
                    for row in shortages
                )
                raise ValueError(
                    "Zgłoszony postęp półproduktów jest za mały dla tej liczby gotowych produktów:\n"
                    + details
                )
            return current_report(zlec_id, wykonano, kto=kto)
        guarded_report._wm_semi_progress_guard = True
        guarded_report._wm_original = current_report
        ZP.report_wykonano = guarded_report
        ZL.report_wykonano = guarded_report

    # Katalog Półproduktów: kolumna z aktywnymi produktami, które używają pozycji.
    UI = GMB.MagazynBOM
    old_build_pp = UI._build_polprodukty
    old_load_pp = UI._load_polprodukty
    if not getattr(old_build_pp, "_wm_product_links_column", False):
        def build_pp(self, parent):
            old_build_pp(self, parent)
            columns = list(self.tree_pp.cget("columns"))
            if "produkty" not in columns:
                if "id" in columns:
                    columns.insert(columns.index("id"), "produkty")
                else:
                    columns.append("produkty")
                self.tree_pp.configure(columns=tuple(columns))
            self.tree_pp.heading("produkty", text="Produkt(y)")
            self.tree_pp.column("produkty", width=280, anchor="w")
        build_pp._wm_product_links_column = True
        build_pp._wm_original = old_build_pp
        UI._build_polprodukty = build_pp

        def load_pp(self):
            if "produkty" not in list(self.tree_pp.cget("columns")):
                return old_load_pp(self)
            links = _semi_product_links(self.model)
            self.tree_pp.delete(*self.tree_pp.get_children())
            for code, rec in sorted(
                self.model.polprodukty.items(),
                key=lambda pair: str(pair[1].get("nazwa", "")).casefold(),
            ):
                raw = rec.get("surowiec") if isinstance(rec.get("surowiec"), dict) else {}
                raw_id = str(raw.get("kod") or "")
                raw_name = self._raw_by_id.get(raw_id, {}).get("nazwa") or raw_id
                self.tree_pp.insert(
                    "",
                    "end",
                    values=(
                        rec.get("nazwa", ""),
                        raw_name,
                        GMB._fmt_num(raw.get("ilosc_na_szt", 0)),
                        raw.get("jednostka", ""),
                        ", ".join(rec.get("czynnosci", []) or []),
                        ", ".join(links.get(code, [])) or "—",
                        code,
                    ),
                )
        load_pp._wm_product_links_column = True
        load_pp._wm_original = old_load_pp
        UI._load_polprodukty = load_pp

    Panel = GPP.PlanistaPanel
    old_build_orders = Panel._build_orders
    old_report_done = Panel.report_done
    if getattr(old_build_orders, "_wm_semi_progress", False):
        return

    def report_semis(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Postęp półproduktów — {order.get('id')}")
        dlg.transient(self.root)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(
            frm,
            text=f"Zlecenie {order.get('id')} — produkt {order.get('produkt')}",
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        cols = ("nazwa", "potrzeba", "magazyn", "do_wyk", "wykonano", "pozostalo", "id")
        tree = ttk.Treeview(frm, columns=cols, show="headings", height=8)
        labels = {
            "nazwa": "Półprodukt",
            "potrzeba": "Potrzeba łącznie",
            "magazyn": "Z magazynu",
            "do_wyk": "Plan do wykonania",
            "wykonano": "Wykonano",
            "pozostalo": "Pozostało",
            "id": "ID",
        }
        widths = {"nazwa": 220, "potrzeba": 110, "magazyn": 100, "do_wyk": 120, "wykonano": 100, "pozostalo": 100, "id": 90}
        for col in cols:
            tree.heading(col, text=labels[col])
            tree.column(col, width=widths[col], anchor="w")
        tree.pack(fill="both", expand=True)

        edit = ttk.Frame(frm)
        edit.pack(fill="x", pady=(8, 0))
        ttk.Label(edit, text="Nowa łączna ilość wykonana:").pack(side="left")
        value = tk.StringVar(value="0")
        ttk.Entry(edit, textvariable=value, width=12).pack(side="left", padx=(8, 4))
        add_help_button(
            edit,
            "Wpisz łączną liczbę sztuk wybranego półproduktu wykonaną w tym zleceniu. Ta wartość śledzi postęp produkcji; rozchód materiału pozostaje rozliczany obecnym mechanizmem zlecenia.",
            command_only=False,
        ).pack(side="left", padx=(0, 8))

        def fill(current_order):
            tree.delete(*tree.get_children())
            for row in semi_progress_rows(current_order):
                tree.insert(
                    "",
                    "end",
                    iid=row["kod"],
                    values=(
                        row["nazwa"],
                        _fmt(row["potrzeba"]),
                        _fmt(row["z_magazynu"]),
                        _fmt(row["do_wykonania"]),
                        _fmt(row["wykonano"]),
                        _fmt(row["pozostalo"]),
                        row["kod"],
                    ),
                )

        def on_select(_event=None):
            selection = tree.selection()
            if not selection:
                return
            code = selection[0]
            row = next((item for item in semi_progress_rows(order) if item["kod"] == code), None)
            if row:
                value.set(_fmt(row["wykonano"]))

        def save_progress():
            nonlocal order
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("Postęp półproduktów", "Wybierz półprodukt.", parent=dlg)
                return
            try:
                order = report_polprodukt_wykonano(
                    order["id"],
                    selection[0],
                    float(value.get().replace(",", ".")),
                    kto=self.login or "system",
                )
            except Exception as exc:
                messagebox.showerror("Postęp półproduktów", str(exc), parent=dlg)
                return
            fill(order)
            self.refresh()

        tree.bind("<<TreeviewSelect>>", on_select)
        ttk.Button(edit, text="Zapisz postęp", command=save_progress).pack(side="left")
        ttk.Button(edit, text="Zamknij", command=dlg.destroy).pack(side="right")
        fill(order)

    def report_done(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Rozlicz wykonanie")
        dlg.transient(self.root)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        current = _f(order.get("wykonano"))
        ttk.Label(frm, text=f"Dotychczas wykonano: {_fmt(current)}").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frm, text="Nowa łączna ilość wykonana:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        var = tk.StringVar(value=_fmt(current))
        ttk.Entry(frm, textvariable=var, width=16).grid(row=1, column=1, padx=(8, 4), pady=(8, 0))
        add_help_button(
            frm,
            "Po włączeniu śledzenia półproduktów WM sprawdzi, czy ich zgłoszony postęp wystarcza do podanej liczby gotowych produktów. Brakujący postęp można zatwierdzić tylko po świadomym potwierdzeniu ostrzeżenia.",
            row=1,
            column=2,
            padx=(0, 0),
            pady=(8, 0),
        )

        def save():
            try:
                new_value = float(var.get().replace(",", "."))
                shortages = semi_shortages_for_completion(order, new_value)
                allow = False
                if shortages:
                    details = "\n".join(
                        f"• {row['nazwa']}: brakuje zgłosić {_fmt(row['brakuje'])} szt."
                        for row in shortages
                    )
                    allow = messagebox.askyesno(
                        "Brak postępu półproduktów",
                        "Zgłoszony postęp półproduktów jest za mały dla tej liczby gotowych produktów:\n\n"
                        + details
                        + "\n\nZatwierdzić wykonanie produktu mimo to?",
                        parent=dlg,
                    )
                    if not allow:
                        return
                ZP.report_wykonano(
                    order["id"],
                    new_value,
                    kto=self.login or "system",
                    allow_incomplete_semis=allow,
                )
            except Exception as exc:
                messagebox.showerror("Rozliczenie", str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        ttk.Button(frm, text="Zapisz", command=save).grid(row=2, column=1, sticky="e", pady=(10, 0))

    def build_orders(self, parent):
        old_build_orders(self, parent)
        bars = [child for child in parent.winfo_children() if isinstance(child, ttk.Frame)]
        if not bars:
            return
        bar = bars[-1]
        ttk.Button(bar, text="Wykonano półprodukty…", command=self.report_semis).pack(side="left", padx=(6, 0))
        add_help_button(
            bar,
            "Rejestruje postęp wykonania poszczególnych półproduktów w wybranym zleceniu. WM wykorzystuje ten postęp do kontroli, czy można rozliczyć odpowiednią liczbę gotowych produktów.",
            command_only=False,
        ).pack(side="left", padx=(4, 0))

    Panel.report_semis = report_semis
    Panel.report_done = report_done
    build_orders._wm_semi_progress = True
    build_orders._wm_original = old_build_orders
    Panel._build_orders = build_orders


__all__ = [
    "install_planista_semi_progress_runtime",
    "report_polprodukt_wykonano",
    "semi_progress_rows",
    "semi_shortages_for_completion",
    "_full_semi_targets",
    "_semi_product_links",
]
