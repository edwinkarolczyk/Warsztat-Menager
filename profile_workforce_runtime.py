# version: 1.0
"""Minimalne rozszerzenia Profile WM: obecność, urlopy, użytkownicy i opinie.

Runtime celowo nie przebudowuje istniejącego wyglądu Profilu. Dokłada tylko
małe zakładki/akcje do istniejących Notebooków i korzysta z aktualnych styli.
"""
from __future__ import annotations

import sys
import threading
import time as _time
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk
from typing import Any

from ui_context_help import add_help_button
from services import attendance_service
from services import feedback_service
from services import leave_balance_service
from services import workforce_profile_service

_INSTALLED = False
_FEEDBACK_TEXT_PATCHED = False


def _fmt(value: Any) -> str:
    try:
        number = float(value or 0)
        return str(int(number)) if number.is_integer() else f"{number:.1f}"
    except Exception:
        return str(value or "0")


def _actor(panel=None) -> str:
    try:
        from services.profile_service import ProfileService
        value = str(ProfileService.ensure_active_user_or_none() or "").strip()
        if value:
            return value
    except Exception:
        pass
    return str(getattr(getattr(panel, "owner", None), "login", "") or "").strip()


def _month_value(panel) -> tuple[int, int]:
    raw = str(getattr(panel, "_wm_att_month_var", tk.StringVar(value=date.today().strftime("%Y-%m"))).get())
    try:
        year, month = raw.split("-", 1)
        return int(year), int(month)
    except Exception:
        return date.today().year, date.today().month


def _month_choices() -> list[str]:
    today = date.today().replace(day=1)
    out: list[str] = []
    current = today
    for _ in range(18):
        out.append(current.strftime("%Y-%m"))
        current = (current.replace(day=1) - timedelta(days=1)).replace(day=1)
    return out


def _absence_totals(login: str, year: int) -> tuple[float, float]:
    try:
        from services.leave_workflow_service import read_leaves
        rows = read_leaves()
    except Exception:
        rows = []
    key = str(login or "").strip().casefold()
    l4 = nn = 0.0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("login") or "").strip().casefold() != key:
            continue
        if str(row.get("date") or "")[:4] != str(year):
            continue
        kind = str(row.get("type") or "").strip().casefold()
        try:
            qty = float(row.get("quantity_days") or 1.0)
        except Exception:
            qty = 1.0
        if kind == "l4":
            l4 += qty
        elif kind == "nn":
            nn += qty
    return l4, nn


def _render_foreman_leaves(self) -> None:
    """Bilans urlopu bez kolumny spóźnień; wygląd zgodny z obecnym panelem."""
    parent = self._tabs.get("Urlopy")
    if parent is None:
        return
    self._clear(parent)
    year = date.today().year
    box = ttk.LabelFrame(
        parent,
        text=f"Bilans urlopów — {year}",
        style="WM.Section.TLabelframe",
        padding=8,
    )
    box.pack(fill="both", expand=True, padx=8, pady=8)
    tree = self._make_tree(
        box,
        [
            ("name", "Pracownik", 185, "w"),
            ("ent", "Należne", 72, "center"),
            ("carry", "Zaległy", 72, "center"),
            ("used", "Wykorzystano", 88, "center"),
            ("pending", "Oczekuje", 72, "center"),
            ("remain", "Pozostało", 82, "center"),
            ("l4", "L4", 55, "center"),
            ("nn", "NN", 55, "center"),
        ],
        height=13,
    )
    for user in workforce_profile_service.list_users(active_only=True):
        role = str(user.get("rola") or user.get("role") or "").casefold()
        if role == "guest":
            continue
        login = str(user.get("login") or "").strip()
        bal = leave_balance_service.get_balance(login, year)
        l4, nn = _absence_totals(login, year)
        remaining = float(bal.get("remaining") or 0.0)
        tag = "urgent" if remaining <= 0 else ("warning" if remaining <= 5 else "ok")
        tree.insert(
            "",
            "end",
            values=(
                workforce_profile_service.display_name(user),
                _fmt(bal.get("entitlement")),
                _fmt(bal.get("carryover")),
                _fmt(bal.get("used")),
                _fmt(bal.get("pending")),
                _fmt(remaining),
                _fmt(l4),
                _fmt(nn),
            ),
            tags=(tag,),
        )

    help_row = ttk.Frame(parent, style="WM.Container.TFrame")
    help_row.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Label(
        help_row,
        text="🟢 saldo bezpieczne   🟠 1–5 dni   🔴 0 lub mniej",
        style="WM.Muted.TLabel",
    ).pack(side="left")
    add_help_button(
        help_row,
        "Zaległy urlop przechodzi na kolejny rok i jest wykorzystywany przed urlopem bieżącym. Oczekujące wnioski są pokazywane osobno.",
    ).pack(side="left", padx=(6, 0))


