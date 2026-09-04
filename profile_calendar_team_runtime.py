# version: 1.0
"""Rozszerza istniejący Kalendarz Profilu o tryb „Zespół” dla Brygadzisty.

Tryb „Mój” pozostaje bez zmian. Tryb „Zespół” pokazuje w kafelkach krótki
skrót i otwiera szczegóły dnia bez przeciążania głównego kalendarza.
"""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk
from typing import Any

from services import attendance_service, day_pay_service, workforce_profile_service
from ui_context_help import add_help_button

_INSTALLED = False


def _active_login() -> str:
    try:
        from services.profile_service import ProfileService
        return str(ProfileService.ensure_active_user_or_none() or "").strip()
    except Exception:
        return ""


def _is_foreman() -> bool:
    login = _active_login()
    return bool(login and workforce_profile_service.is_foreman(login))


def _slot_text(slot: str | None) -> str:
    return {"RANO": "06–14", "POPO": "14–22"}.get(str(slot or ""), "—")


def _leave_code(kind: Any) -> str:
    key = str(kind or "").strip().casefold()
    return {
        "urlop": "UR",
        "l4": "L4",
        "nn": "NN",
        "sila_wyzsza": "ŚW",
        "siła_wyższa": "ŚW",
        "force_majeure": "ŚW",
        "urlop_bezplatny": "UB",
        "urlop_bezpłatny": "UB",
        "unpaid": "UB",
    }.get(key, str(kind or "").strip().upper())


def _short_name(user: dict) -> str:
    first = str(user.get("imie") or "").strip()
    if first:
        return first
    shown = workforce_profile_service.display_name(user)
    return shown.split()[0] if shown else str(user.get("login") or "—")


def _team_day_rows(day: date) -> list[dict]:
    try:
        from services.leave_workflow_service import read_leaves, read_requests
        leaves = read_leaves()
        requests = read_requests()
    except Exception:
        leaves, requests = [], []

    day_text = day.isoformat()
    pending_by_login: set[str] = set()
    for request in requests:
        if str(request.get("status") or "").strip().casefold() != "pending":
            continue
        if day_text in {str(value)[:10] for value in (request.get("dates") or [])}:
            pending_by_login.add(str(request.get("login") or "").strip().casefold())

    leave_by_login: dict[str, dict] = {}
    for row in leaves:
        if str(row.get("date") or "")[:10] != day_text:
            continue
        login = str(row.get("login") or "").strip().casefold()
        if login:
            leave_by_login[login] = dict(row)

    out: list[dict] = []
    for user in workforce_profile_service.list_users(active_only=True):
        role = str(user.get("rola") or user.get("role") or "").strip().casefold()
        login = str(user.get("login") or "").strip()
        if not login or role == "guest":
            continue
        key = login.casefold()
        try:
            slot = attendance_service._planned_slot_for_day(login, day)
        except Exception:
            slot = None

        att_row = None
        try:
            for row in attendance_service.month_records(login, day.year, day.month):
                if str(row.get("date") or "")[:10] == day_text:
                    att_row = dict(row)
                    if str(row.get("slot") or "") == str(slot or ""):
                        break
        except Exception:
            pass

        leave = leave_by_login.get(key)
        status_code = ""
        status_text = ""
        pay_percent = None
        pay_label = "—"
        if leave:
            status_code = _leave_code(leave.get("type"))
            labels = {
                "UR": "Urlop",
                "L4": "L4",
                "NN": "NN",
                "ŚW": "Siła wyższa",
                "UB": "Urlop bezpłatny",
            }
            status_text = labels.get(status_code, status_code)
            pay_percent = leave.get("pay_percent")
            if pay_percent is None:
                pay_percent = day_pay_service.compensation(status_code).get("pay_percent")
        elif key in pending_by_login:
            status_code = "?UR"
            status_text = "Urlop — oczekuje"
        elif att_row:
            reason = str(att_row.get("reason") or "").strip()
            if reason:
                status_code = day_pay_service.normalize_code(reason)
                status_text = str(att_row.get("pay_label") or status_code)
                pay_percent = att_row.get("pay_percent")
            else:
                status = str(att_row.get("status") or "")
                if status == attendance_service.STATUS_PRESENT:
                    status_code = "PRACA"
                    status_text = "Obecność potwierdzona"
                    pay_percent = att_row.get("pay_percent", 100.0)
                elif status == attendance_service.STATUS_MISSING:
                    status_code = "BR"
                    status_text = "Brak logowania — decyzja"
                elif status in {attendance_service.STATUS_PENDING_LATE, attendance_service.STATUS_SATURDAY}:
                    status_code = "DEC"
                    status_text = "Do decyzji Brygadzisty"
                else:
                    status_code = "PLAN"
                    status_text = "Zaplanowana zmiana"
        elif slot:
            status_code = "PLAN"
            status_text = "Zaplanowana zmiana"
        else:
            status_code = "WOLNE"
            status_text = "Wolne"

        if pay_percent is not None:
            try:
                pay_label = f"{float(pay_percent):g}%"
            except Exception:
                pay_label = str(pay_percent)
        elif status_code in {"BR", "DEC", "?UR"}:
            pay_label = "do decyzji"

        summary_status = {
            "PRACA": _slot_text(slot or (att_row or {}).get("slot")),
            "PLAN": _slot_text(slot or (att_row or {}).get("slot")),
            "UR": "UR",
            "?UR": "?UR",
            "L4": "L4",
            "ŚW": "ŚW",
            "UB": "UB",
            "NN": "NN",
            "BR": "BR",
            "DEC": "DEC",
            "WOLNE": "wolne",
        }.get(status_code, status_code)

        out.append({
            "login": login,
            "name": workforce_profile_service.display_name(user),
            "short_name": _short_name(user),
            "slot": slot or str((att_row or {}).get("slot") or ""),
            "shift": _slot_text(slot or (att_row or {}).get("slot")),
            "status_code": status_code,
            "status": status_text,
            "summary": summary_status,
            "pay_percent": pay_percent,
            "pay_label": pay_label,
        })
    return out


