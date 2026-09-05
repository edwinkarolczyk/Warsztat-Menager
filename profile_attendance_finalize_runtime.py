# version: 1.4
"""Końcowe ujednolicenie Profili: Ruch WM, Obecność, decyzje i pełna edycja.

Ten runtime jest instalowany jako ostatnia warstwa Profili. Nie tworzy kolejnego
źródła danych: korzysta wyłącznie z aktualnego snapshotu brygadzisty,
AttendanceService, WorkforceProfileService i FeedbackService.
"""
from __future__ import annotations

import json
import os
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from services import (
    attendance_service,
    feedback_service,
    leave_workflow_service,
    workforce_profile_service,
)
from ui_context_help import add_help_button

_INSTALLED = False
_MONTH_NAMES = (
    "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
    "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
)


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


def _month_choices() -> list[str]:
    today = date.today().replace(day=1)
    out: list[str] = []
    current = today
    for _ in range(24):
        out.append(current.strftime("%Y-%m"))
        current = (current - timedelta(days=1)).replace(day=1)
    return out


def _month_tuple(raw: str) -> tuple[int, int]:
    try:
        year, month = str(raw).split("-", 1)
        return int(year), int(month)
    except Exception:
        return date.today().year, date.today().month


def _month_label(month: int) -> str:
    try:
        return _MONTH_NAMES[int(month) - 1].capitalize()
    except Exception:
        return str(month)


def _shift_label(slot: str | None) -> str:
    if slot == attendance_service.RANO:
        return "I zmiana"
    if slot == attendance_service.POPO:
        return "II zmiana"
    return "Wolne"


def _fit_name_column(tree: ttk.Treeview, values: list[str], *, minimum: int = 120, maximum: int = 260) -> None:
    """Dopasuj Pracownik do najdłuższej widocznej nazwy, bez rozciągania."""
    try:
        font = tkfont.nametofont("TkDefaultFont")
        samples = ["Pracownik", *[str(value or "") for value in values]]
        width = max(font.measure(text) for text in samples) + 34
    except Exception:
        width = 160
    width = max(minimum, min(maximum, int(width)))
    try:
        tree.column("name", width=width, minwidth=minimum, stretch=False)
    except Exception:
        pass


def _team_by_login(panel) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in getattr(panel, "snapshot", {}).get("team") or []:
        login = str(row.get("login") or "").strip().casefold()
        if login:
            out[login] = row
    return out


def _status_text(row: dict) -> str:
    status = str(row.get("status") or "")
    mapping = {
        attendance_service.STATUS_PRESENT: "Obecny",
        attendance_service.STATUS_PENDING_LATE: "Do decyzji",
        attendance_service.STATUS_MISSING: "Brak logowania",
        attendance_service.STATUS_EXCUSED: str(row.get("reason") or "Nieobecność"),
        attendance_service.STATUS_SATURDAY: "Sobota — decyzja",
        attendance_service.STATUS_PLANNED: "Plan",
        "DATA_CONFLICT": "Konflikt danych",
    }
    return mapping.get(status, status or "—")


def _first_login(row: dict) -> str:
    raw = str(row.get("first_login_ts") or row.get("logged_ts") or "")
    if not raw:
        return "—"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%H:%M")
    except Exception:
        return raw[-8:-3] if len(raw) >= 8 else raw


def _absence_month(login: str, year: int, month: int) -> tuple[float, float]:
    try:
        rows = list(leave_workflow_service.calendar_snapshot(login, year, month).get("leaves") or [])
    except Exception:
        rows = []
    vac = l4 = 0.0
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("type") or "").strip().casefold()
        try:
            qty = float(row.get("quantity_days") or 1.0)
        except Exception:
            qty = 1.0
        if kind == "urlop":
            vac += qty
        elif kind == "l4":
            l4 += qty
    return vac, l4


def _build_my_attendance_card(parent, login: str):
    today = date.today()
    summary = attendance_service.summary_for_month(login, today.year, today.month)
    box = ttk.LabelFrame(parent, text="Moja obecność", style="WM.Section.TLabelframe", padding=12)

    monthly = (
        f"🕒 {_month_label(today.month)}: {_fmt(summary.get('days'))} dniówki | "
        f"{_fmt(summary.get('missing'))} braków | {_fmt(summary.get('pending'))} do decyzji | "
        f"{_fmt(summary.get('overtime_hours'))} h nadgodzin"
    )
    ttk.Label(box, text=monthly, style="WM.TLabel").pack(anchor="w")

    today_rows = [
        dict(row) for row in attendance_service.month_records(login, today.year, today.month)
        if str(row.get("date") or "")[:10] == today.isoformat()
    ]
    if today_rows:
        row = sorted(
            today_rows,
            key=lambda item: (
                0 if item.get("status") != attendance_service.STATUS_PLANNED else 1,
                0 if item.get("slot") == attendance_service.RANO else 1,
            ),
        )[0]
        today_text = (
            f"Dzisiaj: {_shift_label(str(row.get('slot') or ''))} | "
            f"pierwsze logowanie: {_first_login(row)} | {_status_text(row)}"
        )
    else:
        try:
            planned = attendance_service._planned_slot_for_day(login, today)
        except Exception:
            planned = None
        today_text = f"Dzisiaj: {_shift_label(planned)} | pierwsze logowanie: — | {'Plan' if planned else 'Wolne'}"

    today_row = ttk.Frame(box, style="WM.TFrame")
    today_row.pack(fill="x", pady=(5, 0))
    ttk.Label(today_row, text=today_text, style="WM.Muted.TLabel").pack(side="left")
    add_help_button(
        today_row,
        "Karta pokazuje bieżący miesiąc i stan dzisiejszego dnia z ewidencji WM. Braki i pozycje do decyzji wynikają z Grafiku oraz faktycznych logowań.",
    ).pack(side="left", padx=(6, 0))
    return box


def _patch_my_attendance_card() -> None:
    try:
        import gui_profile_core as profile_core
    except Exception:
        return
    cls = profile_core.ProfileView
    if getattr(cls, "_wm_my_attendance_card_v13", False):
        return
    original = cls._render_simple_profile

    def render_simple_profile(self, parent) -> None:
        original(self, parent)
        login = str(getattr(self, "login", "") or "").strip()
        if not login:
            return
        try:
            card = _build_my_attendance_card(parent, login)
        except Exception as exc:
            print(f"[WM-DBG][PROFILE][WARN] my attendance card failed: {exc!r}")
            return
        before_widget = None
        try:
            for child in parent.winfo_children():
                if isinstance(child, ttk.LabelFrame) and str(child.cget("text")) == "Moje Dyspozycje":
                    before_widget = child
                    break
        except Exception:
            before_widget = None
        if before_widget is not None:
            card.pack(fill="x", pady=(0, 10), before=before_widget)
        else:
            card.pack(fill="x", pady=(0, 10))

    cls._render_simple_profile = render_simple_profile
    cls._wm_my_attendance_card_v13 = True