def _render_attendance(self) -> None:
    parent = self._tabs.get("Obecność")
    if parent is None:
        return
    self._clear(parent)
    top = ttk.Frame(parent, style="WM.Container.TFrame")
    top.pack(fill="x", padx=8, pady=(8, 6))
    ttk.Label(top, text="Miesiąc:", style="WM.Muted.TLabel").pack(side="left")
    if not hasattr(self, "_wm_att_month_var"):
        self._wm_att_month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
    month_box = ttk.Combobox(
        top,
        textvariable=self._wm_att_month_var,
        values=_month_choices(),
        state="readonly",
        width=9,
    )
    month_box.pack(side="left", padx=(6, 8))
    month_box.bind("<<ComboboxSelected>>", lambda _e: _render_attendance(self), add="+")
    add_help_button(
        top,
        "Dniówka powstaje z pierwszego logowania do WM zgodnie z grafikiem. Bardzo późne logowanie oraz sobota wymagają decyzji brygadzisty.",
    ).pack(side="left")

    year, month = _month_value(self)
    box = ttk.LabelFrame(
        parent,
        text=f"Ewidencja obecności — {year:04d}-{month:02d}",
        style="WM.Section.TLabelframe",
        padding=8,
    )
    box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    tree = self._make_tree(
        box,
        [
            ("name", "Pracownik", 185, "w"),
            ("days", "🟢 Dniówki", 80, "center"),
            ("sat", "🟣 Soboty", 74, "center"),
            ("ot", "🟠 Nadgodz.", 84, "center"),
            ("vac", "🔵 Urlop", 65, "center"),
            ("l4", "🟣 L4", 55, "center"),
            ("miss", "🔴 Brak", 58, "center"),
            ("pending", "🟠 Decyzja", 70, "center"),
        ],
        height=13,
    )
    by_iid: dict[str, str] = {}
    for user in workforce_profile_service.list_users(active_only=True):
        login = str(user.get("login") or "").strip()
        role = str(user.get("rola") or user.get("role") or "").casefold()
        if not login or role == "guest":
            continue
        summary = attendance_service.summary_for_month(login, year, month)
        # Urlop/L4 bierzemy także z kanonicznej ewidencji nieobecności.
        try:
            from services.leave_workflow_service import read_leaves
            leave_rows = read_leaves()
        except Exception:
            leave_rows = []
        vac = l4 = 0.0
        prefix = f"{year:04d}-{month:02d}-"
        for row in leave_rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("login") or "").strip().casefold() != login.casefold():
                continue
            if not str(row.get("date") or "").startswith(prefix):
                continue
            kind = str(row.get("type") or "").casefold()
            try:
                qty = float(row.get("quantity_days") or 1.0)
            except Exception:
                qty = 1.0
            if kind == "urlop":
                vac += qty
            elif kind == "l4":
                l4 += qty
        pending = float(summary.get("pending") or 0.0)
        missing = float(summary.get("missing") or 0.0)
        tag = "urgent" if missing else ("warning" if pending else "ok")
        iid = tree.insert(
            "",
            "end",
            values=(
                workforce_profile_service.display_name(user),
                _fmt(summary.get("days")),
                _fmt(summary.get("saturday_days")),
                f"{_fmt(summary.get('overtime_hours'))} h",
                _fmt(vac),
                _fmt(l4),
                _fmt(missing),
                _fmt(pending),
            ),
            tags=(tag,),
        )
        by_iid[iid] = login
    self._wm_attendance_user_by_iid = by_iid
    self._wm_attendance_tree = tree

    actions = ttk.Frame(parent, style="WM.Container.TFrame")
    actions.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Button(actions, text="Szczegóły pracownika", command=lambda: _open_selected_details(self)).pack(side="left")
    ttk.Button(actions, text="Korekta", command=lambda: _open_correction(self)).pack(side="left", padx=(8, 0))
    add_help_button(
        actions,
        "Korekta pozwala brygadziście dopisać lub zmienić dniówkę oraz zatwierdzić nadgodziny. Każda korekta trafia do Historii.",
    ).pack(side="left", padx=(6, 0))


