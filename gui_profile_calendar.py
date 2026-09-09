# version: 1.0
"""Kalendarz nieobecności dla Profilu oraz workflow akceptacji brygadzisty."""
from __future__ import annotations

import calendar as _calendar
import tkinter as tk
from datetime import date
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from logger import log_akcja
from services.leave_workflow_service import (
    add_l4,
    approve_request,
    calendar_snapshot,
    dates_from_range,
    read_requests,
    reject_request,
    request_vacation,
)
from services.profile_service import ProfileService, get_all_users

WM_BG = "#121415"
WM_BG_ELEV = "#1A1D1F"
WM_TEXT = "#E6E7E8"
WM_ACCENT = "#FF6B1A"
WM_OK = "#245b36"
WM_WARN = "#6b4f16"
WM_BAD = "#6b2525"
WM_L4 = "#294b72"


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def _display_name(user: dict) -> str:
    direct = str(user.get("display_name") or user.get("nazwa") or user.get("name") or "").strip()
    if direct:
        return direct
    full = " ".join(
        part
        for part in (
            str(user.get("imie") or "").strip(),
            str(user.get("nazwisko") or "").strip(),
        )
        if part
    )
    return full or str(user.get("login") or "").strip() or "—"


def _users() -> list[dict]:
    try:
        raw = get_all_users()
    except Exception:
        raw = []
    if isinstance(raw, dict):
        raw = raw.get("users") or raw.get("profiles") or list(raw.values())
    rows = [dict(row) for row in (raw or []) if isinstance(row, dict) and row.get("login")]
    rows.sort(key=lambda row: _display_name(row).casefold())
    return rows


def _status_label(value: Any) -> str:
    return {
        "pending": "Oczekuje",
        "approved": "Zaakceptowany",
        "rejected": "Odrzucony",
    }.get(_norm(value), str(value or "—"))