def _render_ruch_wm(self) -> None:
    """Operacyjny widok WM. Bez obecności, zmiany i wejścia do profilu pracownika."""
    parent = self._tabs.get("Zespół")
    if parent is None:
        return
    self._clear(parent)

    box = ttk.LabelFrame(
        parent,
        text=f"Ruch WM — {getattr(self, 'snapshot', {}).get('period_label', '')}",
        style="WM.Section.TLabelframe",
        padding=8,
    )
    box.pack(fill="both", expand=True, padx=8, pady=8)
    tree = self._make_tree(
        box,
        [
            ("name", "Pracownik", 160, "w"),
            ("role", "Rola", 105, "w"),
            ("open", "Otwarte", 72, "center"),
            ("done", "Wykonane", 78, "center"),
            ("urgent", "Pilne", 58, "center"),
            ("tools", "Narzędzia", 78, "center"),
            ("machines", "Maszyny", 72, "center"),
            ("services", "Serwisy", 68, "center"),
            ("leave", "Urlop poz.", 80, "center"),
        ],
        height=13,
    )

    mapping: dict[str, str] = {}
    names: list[str] = []
    for row in getattr(self, "snapshot", {}).get("team") or []:
        name = str(row.get("name") or row.get("login") or "—")
        names.append(name)
        try:
            leave = float(row.get("leave_remaining") or 0)
            leave_text = str(int(leave)) if leave.is_integer() else f"{leave:.1f}"
        except Exception:
            leave_text = str(row.get("leave_remaining") or "0")
        iid = tree.insert(
            "",
            "end",
            values=(
                name,
                row.get("role"),
                row.get("open", 0),
                row.get("done", 0),
                row.get("urgent", 0),
                row.get("tools", 0),
                row.get("machines", 0),
                row.get("services", 0),
                leave_text,
            ),
        )
        mapping[iid] = str(row.get("login") or "")
    _fit_name_column(tree, names)
    self._wm_ruch_tree = tree
    self._wm_ruch_login = mapping

    actions = ttk.Frame(parent, style="WM.Container.TFrame")
    actions.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Label(
        actions,
        text="Ten widok pokazuje aktywność operacyjną WM. Zmiana i obecność są wyłącznie w zakładce Obecność.",
        style="WM.Muted.TLabel",
    ).pack(side="left")
    add_help_button(
        actions,
        "Ruch WM pokazuje zadania, narzędzia, maszyny i serwisy powiązane z pracownikiem. Nie służy do rozliczania dniówek ani nieobecności.",
    ).pack(side="left", padx=(6, 0))


def _absence_labels(login: str, day_text: str) -> list[str]:
    labels: list[str] = []
    try:
        rows = leave_workflow_service.active_absences_for_day(login, day_text)
    except Exception:
        rows = []
    for row in rows:
        kind = str(row.get("type") or "").strip().casefold()
        label = {"urlop": "UR", "l4": "L4", "nn": "NN"}.get(kind, kind.upper())
        if label and label not in labels:
            labels.append(label)
    return labels


def _decision_type(case: dict) -> str:
    if case.get("is_conflict"):
        return "Konflikt"
    status = str(case.get("status") or "")
    if status == attendance_service.STATUS_MISSING:
        return "Brak"
    if status == attendance_service.STATUS_PENDING_LATE:
        return "Późne logowanie"
    if status == attendance_service.STATUS_SATURDAY:
        return "Sobota"
    return "Decyzja"


def _all_decisions(year: int, month: int) -> list[dict]:
    rows: list[dict] = []
    for user in workforce_profile_service.list_users(active_only=True):
        login = str(user.get("login") or "").strip()
        role = str(user.get("rola") or user.get("role") or "").strip().casefold()
        if not login or role == "guest":
            continue
        display_name = workforce_profile_service.display_name(user)
        by_key: dict[tuple[str, str], dict] = {}
        for row in attendance_service.decision_records(login, year, month):
            item = dict(row)
            item["display_name"] = display_name
            item["login"] = login
            by_key[(str(item.get("date") or ""), str(item.get("slot") or ""))] = item

        for row in attendance_service.month_records(login, year, month):
            day_text = str(row.get("date") or "")[:10]
            slot = str(row.get("slot") or attendance_service.RANO)
            reason = str(row.get("reason") or "").strip().upper()
            if reason == "SW":
                reason = "ŚW"
            leave_labels = _absence_labels(login, day_text)
            status = str(row.get("status") or "")
            labels = list(leave_labels)
            if reason and reason not in labels:
                labels.append(reason)

            conflict = False
            if leave_labels and status != attendance_service.STATUS_EXCUSED:
                conflict = True
            elif reason and status != attendance_service.STATUS_EXCUSED:
                conflict = True
            elif leave_labels and reason and reason not in leave_labels:
                conflict = True
            if not conflict:
                continue

            current_state = _status_text(row)
            item = dict(row)
            item.update({
                "login": login,
                "display_name": display_name,
                "is_conflict": True,
                "status": "DATA_CONFLICT",
                "conflict_reason": reason or (leave_labels[0] if leave_labels else ""),
                "decision_label": f"{', '.join(labels) or 'Nieobecność'} + {current_state}",
            })
            by_key[(day_text, slot)] = item

        rows.extend(by_key.values())

    rows.sort(
        key=lambda item: (
            0 if item.get("is_conflict") else 1,
            str(item.get("date") or ""),
            str(item.get("display_name") or ""),
        )
    )
    return rows


