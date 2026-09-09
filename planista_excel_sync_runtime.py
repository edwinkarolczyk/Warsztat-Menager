# WM-VERSION: 0.1
# Plik: planista_excel_sync_runtime.py
# version: 1.0
"""Kontrolowany podgląd i zatwierdzanie synchronizacji Excel -> zlecenia WM."""

from __future__ import annotations

from collections import Counter
import tkinter as tk
from tkinter import messagebox, ttk

from planista_excel_orders import (
    ACTION_CONFLICT,
    ACTION_CREATE,
    ACTION_NONE,
    ACTION_PROTECTED,
    ACTION_REMOVED,
    ACTION_SKIP,
    ACTION_UPDATE,
    ExcelOrderSyncError,
    apply_order_sync,
    build_order_sync_plan,
)
from ui_context_help import add_help_button
from ui_theme import get_theme_color


WRITABLE_ACTIONS = {ACTION_CREATE, ACTION_UPDATE}

_SELECT_HELP = (
    "Zaznacz tylko pozycje z akcją Utwórz lub Aktualizuj. "
    "Pozycje chronione, niejednoznaczne i usunięte z Excela nie są zapisywane automatycznie."
)
_APPLY_HELP = (
    "Wykonuje wyłącznie zaznaczone pozycje po dodatkowym potwierdzeniu. "
    "Przed zapisem WM ponownie sprawdza konflikty i aktualny stan zleceń."
)


def _text(value) -> str:
    return str(value or "").strip()


def _fmt_qty(value) -> str:
    if value in (None, ""):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _writable_identities(plan: dict) -> set[str]:
    return {
        _text(item.get("identity"))
        for item in list(plan.get("items") or [])
        if isinstance(item, dict)
        and item.get("action") in WRITABLE_ACTIONS
        and _text(item.get("identity"))
    }


def _selected_action_counts(plan: dict, selected: set[str]) -> Counter:
    return Counter(
        item.get("action")
        for item in list(plan.get("items") or [])
        if isinstance(item, dict)
        and _text(item.get("identity")) in selected
        and item.get("action") in WRITABLE_ACTIONS
    )


def _sync_item_sort_key(item: dict) -> tuple[int, int]:
    action = item.get("action")
    priority = {
        ACTION_CREATE: 0,
        ACTION_UPDATE: 0,
        ACTION_NONE: 1,
        ACTION_PROTECTED: 2,
        ACTION_CONFLICT: 2,
        ACTION_SKIP: 3,
        ACTION_REMOVED: 4,
    }.get(action, 5)
    try:
        source_row = int(item.get("source_row") or 0)
    except (TypeError, ValueError):
        source_row = 0
    return priority, source_row


def _row_note(item: dict) -> str:
    row = item.get("row") if isinstance(item.get("row"), dict) else {}
    parts = []
    for value in (
        item.get("reason"),
        row.get("excel_change_note"),
        row.get("match_note"),
    ):
        text = _text(value)
        if text and text not in parts:
            parts.append(text)
    return "; ".join(parts)


def _change_label(item: dict) -> str:
    row = item.get("row") if isinstance(item.get("row"), dict) else {}
    status = _text(row.get("excel_change_status"))
    fields = [str(value) for value in list(row.get("excel_change_fields") or []) if str(value).strip()]
    if fields:
        return f"{status} — {', '.join(fields)}" if status else ", ".join(fields)
    return status


def _summary_text(plan: dict) -> str:
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return (
        f"{ACTION_CREATE}: {summary.get(ACTION_CREATE, 0)}   |   "
        f"{ACTION_UPDATE}: {summary.get(ACTION_UPDATE, 0)}   |   "
        f"{ACTION_NONE}: {summary.get(ACTION_NONE, 0)}   |   "
        f"{ACTION_PROTECTED}: {summary.get(ACTION_PROTECTED, 0)}   |   "
        f"{ACTION_CONFLICT}: {summary.get(ACTION_CONFLICT, 0)}   |   "
        f"{ACTION_SKIP}: {summary.get(ACTION_SKIP, 0)}"
    )