class ProfileCalendarPanel(ttk.Frame):
    """Miesięczny kalendarz jednego użytkownika z wnioskami urlopowymi."""

    def __init__(self, master, *, login: str, owner=None, **kwargs) -> None:
        super().__init__(master, style="WM.Container.TFrame", **kwargs)
        self.owner = owner
        self.login = str(login or "").strip()
        today = date.today()
        self.year = today.year
        self.month = today.month
        self.selection_start: date | None = None
        self.selection_end: date | None = None
        self._note_var = tk.StringVar(value="")
        self._selection_var = tk.StringVar(value="Kliknij pierwszy i ostatni dzień urlopu.")
        self._month_var = tk.StringVar(value="")
        self._build()
        self.refresh()
        try:
            self.winfo_toplevel().bind("<<LeavesUpdated>>", self._on_external_update, add="+")
        except Exception:
            pass

    def _build(self) -> None:
        head = ttk.Frame(self, style="WM.Container.TFrame")
        head.pack(fill="x", padx=12, pady=(10, 6))
        ttk.Label(head, text="KALENDARZ", style="WM.H1.TLabel").pack(side="left")
        nav = ttk.Frame(head, style="WM.Container.TFrame")
        nav.pack(side="right")
        ttk.Button(nav, text="‹", width=4, command=self._prev_month).pack(side="left")
        ttk.Label(nav, textvariable=self._month_var, style="WM.Muted.TLabel", width=18, anchor="center").pack(side="left", padx=6)
        ttk.Button(nav, text="›", width=4, command=self._next_month).pack(side="left")
        ttk.Button(nav, text="Dzisiaj", command=self._today).pack(side="left", padx=(8, 0))
        ttk.Button(nav, text="Odśwież", command=self.refresh).pack(side="left", padx=(6, 0))

        legend = ttk.Frame(self, style="WM.Container.TFrame")
        legend.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Label(
            legend,
            text="URL = urlop zaakceptowany   •   ? URL = wniosek oczekuje   •   L4 = zwolnienie   •   ODR = wniosek odrzucony",
            style="WM.Muted.TLabel",
        ).pack(anchor="w")

        body = ttk.Frame(self, style="WM.Container.TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        self.calendar_box = ttk.Frame(body, style="WM.Container.TFrame")
        self.calendar_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        side = ttk.Frame(body, style="WM.Card.TFrame", padding=12)
        side.grid(row=0, column=1, sticky="nsew")
        ttk.Label(side, text="WNIOSEK URLOPOWY", style="WM.CardLabel.TLabel").pack(anchor="w")
        ttk.Label(side, textvariable=self._selection_var, style="WM.CardMuted.TLabel", wraplength=360).pack(anchor="w", pady=(6, 10))
        ttk.Label(side, text="Uwagi:", style="WM.CardMuted.TLabel").pack(anchor="w")
        ttk.Entry(side, textvariable=self._note_var).pack(fill="x", pady=(4, 8))
        ttk.Button(side, text="Wyślij do akceptacji", command=self._submit_vacation).pack(anchor="w")
        ttk.Label(
            side,
            text="Urlop pojawi się w ewidencji dopiero po akceptacji brygadzisty.",
            style="WM.CardMuted.TLabel",
            wraplength=360,
        ).pack(anchor="w", pady=(8, 14))

        ttk.Separator(side, orient="horizontal").pack(fill="x", pady=(0, 10))
        ttk.Label(side, text="MOJE WNIOSKI", style="WM.CardLabel.TLabel").pack(anchor="w", pady=(0, 6))
        cols = ("range", "days", "status")
        self.requests_tree = ttk.Treeview(side, columns=cols, show="headings", height=10)
        self.requests_tree.heading("range", text="Termin")
        self.requests_tree.heading("days", text="Dni")
        self.requests_tree.heading("status", text="Status")
        self.requests_tree.column("range", width=150, anchor="w")
        self.requests_tree.column("days", width=45, anchor="center")
        self.requests_tree.column("status", width=110, anchor="center")
        self.requests_tree.pack(fill="both", expand=True)

    def _on_external_update(self, _event=None) -> None:
        try:
            if self.winfo_exists():
                self.after_idle(self.refresh)
        except Exception:
            pass

    def _prev_month(self) -> None:
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self.selection_start = self.selection_end = None
        self.refresh()

    def _next_month(self) -> None:
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self.selection_start = self.selection_end = None
        self.refresh()

    def _today(self) -> None:
        today = date.today()
        self.year, self.month = today.year, today.month
        self.selection_start = self.selection_end = None
        self.refresh()

    def _selected_dates(self) -> list[str]:
        if self.selection_start is None or self.selection_end is None:
            return []
        return dates_from_range(self.selection_start, self.selection_end)

    def _select_day(self, day: int) -> None:
        clicked = date(self.year, self.month, day)
        if self.selection_start is None:
            self.selection_start = self.selection_end = clicked
        elif self.selection_start == self.selection_end:
            if clicked < self.selection_start:
                self.selection_start = clicked
            else:
                self.selection_end = clicked
        else:
            self.selection_start = self.selection_end = clicked
        self._update_selection_text()
        self._render_calendar()

    def _update_selection_text(self) -> None:
        if self.selection_start is None or self.selection_end is None:
            self._selection_var.set("Kliknij pierwszy i ostatni dzień urlopu.")
            return
        try:
            selected = self._selected_dates()
        except Exception as exc:
            self._selection_var.set(str(exc))
            return
        first = self.selection_start.strftime("%d-%m-%Y")
        last = self.selection_end.strftime("%d-%m-%Y")
        if first == last:
            self._selection_var.set(f"{first}   •   dni urlopowe: {len(selected)}")
        else:
            self._selection_var.set(f"{first} → {last}   •   dni urlopowe: {len(selected)}")

    def _day_marks(self, snapshot: dict) -> dict[str, dict[str, str]]:
        marks: dict[str, dict[str, str]] = {}
        for row in snapshot.get("leaves") or []:
            day = str(row.get("date") or "")[:10]
            kind = _norm(row.get("type"))
            if kind == "urlop":
                marks[day] = {"label": "URL", "bg": WM_OK}
            elif kind == "l4":
                marks[day] = {"label": "L4", "bg": WM_L4}
            elif kind == "nn":
                marks[day] = {"label": "NN", "bg": WM_BAD}
            else:
                marks[day] = {"label": str(row.get("type") or "N").upper()[:4], "bg": WM_BAD}
        for request in snapshot.get("requests") or []:
            status = _norm(request.get("status"))
            if status == "approved":
                continue
            label = "? URL" if status == "pending" else "ODR"
            bg = WM_WARN if status == "pending" else WM_BAD
            for day in request.get("dates") or []:
                text = str(day)
                if text not in marks:
                    marks[text] = {"label": label, "bg": bg}
        return marks

    def _render_calendar(self) -> None:
        for child in self.calendar_box.winfo_children():
            child.destroy()
        month_names = (
            "",
            "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
            "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień",
        )
        self._month_var.set(f"{month_names[self.month]} {self.year}")
        snapshot = getattr(self, "_snapshot", {"leaves": [], "requests": []})
        marks = self._day_marks(snapshot)

        for col, label in enumerate(("Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nie")):
            self.calendar_box.columnconfigure(col, weight=1, uniform="cal")
            ttk.Label(self.calendar_box, text=label, style="WM.Muted.TLabel", anchor="center").grid(
                row=0, column=col, sticky="ew", padx=2, pady=(0, 4)
            )

        weeks = _calendar.Calendar(firstweekday=0).monthdayscalendar(self.year, self.month)
        today = date.today()
        for row_idx, week in enumerate(weeks, start=1):
            self.calendar_box.rowconfigure(row_idx, weight=1, uniform="calrow")
            for col, day in enumerate(week):
                if not day:
                    tk.Frame(self.calendar_box, bg=WM_BG).grid(row=row_idx, column=col, sticky="nsew", padx=2, pady=2)
                    continue
                current = date(self.year, self.month, day)
                key = current.isoformat()
                mark = marks.get(key)
                selected = (
                    self.selection_start is not None
                    and self.selection_end is not None
                    and min(self.selection_start, self.selection_end) <= current <= max(self.selection_start, self.selection_end)
                )
                bg = WM_ACCENT if selected else (mark["bg"] if mark else WM_BG_ELEV)
                fg = "#ffffff" if selected or mark else WM_TEXT
                text = str(day)
                if mark:
                    text += f"\n{mark['label']}"
                elif current == today:
                    text += "\nDZIŚ"
                btn = tk.Button(
                    self.calendar_box,
                    text=text,
                    command=lambda d=day: self._select_day(d),
                    bg=bg,
                    fg=fg,
                    activebackground=WM_ACCENT,
                    activeforeground="#ffffff",
                    relief="flat",
                    bd=0,
                    font=("Segoe UI", 10, "bold" if mark or current == today else "normal"),
                    justify="center",
                    height=3,
                )
                btn.grid(row=row_idx, column=col, sticky="nsew", padx=2, pady=2)

    def _render_requests(self) -> None:
        tree = self.requests_tree
        tree.delete(*tree.get_children())
        rows = read_requests(login=self.login)
        for row in rows[:50]:
            start = str(row.get("date_start") or "—")
            end = str(row.get("date_end") or start)
            period = start if start == end else f"{start} → {end}"
            tree.insert(
                "",
                "end",
                values=(period, int(float(row.get("quantity_days") or 0)), _status_label(row.get("status"))),
            )

    def _submit_vacation(self) -> None:
        try:
            days = self._selected_dates()
        except Exception as exc:
            messagebox.showerror("Urlop", str(exc), parent=self.winfo_toplevel())
            return
        if not days:
            messagebox.showinfo("Urlop", "Zaznacz co najmniej jeden dzień roboczy.", parent=self.winfo_toplevel())
            return
        if not messagebox.askyesno(
            "Wniosek urlopowy",
            f"Wysłać wniosek o {len(days)} dni urlopu do akceptacji brygadzisty?",
            parent=self.winfo_toplevel(),
        ):
            return
        try:
            request_vacation(self.login, days, self._note_var.get())
        except Exception as exc:
            messagebox.showerror("Urlop", f"Nie udało się wysłać wniosku:\n{exc}", parent=self.winfo_toplevel())
            return
        self._note_var.set("")
        self.selection_start = self.selection_end = None
        self.refresh()
        self._emit_update()
        messagebox.showinfo("Urlop", "Wniosek został wysłany do brygadzisty.", parent=self.winfo_toplevel())

    def _emit_update(self) -> None:
        try:
            self.winfo_toplevel().event_generate("<<LeavesUpdated>>", when="tail")
        except Exception:
            pass

    def refresh(self) -> None:
        try:
            self._snapshot = calendar_snapshot(self.login, self.year, self.month)
        except Exception as exc:
            log_akcja(f"[WM-ERR][PROFILE_CAL] Błąd wczytania kalendarza: {exc}")
            self._snapshot = {"leaves": [], "requests": []}
        self._update_selection_text()
        self._render_calendar()
        try:
            self._render_requests()
        except Exception as exc:
            log_akcja(f"[WM-ERR][PROFILE_CAL] Błąd listy wniosków: {exc}")


def _actor_login(panel) -> str:
    try:
        active = str(ProfileService.ensure_active_user_or_none() or "").strip()
    except Exception:
        active = ""
    return active or str(getattr(getattr(panel, "owner", None), "login", "") or "").strip()


def _emit_leaves_update(panel) -> None:
    try:
        panel.winfo_toplevel().event_generate("<<LeavesUpdated>>", when="tail")
    except Exception:
        pass


def _open_requests_dialog(panel) -> None:
    win = tk.Toplevel(panel)
    win.title("Wnioski urlopowe")
    try:
        win.transient(panel.winfo_toplevel())
    except Exception:
        pass
    win.geometry("900x480")

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)
    cols = ("worker", "from", "to", "days", "note")
    tree = ttk.Treeview(frame, columns=cols, show="headings")
    for key, label, width in (
        ("worker", "Pracownik", 190),
        ("from", "Od", 105),
        ("to", "Do", 105),
        ("days", "Dni", 55),
        ("note", "Uwagi", 340),
    ):
        tree.heading(key, text=label)
        tree.column(key, width=width, anchor="center" if key in {"from", "to", "days"} else "w")
    tree.pack(fill="both", expand=True)

    users = {_norm(row.get("login")): _display_name(row) for row in _users()}
    requests_by_iid: dict[str, dict] = {}

    def reload_rows() -> None:
        tree.delete(*tree.get_children())
        requests_by_iid.clear()
        for request in read_requests(status="pending"):
            login = str(request.get("login") or "")
            iid = tree.insert(
                "",
                "end",
                values=(
                    users.get(_norm(login), login),
                    request.get("date_start"),
                    request.get("date_end"),
                    int(float(request.get("quantity_days") or 0)),
                    request.get("note") or "",
                ),
            )
            requests_by_iid[iid] = request

    def selected() -> dict | None:
        items = tree.selection()
        if not items:
            messagebox.showinfo("Wnioski", "Wybierz wniosek z listy.", parent=win)
            return None
        return requests_by_iid.get(items[0])

    def approve() -> None:
        request = selected()
        if not request:
            return
        if not messagebox.askyesno(
            "Akceptacja urlopu",
            f"Zaakceptować urlop dla {users.get(_norm(request.get('login')), request.get('login'))}?",
            parent=win,
        ):
            return
        try:
            approve_request(str(request.get("id")), _actor_login(panel))
        except Exception as exc:
            messagebox.showerror("Wnioski", f"Nie udało się zaakceptować:\n{exc}", parent=win)
            return
        reload_rows()
        panel.refresh_data()
        _emit_leaves_update(panel)

    def reject() -> None:
        request = selected()
        if not request:
            return
        reason = simpledialog.askstring("Odrzuć urlop", "Powód (opcjonalnie):", parent=win)
        if reason is None:
            return
        try:
            reject_request(str(request.get("id")), _actor_login(panel), reason)
        except Exception as exc:
            messagebox.showerror("Wnioski", f"Nie udało się odrzucić:\n{exc}", parent=win)
            return
        reload_rows()
        panel.refresh_data()
        _emit_leaves_update(panel)

    actions = ttk.Frame(frame)
    actions.pack(fill="x", pady=(10, 0))
    ttk.Button(actions, text="Zaakceptuj", command=approve).pack(side="left")
    ttk.Button(actions, text="Odrzuć", command=reject).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Zamknij", command=win.destroy).pack(side="right")
    reload_rows()


