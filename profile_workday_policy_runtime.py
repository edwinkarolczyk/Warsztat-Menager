# version: 1.1
"""Spina Profil -> Grafik -> Obecność dla skonfigurowanych dni pracy.

Zasady:
- dzień wyłączony w ``workdays`` jest dniem wolnym i nie tworzy BR/PLAN,
- L4/urlopy mogą nadal obejmować dzień wolny,
- rzeczywista praca w dniu wolnym wymaga jawnego zaznaczenia w edytorze,
- jawny wyjątek zapisuje znacznik ``offday_work`` w rekordzie Obecności,
- końcowa tabela Obecności pokazuje dzień tygodnia,
- Kalendarz Brygadzisty pokazuje kompaktowy zespół pod kalendarzem (maks. 6 wierszy).
"""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk
from typing import Any

from services import attendance_service, leave_workflow_service, workforce_profile_service
from ui_context_help import add_help_button

_INSTALLED = False
_ACTIVE_OVERRIDE: dict[str, bool] = {}
_LEAVE_CODES = {"L4", "NN", "UR", "UŻ", "UB"}
_CALENDAR_LEAVE_CODES = {"UR", "?UR", "L4", "ŚW", "UB", "NN"}
_WEEKDAYS = ("Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nie")


def _key(value: Any) -> str:
    return str(value or "").strip().casefold()


def _weekday_label(day_text: Any) -> str:
    try:
        return _WEEKDAYS[date.fromisoformat(str(day_text or "")[:10]).weekday()]
    except Exception:
        return "—"


def _work_payload(payload: dict[str, Any]) -> bool:
    """Czy zapis reprezentuje pracę, a nie samą nieobecność obejmującą dzień wolny."""
    absence = str(payload.get("absence") or "").strip().upper()
    try:
        day_value = float(payload.get("day_value") or 0.0)
    except Exception:
        day_value = 0.0
    try:
        overtime = float(payload.get("overtime_hours") or 0.0)
    except Exception:
        overtime = 0.0
    first_login = str(payload.get("first_login") or "").strip()

    if absence in _LEAVE_CODES and day_value == 0.0 and overtime == 0.0 and not first_login:
        return False
    return True


def _is_offday(login: str, day_text: str) -> bool:
    user = workforce_profile_service.get_user(login)
    if not user:
        raise ValueError("Nie znaleziono profilu pracownika.")
    return not workforce_profile_service.is_workday(user, day_text)


def _ensure_allowed(login: str, payload: dict[str, Any], *, allow_offday: bool) -> bool:
    """Waliduj zapis i zwróć True, gdy to jawna praca w dniu wolnym."""
    day_text = str(payload.get("date") or "")[:10]
    offday = _is_offday(login, day_text)
    if not offday:
        return False
    if not _work_payload(payload):
        return False
    if not allow_offday:
        raise ValueError(
            "Ten dzień jest wyłączony w Profil -> Grafik -> Dni pracy. "
            "Jeśli pracownik faktycznie pracował w dniu wolnym, zaznacz 'Praca w dniu wolnym'."
        )
    return True


def _set_offday_marker(
    login: str,
    day_text: str,
    slot: str,
    *,
    enabled: bool,
    actor: str,
    note: str,
) -> None:
    """Zapisz/usuń jawny znacznik pracy poza zwykłym grafikiem."""
    login_n = _key(login)
    doc, _slot_map, rec = attendance_service._record(day_text, slot, login_n, create=False)
    if not isinstance(rec, dict):
        return
    before = dict(rec)
    if enabled:
        rec["offday_work"] = True
        rec["offday_work_actor"] = str(actor or "")
        rec["offday_work_ts"] = attendance_service._now_iso()
    else:
        rec.pop("offday_work", None)
        rec.pop("offday_work_actor", None)
        rec.pop("offday_work_ts", None)
    if before == rec:
        return
    attendance_service._write(attendance_service.data_path(), doc)
    attendance_service._audit(
        action="offday_work" if enabled else "offday_work_clear",
        login=login_n,
        date_ymd=day_text,
        slot=slot,
        actor=actor,
        before=before,
        after=dict(rec),
        note=note or ("Praca w dniu wolnym" if enabled else "Usunięto wyjątek dnia wolnego"),
    )