def _open_day_details(panel, day_number: int) -> None:
    selected_day = date(panel.year, panel.month, int(day_number))
    rows = _team_day_rows(selected_day)
    win = tk.Toplevel(panel)
    win.title(f"Zespół — {selected_day.strftime('%d-%m-%Y')}")
    win.geometry("780x470")
    try:
        win.transient(panel.winfo_toplevel())
    except Exception:
        pass

    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    top = ttk.Frame(body)
    top.pack(fill="x", pady=(0, 8))
    ttk.Label(top, text=f"Zespół — {selected_day.strftime('%d-%m-%Y')}").pack(side="left")
    add_help_button(
        top,
        "Zmiana pochodzi z Grafiku. Status łączy Urlopy, L4, Siłę wyższą i Obecność; procent płatności jest tylko informacją źródłową pod przyszłe sugerowane wypłaty.",
    ).pack(side="left", padx=(6, 0))

    cols = ("name", "shift", "status", "pay")
    tree = ttk.Treeview(body, columns=cols, show="headings", height=14)
    for key, label, width in (
        ("name", "Pracownik", 210),
        ("shift", "Zmiana", 110),
        ("status", "Status", 280),
        ("pay", "Płatność", 100),
    ):
        tree.heading(key, text=label)
        tree.column(key, width=width, anchor="w" if key in {"name", "status"} else "center")
    tree.pack(fill="both", expand=True)
    tree.tag_configure("ok", foreground="#22c55e")
    tree.tag_configure("warn", foreground="#f59e0b")
    tree.tag_configure("bad", foreground="#ef4444")
    tree.tag_configure("muted", foreground="#A7A9AB")

    by_iid: dict[str, dict] = {}
    for row in rows:
        code = row["status_code"]
        tag = "bad" if code in {"BR", "NN"} else ("warn" if code in {"DEC", "?UR", "ŚW"} else ("muted" if code == "WOLNE" else "ok"))
        iid = tree.insert("", "end", values=(row["name"], row["shift"], row["status"], row["pay_label"]), tags=(tag,))
        by_iid[iid] = row

    def open_profile(_event=None) -> None:
        selected = tree.selection()
        if not selected:
            return
        row = by_iid.get(selected[0])
        if not row:
            return
        try:
            import profile_foreman_edit_runtime as edit_runtime
            tab = "Urlopy" if row["status_code"] in {"UR", "?UR", "L4", "ŚW", "UB", "NN"} else "Obecność"
            edit_runtime.open_employee_editor(panel, row["login"], initial_tab=tab, on_saved=panel.refresh)
        except Exception:
            pass

    tree.bind("<Double-1>", open_profile, add="+")
    bottom = ttk.Frame(body)
    bottom.pack(fill="x", pady=(8, 0))
    ttk.Button(bottom, text="Otwórz profil", command=open_profile).pack(side="left")
    ttk.Button(bottom, text="Zamknij", command=win.destroy).pack(side="right")


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    import gui_profile_calendar as calendar_ui

    cls = calendar_ui.ProfileCalendarPanel
    if getattr(cls, "_wm_team_calendar", False):
        _INSTALLED = True
        return

    original_build = cls._build
    original_render = cls._render_calendar

    def _build(self):
        original_build(self)
        if not _is_foreman():
            return
        self._wm_calendar_mode = tk.StringVar(value="Mój")
        body = getattr(self, "calendar_box", None)
        body = body.master if body is not None else None
        bar = ttk.Frame(self, style="WM.Container.TFrame")
        if body is not None:
            bar.pack(fill="x", padx=12, pady=(0, 6), before=body)
        else:
            bar.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Label(bar, text="Widok:", style="WM.Muted.TLabel").pack(side="left")

        def switch(mode: str) -> None:
            self._wm_calendar_mode.set(mode)
            self.selection_start = self.selection_end = None
            self._render_calendar()

        ttk.Radiobutton(bar, text="Mój", value="Mój", variable=self._wm_calendar_mode, command=lambda: switch("Mój")).pack(side="left", padx=(6, 0))
        ttk.Radiobutton(bar, text="Zespół", value="Zespół", variable=self._wm_calendar_mode, command=lambda: switch("Zespół")).pack(side="left", padx=(6, 0))
        add_help_button(
            bar,
            "Mój pokazuje Twój dotychczasowy kalendarz i wnioski. Zespół pokazuje skrót zmian i nieobecności wszystkich pracowników; kliknij dzień, aby zobaczyć pełne szczegóły.",
        ).pack(side="left", padx=(6, 0))
        ttk.Label(
            bar,
            text="Zespół: 06–14 / 14–22 / UR / ?UR / L4 / ŚW / BR / DEC",
            style="WM.Muted.TLabel",
        ).pack(side="left", padx=(14, 0))

    def _render_calendar(self):
        original_render(self)
        if not _is_foreman() or str(getattr(self, "_wm_calendar_mode", tk.StringVar(value="Mój")).get()) != "Zespół":
            return
        for child in self.calendar_box.winfo_children():
            if not isinstance(child, tk.Button):
                continue
            try:
                day_number = int(str(child.cget("text")).splitlines()[0])
            except Exception:
                continue
            selected_day = date(self.year, self.month, day_number)
            rows = _team_day_rows(selected_day)
            visible = [row for row in rows if row["status_code"] != "WOLNE"]
            shown = visible[:3]
            lines = [str(day_number)] + [f"{row['short_name']} {row['summary']}" for row in shown]
            if len(visible) > len(shown):
                lines.append(f"+{len(visible) - len(shown)} więcej")
            codes = {row["status_code"] for row in rows}
            bg = calendar_ui.WM_BAD if codes.intersection({"BR", "NN"}) else (calendar_ui.WM_WARN if codes.intersection({"DEC", "?UR", "ŚW"}) else calendar_ui.WM_BG_ELEV)
            child.configure(
                text="\n".join(lines),
                command=lambda d=day_number: _open_day_details(self, d),
                bg=bg,
                fg="#ffffff" if bg != calendar_ui.WM_BG_ELEV else calendar_ui.WM_TEXT,
                justify="left",
                anchor="nw",
                height=4,
                font=("Segoe UI", 9),
            )

    cls._build = _build
    cls._render_calendar = _render_calendar
    cls._wm_team_calendar = True
    _INSTALLED = True


__all__ = ["install"]