def _open_l4_dialog(panel) -> None:
    win = tk.Toplevel(panel)
    win.title("Dodaj L4")
    try:
        win.transient(panel.winfo_toplevel())
        win.grab_set()
    except Exception:
        pass

    frame = ttk.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)
    users = _users()
    labels: list[str] = []
    login_by_label: dict[str, str] = {}
    for user in users:
        login = str(user.get("login") or "").strip()
        label = f"{_display_name(user)} (@{login})"
        labels.append(label)
        login_by_label[label] = login

    worker_var = tk.StringVar(value=labels[0] if labels else "")
    start_var = tk.StringVar(value=date.today().isoformat())
    end_var = tk.StringVar(value=date.today().isoformat())
    note_var = tk.StringVar(value="")

    ttk.Label(frame, text="Pracownik:").grid(row=0, column=0, sticky="w", pady=4)
    ttk.Combobox(frame, textvariable=worker_var, values=labels, state="readonly", width=34).grid(row=0, column=1, sticky="ew", pady=4)
    ttk.Label(frame, text="Od (RRRR-MM-DD):").grid(row=1, column=0, sticky="w", pady=4)
    ttk.Entry(frame, textvariable=start_var).grid(row=1, column=1, sticky="ew", pady=4)
    ttk.Label(frame, text="Do (RRRR-MM-DD):").grid(row=2, column=0, sticky="w", pady=4)
    ttk.Entry(frame, textvariable=end_var).grid(row=2, column=1, sticky="ew", pady=4)
    ttk.Label(frame, text="Uwagi:").grid(row=3, column=0, sticky="w", pady=4)
    ttk.Entry(frame, textvariable=note_var).grid(row=3, column=1, sticky="ew", pady=4)
    frame.columnconfigure(1, weight=1)

    def save() -> None:
        login = login_by_label.get(worker_var.get(), "")
        try:
            days = dates_from_range(start_var.get(), end_var.get(), include_sundays=True)
            added = add_l4(login, days, _actor_login(panel), note_var.get())
        except Exception as exc:
            messagebox.showerror("L4", f"Nie udało się dodać L4:\n{exc}", parent=win)
            return
        messagebox.showinfo("L4", f"Dodano L4: {added} dni kalendarzowych.", parent=win)
        win.destroy()
        panel.refresh_data()
        _emit_leaves_update(panel)

    actions = ttk.Frame(frame)
    actions.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(actions, text="Anuluj", command=win.destroy).pack(side="right")
    ttk.Button(actions, text="Dodaj L4", command=save).pack(side="right", padx=(0, 8))