def _find_editor(frame) -> ttk.LabelFrame | None:
    stack = list(frame.winfo_children())
    while stack:
        widget = stack.pop(0)
        if isinstance(widget, ttk.LabelFrame):
            try:
                if str(widget.cget("text")) == "Edycja zaznaczonego dnia":
                    return widget
            except Exception:
                pass
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass
    return None


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


def _record_offday_flag(login: str, day_text: str, slot: str) -> bool:
    if not day_text:
        return False
    try:
        parsed = date.fromisoformat(day_text[:10])
        for row in attendance_service.month_records(login, parsed.year, parsed.month):
            if str(row.get("date") or "")[:10] != parsed.isoformat():
                continue
            if str(row.get("slot") or "") != str(slot or ""):
                continue
            return bool(row.get("offday_work"))
    except Exception:
        pass
    return False


def _install_weekday_column(tree: ttk.Treeview) -> None:
    """Dodaj kolumnę dnia tygodnia także do kolejnych odświeżeń tabeli."""
    if getattr(tree, "_wm_weekday_column_v1", False):
        return
    old_columns = list(tree.cget("columns") or ())
    if "date" not in old_columns or "weekday" in old_columns:
        return

    date_idx = old_columns.index("date")
    new_columns = list(old_columns)
    new_columns.insert(date_idx + 1, "weekday")
    tree.configure(columns=new_columns, displaycolumns=new_columns)
    tree.heading("weekday", text="Dzień")
    tree.column("weekday", width=58, minwidth=48, anchor="center", stretch=False)

    def with_weekday(values):
        data = list(values or ())
        if len(data) == len(new_columns):
            return tuple(data)
        if len(data) != len(old_columns):
            return tuple(data)
        data.insert(date_idx + 1, _weekday_label(data[date_idx]))
        return tuple(data)

    for iid in tree.get_children(""):
        try:
            tree.item(iid, values=with_weekday(tree.item(iid, "values") or ()))
        except Exception:
            pass

    original_insert = tree.insert

    def insert_with_weekday(parent, index, iid=None, **kw):
        if "values" in kw:
            kw["values"] = with_weekday(kw.get("values"))
        return original_insert(parent, index, iid=iid, **kw)

    tree.insert = insert_with_weekday
    tree._wm_weekday_column_v1 = True


def _decorate_attendance(frame, login: str) -> None:
    """Dodaj jawny przełącznik wyjątku i dzień tygodnia bez kolejnego okna."""
    if getattr(frame, "_wm_workday_policy_ui_v1", False):
        return
    editor = _find_editor(frame)
    if editor is None:
        return

    buttons = [widget for widget in _walk(editor) if isinstance(widget, ttk.Button)]
    save_button = next((w for w in buttons if str(w.cget("text")) == "Zapisz wszystko"), None)
    new_button = next((w for w in buttons if str(w.cget("text")) == "Nowy dzień"), None)
    if save_button is None:
        return

    actions = save_button.master
    offday_var = tk.BooleanVar(value=False)
    check = ttk.Checkbutton(actions, text="Praca w dniu wolnym", variable=offday_var)
    check.pack(side="left", padx=(6, 0))
    add_help_button(
        actions,
        "Zaznacz tylko wtedy, gdy pracownik faktycznie pracował w dniu wyłączonym w Grafik -> Dni pracy. "
        "Bez tego WM traktuje taki dzień jako Wolne i nie pozwala dopisać zwykłej dniówki.",
    ).pack(side="left", padx=(4, 0))

    original_save_command = str(save_button.cget("command") or "")
    if original_save_command:
        def save_with_policy() -> None:
            key = _key(login)
            _ACTIVE_OVERRIDE[key] = bool(offday_var.get())
            try:
                save_button.tk.call(original_save_command)
            finally:
                _ACTIVE_OVERRIDE.pop(key, None)

        save_button.configure(command=save_with_policy)

    if new_button is not None:
        original_new_command = str(new_button.cget("command") or "")
        if original_new_command:
            def new_with_reset() -> None:
                offday_var.set(False)
                new_button.tk.call(original_new_command)

            new_button.configure(command=new_with_reset)

    tree = next(
        (
            widget for widget in _walk(frame)
            if isinstance(widget, ttk.Treeview)
            and {"date", "slot"}.issubset(set(widget.cget("columns") or ()))
        ),
        None,
    )
    if tree is not None:
        _install_weekday_column(tree)

        def sync_from_selection(_event=None) -> None:
            selected = tree.selection()
            if not selected:
                offday_var.set(False)
                return
            try:
                values = tree.item(selected[0], "values") or ()
                columns = list(tree.cget("columns") or ())
                day_text = str(values[columns.index("date")]) if "date" in columns else ""
                slot = str(values[columns.index("slot")]) if "slot" in columns else ""
                offday_var.set(_record_offday_flag(login, day_text, slot))
            except Exception:
                offday_var.set(False)

        tree.bind("<<TreeviewSelect>>", sync_from_selection, add="+")

    frame._wm_workday_policy_ui_v1 = True


