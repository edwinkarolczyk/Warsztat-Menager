# version: 1.2
"""Edycja zapisanej zmiany, dniówki i rodzaju nieobecności w Profilu WM."""
from __future__ import annotations

import tkinter as tk
import uuid
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Any, Callable

import profile_attendance_finalize_runtime as final
from services import (
    attendance_service,
    day_pay_service,
    leave_workflow_service,
    workforce_profile_service,
)
from ui_context_help import add_help_button

_INSTALLED = False
_ABSENCE_CHOICES = ("Brak", "ŚW", "L4", "NN", "UR", "UŻ")
_ABSENCE_CODES = {"BRAK", "ŚW", "L4", "NN", "UR", "UŻ"}


def _initial_day_value(case: dict) -> float:
    status = str(case.get("status") or "")
    if status == attendance_service.STATUS_MISSING:
        return 0.0
    if status == attendance_service.STATUS_PENDING_LATE:
        return 1.0
    try:
        value = float(case.get("day_value"))
    except Exception:
        return 1.0
    return value if value in {0.0, 0.5, 1.0} else 1.0


def _normalize_absence_choice(value: Any) -> str:
    code = day_pay_service.normalize_code(value)
    if code not in _ABSENCE_CODES:
        raise ValueError("Rodzaj nieobecności musi być: Brak, ŚW, L4, NN, UR albo UŻ.")
    return code


def _display_absence(code: Any) -> str:
    normalized = _normalize_absence_choice(code)
    return "Brak" if normalized == "BRAK" else normalized


def _absence_code_from_row(row: dict) -> str:
    for key in ("absence_code", "pay_code"):
        raw = str(row.get(key) or "").strip()
        if not raw:
            continue
        code = day_pay_service.normalize_code(raw)
        if code in _ABSENCE_CODES - {"BRAK"}:
            return code

    kind = str(row.get("type") or "").strip().casefold()
    mapping = {
        "sila_wyzsza": "ŚW",
        "siła_wyższa": "ŚW",
        "l4": "L4",
        "nn": "NN",
        "urlop": "UR",
        "uż": "UŻ",
        "uz": "UŻ",
    }
    return mapping.get(kind, "BRAK")


def _active_absence_codes(login: str, day_text: str) -> list[str]:
    try:
        rows = leave_workflow_service.active_absences_for_day(login, day_text)
    except Exception:
        rows = []
    out: list[str] = []
    for row in rows:
        code = _absence_code_from_row(row)
        if code != "BRAK" and code not in out:
            out.append(code)
    return out


def _absence_labels_runtime(login: str, day_text: str) -> list[str]:
    return _active_absence_codes(login, day_text)


def _current_absence_code(login: str, day_text: str, case: dict) -> str:
    codes = _active_absence_codes(login, day_text)
    if codes:
        return codes[0]
    reason = final._absence_label(case.get("reason") or case.get("conflict_reason"))
    try:
        code = day_pay_service.normalize_code(reason)
    except Exception:
        code = ""
    return code if code in _ABSENCE_CODES - {"BRAK"} else "BRAK"


def _restore_work_state(rec: dict, slot: str, day_text: str) -> None:
    try:
        day_value = float(rec.get("day_value") or 0.0)
    except Exception:
        day_value = 0.0
    first_login = str(rec.get("first_login_ts") or rec.get("logged_ts") or "").strip()

    if day_value > 0:
        rec.update({
            "reason": "",
            "status": attendance_service.STATUS_PRESENT,
            "day_value": day_value,
            "confirmed": True,
            "approval_required": False,
        })
        day_pay_service.apply_to_record(rec, "PRACA", pay_day_value=day_value)
        return

    if first_login:
        moment = attendance_service._parse_dt(first_login)
        if moment is not None:
            try:
                saturday = date.fromisoformat(day_text).weekday() == 5
            except Exception:
                saturday = False
            status = attendance_service.classify_login(slot, moment, saturday=saturday)
            if status == attendance_service.STATUS_PRESENT:
                rec.update({
                    "reason": "",
                    "status": attendance_service.STATUS_PRESENT,
                    "day_value": 1.0,
                    "confirmed": True,
                    "approval_required": False,
                })
                day_pay_service.apply_to_record(rec, "PRACA", pay_day_value=1.0)
                return
            rec.update({
                "reason": "",
                "status": status,
                "day_value": 0.0,
                "confirmed": False,
                "approval_required": True,
            })
            day_pay_service.mark_pending(rec)
            return

    rec.update({
        "reason": "",
        "status": attendance_service.STATUS_MISSING,
        "day_value": 0.0,
        "confirmed": False,
        "approval_required": True,
    })
    day_pay_service.mark_pending(rec)