def _selected_attendance_login(panel) -> str:
    tree = getattr(panel, "_wm_attendance_tree", None)
    mapping = getattr(panel, "_wm_attendance_user_by_iid", {})
    if tree is None:
        return ""
    selected = tree.selection()
    return str(mapping.get(selected[0], "")) if selected else ""


def _open_selected_details(panel) -> None:
    login = _selected_attendance_login(panel)
    if not login:
        messagebox.showinfo("Profil", "Wybierz pracownika z listy.", parent=panel.winfo_toplevel())
        return
    open_employee_details(panel, login)


def _grid_field(parent, row: int, label: str, widget, help_text: str = "") -> None:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
    widget.grid(row=row, column=1, sticky="ew", pady=4)
    if help_text:
        add_help_button(parent, help_text, row=row, column=2, padx=(6, 0), sticky="w")


def _open_correction(panel) -> None:
    login = _selected_attendance_login(panel)
    if not login:
        messagebox.showinfo("Obecność", "Wybierz pracownika z listy.", parent=panel.winfo_toplevel())
        return
    win = tk.Toplevel(panel)
    win.title(f"Korekta obecności — {login}")
    try:
        win.transient(panel.winfo_toplevel())
        win.grab_set()
    except Exception:
        pass
    frame = ttk.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)

    day_var = tk.StringVar(value=date.today().isoformat())
    slot_var = tk.StringVar(value="RANO")
    change_day = tk.BooleanVar(value=True)
    value_var = tk.StringVar(value="1")
    change_ot = tk.BooleanVar(value=False)
    hours_var = tk.StringVar(value="0")
    ot_type = tk.StringVar(value="zwykle")
    note_var = tk.StringVar(value="")

    _grid_field(frame, 0, "Data:", ttk.Entry(frame, textvariable=day_var))
    _grid_field(frame, 1, "Zmiana:", ttk.Combobox(frame, textvariable=slot_var, values=("RANO", "POPO"), state="readonly"))
    ttk.Checkbutton(frame, text="Zmień dniówkę", variable=change_day).grid(row=2, column=0, sticky="w", pady=4)
    day_box = ttk.Combobox(frame, textvariable=value_var, values=("0", "0.5", "1"), state="readonly")
    day_box.grid(row=2, column=1, sticky="ew", pady=4)
    add_help_button(frame, "Dniówka może mieć wartość 0, 0,5 lub 1. Ręczny zapis brygadzisty jest oznaczony w Historii.", row=2, column=2, padx=(6, 0))
    ttk.Checkbutton(frame, text="Nadgodziny", variable=change_ot).grid(row=3, column=0, sticky="w", pady=4)
    ot_wrap = ttk.Frame(frame)
    ot_wrap.grid(row=3, column=1, sticky="ew", pady=4)
    ttk.Entry(ot_wrap, textvariable=hours_var, width=7).pack(side="left")
    ttk.Label(ot_wrap, text=" h   ").pack(side="left")
    ttk.Combobox(
        ot_wrap,
        textvariable=ot_type,
        values=("zwykle", "sobota", "niedziela", "swieto"),
        state="readonly",
        width=12,
    ).pack(side="left", fill="x", expand=True)
    add_help_button(frame, "Sobota jest liczona oddzielnie od zwykłych dniówek. Godziny nadliczbowe zatwierdza brygadzista, a nie sam czas otwarcia WM.", row=3, column=2, padx=(6, 0))
    _grid_field(frame, 4, "Uwagi:", ttk.Entry(frame, textvariable=note_var))

    def save() -> None:
        try:
            date.fromisoformat(day_var.get())
            if change_day.get():
                attendance_service.set_manual_day(
                    day_var.get(), slot_var.get(), login, float(value_var.get()), _actor(panel), note_var.get()
                )
            if change_ot.get():
                attendance_service.set_overtime(
                    day_var.get(), slot_var.get(), login, float(hours_var.get()), _actor(panel),
                    overtime_type=ot_type.get(), note=note_var.get(),
                )
        except Exception as exc:
            messagebox.showerror("Obecność", f"Nie udało się zapisać korekty:\n{exc}", parent=win)
            return
        win.destroy()
        _render_attendance(panel)

    actions = ttk.Frame(frame)
    actions.grid(row=5, column=0, columnspan=3, sticky="e", pady=(12, 0))
    ttk.Button(actions, text="Anuluj", command=win.destroy).pack(side="right")
    ttk.Button(actions, text="Zapisz", command=save).pack(side="right", padx=(0, 8))