def install_foreman_leave_workflow(panel_cls) -> None:
    """Dołóż obsługę wniosków i L4 do istniejącej karty Urlopy brygadzisty."""
    if getattr(panel_cls, "_wm_leave_workflow_installed", False):
        return
    original = panel_cls._render_leaves

    def _render_leaves_with_workflow(self) -> None:
        original(self)
        parent = self._tabs.get("Urlopy")
        if parent is None:
            return
        try:
            pending = len(read_requests(status="pending"))
        except Exception:
            pending = 0
        toolbar = ttk.Frame(parent, style="WM.Container.TFrame")
        children = parent.winfo_children()
        pack_args = {"fill": "x", "padx": 8, "pady": (8, 2)}
        if children:
            pack_args["before"] = children[0]
        toolbar.pack(**pack_args)
        ttk.Label(
            toolbar,
            text=f"Wnioski oczekujące: {pending}",
            style="WM.Muted.TLabel",
        ).pack(side="left")
        ttk.Button(
            toolbar,
            text=f"Wnioski urlopowe ({pending})",
            command=lambda: _open_requests_dialog(self),
        ).pack(side="right")
        ttk.Button(
            toolbar,
            text="Dodaj L4",
            command=lambda: _open_l4_dialog(self),
        ).pack(side="right", padx=(0, 8))

    panel_cls._render_leaves = _render_leaves_with_workflow
    panel_cls._wm_leave_workflow_installed = True
    log_akcja("[WM-DBG][FOREMAN] Workflow urlopów/L4 aktywny.")


__all__ = ["ProfileCalendarPanel", "install_foreman_leave_workflow"]
