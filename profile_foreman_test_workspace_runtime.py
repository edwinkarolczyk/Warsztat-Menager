# version: 1.0
"""Testowy scalony widok Brygadzisty oraz końcowe poprawki kliknięć Kalendarza.

Zakres jest celowo izolowany:
- nie usuwa istniejących kart Pulpit / Ruch WM / Obecność / Urlopy,
- dodaje wyłącznie kartę TESTOWA z jednym wierszem na pracownika,
- maksymalnie 4 pracowników trafia do jednego bloku; kolejni przechodzą niżej,
- dwuklik LPP otwiera istniejący edytor pracownika,
- kliknięcie dnia w Kalendarzu otwiera istniejące okno szczegółów dnia.
"""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any

from services import workforce_profile_service
from ui_context_help import add_help_button

_INSTALLED = False


def _key(value: Any) -> str:
    return str(value or "").strip().casefold()


def _days(value: Any) -> str:
    try:
        number = float(value or 0)
    except Exception:
        number = 0.0
    return str(int(number)) if number.is_integer() else f"{number:.1f}"


def _selected_tab_text(panel) -> str:
    notebook = getattr(panel, "notebook", None)
    if notebook is None:
        return ""
    try:
        return str(notebook.tab(notebook.select(), "text") or "")
    except Exception:
        return ""


def _open_employee(owner, login: str, *, initial_tab: str = "Obecność", on_saved=None) -> None:
    login = str(login or "").strip()
    if not login:
        return
    try:
        import profile_foreman_edit_runtime as edit_runtime

        edit_runtime.open_employee_editor(
            owner,
            login,
            initial_tab=initial_tab,
            on_saved=on_saved,
        )
    except Exception as exc:
        try:
            parent = owner.winfo_toplevel()
        except Exception:
            parent = None
        messagebox.showerror(
            "Profil",
            f"Nie udało się otworzyć profilu:\n{exc}",
            parent=parent,
        )


def _today_attendance_rows() -> dict[str, dict]:
    today = date.today()
    try:
        import profile_calendar_team_runtime as team_runtime
        import profile_foreman_workspace_runtime as workspace_runtime

        rows = team_runtime._team_day_rows(today)
    except Exception:
        return {}

    out: dict[str, dict] = {}
    for base in rows:
        if not isinstance(base, dict):
            continue
        try:
            row = workspace_runtime._team_detail_row(today, base)
        except Exception:
            row = dict(base)
        login = _key(row.get("login"))
        if login:
            out[login] = row
    return out


def _merged_test_rows(panel) -> list[dict]:
    snapshot_rows = [
        dict(row)
        for row in (getattr(panel, "snapshot", {}).get("team") or [])
        if isinstance(row, dict)
    ]
    attendance = _today_attendance_rows()
    merged: list[dict] = []
    seen: set[str] = set()

    for row in snapshot_rows:
        login = str(row.get("login") or "").strip()
        key = _key(login)
        if not key:
            continue
        seen.add(key)
        day_row = attendance.get(key, {})
        merged.append({
            "login": login,
            "name": str(row.get("name") or login),
            "shift": str(day_row.get("shift") or row.get("shift") or "—"),
            "presence": str(day_row.get("status") or row.get("status") or "—"),
            "status_code": str(day_row.get("status_code") or ""),
            "first": str(day_row.get("first_login") or "—"),
            "day": str(day_row.get("day_value") or "0"),
            "overtime": str(day_row.get("overtime") or "—"),
            "leave": _days(row.get("leave_remaining")),
            "open": int(row.get("open") or 0),
            "progress": int(row.get("in_progress") or 0),
            "urgent": int(row.get("urgent") or 0),
            "work": str(row.get("current_work") or "—"),
        })

    # Gdy snapshot chwilowo nie zawiera aktywnego pracownika, nie gub go z TESTOWEJ.
    for key, day_row in attendance.items():
        if key in seen:
            continue
        login = str(day_row.get("login") or key).strip()
        user = workforce_profile_service.get_user(login) or {"login": login}
        merged.append({
            "login": login,
            "name": workforce_profile_service.display_name(user) or login,
            "shift": str(day_row.get("shift") or "—"),
            "presence": str(day_row.get("status") or "—"),
            "status_code": str(day_row.get("status_code") or ""),
            "first": str(day_row.get("first_login") or "—"),
            "day": str(day_row.get("day_value") or "0"),
            "overtime": str(day_row.get("overtime") or "—"),
            "leave": "—",
            "open": 0,
            "progress": 0,
            "urgent": 0,
            "work": "—",
        })

    merged.sort(key=lambda item: (_key(item.get("name")), _key(item.get("login"))))
    return merged