def _render_feedback(self) -> None:
    parent = self._tabs.get("Opinie")
    if parent is None:
        return
    self._clear(parent)
    totals = feedback_service.counts()
    top = ttk.Frame(parent, style="WM.Container.TFrame")
    top.pack(fill="x", padx=8, pady=(8, 6))
    ttk.Label(
        top,
        text=(
            f"🔴 Nowe: {totals.get('nowa',0)}   🟡 Zaplanowane: {totals.get('zaplanowana',0)}   "
            f"🟠 W realizacji: {totals.get('w_realizacji',0)}   🟢 Wykonane: {totals.get('wykonana',0)}"
        ),
        style="WM.Muted.TLabel",
    ).pack(side="left")
    add_help_button(
        top,
        "Status opinii pokazuje pracownikowi, co dzieje się z jego zgłoszeniem. Oryginalna treść opinii pozostaje bez zmian.",
    ).pack(side="left", padx=(6, 0))

    box = ttk.LabelFrame(parent, text="Opinie użytkowników", style="WM.Section.TLabelframe", padding=8)
    box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    tree = self._make_tree(
        box,
        [
            ("date", "Data", 130, "center"),
            ("author", "Autor", 125, "w"),
            ("module", "Moduł", 105, "w"),
            ("message", "Opinia", 480, "w"),
            ("status", "Status", 120, "center"),
        ],
        height=13,
    )
    by_iid: dict[str, str] = {}
    for row in feedback_service.list_feedback():
        status = str(row.get("status") or "nowa")
        tag = "ok" if status == "wykonana" else ("warning" if status in {"zaplanowana", "w_realizacji"} else "urgent")
        created = str(row.get("created_at") or "").replace("T", " ")[:16]
        iid = tree.insert(
            "",
            "end",
            values=(created, row.get("login"), row.get("module"), row.get("message"), feedback_service.status_label(status)),
            tags=(tag,),
        )
        by_iid[iid] = str(row.get("id") or "")
    self._wm_feedback_tree = tree
    self._wm_feedback_by_iid = by_iid

    actions = ttk.Frame(parent, style="WM.Container.TFrame")
    actions.pack(fill="x", padx=8, pady=(0, 8))
    status_var = tk.StringVar(value="w_realizacji")
    module_var = tk.StringVar(value="Inne")
    ttk.Label(actions, text="Status:").pack(side="left")
    ttk.Combobox(actions, textvariable=status_var, values=feedback_service.STATUSES, state="readonly", width=14).pack(side="left", padx=(5, 8))
    ttk.Label(actions, text="Moduł:").pack(side="left")
    ttk.Combobox(
        actions,
        textvariable=module_var,
        values=("Profile", "Maszyny", "Narzędzia", "Dyspozycje", "Planista", "Magazyn", "Inne"),
        width=14,
    ).pack(side="left", padx=(5, 8))

    def update_selected() -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Opinie", "Wybierz opinię z listy.", parent=self.winfo_toplevel())
            return
        fid = by_iid.get(selected[0], "")
        try:
            feedback_service.update_feedback(
                fid, status=status_var.get(), module=module_var.get(), actor=_actor(self)
            )
        except Exception as exc:
            messagebox.showerror("Opinie", f"Nie udało się zapisać:\n{exc}", parent=self.winfo_toplevel())
            return
        _render_feedback(self)

    ttk.Button(actions, text="Zapisz status", command=update_selected).pack(side="left")
    add_help_button(
        actions,
        "Brygadzista może zmienić status oraz przypisać opinię do modułu. Autor zobaczy aktualny status w szczegółach swojego profilu.",
    ).pack(side="left", padx=(6, 0))


