# version: 1.0
"""Integracja Planista -> Dyspozycje dla zleceń produkcyjnych."""

from __future__ import annotations

import datetime as _dt
import html as _html
import os
import re
import tempfile
import webbrowser
from pathlib import Path
from typing import Any

_ACTIVE_STATUSES = {"nowa", "w_toku", "wstrzymana"}
_PRODUCTION_LABELS = {
    "zlecenie produkcyjne",
    "wykonanie produkcji",
    "zlecenie_wykonania",
}


def _fmt_qty(value: Any) -> str:
    try:
        number = float(value or 0)
    except Exception:
        return str(value or "")
    return str(int(number)) if number.is_integer() else f"{number:.3f}".rstrip("0").rstrip(".")


def _parse_deadline(value: Any) -> _dt.date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%y", "%d-%m-%Y"):
        try:
            return _dt.datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def _deadline_iso(value: Any) -> str:
    parsed = _parse_deadline(value)
    return parsed.isoformat() if parsed is not None else ""


def _deadline_display(value: Any) -> str:
    parsed = _parse_deadline(value)
    return parsed.strftime("%d-%m-%y") if parsed is not None else ""


def priority_for_deadline(value: Any, *, today: _dt.date | None = None) -> str:
    """Wyznacz priorytet produkcji z terminu zlecenia."""
    deadline = _parse_deadline(value)
    if deadline is None:
        return "normalny"
    base = today or _dt.date.today()
    days = (deadline - base).days
    if days <= 3:
        return "krytyczny"
    if days <= 7:
        return "wysoki"
    if days <= 21:
        return "normalny"
    return "niski"


def creator_type_values(values, *, edit_mode: bool) -> list[str]:
    """Magazyn ukryj tylko podczas tworzenia nowej Dyspozycji."""
    result = [str(value) for value in values]
    if edit_mode:
        return result
    return [value for value in result if value.strip().casefold() != "magazyn"]


def _planista_orders() -> list[dict[str, Any]]:
    try:
        import zlecenia_logika as ZL

        rows = ZL.list_zlecenia()
    except Exception:
        rows = []
    return [dict(row) for row in rows or [] if isinstance(row, dict)]


def _order_id(order: dict[str, Any]) -> str:
    return str(order.get("id") or order.get("number") or "").strip()


def planista_order_choices() -> list[tuple[str, str]]:
    """Zwróć wyłącznie realne zlecenia z aktualnego Planisty."""
    out: list[tuple[str, str]] = []
    for order in _planista_orders():
        order_id = _order_id(order)
        if not order_id:
            continue
        product = str(order.get("produkt") or order.get("product_code") or "—").strip() or "—"
        qty = _fmt_qty(order.get("ilosc", order.get("qty", 0)))
        out.append((f"zlecenie:{order_id}", f"{order_id} — {product} — {qty} szt."))
    return out


def _find_order(order_id: str) -> dict[str, Any]:
    wanted = str(order_id or "").strip()
    if wanted.lower().startswith("zlecenie:"):
        wanted = wanted.split(":", 1)[1].strip()
    for order in _planista_orders():
        if _order_id(order).casefold() == wanted.casefold():
            return order
    return {}


def planista_order_context(object_id: str) -> dict[str, Any]:
    """Kontekst zgodny z kreatorem Dyspozycji, oparty na bieżącym Planista/Zlecenia."""
    order = _find_order(object_id)
    if not order:
        raw = str(object_id or "").strip()
        code = raw.split(":", 1)[1] if raw.lower().startswith("zlecenie:") else raw
        return {
            "poziom_wykonania": "zlecenie",
            "nr_zlecenia": code,
            "ilosc_domyslna": 1,
        }

    order_id = _order_id(order)
    product = str(order.get("produkt") or order.get("product_code") or "").strip()
    qty = order.get("ilosc", order.get("qty", 1))
    deadline = _deadline_iso(order.get("termin") or order.get("deadline"))
    return {
        "poziom_wykonania": "zlecenie",
        "nr_zlecenia": order_id,
        "order_id": order_id,
        "product_code": product,
        "ilosc_domyslna": qty,
        "termin": deadline,
        "priorytet": priority_for_deadline(deadline),
        "client": str(order.get("client") or order.get("klient") or ""),
    }