def _clear_other_absence_slots(login: str, day_text: str, target_slot: str) -> None:
    """Usuń stary ślad nieobecności z drugiej zmiany przy świadomym przeniesieniu."""
    login_n = str(login or "").strip().casefold()
    target_slot = str(target_slot or "").strip().upper()
    doc = attendance_service._read(attendance_service.data_path(), {})
    day = doc.get(str(day_text), {}) if isinstance(doc, dict) else {}
    if not isinstance(day, dict):
        return

    changed = False
    for slot in (attendance_service.RANO, attendance_service.POPO):
        if slot == target_slot:
            continue
        slot_map = day.get(slot)
        if not isinstance(slot_map, dict):
            continue
        storage_key, rec = attendance_service._matching_record(slot_map, login_n)
        if not isinstance(rec, dict):
            continue
        reason = day_pay_service.normalize_code(rec.get("reason"))
        if reason not in _ABSENCE_CODES - {"BRAK"}:
            continue

        first_login = str(rec.get("first_login_ts") or rec.get("logged_ts") or "").strip()
        try:
            day_value = float(rec.get("day_value") or 0.0)
        except Exception:
            day_value = 0.0
        overtime = rec.get("overtime")
        has_overtime = isinstance(overtime, dict) and bool(
            float(overtime.get("hours") or 0.0) or overtime.get("status")
        )
        has_activity = bool(
            first_login
            or day_value > 0
            or str(rec.get("status") or "") == attendance_service.STATUS_PRESENT
            or has_overtime
        )

        if has_activity:
            _restore_work_state(rec, slot, day_text)
        elif storage_key is not None:
            slot_map.pop(storage_key, None)
        changed = True

    if changed:
        attendance_service._write(attendance_service.data_path(), doc)


def _sync_attendance_choice(
    login: str,
    day_text: str,
    slot: str,
    code: str,
    actor: str,
    note: str,
) -> dict:
    target_slot = str(slot or "").strip().upper()
    if target_slot not in attendance_service.VALID_SLOTS:
        target_slot = leave_workflow_service._slot_for_attendance(login, day_text)

    login_n = str(login or "").strip().casefold()
    doc, _slot_map, rec = attendance_service._record(
        day_text,
        target_slot,
        login_n,
        create=True,
    )
    before = dict(rec)
    had_login = bool(str(rec.get("first_login_ts") or rec.get("logged_ts") or "").strip())
    try:
        day_value = float(rec.get("day_value") or 0.0)
    except Exception:
        day_value = 0.0
    had_work = (
        str(rec.get("status") or "") == attendance_service.STATUS_PRESENT
        or day_value > 0
        or had_login
    )

    if code == "BRAK":
        _restore_work_state(rec, target_slot, day_text)
    elif code == "ŚW" and had_work:
        _restore_work_state(rec, target_slot, day_text)
    else:
        rec.update({
            "planned": True,
            "reason": code,
            "status": attendance_service.STATUS_EXCUSED,
            "day_value": 0.0,
            "confirmed": False,
            "approval_required": False,
        })
        day_pay_service.apply_to_record(rec, code, pay_day_value=1.0)

    rec.update({
        "planned": True,
        "confirmed_by": str(actor or ""),
        "confirmed_ts": attendance_service._now_iso(),
        "source": "foreman_absence_edit",
        "manual_note": str(note or "").strip(),
        "user_id": rec.get("user_id") or attendance_service.user_id_for(login_n),
    })
    rec.setdefault("login_snapshot", login_n)
    attendance_service._write(attendance_service.data_path(), doc)
    attendance_service._audit(
        action="absence_kind_edit",
        login=login_n,
        date_ymd=day_text,
        slot=target_slot,
        actor=actor,
        before=before,
        after=dict(rec),
        note=f"Rodzaj nieobecności: {_display_absence(code)}. {str(note or '').strip()}".strip(),
    )
    return dict(rec)