def _open_case_dialog(owner, case: dict, on_saved: Callable[[], None] | None = None) -> None:
    login = str(case.get("login") or "").strip()
    if not login:
        return
    win = tk.Toplevel(owner)
    win.title(f"Decyzja obecności — {case.get('display_name') or login}")
    try:
        win.transient(owner.winfo_toplevel())
        win.grab_set()
    except Exception:
        pass
    frame = ttk.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)

    day_var = tk.StringVar(value=str(case.get("date") or ""))
    slot_var = tk.StringVar(value=str(case.get("slot") or attendance_service.RANO))
    value_var = tk.StringVar(value="0" if case.get("status") == attendance_service.STATUS_MISSING else "1")
    save_day_var = tk.BooleanVar(value=case.get("status") != attendance_service.STATUS_SATURDAY)
    ot_var = tk.BooleanVar(value=case.get("status") == attendance_service.STATUS_SATURDAY)
    hours_var = tk.StringVar(value="8" if case.get("status") == attendance_service.STATUS_SATURDAY else "0")
    ot_type_var = tk.StringVar(value="sobota" if case.get("status") == attendance_service.STATUS_SATURDAY else "zwykle")
    note_var = tk.StringVar(value="")

    fields = [
        ("Pracownik:", case.get("display_name") or login),
        ("Data:", day_var.get()),
        ("Zmiana:", slot_var.get()),
        ("Typ:", _decision_type(case)),
        ("Pierwsze logowanie:", _first_login(case)),
        ("Stan:", case.get("decision_label") or _status_text(case)),
    ]
    for row_no, (label, value) in enumerate(fields):
        ttk.Label(frame, text=label).grid(row=row_no, column=0, sticky="w", pady=3)
        ttk.Label(frame, text=str(value or "—")).grid(row=row_no, column=1, sticky="w", pady=3)

    row_no = len(fields)
    if case.get("is_conflict"):
        warning = ttk.Frame(frame)
        warning.grid(row=row_no, column=0, columnspan=3, sticky="ew", pady=(7, 2))
        ttk.Label(
            warning,
            text="⚠ Ten dzień ma sprzeczne dane. Wybierz, czy prawidłowa jest nieobecność, czy dniówka.",
            style="WM.Muted.TLabel",
        ).pack(side="left")
        add_help_button(
            warning,
            "Zachowanie nieobecności wyzeruje dniówkę i ustawi właściwy powód. Zapis dniówki anuluje aktywną nieobecność, ale pozostawi ją w Historii.",
        ).pack(side="left", padx=(6, 0))
        row_no += 1

    ttk.Checkbutton(frame, text="Zapisz dniówkę", variable=save_day_var).grid(row=row_no, column=0, sticky="w", pady=(10, 4))
    ttk.Combobox(frame, textvariable=value_var, values=("0", "0.5", "1"), state="readonly", width=10).grid(
        row=row_no, column=1, sticky="w", pady=(10, 4)
    )
    add_help_button(
        frame,
        "Wybierz 0, 0,5 albo 1 dla wskazanego dnia. Jeśli dzień ma L4, ŚW, NN lub urlop, WM poprosi o potwierdzenie zastąpienia nieobecności korektą.",
        row=row_no,
        column=2,
        padx=(6, 0),
    )

    row_no += 1
    ttk.Checkbutton(frame, text="Nadgodziny", variable=ot_var).grid(row=row_no, column=0, sticky="w", pady=4)
    ot_wrap = ttk.Frame(frame)
    ot_wrap.grid(row=row_no, column=1, sticky="w", pady=4)
    ttk.Entry(ot_wrap, textvariable=hours_var, width=7).pack(side="left")
    ttk.Label(ot_wrap, text=" h  ").pack(side="left")
    ttk.Combobox(
        ot_wrap,
        textvariable=ot_type_var,
        values=("zwykle", "sobota", "niedziela", "swieto"),
        state="readonly",
        width=12,
    ).pack(side="left")
    add_help_button(
        frame,
        "Sobota jest zatwierdzana osobno od zwykłej dniówki. Nadgodziny nie są wyliczane z samego czasu otwarcia WM.",
        row=row_no,
        column=2,
        padx=(6, 0),
    )

    row_no += 1
    ttk.Label(frame, text="Powód / uwaga:").grid(row=row_no, column=0, sticky="w", pady=4)
    ttk.Entry(frame, textvariable=note_var).grid(row=row_no, column=1, sticky="ew", pady=4)
    add_help_button(
        frame,
        "Przy ręcznej decyzji wpisz krótki powód. Pozwala to później odtworzyć, dlaczego dniówka lub nadgodziny zostały zmienione.",
        row=row_no,
        column=2,
        padx=(6, 0),
    )

    row_no += 1
    current_text = str(case.get("decision_label") or _status_text(case) or "—")
    preview_var = tk.StringVar(value="")
    preview = ttk.Frame(frame)
    preview.grid(row=row_no, column=0, columnspan=3, sticky="ew", pady=(8, 2))
    ttk.Label(preview, text="Podgląd zmiany:", style="WM.Muted.TLabel").pack(side="left")
    ttk.Label(preview, textvariable=preview_var).pack(side="left", padx=(6, 0))
    add_help_button(
        preview,
        "Przed zapisem WM pokazuje stan bieżący i wynik korekty. To jest tylko podgląd — dane zmienią się dopiero po użyciu Zapisz decyzję.",
    ).pack(side="left", padx=(6, 0))

    def _refresh_preview(*_args) -> None:
        target: list[str] = []
        if save_day_var.get():
            target.append(f"{_fmt(value_var.get())} dniówki")
        if ot_var.get():
            target.append(f"{_fmt(hours_var.get())} h nadgodzin ({ot_type_var.get()})")
        preview_var.set(f"{current_text} → {' + '.join(target) if target else 'bez zmiany'}")

    for var in (save_day_var, value_var, ot_var, hours_var, ot_type_var):
        try:
            var.trace_add("write", _refresh_preview)
        except Exception:
            pass
    _refresh_preview()

    def _finish() -> None:
        win.destroy()
        if callable(on_saved):
            on_saved()

    def keep_absence() -> None:
        note = note_var.get().strip()
        if not note:
            messagebox.showinfo("Obecność", "Wpisz powód lub krótką uwagę.", parent=win)
            return
        reason = str(case.get("conflict_reason") or "").strip().upper()
        if reason == "SW":
            reason = "ŚW"
        if reason not in {"L4", "UR", "UŻ", "ŚW", "NN"}:
            messagebox.showerror("Obecność", "Nie udało się ustalić rodzaju nieobecności.", parent=win)
            return
        try:
            attendance_service.set_reason(
                day_var.get(), slot_var.get(), login, _actor(owner), reason,
                datetime.now().astimezone().isoformat(timespec="seconds"),
            )
        except Exception as exc:
            messagebox.showerror("Obecność", f"Nie udało się zachować nieobecności:\n{exc}", parent=win)
            return
        _finish()

    def save() -> None:
        note = note_var.get().strip()
        if not note:
            messagebox.showinfo("Obecność", "Wpisz powód lub krótką uwagę.", parent=win)
            return
        replace_absence = False
        try:
            if save_day_var.get():
                conflict = attendance_service.absence_conflict(day_var.get(), login)
                if conflict.get("has_conflict"):
                    conflict_slot = str(conflict.get("slot") or "")
                    if conflict_slot and conflict_slot != slot_var.get():
                        messagebox.showinfo(
                            "Korekta nieobecności",
                            f"Nieobecność jest zapisana na zmianie {conflict_slot}. Wybierz tę samą zmianę.",
                            parent=win,
                        )
                        return
                    labels = ", ".join(conflict.get("reasons") or []) or "nieobecność"
                    if not messagebox.askyesno(
                        "Korekta nieobecności",
                        f"Ten dzień ma wpis {labels}. Zastąpić nieobecność korektą?\n\n"
                        "Wpis nieobecności zostanie anulowany, ale pozostanie w historii.",
                        parent=win,
                    ):
                        return
                    replace_absence = True
                attendance_service.set_manual_day(
                    day_var.get(), slot_var.get(), login, float(value_var.get()), _actor(owner), note,
                    replace_absence=replace_absence,
                )
            if ot_var.get():
                attendance_service.set_overtime(
                    day_var.get(),
                    slot_var.get(),
                    login,
                    float(hours_var.get()),
                    _actor(owner),
                    overtime_type=ot_type_var.get(),
                    day_value=1.0 if ot_type_var.get() == "sobota" else None,
                    note=note,
                )
        except Exception as exc:
            messagebox.showerror("Obecność", f"Nie udało się zapisać decyzji:\n{exc}", parent=win)
            return
        _finish()

    row_no += 1
    actions = ttk.Frame(frame)
    actions.grid(row=row_no, column=0, columnspan=3, sticky="e", pady=(12, 0))
    ttk.Button(actions, text="Anuluj", command=win.destroy).pack(side="right")
    ttk.Button(actions, text="Zapisz decyzję", command=save).pack(side="right", padx=(0, 8))
    if case.get("is_conflict"):
        ttk.Button(actions, text="Zachowaj nieobecność", command=keep_absence).pack(side="right", padx=(0, 8))