def find_active_planista_dispatch(
    order_id: str,
    *,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Znajdź aktywną dyspozycję wykonania przypiętą do tego zlecenia."""
    wanted = str(order_id or "").strip()
    if wanted.lower().startswith("zlecenie:"):
        wanted = wanted.split(":", 1)[1].strip()
    if not wanted:
        return None

    if rows is None:
        try:
            from dyspozycje_store import load_dyspozycje

            rows = load_dyspozycje()
        except Exception:
            rows = []

    object_key = f"zlecenie:{wanted}".casefold()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        typ = str(row.get("typ_dyspozycji") or "").strip().lower()
        if typ not in {"zlecenie_wykonania", "zamowienie"}:
            continue
        status = str(row.get("status") or "nowa").strip().lower()
        if status not in _ACTIVE_STATUSES:
            continue
        object_id = str(row.get("obiekt_id") or "").strip().casefold()
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        meta_order = str(meta.get("nr_zlecenia") or meta.get("order_id") or "").strip()
        if object_id == object_key or meta_order.casefold() == wanted.casefold():
            return dict(row)
    return None


def ensure_planista_dispatch(
    order: dict[str, Any],
    *,
    autor: str = "",
) -> tuple[dict[str, Any], bool]:
    """Utwórz jedną aktywną Dyspozycję dla zlecenia Planisty."""
    from dyspozycje_store import add_dyspozycja, make_dyspozycja

    order_id = _order_id(order)
    if not order_id:
        raise ValueError("Zlecenie Planisty nie ma ID.")

    existing = find_active_planista_dispatch(order_id)
    if existing is not None:
        return existing, False

    product = str(order.get("produkt") or order.get("product_code") or "").strip()
    qty = order.get("ilosc", order.get("qty", 0))
    deadline = _deadline_iso(order.get("termin") or order.get("deadline"))
    meta = {
        "poziom_wykonania": "zlecenie",
        "nr_zlecenia": order_id,
        "order_id": order_id,
        "product_code": product,
        "ilosc_do_wykonania": qty,
        "termin_planisty": deadline,
    }
    record = make_dyspozycja(
        typ_dyspozycji="zlecenie_wykonania",
        tytul=f"Wykonaj Zlecenie {order_id}",
        opis=f"Produkt: {product or '—'} | Ilość: {_fmt_qty(qty)}",
        autor=str(autor or "system").strip() or "system",
        przypisane_do="",
        dla_wszystkich=True,
        termin=deadline,
        priorytet=priority_for_deadline(deadline),
        modul_zrodlowy="zlecenia",
        obiekt_id=f"zlecenie:{order_id}",
        status="nowa",
        meta=meta,
    )
    add_dyspozycja(record)
    return record, True


def enhance_work_order_html(order: dict[str, Any], source_html: str) -> str:
    """Zamień parę Ilość/Wykonano na warsztatowe Potrzeba / wykonane."""
    qty = _html.escape(_fmt_qty(order.get("ilosc", order.get("qty", 0))))
    replacement = (
        f"<div><b>Potrzeba / wykonane:</b> {qty} / "
        "<b>[&nbsp;&nbsp;&nbsp;]</b></div>"
    )
    pattern = r"<div><b>Ilość:</b>.*?</div>\s*<div><b>Wykonano:</b>.*?</div>"
    changed, count = re.subn(pattern, replacement, str(source_html or ""), count=1, flags=re.S)
    if count:
        return changed
    marker = "</div>\n<table>"
    if marker in str(source_html or ""):
        return str(source_html).replace(marker, f"{replacement}\n</div>\n<table>", 1)
    return str(source_html or "")


def _is_production_label(value: Any) -> bool:
    return str(value or "").strip().casefold() in _PRODUCTION_LABELS


def _walk_widgets(widget):
    try:
        children = list(widget.winfo_children())
    except Exception:
        children = []
    for child in children:
        yield child
        yield from _walk_widgets(child)


def _grid_widget(frame, cls, row: int, column: int):
    try:
        children = list(frame.winfo_children())
    except Exception:
        return None
    for widget in children:
        if not isinstance(widget, cls):
            continue
        try:
            info = widget.grid_info()
            if int(info.get("row", -1)) == row and int(info.get("column", -1)) == column:
                return widget
        except Exception:
            continue
    return None


def _set_textvariable(window, widget, value: Any) -> None:
    try:
        name = str(widget.cget("textvariable") or "")
        if name:
            window.setvar(name, str(value))
            return
    except Exception:
        pass
    try:
        widget.set(str(value))
    except Exception:
        pass


def _configure_creator_window(window) -> None:
    """Dostosuj nowy kreator; edycja zachowuje historyczny typ Magazyn."""
    try:
        title = str(window.title() or "")
    except Exception:
        return
    if title not in {"Kreator – Dodaj Dyspozycję", "Kreator – Edytuj Dyspozycję"}:
        return
    if getattr(window, "_wm_planista_dispatch_bound", False):
        return

    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception:
        return

    frames = [child for child in window.winfo_children() if isinstance(child, ttk.Frame)]
    if not frames:
        return
    frame = frames[0]
    type_combo = _grid_widget(frame, ttk.Combobox, 1, 1)
    object_combo = _grid_widget(frame, ttk.Combobox, 3, 1)
    priority_combo = _grid_widget(frame, ttk.Combobox, 5, 1)
    deadline_frame = _grid_widget(frame, ttk.Frame, 6, 1)
    qty_frame = _grid_widget(frame, ttk.Frame, 3, 2)
    if type_combo is None or object_combo is None or priority_combo is None:
        return

    deadline_entry = None
    if deadline_frame is not None:
        deadline_entry = next(
            (child for child in deadline_frame.winfo_children() if isinstance(child, (ttk.Entry, tk.Entry))),
            None,
        )
    qty_entry = None
    if qty_frame is not None:
        qty_entry = next(
            (child for child in qty_frame.winfo_children() if isinstance(child, (ttk.Entry, tk.Entry))),
            None,
        )

    window._wm_planista_dispatch_bound = True
    edit_mode = title == "Kreator – Edytuj Dyspozycję"
    try:
        values = creator_type_values(type_combo.cget("values"), edit_mode=edit_mode)
        type_combo.configure(values=values)
        if not edit_mode and str(type_combo.get()).strip().casefold() == "magazyn":
            type_combo.set(values[0] if values else "")
    except Exception:
        pass

    def _selected_context() -> dict[str, Any]:
        label = str(object_combo.get() or "").strip()
        object_id = ""
        for candidate_id, candidate_label in planista_order_choices():
            if str(candidate_label).strip() == label:
                object_id = candidate_id
                break
        return planista_order_context(object_id) if object_id else {}

    def _sync_fields() -> None:
        if not _is_production_label(type_combo.get()):
            try:
                priority_combo.configure(state="readonly")
            except Exception:
                pass
            return
        ctx = _selected_context()
        if not ctx:
            return
        if qty_entry is not None:
            _set_textvariable(window, qty_entry, _fmt_qty(ctx.get("ilosc_domyslna", 1)))
            try:
                qty_entry.configure(state="readonly")
            except Exception:
                pass
        if deadline_entry is not None:
            _set_textvariable(window, deadline_entry, _deadline_display(ctx.get("termin")))
        _set_textvariable(window, priority_combo, priority_for_deadline(ctx.get("termin")))
        try:
            priority_combo.configure(state="disabled")
        except Exception:
            pass

    def _after_selection(_event=None) -> None:
        try:
            window.after_idle(_sync_fields)
        except Exception:
            _sync_fields()

    type_combo.bind("<<ComboboxSelected>>", _after_selection, add="+")
    object_combo.bind("<<ComboboxSelected>>", _after_selection, add="+")

    if not edit_mode:
        save_button = next(
            (
                widget
                for widget in _walk_widgets(window)
                if isinstance(widget, ttk.Button)
                and str(widget.cget("text") or "").strip() == "Zapisz"
            ),
            None,
        )
        if save_button is not None:
            original_command = str(save_button.cget("command") or "")

            def _guarded_save() -> None:
                if _is_production_label(type_combo.get()):
                    ctx = _selected_context()
                    order_id = str(ctx.get("nr_zlecenia") or "").strip()
                    if order_id and find_active_planista_dispatch(order_id) is not None:
                        messagebox.showwarning(
                            "Dyspozycje",
                            f"Zlecenie {order_id} ma już aktywną Dyspozycję. Nie utworzono duplikatu.",
                            parent=window,
                        )
                        return
                if original_command:
                    window.tk.call(original_command)

            save_button.configure(command=_guarded_save)

    _after_selection()


def _patch_sources_and_creator() -> None:
    import dyspozycje_sources as sources
    import gui_dyspozycje_creator as creator

    sources.load_zlecenie_wykonania_choices = planista_order_choices
    sources.load_zlecenie_wykonania_context = planista_order_context
    creator.load_zlecenie_wykonania_choices = planista_order_choices
    creator.load_zlecenie_wykonania_context = planista_order_context
    creator._DYSP_TYPE_LABELS["zlecenie_wykonania"] = "Zlecenie produkcyjne"

    old_open = creator.open_dyspozycje_creator
    if getattr(old_open, "_wm_planista_dispatch_runtime", False):
        return

    def open_creator(*args, **kwargs):
        window = old_open(*args, **kwargs)
        try:
            window.after_idle(lambda: _configure_creator_window(window))
        except Exception:
            _configure_creator_window(window)
        return window

    open_creator._wm_planista_dispatch_runtime = True
    open_creator._wm_original = old_open
    creator.open_dyspozycje_creator = open_creator


def _patch_work_order_html() -> None:
    import gui_planista as GP
    import gui_planista_panel as GPP

    base = GP._work_order_html
    if getattr(base, "_wm_dispatch_progress", False):
        enhanced = base
    else:
        def enhanced(order):
            return enhance_work_order_html(order, base(order))

        enhanced._wm_dispatch_progress = True
        enhanced._wm_original = base
        GP._work_order_html = enhanced
    GPP._work_order_html = enhanced


def _print_order(order: dict[str, Any]) -> None:
    import gui_planista as GP

    folder = Path(tempfile.gettempdir()) / "WarsztatMenager" / "wydruki"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"zlecenie_{_order_id(order)}.html"
    path.write_text(GP._work_order_html(order), encoding="utf-8")
    if os.name == "nt":
        os.startfile(str(path))
    else:
        webbrowser.open(path.as_uri())


def _find_add_order_dialog(root):
    for widget in _walk_widgets(root):
        try:
            if str(widget.winfo_class()) == "Toplevel" and str(widget.title()) == "Dodaj zlecenie":
                return widget
        except Exception:
            continue
    return None


def _patch_planista_add_order() -> None:
    import gui_planista_panel as GPP
    from tkinter import messagebox, ttk

    Panel = GPP.PlanistaPanel
    old_add = getattr(Panel, "add_order", None)
    if not callable(old_add) or getattr(old_add, "_wm_dispatch_autocreate", False):
        return

    def add_order(self):
        result = old_add(self)
        dialog = _find_add_order_dialog(self.root)
        if dialog is None:
            return result

        add_button = next(
            (
                widget
                for widget in _walk_widgets(dialog)
                if isinstance(widget, ttk.Button)
                and str(widget.cget("text") or "").strip() == "Dodaj zlecenie"
            ),
            None,
        )
        if add_button is None or getattr(dialog, "_wm_dispatch_save_wrapped", False):
            return result

        original_command = str(add_button.cget("command") or "")
        if not original_command:
            return result
        dialog._wm_dispatch_save_wrapped = True

        def _save_create_dispatch_print() -> None:
            before = {_order_id(row) for row in _planista_orders() if _order_id(row)}
            dialog.tk.call(original_command)
            created_order = next(
                (
                    row
                    for row in _planista_orders()
                    if _order_id(row) and _order_id(row) not in before
                ),
                None,
            )
            if created_order is None:
                return
            try:
                _record, created = ensure_planista_dispatch(
                    created_order,
                    autor=str(getattr(self, "login", "") or "system"),
                )
                if created:
                    _print_order(created_order)
            except Exception as exc:
                messagebox.showerror(
                    "Planista",
                    "Zlecenie zapisano, ale nie udało się utworzyć Dyspozycji lub wydruku:\n"
                    f"{exc}",
                    parent=self,
                )

        add_button.configure(command=_save_create_dispatch_print)
        return result

    add_order._wm_dispatch_autocreate = True
    add_order._wm_original = old_add
    Panel.add_order = add_order


_installed = False


def install_planista_dispatch_runtime() -> bool:
    """Włącz integrację raz na proces, bez migracji historycznych Dyspozycji."""
    global _installed
    if _installed:
        return True
    _patch_sources_and_creator()
    _patch_work_order_html()
    _patch_planista_add_order()
    _installed = True
    return True


__all__ = [
    "creator_type_values",
    "enhance_work_order_html",
    "ensure_planista_dispatch",
    "find_active_planista_dispatch",
    "install_planista_dispatch_runtime",
    "planista_order_choices",
    "planista_order_context",
    "priority_for_deadline",
]