def _replace_absence_for_day(
    login: str,
    day_text: str,
    actor_login: str,
    choice: str,
    note: str,
    *,
    attendance_slot: str,
    source_slot: str | None = None,
) -> str:
    actor = leave_workflow_service._require_foreman(actor_login)
    day_text = leave_workflow_service._parse_day(day_text).isoformat()
    code = _normalize_absence_choice(choice)
    target_slot = str(attendance_slot or "").strip().upper()
    if target_slot not in attendance_service.VALID_SLOTS:
        target_slot = leave_workflow_service._slot_for_attendance(login, day_text)
    source_slot = str(source_slot or target_slot).strip().upper()
    if source_slot not in attendance_service.VALID_SLOTS:
        source_slot = target_slot

    uid, current_login = leave_workflow_service._identity(login)
    login = current_login or str(login or "").strip()
    if not login:
        raise ValueError("Brak pracownika.")

    rows_before = leave_workflow_service._read_all_leaves()
    rows = [dict(row) for row in rows_before]
    active_rows = [
        row for row in rows_before
        if leave_workflow_service._same_day(row, login, day_text)
    ]
    current_codes = [_absence_code_from_row(row) for row in active_rows]
    current_shifts = [
        str(row.get("shift") or source_slot).strip().upper()
        for row in active_rows
    ]
    same_canonical = (
        len(active_rows) == 1
        and current_codes == [code]
        and current_shifts == [target_slot]
    )
    if code == "BRAK":
        same_canonical = not active_rows

    attendance_before = attendance_service._read(attendance_service.data_path(), {})
    leaves_changed = False
    try:
        if not same_canonical:
            cancelled_at = leave_workflow_service._utc_now()
            cancelled_ids: list[str] = []
            for row in rows:
                if not leave_workflow_service._same_day(row, login, day_text):
                    continue
                row["status"] = leave_workflow_service._CANCELLED
                row["cancelled_by"] = actor
                row["cancelled_at"] = cancelled_at
                row["cancel_note"] = (
                    f"Zmiana rodzaju/zmiany nieobecności na {_display_absence(code)} {target_slot}. "
                    f"{str(note or '').strip()}"
                ).strip()
                if row.get("id"):
                    cancelled_ids.append(str(row.get("id")))

            if code != "BRAK":
                type_name = {
                    "ŚW": "sila_wyzsza",
                    "L4": "l4",
                    "NN": "nn",
                    "UR": "urlop",
                    "UŻ": "urlop",
                }[code]
                created = leave_workflow_service._utc_now()
                token = uuid.uuid4().hex[-10:]
                new_row = {
                    "id": f"leave_{day_text}_{login}_{type_name}_{token}",
                    "user_id": uid,
                    "login": login,
                    "login_snapshot": login,
                    "type": type_name,
                    "absence_code": code,
                    "date": day_text,
                    "shift": target_slot,
                    "quantity_days": 1.0,
                    "minutes": 0,
                    "approved_by": actor,
                    "created_at": created,
                    "note": str(note or "").strip(),
                    "entered_by": actor,
                    "replaces": cancelled_ids,
                }
                new_row.update(day_pay_service.compensation(code, pay_day_value=1.0))
                if code in {"UR", "UŻ"}:
                    sources = leave_workflow_service._source_years_for_dates(login, [day_text])
                    new_row["leave_source_year"] = int(sources.get(day_text, int(day_text[:4])))
                rows.append(new_row)

            leave_workflow_service._write_json(leave_workflow_service.leaves_path(), rows)
            leaves_changed = True

        _clear_other_absence_slots(login, day_text, target_slot)
        _sync_attendance_choice(
            login,
            day_text,
            target_slot,
            code,
            actor,
            note,
        )
    except Exception:
        try:
            if leaves_changed:
                leave_workflow_service._write_json(
                    leave_workflow_service.leaves_path(),
                    rows_before,
                )
        finally:
            try:
                attendance_service._write(attendance_service.data_path(), attendance_before)
            except Exception:
                pass
        raise
    return code