def show_excel_sync_preview(owner, payload: dict) -> None:
    """Pokaż akcje i pozwól jawnie zatwierdzić tylko bezpieczne operacje zapisu."""
    try:
        plan = build_order_sync_plan(payload)
    except Exception as exc:
        messagebox.showerror(
            "Synchronizacja planu Excel",
            f"Nie udało się przygotować podglądu synchronizacji:\n{exc}",
            parent=getattr(owner, "root", owner),
        )
        return

    root = getattr(owner, "root", owner)
    dlg = tk.Toplevel(root)
    dlg.title("Planista — synchronizacja Excel → zlecenia WM")
    dlg.transient(root)
    dlg.geometry("1560x760")

    selected: set[str] = set()
    item_by_iid: dict[str, dict] = {}

    top = ttk.Frame(dlg, padding=10)
    top.pack(fill="x")
    ttk.Label(
        top,
        text=(
            f"Plik: {payload.get('source_name', '')}   |   Arkusz: {payload.get('sheet', '')}   |   "
            f"Pozycje: {len(payload.get('rows') or [])}"
        ),
        font=("Arial", 10, "bold"),
    ).pack(anchor="w")
    summary_var = tk.StringVar(value=_summary_text(plan))
    ttk.Label(top, textvariable=summary_var).pack(anchor="w", pady=(3, 0))
    ttk.Label(
        top,
        text=(
            "Samo otwarcie tego okna niczego nie zapisuje. "
            "Zlecenia WM zmienią się dopiero po zaznaczeniu pozycji i dodatkowym potwierdzeniu; plik Excel pozostaje tylko do odczytu."
        ),
    ).pack(anchor="w", pady=(3, 0))

    body = ttk.Frame(dlg, padding=(10, 0, 10, 8))
    body.pack(fill="both", expand=True)
    cols = (
        "select",
        "excel",
        "wm_product",
        "qty",
        "change",
        "action",
        "workshop_order",
        "date",
        "process",
        "note",
    )
    labels = {
        "select": "Wybór",
        "excel": "Excel",
        "wm_product": "Produkt WM",
        "qty": "Ilość",
        "change": "Zmiana",
        "action": "Akcja",
        "workshop_order": "Zlecenie warsztatowe",
        "date": "Data wysyłki",
        "process": "Proces",
        "note": "Uwagi",
    }
    widths = {
        "select": 65,
        "excel": 310,
        "wm_product": 250,
        "qty": 75,
        "change": 190,
        "action": 125,
        "workshop_order": 125,
        "date": 105,
        "process": 95,
        "note": 440,
    }
    tree = ttk.Treeview(body, columns=cols, show="headings", selectmode="browse")
    for col in cols:
        tree.heading(col, text=labels[col])
        tree.column(col, width=widths[col], anchor="w", stretch=col in {"excel", "wm_product", "note"})

    tree.tag_configure(
        "writable",
        background=get_theme_color("success", fallback="#29a36a"),
        foreground=get_theme_color("fg", fallback="#ffffff"),
    )
    tree.tag_configure(
        "protected",
        background=get_theme_color("warning", fallback="#b7791f"),
        foreground=get_theme_color("fg", fallback="#ffffff"),
    )
    tree.tag_configure(
        "conflict",
        background=get_theme_color("danger", fallback="#b93b3b"),
        foreground=get_theme_color("fg", fallback="#ffffff"),
    )

    yscroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    xscroll = ttk.Scrollbar(body, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    yscroll.grid(row=0, column=1, sticky="ns")
    xscroll.grid(row=1, column=0, sticky="ew")
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=1)

    controls = ttk.Frame(dlg, padding=(10, 0, 10, 10))
    controls.pack(fill="x")
    selected_var = tk.StringVar(value="Zaznaczone: 0")
    ttk.Label(controls, textvariable=selected_var).pack(side="left", padx=(0, 12))

    apply_button = ttk.Button(controls, text="Wykonaj zaznaczone", state="disabled")

    def update_controls() -> None:
        selected_var.set(f"Zaznaczone: {len(selected)}")
        apply_button.configure(state="normal" if selected else "disabled")

    def tag_for(item: dict) -> tuple[str, ...]:
        action = item.get("action")
        if action in WRITABLE_ACTIONS:
            return ("writable",)
        if action == ACTION_PROTECTED:
            return ("protected",)
        if action == ACTION_CONFLICT:
            return ("conflict",)
        return ()

    def refresh_tree(new_plan: dict) -> None:
        nonlocal plan
        plan = new_plan
        selected.intersection_update(_writable_identities(plan))
        tree.delete(*tree.get_children())
        item_by_iid.clear()
        for idx, item in enumerate(sorted(list(plan.get("items") or []), key=_sync_item_sort_key)):
            if not isinstance(item, dict):
                continue
            row = item.get("row") if isinstance(item.get("row"), dict) else {}
            identity = _text(item.get("identity"))
            action = item.get("action")
            selectable = action in WRITABLE_ACTIONS and bool(identity)
            mark = "☑" if identity in selected and selectable else ("☐" if selectable else "—")
            excel_text = " | ".join(
                part
                for part in (
                    _text(item.get("nr_zlec")),
                    _text(row.get("excel_oznaczenie")),
                    _text(row.get("produkt")),
                )
                if part
            )
            wm_product = " | ".join(
                part
                for part in (
                    _text(item.get("wm_symbol")),
                    _text(item.get("wm_name")),
                )
                if part
            )
            iid = f"sync-{idx}"
            item_by_iid[iid] = item
            tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    mark,
                    excel_text,
                    wm_product,
                    _fmt_qty(item.get("ilosc")),
                    _change_label(item),
                    action or "",
                    item.get("order_id", ""),
                    item.get("termin", ""),
                    item.get("proces", ""),
                    _row_note(item),
                ),
                tags=tag_for(item),
            )
        summary_var.set(_summary_text(plan))
        update_controls()

    def toggle_iid(iid: str) -> None:
        item = item_by_iid.get(iid)
        if not item or item.get("action") not in WRITABLE_ACTIONS:
            return
        identity = _text(item.get("identity"))
        if not identity:
            return
        if identity in selected:
            selected.remove(identity)
            tree.set(iid, "select", "☐")
        else:
            selected.add(identity)
            tree.set(iid, "select", "☑")
        update_controls()

    def toggle_event(event=None) -> str | None:
        iid = ""
        if event is not None and getattr(event, "y", None) is not None:
            iid = tree.identify_row(event.y)
        if not iid:
            current = tree.selection()
            iid = current[0] if current else ""
        if iid:
            toggle_iid(iid)
        return "break"

    def select_safe() -> None:
        selected.clear()
        selected.update(_writable_identities(plan))
        refresh_tree(plan)

    def clear_selected() -> None:
        selected.clear()
        refresh_tree(plan)

    def apply_selected() -> None:
        if not selected:
            messagebox.showinfo(
                "Synchronizacja planu Excel",
                "Zaznacz co najmniej jedną pozycję Utwórz lub Aktualizuj.",
                parent=dlg,
            )
            return

        # Przed potwierdzeniem odczytaj zlecenia jeszcze raz. Jeżeli stan WM
        # zmienił się od otwarcia okna, użytkownik musi zobaczyć nowy plan.
        try:
            fresh_plan = build_order_sync_plan(payload)
        except Exception as exc:
            messagebox.showerror(
                "Synchronizacja planu Excel",
                f"Nie udało się ponownie sprawdzić zleceń WM:\n{exc}",
                parent=dlg,
            )
            return

        fresh_writable = _writable_identities(fresh_plan)
        stale = selected - fresh_writable
        if stale:
            selected.clear()
            refresh_tree(fresh_plan)
            messagebox.showwarning(
                "Synchronizacja planu Excel",
                "Stan zleceń WM zmienił się od otwarcia podglądu. Lista została odświeżona; sprawdź akcje i zaznacz pozycje ponownie.",
                parent=dlg,
            )
            return

        counts = _selected_action_counts(fresh_plan, selected)
        prompt = (
            f"Czy wykonać zaznaczone operacje?\n\n"
            f"{ACTION_CREATE}: {counts.get(ACTION_CREATE, 0)}\n"
            f"{ACTION_UPDATE}: {counts.get(ACTION_UPDATE, 0)}\n\n"
            "Operacje zmienią zlecenia WM i mogą przeliczyć rezerwacje materiałów. "
            "Plik Excel nie zostanie zmieniony."
        )
        if not messagebox.askyesno("Potwierdź synchronizację", prompt, parent=dlg):
            return

        by_identity = {
            _text(item.get("identity")): item
            for item in list(fresh_plan.get("items") or [])
            if isinstance(item, dict) and item.get("action") in WRITABLE_ACTIONS
        }
        autor = _text(getattr(owner, "login", "")) or "Planista Excel"
        succeeded = []
        failed = []
        apply_button.configure(state="disabled")
        dlg.configure(cursor="watch")
        try:
            # Każda pozycja jest osobną kontrolowaną operacją. Dzięki temu błąd
            # jednej pozycji nie ukrywa wyniku już zapisanych, niezależnych pozycji.
            for identity in list(selected):
                item = by_identity.get(identity)
                if not item:
                    failed.append((identity, "Pozycja przestała być dostępna do zapisu."))
                    continue
                single_plan = {"items": [item]}
                try:
                    result = apply_order_sync(
                        payload,
                        single_plan,
                        approved_identities={identity},
                        autor=autor,
                    )
                    if result.get("written") == 1:
                        succeeded.extend(result.get("results") or [])
                    else:
                        failed.append((identity, "Silnik nie potwierdził zapisu pozycji."))
                except ExcelOrderSyncError as exc:
                    failed.append((identity, str(exc)))
                except Exception as exc:  # pragma: no cover - ochrona UI przy awarii zapisu
                    failed.append((identity, f"Nieoczekiwany błąd: {exc}"))
        finally:
            dlg.configure(cursor="")

        try:
            current_plan = build_order_sync_plan(payload)
        except Exception:
            current_plan = fresh_plan
        selected.clear()
        refresh_tree(current_plan)
        try:
            owner.refresh()
        except Exception:
            pass

        created = sum(1 for item in succeeded if item.get("action") == ACTION_CREATE)
        updated = sum(1 for item in succeeded if item.get("action") == ACTION_UPDATE)
        if failed:
            details = "\n".join(f"• {identity}: {reason}" for identity, reason in failed[:8])
            extra = "" if len(failed) <= 8 else f"\n… oraz {len(failed) - 8} kolejnych błędów."
            messagebox.showwarning(
                "Synchronizacja zakończona częściowo",
                (
                    f"Zapisano: {len(succeeded)} (utworzono {created}, zaktualizowano {updated}).\n"
                    f"Nie zapisano: {len(failed)}.\n\n{details}{extra}\n\n"
                    "Stan WM został ponownie odczytany i podgląd odświeżony."
                ),
                parent=dlg,
            )
            return

        messagebox.showinfo(
            "Synchronizacja zakończona",
            f"Zapisano {len(succeeded)} pozycji: utworzono {created}, zaktualizowano {updated}.",
            parent=dlg,
        )

    tree.bind("<Double-1>", toggle_event)
    tree.bind("<space>", toggle_event)

    ttk.Button(controls, text="Zaznacz bezpieczne", command=select_safe).pack(side="left")
    add_help_button(controls, _SELECT_HELP, command_only=False).pack(side="left", padx=(4, 10))
    ttk.Button(controls, text="Wyczyść wybór", command=clear_selected).pack(side="left")
    ttk.Button(controls, text="Zamknij", command=dlg.destroy).pack(side="right")
    apply_button.configure(command=apply_selected)
    apply_button.pack(side="right", padx=(0, 4))
    add_help_button(controls, _APPLY_HELP, command_only=False).pack(side="right", padx=(0, 4))

    refresh_tree(plan)