def _ensure_foreman_tabs(self) -> None:
    notebook = getattr(self, "notebook", None)
    tabs = getattr(self, "_tabs", {})
    if notebook is None or not isinstance(tabs, dict):
        return

    def add_tab(name: str, pos: int | str = "end"):
        if name in tabs:
            return tabs[name]
        frame = ttk.Frame(notebook, style="WM.Container.TFrame")
        notebook.add(frame, text=name)
        tabs[name] = frame
        try:
            notebook.insert(pos, frame)
        except Exception:
            pass
        return frame

    # Zachowujemy obecne zakładki; tylko dokładamy trzy brakujące.
    add_tab("Obecność", 2)
    urlopy = tabs.get("Urlopy")
    try:
        after_urlop = int(notebook.index(urlopy)) + 1 if urlopy is not None else "end"
    except Exception:
        after_urlop = "end"
    users_tab = add_tab("Użytkownicy", after_urlop)
    try:
        after_users = int(notebook.index(users_tab)) + 1
    except Exception:
        after_users = "end"
    add_tab("Opinie", after_users)

    # Naprawiamy wcześniejszy niedostępny montaż administracji pod nazwą "Profile".
    if users_tab is not None and not getattr(self, "_wm_users_admin_built", False):
        try:
            from profile_admin_ui import ProfileAdminNotebook
            admin = ProfileAdminNotebook(users_tab)
            admin.pack(fill="both", expand=True)
            self._wm_profile_admin = admin
            self._wm_users_admin_built = True
        except Exception as exc:
            ttk.Label(users_tab, text=f"Administracja profili niedostępna: {exc}").pack(anchor="w", padx=12, pady=12)


def _build_details_tab_text(parent, rows: list[tuple[str, str]]) -> None:
    wrap = ttk.Frame(parent, padding=12)
    wrap.pack(fill="both", expand=True)
    for label, value in rows:
        line = ttk.Frame(wrap)
        line.pack(fill="x", pady=3)
        ttk.Label(line, text=f"{label}:", width=22).pack(side="left")
        ttk.Label(line, text=str(value or "—")).pack(side="left", fill="x", expand=True)