def _install_absence_label_bridge() -> None:
    final._absence_labels = _absence_labels_runtime

    if getattr(attendance_service, "_wm_absence_kind_labels_v1", False):
        return
    original = attendance_service.absence_conflict

    def absence_conflict(date_ymd: str, login: str) -> dict:
        out = dict(original(date_ymd, login) or {})
        active_codes = _active_absence_codes(login, str(date_ymd)[:10])
        if "UŻ" in active_codes:
            reasons = [str(value) for value in (out.get("reasons") or []) if str(value) != "UR"]
            if "UŻ" not in reasons:
                reasons.append("UŻ")
            out["reasons"] = reasons
            out["has_conflict"] = bool(reasons)
        return out

    attendance_service.absence_conflict = absence_conflict
    attendance_service._wm_absence_kind_labels_v1 = True


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
    original_slot = str(
        case.get("_original_slot") or case.get("slot") or attendance_service.RANO
    ).strip().upper()
    slot_var = tk.StringVar(value=str(case.get("slot") or original_slot).strip().upper())
    original_day = _initial_day_value(case)
    value_var = tk.StringVar(value=final._fmt(original_day))
    save_day_var = tk.BooleanVar(value=case.get("status") != attendance_service.STATUS_SATURDAY)
    ot_var = tk.BooleanVar(value=case.get("status") == attendance_service.STATUS_SATURDAY)
    hours_var = tk.StringVar(value="8" if case.get("status") == attendance_service.STATUS_SATURDAY else "0")
    ot_type_var = tk.StringVar(value="sobota" if case.get("status") == attendance_service.STATUS_SATURDAY else "zwykle")
    note_var = tk.StringVar(value="")
    original_absence = _current_absence_code(login, day_var.get(), case)
    absence_var = tk.StringVar(value=_display_absence(original_absence))

    fields = [
        ("Pracownik:", case.get("display_name") or login),
        ("Data:", day_var.get()),
        ("Zmiana:", slot_var.get()),
        ("Typ:", final._decision_type(case)),
        ("Pierwsze logowanie:", final._first_login(case)),
        ("Stan:", case.get("decision_label") or final._status_text(case)),
    ]
    for row_no, (label, value) in enumerate(fields):
        ttk.Label(frame, text=label).grid(row=row_no, column=0, sticky="w", pady=3)
        if label == "Zmiana:":
            ttk.Combobox(
                frame,
                textvariable=slot_var,
                values=(attendance_service.RANO, attendance_service.POPO),
                state="readonly",
                width=10,
            ).grid(row=row_no, column=1, sticky="w", pady=3)
            add_help_button(
                frame,
                "Możesz zmienić RANO/POPO także dla nieobecności. WM przeniesie stan na wybraną zmianę i nie zostawi starego wpisu aktywnego.",
                row=row_no,
                column=2,
                padx=(6, 0),
            )
        else:
            ttk.Label(frame, text=str(value or "—")).grid(row=row_no, column=1, sticky="w", pady=3)

    row_no = len(fields)
    if case.get("is_conflict"):
        warning = ttk.Frame(frame)
        warning.grid(row=row_no, column=0, columnspan=3, sticky="ew", pady=(7, 2))
        ttk.Label(
            warning,
            text="⚠ Ten dzień ma sprzeczne dane. Popraw rodzaj nieobecności albo zapisz właściwą dniówkę.",
            style="WM.Muted.TLabel",
        ).pack(side="left")
        add_help_button(
            warning,
            "Rodzaj nieobecności możesz poprawić bez kasowania historii. Zapis dniówki nadal może zastąpić nieobecność, jeśli to dniówka jest prawidłowa.",
        ).pack(side="left", padx=(6, 0))
        row_no += 1

    ttk.Label(frame, text="Rodzaj nieobecności:").grid(row=row_no, column=0, sticky="w", pady=(8, 4))
    ttk.Combobox(
        frame,
        textvariable=absence_var,
        values=_ABSENCE_CHOICES,
        state="readonly",
        width=10,
    ).grid(row=row_no, column=1, sticky="w", pady=(8, 4))
    add_help_button(
        frame,
        "Wybierz Brak, ŚW, L4, NN, UR albo UŻ dla tego dnia. Zmiana zapisuje nowy typ, a poprzedni wpis pozostaje w historii jako anulowany.",
        row=row_no,
        column=2,
        padx=(6, 0),
    )
    row_no += 1

    ttk.Checkbutton(
        frame,
        text="Zapisz / zmień dniówkę",
        variable=save_day_var,
    ).grid(row=row_no, column=0, sticky="w", pady=(10, 4))
    ttk.Combobox(
        frame,
        textvariable=value_var,
        values=("0", "0.5", "1"),
        state="readonly",
        width=10,
    ).grid(row=row_no, column=1, sticky="w", pady=(10, 4))
    add_help_button(
        frame,
        "Rodzaj dniówki: 0 = brak, 0,5 = pół dniówki, 1 = pełna dniówka. Przy ponownej edycji WM pokazuje aktualnie zapisaną wartość.",
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
        "Przy ręcznej decyzji wpisz krótki powód. Pozwala to później odtworzyć, dlaczego dniówka, zmiana lub rodzaj nieobecności zostały poprawione.",
        row=row_no,
        column=2,
        padx=(6, 0),
    )

    row_no += 1
    current_text = str(case.get("decision_label") or final._status_text(case) or "—")
    original_day_text = final._fmt(original_day)
    original_absence_text = _display_absence(original_absence)
    preview_var = tk.StringVar(value="")
    preview = ttk.Frame(frame)
    preview.grid(row=row_no, column=0, columnspan=3, sticky="ew", pady=(8, 2))
    ttk.Label(preview, text="Podgląd zmiany:", style="WM.Muted.TLabel").pack(side="left")
    ttk.Label(preview, textvariable=preview_var).pack(side="left", padx=(6, 0))
    add_help_button(
        preview,
        "Przed zapisem WM pokazuje zmianę zmiany roboczej, dniówki i rodzaju nieobecności. Dane zmienią się dopiero po użyciu właściwego przycisku zapisu.",
    ).pack(side="left", padx=(6, 0))

    def refresh_preview(*_args) -> None:
        parts: list[str] = []
        target_slot = str(slot_var.get() or original_slot)
        if target_slot != original_slot:
            parts.append(f"zmiana {original_slot} → {target_slot}")
        if absence_var.get() != original_absence_text:
            parts.append(f"nieobecność {original_absence_text} → {absence_var.get()}")
        if save_day_var.get():
            parts.append(f"dniówka {original_day_text} → {final._fmt(value_var.get())}")
        if ot_var.get():
            parts.append(f"{final._fmt(hours_var.get())} h nadgodzin ({ot_type_var.get()})")
        preview_var.set(f"{current_text} | {' | '.join(parts) if parts else 'bez zmiany'}")

    for var in (slot_var, absence_var, save_day_var, value_var, ot_var, hours_var, ot_type_var):
        try:
            var.trace_add("write", refresh_preview)
        except Exception:
            pass
    refresh_preview()

    def finish() -> None:
        win.destroy()
        if callable(on_saved):
            on_saved()

    def save_absence() -> None:
        note = note_var.get().strip()
        if not note:
            messagebox.showinfo("Obecność", "Wpisz powód lub krótką uwagę.", parent=win)
            return
        try:
            _replace_absence_for_day(
                login,
                day_var.get(),
                final._actor(owner),
                absence_var.get(),
                note,
                attendance_slot=slot_var.get(),
                source_slot=original_slot,
            )
        except Exception as exc:
            messagebox.showerror(
                "Obecność",
                f"Nie udało się zapisać rodzaju nieobecności:\n{exc}",
                parent=win,
            )
            return
        finish()

    def save() -> None:
        note = note_var.get().strip()
        if not note:
            messagebox.showinfo("Obecność", "Wpisz powód lub krótką uwagę.", parent=win)
            return

        replace_absence = False
        manual_original_slot = original_slot
        try:
            if save_day_var.get():
                conflict = attendance_service.absence_conflict(day_var.get(), login)
                if conflict.get("has_conflict"):
                    conflict_slot = str(conflict.get("slot") or "").strip().upper()
                    labels = ", ".join(conflict.get("reasons") or []) or "nieobecność"
                    if not messagebox.askyesno(
                        "Korekta nieobecności",
                        f"Ten dzień ma wpis {labels}. Zastąpić nieobecność korektą?\n\n"
                        "Wpis nieobecności zostanie anulowany, ale pozostanie w historii.",
                        parent=win,
                    ):
                        return

                    if conflict_slot and conflict_slot != slot_var.get():
                        _replace_absence_for_day(
                            login,
                            day_var.get(),
                            final._actor(owner),
                            "Brak",
                            note,
                            attendance_slot=slot_var.get(),
                            source_slot=conflict_slot,
                        )
                        manual_original_slot = slot_var.get()
                        replace_absence = False
                    else:
                        replace_absence = True

                attendance_service.set_manual_day(
                    day_var.get(),
                    slot_var.get(),
                    login,
                    float(value_var.get()),
                    final._actor(owner),
                    note,
                    replace_absence=replace_absence,
                    original_slot=manual_original_slot,
                )
            elif slot_var.get() != original_slot:
                messagebox.showinfo(
                    "Obecność",
                    "Aby zmienić zmianę zapisanego dnia, zaznacz „Zapisz / zmień dniówkę”.",
                    parent=win,
                )
                return

            if ot_var.get():
                attendance_service.set_overtime(
                    day_var.get(),
                    slot_var.get(),
                    login,
                    float(hours_var.get()),
                    final._actor(owner),
                    overtime_type=ot_type_var.get(),
                    day_value=1.0 if ot_type_var.get() == "sobota" else None,
                    note=note,
                )
        except Exception as exc:
            messagebox.showerror("Obecność", f"Nie udało się zapisać decyzji:\n{exc}", parent=win)
            return
        finish()

    row_no += 1
    actions = ttk.Frame(frame)
    actions.grid(row=row_no, column=0, columnspan=3, sticky="e", pady=(12, 0))
    ttk.Button(actions, text="Anuluj", command=win.destroy).pack(side="right")
    ttk.Button(actions, text="Zapisz decyzję", command=save).pack(side="right", padx=(0, 8))
    ttk.Button(actions, text="Zapisz nieobecność", command=save_absence).pack(side="right", padx=(0, 8))