def _install_workspace_policy() -> None:
    import profile_attendance_finalize_runtime as attendance_final
    import profile_foreman_workspace_runtime as workspace

    if getattr(workspace, "_wm_workday_policy_v1", False):
        return

    original_save = workspace._save_attendance_edit
    original_build = workspace._build_employee_attendance
    original_detail = workspace._team_detail_row

    def save_attendance_edit(
        login: str,
        payload: dict[str, Any],
        *,
        source_slot: str,
        original_first_login: str,
        actor: str,
        note: str,
    ) -> None:
        allow_offday = bool(_ACTIVE_OVERRIDE.get(_key(login), False))
        explicit_offday = _ensure_allowed(login, payload, allow_offday=allow_offday)

        attendance_before = attendance_service._read(attendance_service.data_path(), {})
        audit_before = attendance_service._read(attendance_service.audit_path(), [])
        leaves_before = leave_workflow_service._read_all_leaves()
        try:
            original_save(
                login,
                payload,
                source_slot=source_slot,
                original_first_login=original_first_login,
                actor=actor,
                note=note,
            )
            _set_offday_marker(
                login,
                str(payload.get("date") or "")[:10],
                str(payload.get("slot") or ""),
                enabled=explicit_offday,
                actor=actor,
                note=note,
            )
        except Exception:
            try:
                leave_workflow_service._write_json(leave_workflow_service.leaves_path(), leaves_before)
            finally:
                attendance_service._write(attendance_service.data_path(), attendance_before)
                attendance_service._write(attendance_service.audit_path(), audit_before)
            raise

    def build_employee_attendance(frame, login: str, *, on_saved=None) -> None:
        original_build(frame, login, on_saved=on_saved)
        _decorate_attendance(frame, login)

    def team_detail_row(day_obj: date, row: dict) -> dict:
        item = original_detail(day_obj, row)
        if str(row.get("status_code") or "") == "WOLNE":
            item["first_login"] = "—"
            item["day_value"] = "0"
            item["overtime"] = "—"
        return item

    workspace._save_attendance_edit = save_attendance_edit
    workspace._build_employee_attendance = build_employee_attendance
    workspace._team_detail_row = team_detail_row
    attendance_final._build_employee_attendance = build_employee_attendance
    workspace._wm_workday_policy_v1 = True