def open_employee_details(owner, login: str) -> None:
    user = workforce_profile_service.get_user(login) or {"login": login}
    win = tk.Toplevel(owner)
    win.title(f"Profil pracownika — {workforce_profile_service.display_name(user)}")
    try:
        win.transient(owner.winfo_toplevel())
    except Exception:
        pass
    win.geometry("960x620")
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    frames: dict[str, ttk.Frame] = {}
    for name in ("Dane", "Obecność", "Urlopy", "Grafik", "Uprawnienia", "Historia", "Więcej"):
        frame = ttk.Frame(nb)
        nb.add(frame, text=name)
        frames[name] = frame

    _build_details_tab_text(frames["Dane"], [
        ("User ID", user.get("user_id")),
        ("Login", user.get("login")),
        ("Imię", user.get("imie")),
        ("Nazwisko", user.get("nazwisko")),
        ("Rola", user.get("rola") or user.get("role")),
        ("Status", user.get("status") or ("aktywny" if user.get("active", True) else "nieaktywny")),
        ("Zatrudniony od", user.get("zatrudniony_od")),
        ("Zatrudniony do", user.get("zatrudniony_do")),
        ("Telefon", user.get("telefon")),
        ("E-mail", user.get("email")),
    ])

    year, month = date.today().year, date.today().month
    summary = attendance_service.summary_for_month(login, year, month)
    att = frames["Obecność"]
    ttk.Label(
        att,
        text=(
            f"🟢 Dniówki: {_fmt(summary.get('days'))}    🟣 Soboty: {_fmt(summary.get('saturday_days'))}    "
            f"🟠 Nadgodziny: {_fmt(summary.get('overtime_hours'))} h    🔴 Brak: {_fmt(summary.get('missing'))}"
        ),
    ).pack(anchor="w", padx=12, pady=(12, 8))
    cols = ("date", "slot", "first", "status", "day", "ot")
    tree = ttk.Treeview(att, columns=cols, show="headings", height=15)
    for key, label, width in (
        ("date", "Data", 100), ("slot", "Zmiana", 75), ("first", "Pierwsze logowanie", 145),
        ("status", "Status", 150), ("day", "Dniówka", 65), ("ot", "Nadgodziny", 90),
    ):
        tree.heading(key, text=label); tree.column(key, width=width, anchor="center")
    tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    for row in attendance_service.month_records(login, year, month):
        first = str(row.get("first_login_ts") or row.get("logged_ts") or "").replace("T", " ")[11:19]
        overtime = row.get("overtime") if isinstance(row.get("overtime"), dict) else {}
        tree.insert("", "end", values=(row.get("date"), row.get("slot"), first or "—", row.get("status") or row.get("reason") or "—", _fmt(row.get("day_value")), f"{_fmt(overtime.get('hours'))} h" if overtime else "—"))

    bal = leave_balance_service.get_balance(login, year)
    _build_details_tab_text(frames["Urlopy"], [
        (f"Należne {year}", _fmt(bal.get("entitlement"))),
        ("Zaległy", _fmt(bal.get("carryover"))),
        ("Razem dostępne", _fmt(bal.get("available"))),
        ("Wykorzystane", _fmt(bal.get("used"))),
        ("Oczekujące", _fmt(bal.get("pending"))),
        ("Pozostało", _fmt(bal.get("remaining"))),
        ("Po oczekujących", _fmt(bal.get("projected_remaining"))),
    ])

    workdays = user.get("workdays") or user.get("dni_pracy") or [0, 1, 2, 3, 4]
    day_names = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"]
    readable_days = ", ".join(day_names[int(idx)] for idx in workdays if str(idx).isdigit() and 0 <= int(idx) <= 6)
    _build_details_tab_text(frames["Grafik"], [
        ("Dni pracy", readable_days),
        ("Tryb zmian", user.get("tryb_zmian") or user.get("shift_mode") or user.get("zmiana_plan")),
        ("Rotacja start", user.get("rotacja_start") or user.get("shift_start")),
    ])

    disabled = user.get("disabled_modules") or user.get("modules_disabled") or []
    _build_details_tab_text(frames["Uprawnienia"], [
        ("Rola", user.get("rola") or user.get("role")),
        ("Wyłączone moduły", ", ".join(str(x) for x in disabled) if isinstance(disabled, (list, tuple, set)) else disabled),
    ])

    hist = frames["Historia"]
    htree = ttk.Treeview(hist, columns=("ts", "action", "actor", "date", "note"), show="headings", height=16)
    for key, label, width in (("ts", "Data zmiany", 145), ("action", "Akcja", 110), ("actor", "Kto", 100), ("date", "Dzień", 95), ("note", "Uwagi", 330)):
        htree.heading(key, text=label); htree.column(key, width=width, anchor="w")
    htree.pack(fill="both", expand=True, padx=12, pady=12)
    for row in reversed(attendance_service.audit_for_login(login, 200)):
        htree.insert("", "end", values=(str(row.get("ts") or "").replace("T", " ")[:19], row.get("action"), row.get("actor"), row.get("date"), row.get("note")))

    more = frames["Więcej"]
    skills = user.get("umiejetnosci") or {}
    courses = user.get("kursy") or []
    awards = user.get("nagrody") or []
    warnings = user.get("ostrzezenia") or []
    _build_details_tab_text(more, [
        ("Umiejętności", ", ".join(f"{k} ({v})" for k, v in skills.items()) if isinstance(skills, dict) and skills else "—"),
        ("Kursy / certyfikaty", ", ".join(map(str, courses)) if isinstance(courses, list) else courses),
        ("Nagrody / pochwały", ", ".join(map(str, awards)) if isinstance(awards, list) else awards),
        ("Ostrzeżenia", ", ".join(map(str, warnings)) if isinstance(warnings, list) else warnings),
        ("Moje opinie", str(len(feedback_service.list_feedback(login=login)))),
    ])

    ttk.Button(win, text="Zamknij", command=win.destroy).pack(pady=(0, 10))