def _row_tag(row: dict) -> str:
    code = str(row.get("status_code") or "").strip().upper()
    presence = _key(row.get("presence"))
    if code in {"BR", "NN"} or "brak logowania" in presence:
        return "bad"
    if code in {"DEC", "?UR", "ŚW"} or "decyz" in presence or "oczek" in presence:
        return "warn"
    if code == "WOLNE" or presence == "wolne":
        return "muted"
    return "ok"


def _render_test_workspace(panel) -> None:
    parent = getattr(panel, "_tabs", {}).get("TESTOWA")
    if parent is None:
        return

    try:
        panel._clear(parent)
    except Exception:
        for child in list(parent.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

    header = ttk.Frame(parent, style="WM.Container.TFrame")
    header.pack(fill="x", padx=8, pady=(8, 6))
    ttk.Label(
        header,
        text="TESTOWA — Pulpit + Ruch WM + Obecność + Urlopy",
        style="WM.H1.TLabel",
    ).pack(side="left")
    add_help_button(
        header,
        "To jest wyłącznie prototyp wspólnego widoku. Obecne zakładki nie są usuwane ani zmieniane; dwuklik LPP na pracowniku otwiera jego profil.",
    ).pack(side="left", padx=(6, 0))

    rows = _merged_test_rows(panel)
    summary = getattr(panel, "snapshot", {}).get("summary") or {}
    ttk.Label(
        parent,
        text=(
            f"Dzisiaj: {date.today().strftime('%d-%m-%Y')}  •  "
            f"Pracownicy: {len(rows)}  •  "
            f"Zadania otwarte: {summary.get('open_tasks', 0)}  •  "
            f"Pilne: {summary.get('urgent_tasks', 0)}"
        ),
        style="WM.Muted.TLabel",
    ).pack(anchor="w", padx=8, pady=(0, 6))

    columns = (
        ("login", "Login", 82, "w"),
        ("name", "Pracownik", 150, "w"),
        ("shift", "Zmiana", 92, "center"),
        ("presence", "Obecność", 180, "w"),
        ("first", "Wejście", 70, "center"),
        ("day", "Dn.", 45, "center"),
        ("overtime", "Nadgodz.", 105, "center"),
        ("leave", "Urlop", 58, "center"),
        ("open", "Otwarte", 62, "center"),
        ("progress", "W toku", 58, "center"),
        ("urgent", "Pilne", 48, "center"),
        ("work", "Aktualna praca", 220, "w"),
    )

    if not rows:
        ttk.Label(parent, text="Brak pracowników do pokazania.", style="WM.Muted.TLabel").pack(
            anchor="w", padx=8, pady=8
        )
        return

    for start in range(0, len(rows), 4):
        chunk = rows[start:start + 4]
        end = start + len(chunk)
        box = ttk.LabelFrame(
            parent,
            text=f"Pracownicy {start + 1}–{end}",
            style="WM.Section.TLabelframe",
            padding=6,
        )
        box.pack(fill="x", padx=8, pady=(0, 7))

        keys = [key for key, _label, _width, _anchor in columns]
        tree = ttk.Treeview(
            box,
            columns=keys,
            show="headings",
            style="Foreman.Treeview",
            height=max(1, len(chunk)),
        )
        for key, label, width, anchor in columns:
            tree.heading(key, text=label)
            tree.column(
                key,
                width=width,
                minwidth=max(40, width - 25),
                anchor=anchor,
                stretch=key in {"name", "presence", "work"},
            )
        tree.pack(fill="x", expand=True)
        tree.tag_configure("bad", foreground="#ef4444")
        tree.tag_configure("warn", foreground="#f59e0b")
        tree.tag_configure("ok", foreground="#22c55e")
        tree.tag_configure("muted", foreground="#A7A9AB")

        login_by_iid: dict[str, str] = {}
        for row in chunk:
            iid = tree.insert(
                "",
                "end",
                values=(
                    row["login"],
                    row["name"],
                    row["shift"],
                    row["presence"],
                    row["first"],
                    row["day"],
                    row["overtime"],
                    row["leave"],
                    row["open"],
                    row["progress"],
                    row["urgent"],
                    row["work"],
                ),
                tags=(_row_tag(row),),
            )
            login_by_iid[iid] = row["login"]

        def open_from_event(event, *, current_tree=tree, mapping=login_by_iid) -> None:
            iid = current_tree.identify_row(event.y)
            if not iid:
                selected = current_tree.selection()
                iid = selected[0] if selected else ""
            if not iid:
                return
            try:
                current_tree.selection_set(iid)
                current_tree.focus(iid)
            except Exception:
                pass
            login = mapping.get(iid, "")
            _open_employee(
                panel,
                login,
                initial_tab="Obecność",
                on_saved=getattr(panel, "refresh_data", None),
            )

        tree.bind("<Double-1>", open_from_event, add="+")

    ttk.Label(
        parent,
        text="Dwuklik LPP na pracowniku → profil pracownika. Każdy blok ma maksymalnie 4 osoby.",
        style="WM.Muted.TLabel",
    ).pack(anchor="w", padx=8, pady=(0, 8))


def _patch_foreman_test_tab() -> None:
    import gui_profile_foreman as foreman

    cls = foreman.ForemanProfilePanel
    if getattr(cls, "_wm_test_workspace_v1", False):
        return

    original_build = cls._build
    original_refresh = cls.refresh_data

    def build(self, *args, **kwargs):
        result = original_build(self, *args, **kwargs)
        notebook = getattr(self, "notebook", None)
        tabs = getattr(self, "_tabs", None)
        if notebook is None or not isinstance(tabs, dict):
            return result

        if "TESTOWA" not in tabs:
            frame = ttk.Frame(notebook, style="WM.Container.TFrame")
            admin = tabs.get("Administracja")
            try:
                if admin is not None:
                    notebook.insert(notebook.index(admin), frame, text="TESTOWA")
                else:
                    notebook.add(frame, text="TESTOWA")
            except Exception:
                notebook.add(frame, text="TESTOWA")
            tabs["TESTOWA"] = frame

        def on_tab(_event=None) -> None:
            if _selected_tab_text(self) == "TESTOWA":
                _render_test_workspace(self)

        notebook.bind("<<NotebookTabChanged>>", on_tab, add="+")
        self._wm_render_test_workspace = lambda: _render_test_workspace(self)
        return result

    def refresh_data(self, *args, **kwargs):
        result = original_refresh(self, *args, **kwargs)
        if _selected_tab_text(self) == "TESTOWA":
            _render_test_workspace(self)
        return result

    cls._build = build
    cls.refresh_data = refresh_data
    cls._wm_test_workspace_v1 = True


def _patch_calendar_interactions() -> None:
    import gui_profile_calendar as calendar_ui
    import profile_calendar_team_runtime as team_runtime

    cls = calendar_ui.ProfileCalendarPanel
    if getattr(cls, "_wm_calendar_click_fix_v1", False):
        return

    original_build = cls._build
    original_render = cls._render_calendar

    def build(self, *args, **kwargs):
        result = original_build(self, *args, **kwargs)
        if not team_runtime._is_foreman():
            return result

        tree = getattr(self, "_wm_team_detail_tree", None)
        if tree is None:
            return result

        def open_profile_from_event(event=None) -> None:
            iid = ""
            if event is not None:
                try:
                    iid = tree.identify_row(event.y)
                except Exception:
                    iid = ""
            if not iid:
                selected = tree.selection()
                iid = selected[0] if selected else ""
            if not iid:
                return
            try:
                tree.selection_set(iid)
                tree.focus(iid)
            except Exception:
                pass
            row = getattr(self, "_wm_team_detail_rows", {}).get(iid)
            if not isinstance(row, dict):
                return
            _open_employee(
                self,
                str(row.get("login") or ""),
                initial_tab="Obecność",
                on_saved=getattr(self, "refresh", None),
            )

        try:
            tree.unbind("<Double-1>")
        except Exception:
            pass
        tree.bind("<Double-1>", open_profile_from_event, add="+")
        return result

    def render(self, *args, **kwargs):
        result = original_render(self, *args, **kwargs)
        if not team_runtime._is_foreman():
            return result

        def open_day(day_number: int) -> None:
            try:
                self._wm_selected_team_day = date(self.year, self.month, int(day_number))
            except Exception:
                return
            # Zachowaj podświetlenie i panel pod kalendarzem, ale przywróć też
            # właściwe okno dnia, które zostało wcześniej nadpisane przez workspace.
            try:
                self._render_calendar()
            except Exception:
                pass
            team_runtime._open_day_details(self, int(day_number))

        calendar_box = getattr(self, "calendar_box", None)
        if calendar_box is None:
            return result
        for child in calendar_box.winfo_children():
            if not isinstance(child, tk.Button):
                continue
            try:
                day_number = int(str(child.cget("text") or "").splitlines()[0])
            except Exception:
                continue
            child.configure(command=lambda d=day_number: open_day(d))
        return result

    cls._build = build
    cls._render_calendar = render
    cls._wm_calendar_click_fix_v1 = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_foreman_test_tab()
    _patch_calendar_interactions()
    _INSTALLED = True


__all__ = ["install", "_render_test_workspace"]