def _manual_correction(owner, login: str, on_saved: Callable[[], None] | None = None) -> None:
    """Korekta dnia z wyborem z ewidencji i czytelnym podglądem aktualnego stanu."""
    if not login:
        return
    display_name = workforce_profile_service.display_name(
        workforce_profile_service.get_user(login) or {"login": login}
    )
    win = tk.Toplevel(owner)
    win.title(f"Korekta obecności — {display_name}")
    try:
        win.transient(owner.winfo_toplevel())
        win.grab_set()
    except Exception:
        pass

    frame = ttk.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(0, weight=1)

    top = ttk.Frame(frame)
    top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    ttk.Label(top, text="Miesiąc:").pack(side="left")
    month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
    month_box = ttk.Combobox(top, textvariable=month_var, values=_month_choices(), state="readonly", width=9)
    month_box.pack(side="left", padx=(5, 8))
    add_help_button(
        top,
        "Wybierz miesiąc, a następnie dzień z historii obecności. Data i zmiana zostaną podstawione automatycznie; ręczne pola poniżej są tylko awaryjnym wyborem dla dnia bez wpisu.",
    ).pack(side="left")

    history_box = ttk.LabelFrame(frame, text="Wybierz dzień z ewidencji", padding=6)
    history_box.grid(row=1, column=0, sticky="nsew")
    frame.rowconfigure(1, weight=1)
    history = ttk.Treeview(
        history_box,
        columns=("date", "slot", "login", "status", "day"),
        show="headings",
        height=10,
    )
    for key, label, width, anchor in (
        ("date", "Data", 100, "center"),
        ("slot", "Zmiana", 90, "center"),
        ("login", "Pierwsze logowanie", 125, "center"),
        ("status", "Stan teraz", 230, "w"),
        ("day", "Dniówka", 75, "center"),
    ):
        history.heading(key, text=label)
        history.column(key, width=width, anchor=anchor, stretch=key == "status")
    history.pack(fill="both", expand=True)

    select_box = ttk.Frame(frame)
    select_box.grid(row=2, column=0, sticky="ew", pady=(8, 4))
    select_box.columnconfigure(3, weight=1)
    day_var = tk.StringVar(value=date.today().isoformat())
    slot_var = tk.StringVar(value=attendance_service.RANO)
    state_var = tk.StringVar(value="Wybierz dzień z listy lub podaj datę poniżej.")
    ttk.Label(select_box, text="Data:").grid(row=0, column=0, sticky="w")
    ttk.Entry(select_box, textvariable=day_var, width=12).grid(row=0, column=1, sticky="w", padx=(5, 12))
    ttk.Label(select_box, text="Zmiana:").grid(row=0, column=2, sticky="w")
    ttk.Combobox(
        select_box,
        textvariable=slot_var,
        values=(attendance_service.RANO, attendance_service.POPO),
        state="readonly",
        width=10,
    ).grid(row=0, column=3, sticky="w", padx=(5, 0))
    ttk.Label(select_box, textvariable=state_var, style="WM.Muted.TLabel").grid(
        row=1, column=0, columnspan=4, sticky="w", pady=(6, 0)
    )

    rows_by_iid: dict[str, dict] = {}

    def _state_label(row: dict) -> str:
        labels = _absence_labels(login, str(row.get("date") or "")[:10])
        reason = str(row.get("reason") or "").strip().upper()
        if reason == "SW":
            reason = "ŚW"
        if reason and reason not in labels:
            labels.append(reason)
        status = _status_text(row)
        if labels and str(row.get("status") or "") != attendance_service.STATUS_EXCUSED:
            return f"{', '.join(labels)} + {status}"
        if labels:
            return ", ".join(labels)
        return status

    def refresh_history(_event=None) -> None:
        rows_by_iid.clear()
        for iid in history.get_children():
            history.delete(iid)
        year, month = _month_tuple(month_var.get())
        rows = list(attendance_service.month_records(login, year, month))
        rows.sort(key=lambda item: (str(item.get("date") or ""), str(item.get("slot") or "")), reverse=True)
        for row in rows:
            item = dict(row)
            state = _state_label(item)
            iid = history.insert(
                "",
                "end",
                values=(
                    str(item.get("date") or "")[:10],
                    item.get("slot") or "—",
                    _first_login(item),
                    state,
                    _fmt(item.get("day_value")),
                ),
            )
            item["_display_state"] = state
            rows_by_iid[iid] = item
        if not rows:
            history.insert("", "end", values=("—", "—", "—", "Brak wpisów w tym miesiącu", "—"))
        state_var.set("Wybierz dzień z listy lub podaj datę poniżej.")

    def select_history(_event=None) -> None:
        selected = history.selection()
        if not selected:
            return
        item = rows_by_iid.get(selected[0])
        if not item:
            return
        day_var.set(str(item.get("date") or "")[:10])
        slot = str(item.get("slot") or attendance_service.RANO)
        if slot in attendance_service.VALID_SLOTS:
            slot_var.set(slot)
        state_var.set(
            f"Stan teraz: {item.get('_display_state') or _status_text(item)} | "
            f"dniówka: {_fmt(item.get('day_value'))}"
        )

    history.bind("<<TreeviewSelect>>", select_history, add="+")
    month_box.bind("<<ComboboxSelected>>", refresh_history, add="+")

    def continue_edit(_event=None) -> None:
        day_text = day_var.get().strip()
        try:
            parsed_day = date.fromisoformat(day_text)
        except Exception:
            messagebox.showerror("Obecność", "Nieprawidłowa data. Użyj formatu RRRR-MM-DD.", parent=win)
            return
        slot_text = str(slot_var.get() or "").strip().upper()
        if slot_text not in attendance_service.VALID_SLOTS:
            messagebox.showerror("Obecność", "Zmiana musi być RANO albo POPO.", parent=win)
            return

        selected_row: dict[str, Any] | None = None
        for row in attendance_service.month_records(login, parsed_day.year, parsed_day.month):
            if str(row.get("date") or "")[:10] == day_text and str(row.get("slot") or "") == slot_text:
                selected_row = dict(row)
                break

        if selected_row is None:
            selected_row = {
                "date": day_text,
                "slot": slot_text,
                "status": attendance_service.STATUS_MISSING,
                "day_value": 0.0,
                "decision_label": "Brak wpisu w ewidencji",
            }

        labels = _absence_labels(login, day_text)
        reason = str(selected_row.get("reason") or "").strip().upper()
        if reason == "SW":
            reason = "ŚW"
        if reason and reason not in labels:
            labels.append(reason)
        current_status = str(selected_row.get("status") or "")
        current_text = _status_text(selected_row)
        is_conflict = bool(labels and current_status != attendance_service.STATUS_EXCUSED)
        if labels:
            selected_row["decision_label"] = (
                f"{', '.join(labels)} + {current_text}" if is_conflict else ", ".join(labels)
            )
        else:
            selected_row.setdefault("decision_label", current_text)
        selected_row.update({
            "login": login,
            "display_name": display_name,
            "date": day_text,
            "slot": slot_text,
            "is_conflict": is_conflict,
            "conflict_reason": reason or (labels[0] if labels else ""),
        })
        win.destroy()
        _open_case_dialog(owner, selected_row, on_saved=on_saved)

    history.bind("<Double-1>", continue_edit, add="+")
    actions = ttk.Frame(frame)
    actions.grid(row=3, column=0, sticky="e", pady=(10, 0))
    ttk.Button(actions, text="Anuluj", command=win.destroy).pack(side="right")
    ttk.Button(actions, text="Przejdź do korekty", command=continue_edit).pack(side="right", padx=(0, 8))
    refresh_history()


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
    combo = ttk.Combobox(
        top,
        textvariable=self._wm_att_month_var,
        values=_month_choices(),
        state="readonly",
        width=9,
    )
    combo.pack(side="left", padx=(6, 8))
    combo.bind("<<ComboboxSelected>>", lambda _e: _render_attendance(self), add="+")
    add_help_button(
        top,
        "Obecność łączy Grafik z faktycznymi logowaniami do WM. Zaplanowany dzień bez logowania automatycznie trafia do Brak i do kolejki decyzji po zakończeniu okna logowania.",
    ).pack(side="left")

    year, month = _month_tuple(self._wm_att_month_var.get())
    decisions = _all_decisions(year, month)
    decision_counts = {"missing": 0, "late": 0, "saturday": 0, "conflict": 0}
    for case in decisions:
        if case.get("is_conflict"):
            decision_counts["conflict"] += 1
        elif case.get("status") == attendance_service.STATUS_MISSING:
            decision_counts["missing"] += 1
        elif case.get("status") == attendance_service.STATUS_PENDING_LATE:
            decision_counts["late"] += 1
        elif case.get("status") == attendance_service.STATUS_SATURDAY:
            decision_counts["saturday"] += 1

    queue_box = ttk.LabelFrame(
        parent,
        text=f"Do decyzji — {len(decisions)}",
        style="WM.Section.TLabelframe",
        padding=8,
    )
    queue_box.pack(fill="x", padx=8, pady=(0, 8))

    counters = ttk.Frame(queue_box, style="WM.Container.TFrame")
    counters.pack(fill="x", pady=(0, 6))
    ttk.Label(
        counters,
        text=(
            f"🔴 Brak: {decision_counts['missing']}   "
            f"🟠 Późne: {decision_counts['late']}   "
            f"🟣 Soboty: {decision_counts['saturday']}   "
            f"⚠ Konflikty: {decision_counts['conflict']}"
        ),
        style="WM.Muted.TLabel",
    ).pack(side="left")
    add_help_button(
        counters,
        "Liczniki pokazują wszystkie sprawy wymagające reakcji Brygadzisty w wybranym miesiącu. Konflikt oznacza sprzeczne wpisy, np. L4 i jednocześnie dniówkę.",
    ).pack(side="left", padx=(6, 0))

    qtree = self._make_tree(
        queue_box,
        [
            ("name", "Pracownik", 160, "w"),
            ("date", "Data", 95, "center"),
            ("slot", "Zmiana", 80, "center"),
            ("type", "Typ", 120, "w"),
            ("login", "Pierwsze logowanie", 120, "center"),
            ("state", "Stan", 220, "w"),
        ],
        height=6,
    )
    qmap: dict[str, dict] = {}
    qnames: list[str] = []
    for case in decisions:
        name = str(case.get("display_name") or case.get("login") or "—")
        qnames.append(name)
        urgent = bool(case.get("is_conflict")) or case.get("status") == attendance_service.STATUS_MISSING
        iid = qtree.insert(
            "",
            "end",
            values=(
                name,
                case.get("date"),
                case.get("slot"),
                _decision_type(case),
                _first_login(case),
                case.get("decision_label"),
            ),
            tags=("urgent" if urgent else "warning",),
        )
        qmap[iid] = case
    _fit_name_column(qtree, qnames)
    if not decisions:
        qtree.insert(
            "", "end",
            values=("—", "—", "—", "—", "—", "Brak pozycji wymagających decyzji"),
            tags=("ok",),
        )

    def open_queue_case(_event=None) -> None:
        selected = qtree.selection()
        if not selected:
            messagebox.showinfo("Obecność", "Wybierz pozycję z listy Do decyzji.", parent=self.winfo_toplevel())
            return
        case = qmap.get(selected[0])
        if case:
            _open_case_dialog(self, case, on_saved=lambda: _render_attendance(self))

    qtree.bind("<Double-1>", open_queue_case, add="+")
    qactions = ttk.Frame(queue_box, style="WM.Container.TFrame")
    qactions.pack(fill="x", pady=(6, 0))
    ttk.Button(qactions, text="Rozstrzygnij zaznaczone", command=open_queue_case).pack(side="left")
    add_help_button(
        qactions,
        "Tu są braki logowania, późne logowania, soboty i konflikty danych. Po zapisaniu decyzji prawidłowo rozstrzygnięta pozycja znika z tej listy.",
    ).pack(side="left", padx=(6, 0))

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
            ("name", "Pracownik", 160, "w"),
            ("shift", "Zmiana", 135, "center"),
            ("today", "Dzisiaj", 100, "center"),
            ("days", "🟢 Dniówki", 78, "center"),
            ("sat", "🟣 Soboty", 70, "center"),
            ("ot", "🟠 Nadgodz.", 82, "center"),
            ("vac", "🔵 Urlop", 62, "center"),
            ("l4", "🟣 L4", 52, "center"),
            ("miss", "🔴 Brak", 56, "center"),
            ("pending", "🟠 Decyz.", 66, "center"),
        ],
        height=10,
    )
    team = _team_by_login(self)
    mapping: dict[str, str] = {}
    names: list[str] = []
    for user in workforce_profile_service.list_users(active_only=True):
        login = str(user.get("login") or "").strip()
        role = str(user.get("rola") or user.get("role") or "").casefold()
        if not login or role == "guest":
            continue
        summary = attendance_service.summary_for_month(login, year, month)
        vac, l4 = _absence_month(login, year, month)
        team_row = team.get(login.casefold(), {})
        name = workforce_profile_service.display_name(user)
        names.append(name)
        pending = float(summary.get("pending") or 0)
        missing = float(summary.get("missing") or 0)
        tag = "urgent" if missing else ("warning" if pending else "ok")
        iid = tree.insert(
            "",
            "end",
            values=(
                name,
                team_row.get("shift") or "—",
                team_row.get("status") or "—",
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
        mapping[iid] = login
    _fit_name_column(tree, names)
    self._wm_attendance_tree = tree
    self._wm_attendance_user_by_iid = mapping

    actions = ttk.Frame(parent, style="WM.Container.TFrame")
    actions.pack(fill="x", padx=8, pady=(0, 8))

    def selected_login() -> str:
        selected = tree.selection()
        return str(mapping.get(selected[0], "")) if selected else ""

    def details(tab: str = "Obecność") -> None:
        login = selected_login()
        if not login:
            messagebox.showinfo("Obecność", "Wybierz pracownika z ewidencji.", parent=self.winfo_toplevel())
            return
        try:
            import profile_foreman_edit_runtime as edit_runtime
            edit_runtime.open_employee_editor(self, login, initial_tab=tab, on_saved=self.refresh_data)
        except Exception as exc:
            messagebox.showerror("Profil", f"Nie udało się otworzyć profilu:\n{exc}", parent=self.winfo_toplevel())

    ttk.Button(actions, text="Szczegóły pracownika", command=lambda: details("Obecność")).pack(side="left")
    ttk.Button(
        actions,
        text="Korekta ręczna",
        command=lambda: _manual_correction(self, selected_login(), on_saved=lambda: _render_attendance(self))
        if selected_login()
        else messagebox.showinfo("Obecność", "Wybierz pracownika z ewidencji.", parent=self.winfo_toplevel()),
    ).pack(side="left", padx=(8, 0))
    add_help_button(
        actions,
        "Korekta ręczna jest wyjątkiem dla sytuacji, których nie ma w kolejce, np. gdy WM był wyłączony. Przy L4 lub innej nieobecności WM wymaga potwierdzenia zastąpienia wpisu.",
    ).pack(side="left", padx=(6, 0))
    tree.bind("<Double-1>", lambda _e: details("Obecność"), add="+")


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
            f"🔴 Nowe: {totals.get('nowa', 0)}   🟡 Zaplanowane: {totals.get('zaplanowana', 0)}   "
            f"🟠 W realizacji: {totals.get('w_realizacji', 0)}   🟢 Wykonane: {totals.get('wykonana', 0)}"
        ),
        style="WM.Muted.TLabel",
    ).pack(side="left")

    if not hasattr(self, "_wm_feedback_filter"):
        self._wm_feedback_filter = tk.StringVar(value="Wszystkie")
    ttk.Label(top, text="  Filtr:").pack(side="left", padx=(12, 0))
    filter_box = ttk.Combobox(
        top,
        textvariable=self._wm_feedback_filter,
        values=("Wszystkie", *feedback_service.STATUSES),
        state="readonly",
        width=15,
    )
    filter_box.pack(side="left", padx=(4, 6))
    filter_box.bind("<<ComboboxSelected>>", lambda _e: _render_feedback(self), add="+")
    add_help_button(
        top,
        "Filtr ogranicza listę do wybranego statusu. Status, osoba obsługująca i notatka decyzji są widoczne w historii opinii pracownika.",
    ).pack(side="left")

    box = ttk.LabelFrame(parent, text="Opinie użytkowników", style="WM.Section.TLabelframe", padding=8)
    box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    tree = self._make_tree(
        box,
        [
            ("date", "Data", 120, "center"),
            ("author", "Autor", 120, "w"),
            ("module", "Moduł", 95, "w"),
            ("message", "Opinia", 330, "w"),
            ("status", "Status", 110, "center"),
            ("handler", "Obsługuje", 105, "w"),
            ("handled", "Obsłużono", 120, "center"),
            ("note", "Notatka decyzji", 240, "w"),
        ],
        height=11,
    )
    try:
        tree.column("message", stretch=True)
        tree.column("note", stretch=True)
    except Exception:
        pass

    selected_filter = self._wm_feedback_filter.get()
    by_iid: dict[str, dict] = {}
    for row in feedback_service.list_feedback():
        status = str(row.get("status") or "nowa")
        if selected_filter != "Wszystkie" and status != selected_filter:
            continue
        tag = "ok" if status == "wykonana" else ("warning" if status in {"zaplanowana", "w_realizacji"} else "urgent")
        created = str(row.get("created_at") or "").replace("T", " ")[:16]
        handled = str(row.get("handled_at") or "").replace("T", " ")[:16]
        iid = tree.insert(
            "",
            "end",
            values=(
                created,
                row.get("login_snapshot") or row.get("login"),
                row.get("module"),
                row.get("message"),
                feedback_service.status_label(status),
                row.get("handled_by") or "—",
                handled or "—",
                row.get("decision_note") or "—",
            ),
            tags=(tag,),
        )
        by_iid[iid] = dict(row)

    self._wm_feedback_tree = tree
    self._wm_feedback_by_iid = {iid: str(row.get("id") or "") for iid, row in by_iid.items()}

    actions = ttk.Frame(parent, style="WM.Container.TFrame")
    actions.pack(fill="x", padx=8, pady=(0, 8))
    status_var = tk.StringVar(value="w_realizacji")
    module_var = tk.StringVar(value="Inne")
    note_var = tk.StringVar(value="")
    ttk.Label(actions, text="Status:").pack(side="left")
    ttk.Combobox(actions, textvariable=status_var, values=feedback_service.STATUSES, state="readonly", width=14).pack(
        side="left", padx=(5, 8)
    )
    ttk.Label(actions, text="Moduł:").pack(side="left")
    ttk.Combobox(
        actions,
        textvariable=module_var,
        values=("Profile", "Maszyny", "Narzędzia", "Dyspozycje", "Planista", "Magazyn", "Inne"),
        width=13,
    ).pack(side="left", padx=(5, 8))
    ttk.Label(actions, text="Notatka:").pack(side="left")
    ttk.Entry(actions, textvariable=note_var, width=32).pack(side="left", padx=(5, 8), fill="x", expand=True)

    def load_selection(_event=None) -> None:
        selected = tree.selection()
        if not selected:
            return
        row = by_iid.get(selected[0], {})
        status_var.set(str(row.get("status") or "nowa"))
        module_var.set(str(row.get("module") or "Inne"))
        note_var.set(str(row.get("decision_note") or ""))

    def update_selected() -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Opinie", "Wybierz opinię z listy.", parent=self.winfo_toplevel())
            return
        row = by_iid.get(selected[0], {})
        try:
            feedback_service.update_feedback(
                str(row.get("id") or ""),
                status=status_var.get(),
                module=module_var.get(),
                actor=_actor(self),
                decision_note=note_var.get().strip(),
            )
        except Exception as exc:
            messagebox.showerror("Opinie", f"Nie udało się zapisać:\n{exc}", parent=self.winfo_toplevel())
            return
        _render_feedback(self)

    tree.bind("<<TreeviewSelect>>", load_selection, add="+")
    ttk.Button(actions, text="Zapisz obsługę", command=update_selected).pack(side="left")
    add_help_button(
        actions,
        "Zapisuje status, moduł, osobę obsługującą i notatkę decyzji. Oryginalna treść opinii nie jest zmieniana.",
    ).pack(side="left", padx=(6, 0))