def _install_calendar_policy() -> None:
    import profile_calendar_team_runtime as calendar_runtime

    if getattr(calendar_runtime, "_wm_workday_policy_v1", False):
        return

    original_planned = calendar_runtime._planned_slot_from_user
    original_rows = calendar_runtime._team_day_rows_from_snapshots

    def planned_slot(user: dict, day_obj: date, shifts_cfg: dict) -> str | None:
        if not workforce_profile_service.is_workday(user, day_obj):
            return None
        return original_planned(user, day_obj, shifts_cfg)

    def day_rows(
        day_obj: date,
        users: list[dict],
        shifts_cfg: dict,
        attendance_doc: dict,
        leaves: list[dict],
        requests: list[dict],
        *,
        now=None,
    ) -> list[dict]:
        rows = original_rows(
            day_obj,
            users,
            shifts_cfg,
            attendance_doc,
            leaves,
            requests,
            now=now,
        )
        users_by_login = {_key(user.get("login")): user for user in users if isinstance(user, dict)}
        for row in rows:
            user = users_by_login.get(_key(row.get("login")))
            if not user or workforce_profile_service.is_workday(user, day_obj):
                continue
            code = str(row.get("status_code") or "")
            if code in _CALENDAR_LEAVE_CODES:
                continue
            attendance = row.get("_attendance_row") if isinstance(row.get("_attendance_row"), dict) else {}
            if attendance.get("offday_work"):
                row["offday_work"] = True
                if code == "PRACA":
                    row["status"] = "Praca w dniu wolnym — obecność"
                elif code in {"DEC", "BR"}:
                    row["status"] = "Praca w dniu wolnym — do decyzji"
                continue
            row.update(
                {
                    "slot": "",
                    "shift": "—",
                    "status_code": "WOLNE",
                    "status": "Wolne",
                    "summary": "wolne",
                    "pay_percent": None,
                    "pay_label": "—",
                }
            )
        return rows

    calendar_runtime._planned_slot_from_user = planned_slot
    calendar_runtime._team_day_rows_from_snapshots = day_rows
    calendar_runtime._wm_workday_policy_v1 = True


def _install_calendar_layout() -> None:
    """Poszerz kalendarz i umieść kompaktową listę zespołu pod nim."""
    import gui_profile_calendar as calendar_ui

    cls = calendar_ui.ProfileCalendarPanel
    if getattr(cls, "_wm_compact_team_layout_v1", False):
        return

    original_build = cls._build

    def build(self):
        original_build(self)
        tree = getattr(self, "_wm_team_detail_tree", None)
        if tree is None:
            return
        body = getattr(self, "calendar_box", None)
        body = body.master if body is not None else None
        if body is None:
            return

        side = tree.master
        try:
            body.columnconfigure(0, weight=1)
            body.columnconfigure(1, weight=0, minsize=0)
            body.rowconfigure(0, weight=1)
            body.rowconfigure(1, weight=0)
            self.calendar_box.grid_configure(
                row=0,
                column=0,
                columnspan=2,
                sticky="nsew",
                padx=0,
                pady=(0, 8),
            )
            side.grid_configure(row=1, column=0, columnspan=2, sticky="ew")
        except Exception:
            pass

        # Kalendarz jest podglądem. Edycję Obecności i Urlopów wykonujemy w profilu pracownika.
        for child in list(side.winfo_children()):
            if not isinstance(child, ttk.Frame):
                continue
            button_texts = {
                str(widget.cget("text"))
                for widget in _walk(child)
                if isinstance(widget, ttk.Button)
            }
            if {"Obecność", "Urlopy"}.intersection(button_texts):
                child.destroy()

        try:
            tree.unbind("<Double-1>")
        except Exception:
            pass

        def fit_height() -> None:
            try:
                count = len(tree.get_children(""))
                tree.configure(height=max(1, min(6, count or 1)))
            except Exception:
                pass

        fit_height()
        original_insert = tree.insert
        original_delete = tree.delete

        def compact_insert(parent, index, iid=None, **kw):
            result = original_insert(parent, index, iid=iid, **kw)
            fit_height()
            return result

        def compact_delete(*items):
            result = original_delete(*items)
            fit_height()
            return result

        tree.insert = compact_insert
        tree.delete = compact_delete
        self._wm_team_max_visible_rows = 6

        for widget in _walk(side):
            if not isinstance(widget, ttk.Label):
                continue
            try:
                if str(widget.cget("text")).startswith("Kliknij dzień:"):
                    widget.configure(wraplength=1100)
            except Exception:
                pass

    cls._build = build
    cls._wm_compact_team_layout_v1 = True


def install() -> None:
    global _INSTALLED
    _install_workspace_policy()
    _install_calendar_policy()
    _install_calendar_layout()
    _INSTALLED = True


__all__ = [
    "install",
    "_ensure_allowed",
    "_work_payload",
    "_weekday_label",
    "_install_weekday_column",
]
