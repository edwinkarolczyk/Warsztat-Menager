# version: 1.0
"""Końcowe dopracowanie edytora pracownika bez zmiany źródeł danych."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk
from typing import Any

from services import attendance_service, leave_balance_service, workforce_profile_service
from ui_context_help import add_help_button

_INSTALLED = False
_OPEN_EMPLOYEE_WINDOWS: dict[tuple[int, str], tk.Toplevel] = {}


def _walk(widget):
    out = []
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        out.append(child)
        out.extend(_walk(child))
    return out


def _all_toplevels(root) -> set[tk.Toplevel]:
    return {widget for widget in _walk(root) if isinstance(widget, tk.Toplevel)}


def _employee_key(owner, login: str) -> tuple[int, str]:
    try:
        root = owner.winfo_toplevel()
    except Exception:
        root = owner
    user = workforce_profile_service.get_user(login) or {}
    stable = str(user.get("user_id") or login or "").strip().casefold()
    return id(root), stable


def _notebook(win) -> ttk.Notebook | None:
    for widget in _walk(win):
        if isinstance(widget, ttk.Notebook):
            return widget
    return None


def _tabs(nb: ttk.Notebook) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for tab_id in nb.tabs():
            out[str(nb.tab(tab_id, "text"))] = tab_id
    except Exception:
        pass
    return out


def _select_tab(win, name: str) -> None:
    nb = _notebook(win)
    if nb is None:
        return
    tab_id = _tabs(nb).get(str(name or ""))
    if tab_id:
        try:
            nb.select(tab_id)
        except Exception:
            pass


def _raise_window(win, initial_tab: str) -> bool:
    try:
        if not win.winfo_exists():
            return False
        win.deiconify()
        win.lift()
        _select_tab(win, initial_tab)
        try:
            win.focus_force()
        except Exception:
            pass
        return True
    except Exception:
        return False


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _compact(value: Any) -> str:
    if isinstance(value, dict):
        hours = value.get("hours")
        kind = value.get("type")
        status = value.get("status")
        parts = []
        if hours not in (None, "", 0, 0.0):
            parts.append(f"{_fmt(hours)} h")
        if kind:
            parts.append(str(kind))
        if status:
            parts.append(str(status))
        return ", ".join(parts) or "—"
    return _fmt(value)


def _changes(before: Any, after: Any) -> list[str]:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return []
    labels = {
        "slot": "zmiana",
        "day_value": "dniówka",
        "reason": "nieobecność",
        "absence_code": "nieobecność",
        "pay_code": "kod dnia",
        "overtime": "nadgodziny",
        "entitlement": "należny",
        "adjustment": "korekta",
        "carryover": "zaległy",
        "remaining": "pozostało",
        "login": "login",
        "imie": "imię",
        "nazwisko": "nazwisko",
        "rola": "rola",
        "status": "status",
        "zatrudniony_od": "zatrudniony od",
        "zatrudniony_do": "zatrudniony do",
        "telefon": "telefon",
        "email": "e-mail",
        "tryb_zmian": "grafik",
        "shift_mode": "grafik",
        "shift_anchor": "kotwica",
    }
    out: list[str] = []
    seen_labels: set[str] = set()
    for key, label in labels.items():
        if key not in before and key not in after:
            continue
        left, right = before.get(key), after.get(key)
        if left == right or label in seen_labels:
            continue
        seen_labels.add(label)
        out.append(f"{label}: {_compact(left)} → {_compact(right)}")
    return out


def _human_action(row: dict) -> tuple[str, str]:
    action = str(row.get("action") or row.get("_source") or "").strip()
    labels = {
        "profil": "Dane profilu",
        "reset_pin": "Reset PIN",
        "obecnosc": "Korekta obecności",
        "manual_day": "Korekta dniówki",
        "manual_day_replace_absence": "Nieobecność → dniówka",
        "manual_day_move": "Zmiana zmiany",
        "absence_kind_edit": "Zmiana nieobecności",
        "overtime": "Nadgodziny",
        "saldo_urlopu": "Saldo urlopu",
        "grafik": "Grafik",
        "uprawnienia": "Uprawnienia",
    }
    title = labels.get(action, action.replace("_", " ").strip().capitalize() or "Zmiana")
    note = str(row.get("note") or "").strip()
    changes = _changes(row.get("before"), row.get("after"))
    detail = "; ".join(changes)
    if note and note not in detail:
        detail = f"{detail}; {note}".strip("; ")
    if not detail:
        day = str(row.get("date") or "").strip()
        slot = str(row.get("slot") or "").strip()
        detail = " • ".join(value for value in (day, slot) if value) or "Zmiana zapisana w WM"
    return title, detail


def _history_rows(login: str) -> list[dict]:
    try:
        import profile_foreman_edit_runtime as edit_runtime
        profile_rows = edit_runtime._profile_audit(login, 250)
    except Exception:
        profile_rows = []
    rows: list[dict] = []
    for row in profile_rows:
        item = dict(row)
        item["_source"] = "profil"
        rows.append(item)
    try:
        for row in attendance_service.audit_for_login(login, 250):
            item = dict(row)
            item["_source"] = "obecność"
            rows.append(item)
    except Exception:
        pass
    rows.sort(key=lambda item: str(item.get("ts") or ""), reverse=True)
    return rows[:400]


def _decorate_history(win, nb: ttk.Notebook, login: str) -> None:
    history_id = _tabs(nb).get("Historia")
    if not history_id:
        return
    try:
        history = win.nametowidget(history_id)
    except Exception:
        return
    tree = next((widget for widget in _walk(history) if isinstance(widget, ttk.Treeview)), None)
    if tree is None:
        return
    try:
        tree.heading("action", text="Co zmieniono")
        tree.heading("actor", text="Kto")
        tree.heading("note", text="Szczegóły")
        tree.column("action", width=175, anchor="w")
        tree.column("note", width=500, anchor="w")
    except Exception:
        pass

    def refresh() -> None:
        try:
            if not win.winfo_exists():
                return
            tree.delete(*tree.get_children())
            for row in _history_rows(login):
                title, detail = _human_action(row)
                ts = str(row.get("ts") or "").replace("T", " ")[:19]
                tree.insert("", "end", values=(ts, title, row.get("actor") or "—", detail))
        except Exception:
            pass

    for widget in _walk(history):
        if isinstance(widget, ttk.Button):
            try:
                if str(widget.cget("text")) == "Odśwież historię":
                    widget.configure(command=refresh)
            except Exception:
                pass
    refresh()

    try:
        root = win.winfo_toplevel()
        bind_id = root.bind("<<ProfileDataUpdated>>", lambda _e: win.after_idle(refresh), add="+")
    except Exception:
        root, bind_id = None, None

    if root is not None and bind_id:
        def cleanup(event) -> None:
            if event.widget is win:
                try:
                    root.unbind("<<ProfileDataUpdated>>", bind_id)
                except Exception:
                    pass
        win.bind("<Destroy>", cleanup, add="+")


def _grid_widget(parent, row: int, cls) -> Any | None:
    for widget in parent.winfo_children():
        if not isinstance(widget, cls):
            continue
        try:
            if int(widget.grid_info().get("row", -1)) == row:
                return widget
        except Exception:
            pass
    return None


def _set_textvariable(parent, widget, value: Any) -> None:
    try:
        name = str(widget.cget("textvariable") or "")
        if name:
            parent.setvar(name, str(value))
    except Exception:
        pass


def _decorate_leave_year(win, nb: ttk.Notebook, login: str) -> None:
    leaves_id = _tabs(nb).get("Urlopy")
    if not leaves_id:
        return
    try:
        leaves = win.nametowidget(leaves_id)
    except Exception:
        return
    year_entry = _grid_widget(leaves, 0, ttk.Entry)
    ent_entry = _grid_widget(leaves, 1, ttk.Entry)
    adj_entry = _grid_widget(leaves, 2, ttk.Entry)
    carry_entry = _grid_widget(leaves, 3, ttk.Entry)
    status_label = _grid_widget(leaves, 4, ttk.Label)
    if year_entry is None or ent_entry is None or adj_entry is None or carry_entry is None:
        return

    try:
        var_name = str(year_entry.cget("textvariable") or "")
        current = date.today().year
        years = tuple(str(year) for year in range(current - 2, current + 2))
        year_entry.grid_remove()
        combo = ttk.Combobox(leaves, textvariable=var_name, values=years, state="readonly", width=10)
        combo.grid(row=0, column=1, sticky="ew", pady=4)
        add_help_button(
            leaves,
            "Wybierz rok rozliczenia urlopu. WM pokaże należny, zaległy, wykorzystany, oczekujący i pozostały urlop dla wybranego roku.",
            row=0, column=2, padx=(6, 0), sticky="w",
        )
    except Exception:
        return

    def load_year(_event=None) -> None:
        try:
            year = int(leaves.getvar(var_name))
            balance = leave_balance_service.get_balance(login, year)
            import profile_foreman_edit_runtime as edit_runtime
            _set_textvariable(leaves, ent_entry, f"{float(balance.get('entitlement') or 0):g}")
            _set_textvariable(leaves, adj_entry, f"{float(balance.get('adjustment') or 0):g}")
            _set_textvariable(leaves, carry_entry, edit_runtime._format_carryover(balance, year))
            if status_label is not None:
                text = (
                    f"🟡 Zaległy: {float(balance.get('carryover') or 0):g}   "
                    f"🔵 Wykorzystano: {float(balance.get('used') or 0):g}   "
                    f"🟠 Oczekuje: {float(balance.get('pending') or 0):g}   "
                    f"🟢 Pozostało: {float(balance.get('remaining') or 0):g}"
                )
                _set_textvariable(leaves, status_label, text)
        except Exception:
            pass

    combo.bind("<<ComboboxSelected>>", load_year, add="+")
    load_year()


def _simplify_tabs(win, nb: ttk.Notebook) -> None:
    tabs = _tabs(nb)
    perms_id = tabs.get("Uprawnienia")
    more_id = tabs.get("Więcej")
    if not perms_id or not more_id:
        return
    try:
        more = win.nametowidget(more_id)
        nb.hide(perms_id)
    except Exception:
        return

    access = ttk.LabelFrame(more, text="Dostęp i administracja", padding=10)
    access.pack(fill="x", pady=(12, 0))
    ttk.Label(access, text="Rzadziej używane ustawienia pracownika są schowane, ale nadal dostępne.").pack(side="left")

    def open_permissions() -> None:
        try:
            nb.add(perms_id, text="Uprawnienia")
            nb.select(perms_id)
        except Exception:
            pass

    ttk.Button(access, text="Uprawnienia pracownika", command=open_permissions).pack(side="right")
    add_help_button(
        access,
        "Otwiera indywidualne wyłączenia modułów dla tego pracownika. Po przejściu do innej zakładki Uprawnienia ponownie zostaną schowane pod Więcej.",
    ).pack(side="right", padx=(0, 6))

    def tab_changed(_event=None) -> None:
        try:
            selected = nb.select()
            if selected != perms_id and perms_id in nb.tabs():
                nb.hide(perms_id)
        except Exception:
            pass

    nb.bind("<<NotebookTabChanged>>", tab_changed, add="+")


def _refresh_open_profile_views(owner) -> None:
    try:
        root = owner.winfo_toplevel()
    except Exception:
        return
    try:
        root.event_generate("<<ProfileDataUpdated>>", when="tail")
    except Exception:
        pass
    for widget in _walk(root):
        if widget.__class__.__name__ == "ForemanProfilePanel":
            callback = getattr(widget, "refresh_data", None)
            if callable(callback):
                try:
                    widget.after_idle(callback)
                except Exception:
                    pass


def _postprocess(win, login: str) -> None:
    nb = _notebook(win)
    if nb is None:
        return
    _decorate_leave_year(win, nb, login)
    _decorate_history(win, nb, login)
    _simplify_tabs(win, nb)


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    import profile_foreman_edit_runtime as edit_runtime

    if getattr(edit_runtime, "_wm_employee_editor_finish_v1", False):
        _INSTALLED = True
        return

    original = edit_runtime.open_employee_editor

    def open_employee_editor(owner, login: str, *, initial_tab: str = "Dane", on_saved=None) -> None:
        key = _employee_key(owner, login)
        existing = _OPEN_EMPLOYEE_WINDOWS.get(key)
        if existing is not None:
            if _raise_window(existing, initial_tab):
                return
            _OPEN_EMPLOYEE_WINDOWS.pop(key, None)

        try:
            root = owner.winfo_toplevel()
        except Exception:
            root = owner
        before = _all_toplevels(root)

        def saved() -> None:
            try:
                if callable(on_saved):
                    on_saved()
            finally:
                _refresh_open_profile_views(owner)

        original(owner, login, initial_tab=initial_tab, on_saved=saved)
        created = list(_all_toplevels(root) - before)
        if not created:
            return
        win = created[-1]
        _OPEN_EMPLOYEE_WINDOWS[key] = win
        _postprocess(win, login)
        _select_tab(win, initial_tab)

        def cleanup(event) -> None:
            if event.widget is win and _OPEN_EMPLOYEE_WINDOWS.get(key) is win:
                _OPEN_EMPLOYEE_WINDOWS.pop(key, None)

        win.bind("<Destroy>", cleanup, add="+")

    edit_runtime.open_employee_editor = open_employee_editor
    edit_runtime._wm_employee_editor_finish_v1 = True
    _INSTALLED = True


__all__ = ["install"]