def _walk(widget) -> list[tk.Misc]:
    out: list[tk.Misc] = []
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        out.append(child)
        out.extend(_walk(child))
    return out


def _toplevels(owner) -> list[tk.Toplevel]:
    try:
        root = owner.winfo_toplevel()
    except Exception:
        root = owner
    try:
        while getattr(root, "master", None) is not None and isinstance(root.master, tk.Misc):
            if isinstance(root.master, tk.Tk):
                root = root.master
                break
            root = root.master
    except Exception:
        pass
    found: list[tk.Toplevel] = []
    for widget in [root, *_walk(root)]:
        if isinstance(widget, tk.Toplevel):
            found.append(widget)
    return found


def _find_notebook(win: tk.Toplevel) -> ttk.Notebook | None:
    for widget in _walk(win):
        if isinstance(widget, ttk.Notebook):
            return widget
    return None


def _tab_frame(nb: ttk.Notebook, label: str):
    for tab_id in nb.tabs():
        try:
            if str(nb.tab(tab_id, "text")) == label:
                return nb.nametowidget(tab_id)
        except Exception:
            continue
    return None


def _clear_frame(frame) -> None:
    for child in frame.winfo_children():
        try:
            child.destroy()
        except Exception:
            pass


def _feedback_for_login(login: str) -> list[dict]:
    return [dict(row) for row in feedback_service.list_feedback(login=login)]