def _manual_correction(owner, login: str, on_saved: Callable[[], None] | None = None) -> None:
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
    month_box = ttk.Combobox(
        top,
        textvariable=month_var,
        values=final._month_choices(),
        state="readonly",
        width=9,
    )
    month_box.pack(side="left", padx=(5, 8))
    add_help_button(
        top,
        "Wybierz zapisany dzień. Następnie możesz zmienić zmianę RANO/POPO, dniówkę i rodzaj nieobecności bez tworzenia drugiego wpisu.",
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
    ttk.Label(select_box, text="Zmiana docelowa:").grid(row=0, column=2, sticky="w")
    ttk.Combobox(
        select_box,
        textvariable=slot_var,
        values=(attendance_service.RANO, attendance_service.POPO),
        state="readonly",
        width=10,
    ).grid(row=0, column=3, sticky="w", padx=(5, 0))
    ttk.Label(select_box, textvariable=state_var, style="WM.Muted.TLabel").grid(
        row=1,
        column=0,
        columnspan=4,
        sticky="w",
        pady=(6, 0),
    )

    rows_by_iid: dict[str, dict] = {}
    selected_history_row: dict[str, Any] = {}

    def state_label(row: dict) -> str:
        labels = final._absence_labels(login, str(row.get("date") or "")[:10])
        reason = final._absence_label(row.get("reason"))
        if reason and reason not in labels:
            labels.append(reason)
        status = final._status_text(row)
        if labels and str(row.get("status") or "") != attendance_service.STATUS_EXCUSED:
            return f"{', '.join(labels)} + {status}"
        if labels:
            return ", ".join(labels)
        return status

    def refresh_history(_event=None) -> None:
        rows_by_iid.clear()
        selected_history_row.clear()
        for iid in history.get_children():
            history.delete(iid)
        year, month = final._month_tuple(month_var.get())
        rows = list(attendance_service.month_records(login, year, month))
        rows.sort(
            key=lambda item: (str(item.get("date") or ""), str(item.get("slot") or "")),
            reverse=True,
        )
        for row in rows:
            item = dict(row)
            shown_state = state_label(item)
            iid = history.insert(
                "",
                "end",
                values=(
                    str(item.get("date") or "")[:10],
                    item.get("slot") or "—",
                    final._first_login(item),
                    shown_state,
                    final._fmt(item.get("day_value")),
                ),
            )
            item["_display_state"] = shown_state
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
        selected_history_row.clear()
        selected_history_row.update(item)
        day_var.set(str(item.get("date") or "")[:10])
        slot = str(item.get("slot") or attendance_service.RANO)
        if slot in attendance_service.VALID_SLOTS:
            slot_var.set(slot)
        state_var.set(
            f"Stan teraz: {item.get('_display_state') or final._status_text(item)} | "
            f"dniówka: {final._fmt(item.get('day_value'))}. Możesz teraz zmienić zmianę docelową."
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

        target_slot = str(slot_var.get() or "").strip().upper()
        if target_slot not in attendance_service.VALID_SLOTS:
            messagebox.showerror("Obecność", "Zmiana musi być RANO albo POPO.", parent=win)
            return

        selected_row: dict[str, Any] | None = None
        original_slot = target_slot
        if selected_history_row and str(selected_history_row.get("date") or "")[:10] == day_text:
            selected_row = dict(selected_history_row)
            original_slot = str(selected_history_row.get("slot") or target_slot)
        else:
            for row in attendance_service.month_records(login, parsed_day.year, parsed_day.month):
                if (
                    str(row.get("date") or "")[:10] == day_text
                    and str(row.get("slot") or "") == target_slot
                ):
                    selected_row = dict(row)
                    original_slot = str(row.get("slot") or target_slot)
                    break

        if selected_row is None:
            selected_row = {
                "date": day_text,
                "slot": target_slot,
                "status": attendance_service.STATUS_MISSING,
                "day_value": 0.0,
                "decision_label": "Brak wpisu w ewidencji",
            }
            original_slot = target_slot

        labels = final._absence_labels(login, day_text)
        reason = final._absence_label(selected_row.get("reason"))
        if reason and reason not in labels:
            labels.append(reason)
        blocking_labels = [label for label in labels if label != "ŚW"]
        current_status = str(selected_row.get("status") or "")
        current_text = final._status_text(selected_row)
        is_conflict = bool(
            (blocking_labels and current_status != attendance_service.STATUS_EXCUSED)
            or (reason and current_status != attendance_service.STATUS_EXCUSED)
        )
        if labels:
            selected_row["decision_label"] = (
                f"{', '.join(labels)} + {current_text}"
                if current_status != attendance_service.STATUS_EXCUSED
                else ", ".join(labels)
            )
        else:
            selected_row.setdefault("decision_label", current_text)

        selected_row.update({
            "login": login,
            "display_name": display_name,
            "date": day_text,
            "slot": target_slot,
            "_original_slot": original_slot,
            "is_conflict": is_conflict,
            "conflict_reason": reason or (blocking_labels[0] if blocking_labels else ""),
        })
        win.destroy()
        _open_case_dialog(owner, selected_row, on_saved=on_saved)

    history.bind("<Double-1>", continue_edit, add="+")
    actions = ttk.Frame(frame)
    actions.grid(row=3, column=0, sticky="e", pady=(10, 0))
    ttk.Button(actions, text="Anuluj", command=win.destroy).pack(side="right")
    ttk.Button(actions, text="Przejdź do korekty", command=continue_edit).pack(side="right", padx=(0, 8))
    refresh_history()


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _install_absence_label_bridge()
    final._open_case_dialog = _open_case_dialog
    final._manual_correction = _manual_correction
    _INSTALLED = True


__all__ = ["install"]