def _patch_profile_details_button() -> None:
    try:
        import gui_profile_core as core
        cls = core.ProfileView
    except Exception:
        return
    if getattr(cls, "_wm_workforce_details_button", False):
        return
    original = cls._render_simple_profile

    def wrapped(self, parent, *args, **kwargs):
        result = original(self, parent, *args, **kwargs)
        row = ttk.Frame(parent, style="WM.Container.TFrame")
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(
            row,
            text="Szczegóły pracownika",
            command=lambda: open_employee_details(self, str(getattr(self, "login", "") or "")),
        ).pack(side="right")
        add_help_button(
            row,
            "Otwiera szczegóły profilu: Dane, Obecność, Urlopy, Grafik, Uprawnienia, Historia i Więcej. Główny wygląd Profilu pozostaje bez zmian.",
        ).pack(side="right", padx=(0, 6))
        return result

    cls._render_simple_profile = wrapped
    cls._wm_workforce_details_button = True


def _patch_feedback_enter() -> None:
    global _FEEDBACK_TEXT_PATCHED
    if _FEEDBACK_TEXT_PATCHED or getattr(tk.Text, "_wm_feedback_enter", False):
        return
    original_init = tk.Text.__init__

    def patched_init(widget, *args, **kwargs):
        original_init(widget, *args, **kwargs)
        try:
            top = widget.winfo_toplevel()
            if str(top.title()) != "Wyślij opinię":
                return
        except Exception:
            return

        def find_send_button(parent):
            try:
                children = parent.winfo_children()
            except Exception:
                return None
            for child in children:
                try:
                    if isinstance(child, (ttk.Button, tk.Button)) and str(child.cget("text")) == "Wyślij":
                        return child
                except Exception:
                    pass
                found = find_send_button(child)
                if found is not None:
                    return found
            return None

        def on_return(event):
            # Shift+Enter zostawia zwykłą nową linię.
            if int(getattr(event, "state", 0) or 0) & 0x0001:
                return None
            button = find_send_button(widget.winfo_toplevel())
            if button is not None:
                try:
                    button.invoke()
                except Exception:
                    return None
                return "break"
            return None

        widget.bind("<Return>", on_return, add="+")

    tk.Text.__init__ = patched_init
    tk.Text._wm_feedback_enter = True
    _FEEDBACK_TEXT_PATCHED = True


def _patch_login_hours_deferred() -> None:
    """Rozszerz rejestrację logowania na 05:00–23:59 bez dotykania GUI."""
    def worker():
        for _ in range(100):
            module = sys.modules.get("gui_logowanie")
            func = getattr(module, "_slot_now", None) if module is not None else None
            if callable(func) and not getattr(func, "_wm_workforce_hours", False):
                original = func

                def slot_now(moment):
                    t = moment.time()
                    if datetime.strptime("05:00", "%H:%M").time() <= t < datetime.strptime("14:00", "%H:%M").time():
                        return "RANO"
                    if datetime.strptime("14:00", "%H:%M").time() <= t <= datetime.strptime("23:59", "%H:%M").time():
                        return "POPO"
                    return original(moment)

                slot_now._wm_workforce_hours = True
                module._slot_now = slot_now
                return
            _time.sleep(0.05)

    threading.Thread(target=worker, name="wm-profile-login-hours", daemon=True).start()