def _display_extra(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("nazwa", "name", "tytul", "title", "opis", "description"):
            value = item.get(key)
            if value:
                return str(value)
        return json.dumps(item, ensure_ascii=False, sort_keys=True)
    return str(item)


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if value in (None, "", "—"):
        return []
    return [value]


def _profile_audit_path() -> Path:
    try:
        import profile_foreman_edit_runtime as edit_runtime
        return Path(edit_runtime._audit_path())
    except Exception:
        try:
            from core import root_paths
            return root_paths.get_data_root() / "profile_changes_audit.json"
        except Exception:
            return Path("data") / "profile_changes_audit.json"


def _append_profile_audit(*, action: str, actor: str, login: str, before: Any, after: Any, note: str = "") -> None:
    path = _profile_audit_path()
    try:
        with path.open("r", encoding="utf-8") as handle:
            rows = json.load(handle)
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []
    rows.append({
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "action": action,
        "actor": str(actor or ""),
        "login": str(login or ""),
        "before": before,
        "after": after,
        "note": str(note or ""),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _save_extra(login: str, key: str, items: list[Any], actor: str) -> None:
    user = workforce_profile_service.get_user(login)
    if not user:
        raise ValueError("Nie znaleziono pracownika.")
    before = list(_as_list(user.get(key)))
    user[key] = list(items)
    workforce_profile_service.save_user(user)
    _append_profile_audit(
        action=f"extra_{key}",
        actor=actor,
        login=login,
        before=before,
        after=list(items),
        note=f"Edycja pola {key}",
    )


def _build_more_tab(frame, login: str, *, editable: bool) -> None:
    _clear_frame(frame)
    outer = ttk.Frame(frame, padding=10)
    outer.pack(fill="both", expand=True)
    extra_wrap = ttk.Frame(outer)
    extra_wrap.pack(fill="x")
    user = workforce_profile_service.get_user(login) or {"login": login}

    fields = [
        ("Umiejętności", "umiejetnosci"),
        ("Kursy / certyfikaty", "kursy"),
        ("Nagrody / pochwały", "nagrody"),
        ("Ostrzeżenia", "ostrzezenia"),
    ]

    for index, (label, key) in enumerate(fields):
        box = ttk.LabelFrame(extra_wrap, text=label, padding=6)
        box.grid(row=index // 2, column=index % 2, sticky="nsew", padx=4, pady=4)
        extra_wrap.grid_columnconfigure(index % 2, weight=1)
        items = _as_list(user.get(key))
        listbox = tk.Listbox(box, height=4, exportselection=False)
        listbox.pack(fill="both", expand=True)
        for item in items:
            listbox.insert("end", _display_extra(item))

        if editable:
            buttons = ttk.Frame(box)
            buttons.pack(fill="x", pady=(5, 0))

            def add_item(lb=listbox, field=key, local_items=items) -> None:
                value = simpledialog.askstring("Dodaj", "Wpisz treść:", parent=frame.winfo_toplevel())
                if not value:
                    return
                local_items.append(value.strip())
                _save_extra(login, field, local_items, _actor(frame))
                lb.insert("end", value.strip())

            def edit_item(lb=listbox, field=key, local_items=items) -> None:
                selected = lb.curselection()
                if not selected:
                    return
                idx = int(selected[0])
                value = simpledialog.askstring(
                    "Edytuj",
                    "Treść:",
                    initialvalue=_display_extra(local_items[idx]),
                    parent=frame.winfo_toplevel(),
                )
                if value is None:
                    return
                local_items[idx] = value.strip()
                _save_extra(login, field, local_items, _actor(frame))
                lb.delete(idx)
                lb.insert(idx, value.strip())

            def delete_item(lb=listbox, field=key, local_items=items) -> None:
                selected = lb.curselection()
                if not selected:
                    return
                idx = int(selected[0])
                if not messagebox.askyesno("Usuń", "Usunąć zaznaczony wpis?", parent=frame.winfo_toplevel()):
                    return
                local_items.pop(idx)
                _save_extra(login, field, local_items, _actor(frame))
                lb.delete(idx)

            ttk.Button(buttons, text="Dodaj", command=add_item).pack(side="left")
            ttk.Button(buttons, text="Edytuj", command=edit_item).pack(side="left", padx=(5, 0))
            ttk.Button(buttons, text="Usuń", command=delete_item).pack(side="left", padx=(5, 0))
            add_help_button(
                buttons,
                "Brygadzista może dodawać, poprawiać i usuwać wpisy w tej sekcji. Każda zmiana pozostawia ślad w Historii.",
            ).pack(side="left", padx=(6, 0))

    opinions = _feedback_for_login(login)
    op_box = ttk.LabelFrame(outer, text=f"Moje opinie — {len(opinions)}", padding=6)
    op_box.pack(fill="both", expand=True, padx=4, pady=(8, 4))
    tree = ttk.Treeview(
        op_box,
        columns=("date", "message", "module", "status", "handled", "note"),
        show="headings",
        height=7,
    )
    columns = [
        ("date", "Data", 120, "center"),
        ("message", "Opinia", 320, "w"),
        ("module", "Moduł", 90, "w"),
        ("status", "Status", 110, "center"),
        ("handled", "Obsłużono", 120, "center"),
        ("note", "Notatka decyzji", 220, "w"),
    ]
    for key, label, width, anchor in columns:
        tree.heading(key, text=label)
        tree.column(key, width=width, anchor=anchor, stretch=key in {"message", "note"})
    scroll = ttk.Scrollbar(op_box, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    for row in opinions:
        created = str(row.get("created_at") or "").replace("T", " ")[:16]
        handled = str(row.get("handled_at") or "").replace("T", " ")[:16]
        tree.insert(
            "",
            "end",
            values=(
                created or "—",
                row.get("message") or "—",
                row.get("module") or "—",
                feedback_service.status_label(str(row.get("status") or "nowa")),
                handled or "—",
                row.get("decision_note") or "—",
            ),
        )


def _build_employee_attendance(frame, login: str, *, on_saved: Callable[[], None] | None = None) -> None:
    _clear_frame(frame)
    outer = ttk.Frame(frame, padding=10)
    outer.pack(fill="both", expand=True)

    month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
    top = ttk.Frame(outer)
    top.pack(fill="x")
    ttk.Label(top, text="Miesiąc:").pack(side="left")
    month_box = ttk.Combobox(top, textvariable=month_var, values=_month_choices(), state="readonly", width=9)
    month_box.pack(side="left", padx=(5, 8))
    add_help_button(
        top,
        "Najpierw wybierz pozycję z listy Do potwierdzenia. Data i zmiana zostaną podstawione automatycznie, więc nie trzeba ich zgadywać.",
    ).pack(side="left")

    queue_box = ttk.LabelFrame(outer, text="Do potwierdzenia", padding=6)
    queue_box.pack(fill="x", pady=(8, 6))
    qtree = ttk.Treeview(
        queue_box,
        columns=("date", "slot", "login", "state"),
        show="headings",
        height=5,
    )
    for key, label, width, anchor in (
        ("date", "Data", 100, "center"),
        ("slot", "Zmiana", 90, "center"),
        ("login", "Pierwsze logowanie", 130, "center"),
        ("state", "Stan", 260, "w"),
    ):
        qtree.heading(key, text=label)
        qtree.column(key, width=width, anchor=anchor, stretch=key == "state")
    qtree.pack(fill="x")
    qmap: dict[str, dict] = {}

    selected_var = tk.StringVar(value="Wybierz pozycję z listy.")
    ttk.Label(outer, textvariable=selected_var).pack(anchor="w", pady=(4, 3))

    value_var = tk.StringVar(value="1")
    ot_var = tk.BooleanVar(value=False)
    hours_var = tk.StringVar(value="0")
    ot_type_var = tk.StringVar(value="zwykle")
    note_var = tk.StringVar(value="")
    current_case: dict[str, Any] = {}

    form = ttk.Frame(outer)
    form.pack(fill="x", pady=(0, 6))
    form.columnconfigure(1, weight=1)
    ttk.Label(form, text="Dniówka:").grid(row=0, column=0, sticky="w", pady=3)
    ttk.Combobox(form, textvariable=value_var, values=("0", "0.5", "1"), state="readonly", width=8).grid(
        row=0, column=1, sticky="w", pady=3
    )
    add_help_button(
        form,
        "Wartość dotyczy wyłącznie zaznaczonego dnia. Zapis 0 oznacza brak dniówki, 0,5 pół dniówki, a 1 pełną dniówkę.",
        row=0,
        column=2,
        padx=(6, 0),
    )

    ttk.Checkbutton(form, text="Nadgodziny", variable=ot_var).grid(row=1, column=0, sticky="w", pady=3)
    ot_wrap = ttk.Frame(form)
    ot_wrap.grid(row=1, column=1, sticky="w", pady=3)
    ttk.Entry(ot_wrap, textvariable=hours_var, width=7).pack(side="left")
    ttk.Label(ot_wrap, text=" h  ").pack(side="left")
    ttk.Combobox(
        ot_wrap,
        textvariable=ot_type_var,
        values=("zwykle", "sobota", "niedziela", "swieto"),
        state="readonly",
        width=12,
    ).pack(side="left")

    ttk.Label(form, text="Powód / uwaga:").grid(row=2, column=0, sticky="w", pady=3)
    ttk.Entry(form, textvariable=note_var).grid(row=2, column=1, sticky="ew", pady=3)
    add_help_button(
        form,
        "Powód jest wymagany przy ręcznej decyzji Brygadzisty. Trafia do Historii razem ze zmianą.",
        row=2,
        column=2,
        padx=(6, 0),
    )

    history_box = ttk.LabelFrame(outer, text="Historia miesiąca", padding=6)
    history_box.pack(fill="both", expand=True)
    history = ttk.Treeview(
        history_box,
        columns=("date", "slot", "login", "status", "day", "ot"),
        show="headings",
        height=7,
    )
    for key, label, width, anchor in (
        ("date", "Data", 95, "center"),
        ("slot", "Zmiana", 85, "center"),
        ("login", "Pierwsze logowanie", 120, "center"),
        ("status", "Status", 160, "w"),
        ("day", "Dniówka", 70, "center"),
        ("ot", "Nadgodziny", 95, "center"),
    ):
        history.heading(key, text=label)
        history.column(key, width=width, anchor=anchor, stretch=key == "status")
    history.pack(fill="both", expand=True)

    def apply_case(case: dict) -> None:
        current_case.clear()
        current_case.update(case)
        selected_var.set(
            f"{case.get('date')} • {case.get('slot')} • {case.get('decision_label') or _status_text(case)}"
        )
        value_var.set("0" if case.get("status") == attendance_service.STATUS_MISSING else "1")
        if case.get("status") == attendance_service.STATUS_SATURDAY:
            ot_var.set(True)
            hours_var.set("8")
            ot_type_var.set("sobota")
        else:
            ot_var.set(False)
            hours_var.set("0")
            ot_type_var.set("zwykle")
        note_var.set("")

    def select_case(_event=None) -> None:
        selected = qtree.selection()
        if selected and selected[0] in qmap:
            apply_case(qmap[selected[0]])

    qtree.bind("<<TreeviewSelect>>", select_case, add="+")
    qtree.bind("<Double-1>", select_case, add="+")

    def save_selected() -> None:
        if not current_case:
            messagebox.showinfo("Obecność", "Najpierw wybierz pozycję z listy Do potwierdzenia.", parent=frame.winfo_toplevel())
            return
        note = note_var.get().strip()
        if not note:
            messagebox.showinfo("Obecność", "Wpisz powód lub krótką uwagę.", parent=frame.winfo_toplevel())
            return
        try:
            status = str(current_case.get("status") or "")
            if status != attendance_service.STATUS_SATURDAY:
                attendance_service.set_manual_day(
                    str(current_case.get("date")),
                    str(current_case.get("slot")),
                    login,
                    float(value_var.get()),
                    _actor(frame),
                    note,
                )
            if ot_var.get():
                attendance_service.set_overtime(
                    str(current_case.get("date")),
                    str(current_case.get("slot")),
                    login,
                    float(hours_var.get()),
                    _actor(frame),
                    overtime_type=ot_type_var.get(),
                    day_value=1.0 if ot_type_var.get() == "sobota" else None,
                    note=note,
                )
        except Exception as exc:
            messagebox.showerror("Obecność", f"Nie udało się zapisać:\n{exc}", parent=frame.winfo_toplevel())
            return
        if callable(on_saved):
            try:
                on_saved()
            except Exception:
                pass
        refresh()

    buttons = ttk.Frame(outer)
    buttons.pack(fill="x", pady=(0, 8), before=history_box)
    ttk.Button(buttons, text="Zapisz decyzję", command=save_selected).pack(side="left")
    ttk.Button(
        buttons,
        text="Korekta ręczna",
        command=lambda: _manual_correction(frame, login, on_saved=refresh),
    ).pack(side="left", padx=(8, 0))
    add_help_button(
        buttons,
        "Korekta ręczna służy tylko do wyjątków, których nie ma na liście, np. gdy WM był wyłączony. Zwykłe braki logowania pojawiają się automatycznie w kolejce.",
    ).pack(side="left", padx=(6, 0))

    def refresh(_event=None) -> None:
        year, month = _month_tuple(month_var.get())
        qmap.clear()
        for iid in qtree.get_children():
            qtree.delete(iid)
        decisions = attendance_service.decision_records(login, year, month)
        for case in decisions:
            item = dict(case)
            item["login"] = login
            item["display_name"] = workforce_profile_service.display_name(
                workforce_profile_service.get_user(login) or {"login": login}
            )
            iid = qtree.insert(
                "",
                "end",
                values=(item.get("date"), item.get("slot"), _first_login(item), item.get("decision_label")),
            )
            qmap[iid] = item
        if not decisions:
            qtree.insert("", "end", values=("—", "—", "—", "Brak pozycji wymagających decyzji"))

        for iid in history.get_children():
            history.delete(iid)
        for row in attendance_service.month_records(login, year, month):
            ot = row.get("overtime")
            ot_text = "—"
            if isinstance(ot, dict) and ot.get("status") == "confirmed":
                ot_text = f"{_fmt(ot.get('hours'))} h"
            history.insert(
                "",
                "end",
                values=(
                    row.get("date"),
                    row.get("slot"),
                    _first_login(row),
                    _status_text(row),
                    _fmt(row.get("day_value")),
                    ot_text,
                ),
            )
        current_case.clear()
        selected_var.set("Wybierz pozycję z listy.")

    month_box.bind("<<ComboboxSelected>>", refresh, add="+")
    refresh()


def _postprocess_editor(owner, before_ids: set[int], login: str, *, editable: bool,
                        initial_tab: str = "", on_saved: Callable[[], None] | None = None) -> None:
    candidates = [win for win in _toplevels(owner) if id(win) not in before_ids]
    if not candidates:
        return
    win = candidates[-1]
    nb = _find_notebook(win)
    if nb is None:
        return
    if getattr(win, "_wm_profile_finalized", False):
        return
    setattr(win, "_wm_profile_finalized", True)

    attendance = _tab_frame(nb, "Obecność")
    if editable and attendance is not None:
        _build_employee_attendance(attendance, login, on_saved=on_saved)

    more = _tab_frame(nb, "Więcej")
    if more is not None:
        _build_more_tab(more, login, editable=editable)

    if initial_tab:
        target = _tab_frame(nb, initial_tab)
        if target is not None:
            try:
                nb.select(target)
            except Exception:
                pass


def _patch_employee_editors() -> None:
    try:
        import profile_foreman_edit_runtime as edit_runtime
    except Exception:
        return

    if not getattr(edit_runtime, "_wm_no_trim_audit", False):
        edit_runtime._audit = lambda **kwargs: _append_profile_audit(
            action=str(kwargs.get("action") or ""),
            actor=str(kwargs.get("actor") or ""),
            login=str(kwargs.get("login") or ""),
            before=kwargs.get("before"),
            after=kwargs.get("after"),
            note=str(kwargs.get("note") or ""),
        )
        edit_runtime._wm_no_trim_audit = True

    if not getattr(edit_runtime, "_wm_decision_editor_patched", False):
        original = edit_runtime.open_employee_editor

        def open_employee_editor(owner, login: str, initial_tab: str = "Dane", on_saved=None):
            before = {id(win) for win in _toplevels(owner)}
            result = original(owner, login, initial_tab=initial_tab, on_saved=on_saved)
            _postprocess_editor(
                owner,
                before,
                login,
                editable=True,
                initial_tab=initial_tab,
                on_saved=on_saved,
            )
            return result

        edit_runtime.open_employee_editor = open_employee_editor
        edit_runtime._wm_decision_editor_patched = True

    try:
        import profile_workforce_runtime as workforce_runtime
        if not getattr(workforce_runtime, "_wm_my_feedback_details_patched", False):
            original_details = workforce_runtime.open_employee_details

            def open_employee_details(owner, login: str):
                before = {id(win) for win in _toplevels(owner)}
                result = original_details(owner, login)
                _postprocess_editor(owner, before, login, editable=False)
                return result

            workforce_runtime.open_employee_details = open_employee_details
            workforce_runtime._wm_my_feedback_details_patched = True
    except Exception:
        pass


def _patch_foreman_panel() -> None:
    import gui_profile_foreman as foreman

    cls = foreman.ForemanProfilePanel
    cls._render_team = _render_ruch_wm
    cls._render_attendance = _render_attendance
    cls._render_feedback = _render_feedback

    if not getattr(cls, "_wm_profile_final_layout", False):
        original_build = cls._build

        def _build(self, *args, **kwargs):
            result = original_build(self, *args, **kwargs)
            notebook = getattr(self, "notebook", None)
            tabs = getattr(self, "_tabs", {})
            team_tab = tabs.get("Zespół") if isinstance(tabs, dict) else None
            if notebook is not None and team_tab is not None:
                try:
                    notebook.tab(team_tab, text="Ruch WM")
                except Exception:
                    pass

            order = ("Pulpit", "Zespół", "Obecność", "Urlopy", "Użytkownicy", "Opinie", "Statystyki")
            for index, key in enumerate(order):
                tab = tabs.get(key) if isinstance(tabs, dict) else None
                if tab is None:
                    continue
                try:
                    notebook.insert(index, tab)
                except Exception:
                    pass
            for hidden in ("Zadania", "Sprzęt", "Profile"):
                tab = tabs.get(hidden) if isinstance(tabs, dict) else None
                if tab is not None:
                    try:
                        notebook.hide(tab)
                    except Exception:
                        pass
            return result

        cls._build = _build
        cls._wm_profile_final_layout = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    try:
        _patch_my_attendance_card()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] my attendance patch failed: {exc!r}")
    try:
        _patch_employee_editors()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] final employee editor patch failed: {exc!r}")
    try:
        _patch_foreman_panel()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] final foreman layout patch failed: {exc!r}")
    _INSTALLED = True


__all__ = ["install"]