def _patch_core_services() -> None:
    workforce_profile_service.ensure_profile_schema()

    # Jedno źródło profili również dla starego API.
    try:
        import profile_utils as pu
        pu.read_users = lambda *a, **k: workforce_profile_service.list_users()
        pu.get_user = lambda login, *a, **k: workforce_profile_service.get_user(login)
        pu.save_user = lambda user, *a, **k: workforce_profile_service.save_user(user)
        pu.write_users = lambda users, *a, **k: workforce_profile_service.write_users(users)
    except Exception:
        pass
    try:
        from services import profile_service as ps
        ps.get_all_users = lambda *a, **k: workforce_profile_service.list_users()
        ps.get_user = lambda login, *a, **k: workforce_profile_service.get_user(login)
        ps.save_user = lambda user, *a, **k: workforce_profile_service.save_user(user)
        ps.write_users = lambda users, *a, **k: workforce_profile_service.write_users(users)
        ps.ProfileService._load_profiles = classmethod(lambda cls: workforce_profile_service.list_users())
        ps.ProfileService._profiles_cache = None
        ps.count_presence = lambda login, *a, **k: int(round(attendance_service.summary_for_month(login, date.today().year, date.today().month).get("days", 0)))
    except Exception:
        pass

    # Stare GUI attendance_utils pozostaje, ale wykonuje nową logikę.
    try:
        import attendance_utils as au
        au.mark_login = attendance_service.mark_login
        au.confirm_login = attendance_service.confirm_login
        au.set_reason = attendance_service.set_reason
        au.status_for = attendance_service.status_for
    except Exception:
        pass

    # Panel brygadzisty czyta te same profile i ten sam plik urlopów.
    try:
        from services import foreman_stats_service as fs
        fs.get_all_users = lambda: workforce_profile_service.list_users(active_only=True)
        original_user_leave_stats = fs._user_leave_stats

        def user_leave_stats(user, leaves, year):
            login = str(user.get("login") or "")
            old = original_user_leave_stats(user, leaves, year)
            bal = leave_balance_service.get_balance(login, year)
            return {
                "limit": bal.get("available", 0),
                "used": bal.get("used", 0),
                "remaining": bal.get("remaining", 0),
                "carryover": bal.get("carryover", 0),
                "pending": bal.get("pending", 0),
                "l4": old.get("l4", 0),
                "nn": old.get("nn", 0),
                "late_minutes": 0,
            }

        fs._user_leave_stats = user_leave_stats
        try:
            from services import leave_workflow_service as lw
            fs._load_leaves = lambda: (lw.read_leaves(), str(lw.leaves_path()))
        except Exception:
            pass
    except Exception:
        pass


def _patch_foreman_panel() -> None:
    try:
        import gui_profile_foreman as foreman
        cls = foreman.ForemanProfilePanel
    except Exception:
        return
    if getattr(cls, "_wm_workforce_runtime", False):
        return

    original_build = cls._build
    original_render_all = cls._render_all

    def build(self, *args, **kwargs):
        result = original_build(self, *args, **kwargs)
        _ensure_foreman_tabs(self)
        return result

    def render_all(self):
        original_render_all(self)
        _render_attendance(self)
        _render_feedback(self)

    cls._build = build
    cls._render_all = render_all
    # Workflow urlopowy instalowany później owinie tę wersję bez spóźnień.
    cls._render_leaves = _render_foreman_leaves
    cls._wm_workforce_runtime = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_core_services()
    _patch_foreman_panel()
    _patch_profile_details_button()
    _patch_feedback_enter()
    _patch_login_hours_deferred()
    _INSTALLED = True


__all__ = ["install", "open_employee_details"]
