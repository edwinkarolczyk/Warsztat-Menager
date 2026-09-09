# version: 1.0
"""Końcowy workspace Brygadzisty: edycja w Profilu i jeden zaawansowany Kalendarz.

Ta warstwa nie tworzy nowych źródeł danych. Zastępuje wyłącznie końcowe wejścia UI:
- pełna korekta Obecności odbywa się wewnątrz zakładki pracownika,
- Historia i Uprawnienia pozostają zwykłymi zakładkami,
- Kalendarz Brygadzisty ma jeden widok Zespołu i szczegóły dnia po prawej stronie.
"""
from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from services import attendance_service, day_pay_service, leave_workflow_service, workforce_profile_service
from ui_context_help import add_help_button

_INSTALLED = False
_ABSENCE_CHOICES = ("Brak", "ŚW", "L4", "NN", "UR", "UŻ", "UB")
_BLOCKING_ABSENCES = {"L4", "NN", "UR", "UŻ", "UB"}
_OT_TYPES = ("zwykle", "sobota", "niedziela", "swieto")


def _actor(owner=None) -> str:
    try:
        from services.profile_service import ProfileService
        login = str(ProfileService.ensure_active_user_or_none() or "").strip()
        if login:
            return login
    except Exception:
        pass
    return str(getattr(getattr(owner, "owner", None), "login", "") or getattr(owner, "login", "") or "").strip()


def _normalize_absence(value: Any) -> str:
    raw = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    mapping = {
        "": "BRAK", "BRAK": "BRAK",
        "SW": "ŚW", "ŚW": "ŚW", "SILA_WYZSZA": "ŚW", "SIŁA_WYŻSZA": "ŚW",
        "L4": "L4", "NN": "NN", "UR": "UR", "URLOP": "UR",
        "UZ": "UŻ", "UŻ": "UŻ", "URLOP_NA_ZADANIE": "UŻ",
        "UB": "UB", "URLOP_BEZPLATNY": "UB", "URLOP_BEZPŁATNY": "UB",
    }
    code = mapping.get(raw, day_pay_service.normalize_code(raw))
    if code not in {"BRAK", "ŚW", "L4", "NN", "UR", "UŻ", "UB"}:
        raise ValueError("Nieznany rodzaj nieobecności.")
    return code


def _display_absence(code: Any) -> str:
    value = _normalize_absence(code)
    return "Brak" if value == "BRAK" else value


def _validate_attendance_edit(
    day_text: str,
    slot: str,
    day_value: Any,
    absence: Any,
    overtime_hours: Any,
    first_login: str,
) -> dict[str, Any]:
    try:
        parsed_day = date.fromisoformat(str(day_text or "").strip())
    except Exception as exc:
        raise ValueError("Data musi mieć format RRRR-MM-DD.") from exc

    target_slot = str(slot or "").strip().upper()
    if target_slot not in attendance_service.VALID_SLOTS:
        raise ValueError("Zmiana musi być RANO albo POPO.")

    try:
        value = float(str(day_value).replace(",", "."))
    except Exception as exc:
        raise ValueError("Dniówka musi być liczbą: 0, 0.5 albo 1.") from exc
    if value not in {0.0, 0.5, 1.0}:
        raise ValueError("Dniówka może mieć wartość 0, 0.5 albo 1.")

    try:
        hours = float(str(overtime_hours or 0).replace(",", "."))
    except Exception as exc:
        raise ValueError("Nadgodziny muszą być liczbą.") from exc
    if hours < 0:
        raise ValueError("Nadgodziny nie mogą być ujemne.")

    absence_code = _normalize_absence(absence)
    if absence_code in _BLOCKING_ABSENCES and value != 0.0:
        raise ValueError(f"Dla {absence_code} dniówka musi wynosić 0.")
    if absence_code in _BLOCKING_ABSENCES and hours > 0:
        raise ValueError(f"Dla {absence_code} nie zapisuj nadgodzin.")

    login_time = str(first_login or "").strip()
    if login_time and login_time != "—":
        try:
            datetime.strptime(login_time, "%H:%M")
        except Exception as exc:
            raise ValueError("Pierwsze logowanie wpisz jako GG:MM, np. 05:57, albo pozostaw puste.") from exc
    else:
        login_time = ""

    return {
        "date": parsed_day.isoformat(),
        "slot": target_slot,
        "day_value": value,
        "absence": absence_code,
        "overtime_hours": hours,
        "first_login": login_time,
    }


def _leave_code(row: dict) -> str:
    raw = row.get("absence_code") or row.get("pay_code")
    if raw:
        try:
            return _normalize_absence(raw)
        except Exception:
            pass
    kind = str(row.get("type") or "").strip().casefold()
    mapping = {
        "urlop": "UR",
        "l4": "L4",
        "nn": "NN",
        "sila_wyzsza": "ŚW",
        "siła_wyższa": "ŚW",
        "force_majeure": "ŚW",
        "urlop_bezplatny": "UB",
        "urlop_bezpłatny": "UB",
        "unpaid": "UB",
    }
    return mapping.get(kind, "BRAK")


def _absence_for_day(login: str, day_text: str, row: dict | None = None) -> str:
    try:
        active = leave_workflow_service.active_absences_for_day(login, day_text)
    except Exception:
        active = []
    for leave in active:
        code = _leave_code(dict(leave))
        if code != "BRAK":
            return code
    reason = str((row or {}).get("reason") or "").strip()
    if reason:
        try:
            return _normalize_absence(reason)
        except Exception:
            pass
    return "BRAK"


def _first_login_text(row: dict) -> str:
    raw = str(row.get("first_login_ts") or row.get("logged_ts") or "").strip()
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%H:%M")
    except Exception:
        if "T" in raw:
            return raw.split("T", 1)[1][:5]
        return raw[:5]


def _overtime_values(row: dict) -> tuple[float, str]:
    overtime = row.get("overtime") if isinstance(row.get("overtime"), dict) else {}
    try:
        hours = float(overtime.get("hours") or 0.0)
    except Exception:
        hours = 0.0
    return hours, str(overtime.get("type") or "zwykle")


def _replace_absence(
    login: str,
    day_text: str,
    actor: str,
    code: str,
    note: str,
    *,
    target_slot: str,
    source_slot: str,
) -> str:
    """Użyj kanonicznego mechanizmu zmiany nieobecności; dołóż brakujące UB."""
    import profile_attendance_edit_runtime as edit

    edit._ABSENCE_CODES.add("UB")
    edit._ABSENCE_CHOICES = tuple(dict.fromkeys((*edit._ABSENCE_CHOICES, "UB")))
    code = _normalize_absence(code)
    shown = "Brak" if code == "BRAK" else code
    if code != "UB":
        return edit._replace_absence_for_day(
            login,
            day_text,
            actor,
            shown,
            note,
            attendance_slot=target_slot,
            source_slot=source_slot,
        )

    # Starszy runtime nie miał UB w mapie typów. Najpierw anulujemy dotychczasową
    # nieobecność, potem zapisujemy kanoniczny urlop bezpłatny i spinamy jego zmianę.
    edit._replace_absence_for_day(
        login,
        day_text,
        actor,
        "Brak",
        note,
        attendance_slot=target_slot,
        source_slot=source_slot,
    )
    leave_workflow_service.add_unpaid_leave(login, [day_text], actor, note)
    rows = leave_workflow_service.read_leaves()
    changed = False
    for row in rows:
        if not leave_workflow_service._same_day(row, login, day_text):
            continue
        if _leave_code(row) != "UB":
            continue
        row["shift"] = target_slot
        row["absence_code"] = "UB"
        changed = True
    if changed:
        leave_workflow_service._write_json(leave_workflow_service.leaves_path(), rows)
    edit._clear_other_absence_slots(login, day_text, target_slot)
    edit._sync_attendance_choice(login, day_text, target_slot, "UB", actor, note)
    return "UB"


def _set_manual_first_login(login: str, day_text: str, slot: str, hhmm: str, actor: str, note: str) -> None:
    login_n = str(login or "").strip().casefold()
    doc, _slot_map, rec = attendance_service._record(day_text, slot, login_n, create=True)
    before = dict(rec)
    text = str(hhmm or "").strip()
    if text:
        parsed_time = datetime.strptime(text, "%H:%M").time()
        stamp = datetime.combine(date.fromisoformat(day_text), parsed_time).astimezone().isoformat(timespec="seconds")
        rec["first_login_ts"] = stamp
        rec["logged_ts"] = stamp
        rec.setdefault("last_login_ts", stamp)
    else:
        rec["first_login_ts"] = ""
        rec["logged_ts"] = ""
    rec["manual_first_login"] = True
    rec["manual_note"] = str(note or "").strip()
    rec["confirmed_by"] = str(actor or "")
    rec["confirmed_ts"] = attendance_service._now_iso()
    rec["user_id"] = rec.get("user_id") or attendance_service.user_id_for(login_n)
    rec.setdefault("login_snapshot", login_n)
    if before == rec:
        return
    attendance_service._write(attendance_service.data_path(), doc)
    attendance_service._audit(
        action="manual_first_login",
        login=login_n,
        date_ymd=day_text,
        slot=slot,
        actor=actor,
        before=before,
        after=dict(rec),
        note=note,
    )


def _clear_overtime(login: str, day_text: str, slot: str, actor: str, note: str) -> None:
    login_n = str(login or "").strip().casefold()
    doc, _slot_map, rec = attendance_service._record(day_text, slot, login_n, create=False)
    if not isinstance(rec, dict) or not isinstance(rec.get("overtime"), dict):
        return
    before = dict(rec)
    rec.pop("overtime", None)
    attendance_service._write(attendance_service.data_path(), doc)
    attendance_service._audit(
        action="overtime_clear",
        login=login_n,
        date_ymd=day_text,
        slot=slot,
        actor=actor,
        before=before,
        after=dict(rec),
        note=note,
    )


def _save_attendance_edit(
    login: str,
    payload: dict[str, Any],
    *,
    source_slot: str,
    original_first_login: str,
    actor: str,
    note: str,
) -> None:
    """Zapisz cały formularz atomowo z punktu widzenia danych Obecności/Urlopów."""
    day_text = payload["date"]
    target_slot = payload["slot"]
    source_slot = str(source_slot or target_slot).strip().upper()
    if source_slot not in attendance_service.VALID_SLOTS:
        source_slot = target_slot
    absence = payload["absence"]
    value = float(payload["day_value"])
    hours = float(payload["overtime_hours"])
    note = str(note or "").strip() or "Korekta Brygadzisty w Profilu"

    attendance_before = attendance_service._read(attendance_service.data_path(), {})
    audit_before = attendance_service._read(attendance_service.audit_path(), [])
    leaves_before = leave_workflow_service._read_all_leaves()

    try:
        current_absence = _absence_for_day(login, day_text)

        if absence in _BLOCKING_ABSENCES:
            _replace_absence(
                login, day_text, actor, absence, note,
                target_slot=target_slot, source_slot=source_slot,
            )
        else:
            # Dniówka i ŚW mogą współistnieć. Najpierw zdejmujemy blokującą
            # nieobecność, potem przenosimy/zapisujemy dniówkę, a ŚW spinamy na końcu.
            if current_absence in _BLOCKING_ABSENCES:
                _replace_absence(
                    login, day_text, actor, "BRAK", note,
                    target_slot=target_slot, source_slot=source_slot,
                )
            elif absence == "BRAK" and current_absence != "BRAK":
                _replace_absence(
                    login, day_text, actor, "BRAK", note,
                    target_slot=target_slot, source_slot=source_slot,
                )

            attendance_service.set_manual_day(
                day_text,
                target_slot,
                login,
                value,
                actor,
                note,
                original_slot=source_slot,
            )
            if absence == "ŚW":
                _replace_absence(
                    login, day_text, actor, "ŚW", note,
                    target_slot=target_slot, source_slot=target_slot,
                )

        if payload["first_login"] != str(original_first_login or ""):
            _set_manual_first_login(
                login, day_text, target_slot, payload["first_login"], actor, note,
            )

        if hours > 0:
            attendance_service.set_overtime(
                day_text,
                target_slot,
                login,
                hours,
                actor,
                overtime_type=str(payload.get("overtime_type") or "zwykle"),
                day_value=1.0 if str(payload.get("overtime_type")) == "sobota" else None,
                note=note,
            )
        else:
            _clear_overtime(login, day_text, target_slot, actor, note)
    except Exception:
        try:
            leave_workflow_service._write_json(leave_workflow_service.leaves_path(), leaves_before)
        finally:
            attendance_service._write(attendance_service.data_path(), attendance_before)
            attendance_service._write(attendance_service.audit_path(), audit_before)
        raise


def _tree_with_scroll(parent, columns, *, height: int = 12) -> ttk.Treeview:
    wrap = ttk.Frame(parent)
    wrap.pack(fill="both", expand=True)
    keys = [key for key, _label, _width, _anchor in columns]
    tree = ttk.Treeview(wrap, columns=keys, show="headings", height=height)
    for key, label, width, anchor in columns:
        tree.heading(key, text=label)
        tree.column(key, width=width, anchor=anchor, stretch=key in {"status", "note", "name"})
    y = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
    x = ttk.Scrollbar(wrap, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
    tree.grid(row=0, column=0, sticky="nsew")
    y.grid(row=0, column=1, sticky="ns")
    x.grid(row=1, column=0, sticky="ew")
    wrap.rowconfigure(0, weight=1)
    wrap.columnconfigure(0, weight=1)
    tree.tag_configure("bad", foreground="#ef4444")
    tree.tag_configure("warn", foreground="#f59e0b")
    tree.tag_configure("ok", foreground="#22c55e")
    tree.tag_configure("muted", foreground="#A7A9AB")
    return tree


def _build_employee_attendance(frame, login: str, *, on_saved: Callable[[], None] | None = None) -> None:
    """Jedna zakładka = lista miesiąca + pełny edytor zaznaczonego dnia."""
    for child in frame.winfo_children():
        child.destroy()

    outer = ttk.Frame(frame, padding=10)
    outer.pack(fill="both", expand=True)
    month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
    summary_var = tk.StringVar(value="")
    issues_var = tk.StringVar(value="")

    top = ttk.Frame(outer)
    top.pack(fill="x", pady=(0, 6))
    ttk.Label(top, text="Miesiąc:").pack(side="left")
    try:
        import profile_attendance_finalize_runtime as final
        month_values = final._month_choices()
    except Exception:
        month_values = [date.today().strftime("%Y-%m")]
    month_box = ttk.Combobox(top, textvariable=month_var, values=month_values, state="readonly", width=9)
    month_box.pack(side="left", padx=(6, 10))
    ttk.Label(top, textvariable=summary_var).pack(side="left")
    ttk.Label(top, textvariable=issues_var).pack(side="left", padx=(14, 0))

    def export_month() -> None:
        try:
            year, month = map(int, month_var.get().split("-", 1))
            import profile_employee_editor_finish_runtime as finish
            safe_login = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in login) or "pracownik"
            target = filedialog.asksaveasfilename(
                parent=frame.winfo_toplevel(),
                title="Eksport obecności pracownika",
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                initialfile=f"obecnosc_{safe_login}_{year:04d}-{month:02d}.xlsx",
            )
            if target:
                finish._export_attendance_xlsx(target, login, year, month)
        except Exception as exc:
            messagebox.showerror("Eksport obecności", f"Nie udało się utworzyć pliku:\n{exc}", parent=frame.winfo_toplevel())

    ttk.Button(top, text="Eksportuj miesiąc", command=export_month).pack(side="right")
    add_help_button(
        top,
        "Wybierz miesiąc i kliknij dowolny dzień w tabeli. Całą korektę wykonujesz poniżej bez otwierania kolejnych okien.",
    ).pack(side="right", padx=(0, 6))

    table_box = ttk.LabelFrame(outer, text="Ewidencja miesiąca", padding=6)
    table_box.pack(fill="both", expand=True, pady=(0, 6))
    tree = _tree_with_scroll(table_box, [
        ("date", "Data", 92, "center"),
        ("slot", "Zmiana", 78, "center"),
        ("first", "Pierwsze log.", 100, "center"),
        ("status", "Status", 170, "w"),
        ("day", "Dniówka", 65, "center"),
        ("absence", "Nieobecność", 90, "center"),
        ("ot", "Nadgodziny", 90, "center"),
        ("source", "Źródło", 120, "w"),
    ], height=10)
    rows_by_iid: dict[str, dict] = {}

    editor = ttk.LabelFrame(outer, text="Edycja zaznaczonego dnia", padding=10)
    editor.pack(fill="x")
    editor.columnconfigure(1, weight=1)
    editor.columnconfigure(4, weight=1)

    day_var = tk.StringVar(value=date.today().isoformat())
    slot_var = tk.StringVar(value=attendance_service.RANO)
    first_var = tk.StringVar(value="")
    day_value_var = tk.StringVar(value="1")
    absence_var = tk.StringVar(value="Brak")
    overtime_var = tk.StringVar(value="0")
    overtime_type_var = tk.StringVar(value="zwykle")
    note_var = tk.StringVar(value="")
    state_var = tk.StringVar(value="Nowy wpis")
    selected_state: dict[str, Any] = {"source_slot": attendance_service.RANO, "first": "", "is_new": True}

    def label(row: int, col: int, text: str) -> None:
        ttk.Label(editor, text=text).grid(row=row, column=col, sticky="w", pady=3, padx=(0, 5))

    label(0, 0, "Data:")
    ttk.Entry(editor, textvariable=day_var, width=13).grid(row=0, column=1, sticky="ew", pady=3)
    add_help_button(editor, "Data edytowanego dnia. Dla nowego wpisu możesz wpisać dowolny dzień z wybranego miesiąca.", row=0, column=2, padx=(5, 12))
    label(0, 3, "Zmiana:")
    ttk.Combobox(editor, textvariable=slot_var, values=(attendance_service.RANO, attendance_service.POPO), state="readonly", width=11).grid(row=0, column=4, sticky="ew", pady=3)
    add_help_button(editor, "Możesz przenieść zapis między RANO i POPO. WM nie tworzy przy tym drugiego aktywnego wpisu.", row=0, column=5, padx=(5, 0))

    label(1, 0, "Pierwsze logowanie:")
    ttk.Entry(editor, textvariable=first_var, width=10).grid(row=1, column=1, sticky="ew", pady=3)
    add_help_button(editor, "Czas w formacie GG:MM. Korekta czasu jest audytowana, więc pierwotna wartość pozostaje w Historii zmian.", row=1, column=2, padx=(5, 12))
    label(1, 3, "Dniówka:")
    ttk.Combobox(editor, textvariable=day_value_var, values=("0", "0.5", "1"), state="readonly", width=9).grid(row=1, column=4, sticky="ew", pady=3)
    add_help_button(editor, "0 = brak dniówki, 0.5 = pół dniówki, 1 = pełna dniówka. L4, NN, UR, UŻ i UB wymagają wartości 0.", row=1, column=5, padx=(5, 0))

    label(2, 0, "Nieobecność:")
    ttk.Combobox(editor, textvariable=absence_var, values=_ABSENCE_CHOICES, state="readonly", width=10).grid(row=2, column=1, sticky="ew", pady=3)
    add_help_button(editor, "Brak oznacza brak nieobecności. ŚW może współistnieć z pracą; L4, NN, UR, UŻ i UB zastępują dniówkę.", row=2, column=2, padx=(5, 12))
    label(2, 3, "Nadgodziny:")
    ot_wrap = ttk.Frame(editor)
    ot_wrap.grid(row=2, column=4, sticky="ew", pady=3)
    ttk.Entry(ot_wrap, textvariable=overtime_var, width=7).pack(side="left")
    ttk.Label(ot_wrap, text=" h  ").pack(side="left")
    ttk.Combobox(ot_wrap, textvariable=overtime_type_var, values=_OT_TYPES, state="readonly", width=12).pack(side="left", fill="x", expand=True)
    add_help_button(editor, "Wpisz 0, aby usunąć zapisane nadgodziny. Typ rozróżnia zwykłe nadgodziny, sobotę, niedzielę i święto.", row=2, column=5, padx=(5, 0))

    label(3, 0, "Powód / uwaga:")
    ttk.Entry(editor, textvariable=note_var).grid(row=3, column=1, columnspan=4, sticky="ew", pady=3)
    add_help_button(editor, "Krótka uwaga trafia do Historii. Jeśli zostawisz puste, WM zapisze automatycznie „Korekta Brygadzisty w Profilu”.", row=3, column=5, padx=(5, 0))
    ttk.Label(editor, textvariable=state_var).grid(row=4, column=0, columnspan=6, sticky="w", pady=(5, 2))

    def new_day() -> None:
        try:
            year, month = map(int, month_var.get().split("-", 1))
            default_day = date.today() if (year, month) == (date.today().year, date.today().month) else date(year, month, 1)
        except Exception:
            default_day = date.today()
        try:
            planned = attendance_service._planned_slot_for_day(login, default_day)
        except Exception:
            planned = None
        day_var.set(default_day.isoformat())
        slot_var.set(planned if planned in attendance_service.VALID_SLOTS else attendance_service.RANO)
        first_var.set("")
        day_value_var.set("1")
        absence_var.set("Brak")
        overtime_var.set("0")
        overtime_type_var.set("zwykle")
        note_var.set("")
        selected_state.update({"source_slot": slot_var.get(), "first": "", "is_new": True})
        state_var.set("Nowy wpis — ustaw dane i użyj Zapisz wszystko.")
        tree.selection_remove(tree.selection())

    def select_row(_event=None) -> None:
        selected = tree.selection()
        if not selected:
            return
        row = rows_by_iid.get(selected[0])
        if not row:
            return
        day_text = str(row.get("date") or "")[:10]
        slot = str(row.get("slot") or attendance_service.RANO)
        first = _first_login_text(row)
        hours, ot_type = _overtime_values(row)
        absence = _absence_for_day(login, day_text, row)
        day_var.set(day_text)
        slot_var.set(slot)
        first_var.set(first)
        day_value_var.set(str(float(row.get("day_value") or 0.0)).rstrip("0").rstrip(".") or "0")
        absence_var.set(_display_absence(absence))
        overtime_var.set(f"{hours:g}")
        overtime_type_var.set(ot_type if ot_type in _OT_TYPES else "zwykle")
        note_var.set(str(row.get("manual_note") or ""))
        selected_state.update({"source_slot": slot, "first": first, "is_new": bool(row.get("synthetic"))})
        state_var.set(f"Stan: {row.get('_shown_status') or '—'} | źródło: {row.get('source') or '—'}")

    tree.bind("<<TreeviewSelect>>", select_row, add="+")
    tree.bind("<Double-1>", select_row, add="+")

    def save_all() -> None:
        try:
            payload = _validate_attendance_edit(
                day_var.get(), slot_var.get(), day_value_var.get(), absence_var.get(), overtime_var.get(), first_var.get()
            )
            year, month = map(int, month_var.get().split("-", 1))
            parsed = date.fromisoformat(payload["date"])
            if (parsed.year, parsed.month) != (year, month):
                raise ValueError("Data musi należeć do aktualnie wybranego miesiąca.")
            payload["overtime_type"] = overtime_type_var.get()
            _save_attendance_edit(
                login,
                payload,
                source_slot=str(selected_state.get("source_slot") or payload["slot"]),
                original_first_login=str(selected_state.get("first") or ""),
                actor=_actor(frame),
                note=note_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Obecność", f"Nie udało się zapisać zmian:\n{exc}", parent=frame.winfo_toplevel())
            return
        if callable(on_saved):
            try:
                on_saved()
            except Exception:
                pass
        refresh(select_key=(payload["date"], payload["slot"]))

    actions = ttk.Frame(editor)
    actions.grid(row=5, column=0, columnspan=6, sticky="ew", pady=(8, 0))
    ttk.Button(actions, text="Nowy dzień", command=new_day).pack(side="left")
    add_help_button(actions, "Tworzy pusty formularz nowego dnia. Nic nie jest zapisywane, dopóki nie użyjesz Zapisz wszystko.").pack(side="left", padx=(5, 12))
    ttk.Button(actions, text="Zapisz wszystko", command=save_all).pack(side="left")
    add_help_button(actions, "Zapisuje razem zmianę, dniówkę, nieobecność, czas wejścia i nadgodziny. Jeśli którykolwiek element jest błędny, WM cofa całą korektę.").pack(side="left", padx=(5, 12))

    def refresh(_event=None, *, select_key: tuple[str, str] | None = None) -> None:
        rows_by_iid.clear()
        tree.delete(*tree.get_children())
        try:
            year, month = map(int, month_var.get().split("-", 1))
        except Exception:
            year, month = date.today().year, date.today().month
        summary = attendance_service.summary_for_month(login, year, month)
        summary_var.set(
            f"Dniówki: {summary.get('days', 0):g}  •  Nadgodziny: {summary.get('overtime_hours', 0):g} h  •  Braki: {summary.get('missing', 0):g}  •  Do decyzji: {summary.get('pending', 0):g}"
        )
        try:
            import profile_employee_editor_finish_runtime as finish
            issues = finish._employee_inconsistencies(login, year, month)
        except Exception:
            issues = []
        issues_var.set(f"⚠ Niezgodności: {len(issues)}" if issues else "✓ Brak niezgodności")

        wanted_iid = None
        for row in attendance_service.month_records(login, year, month):
            item = dict(row)
            day_text = str(item.get("date") or "")[:10]
            absence = _absence_for_day(login, day_text, item)
            status = str(item.get("status") or "")
            labels = {
                attendance_service.STATUS_PRESENT: "Obecny",
                attendance_service.STATUS_PENDING_LATE: "Późne logowanie — do decyzji",
                attendance_service.STATUS_MISSING: "Brak logowania",
                attendance_service.STATUS_EXCUSED: "Nieobecność",
                attendance_service.STATUS_SATURDAY: "Sobota — do decyzji",
                attendance_service.STATUS_PLANNED: "Plan",
            }
            shown_status = labels.get(status, status or "—")
            if absence != "BRAK":
                shown_status = f"{_display_absence(absence)} | {shown_status}"
            hours, ot_type = _overtime_values(item)
            ot_text = f"{hours:g} h {ot_type}" if hours else "—"
            tag = "bad" if status == attendance_service.STATUS_MISSING or absence == "NN" else (
                "warn" if status in {attendance_service.STATUS_PENDING_LATE, attendance_service.STATUS_SATURDAY} else (
                    "muted" if status == attendance_service.STATUS_PLANNED else "ok"
                )
            )
            iid = tree.insert("", "end", values=(
                day_text,
                item.get("slot") or "—",
                _first_login_text(item) or "—",
                shown_status,
                f"{float(item.get('day_value') or 0.0):g}",
                _display_absence(absence),
                ot_text,
                item.get("source") or "—",
            ), tags=(tag,))
            item["_shown_status"] = shown_status
            rows_by_iid[iid] = item
            if select_key == (day_text, str(item.get("slot") or "")):
                wanted_iid = iid
        if wanted_iid:
            tree.selection_set(wanted_iid)
            tree.see(wanted_iid)
            select_row()
        elif not tree.get_children():
            new_day()

    month_box.bind("<<ComboboxSelected>>", lambda _e: (refresh(), new_day()), add="+")
    refresh()


def _show_all_employee_tabs(win, nb: ttk.Notebook) -> None:
    """Nie chowaj Historii/Uprawnień pod kolejnymi przyciskami."""
    try:
        tabs = list(nb.tabs())
    except Exception:
        return
    for tab_id in tabs:
        try:
            text = str(nb.tab(tab_id, "text"))
            if text == "Dane":
                nb.tab(tab_id, text="Podstawowe")
            elif text in {"Historia", "Uprawnienia"}:
                nb.add(tab_id, text=text)
        except Exception:
            pass


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


def _login_from_display(value: Any) -> str:
    shown = str(value or "").strip().casefold()
    if not shown:
        return ""
    for user in workforce_profile_service.list_users(active_only=False):
        login = str(user.get("login") or "").strip()
        display = workforce_profile_service.display_name(user).strip().casefold()
        if login and shown in {login.casefold(), display}:
            return login
    return ""


def _patch_foreman_attendance_entrypoints() -> None:
    """Listy zbiorcze tylko wybierają pracownika; edycja jest w jego Profilu."""
    import gui_profile_foreman as foreman
    cls = foreman.ForemanProfilePanel
    if getattr(cls, "_wm_inline_attendance_workspace", False):
        return
    original = cls._render_attendance

    def render(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        parent = getattr(self, "_tabs", {}).get("Obecność")
        if parent is None:
            return result

        queue_tree = None
        for widget in _walk(parent):
            if not isinstance(widget, ttk.Treeview):
                continue
            try:
                cols = set(widget.cget("columns") or ())
            except Exception:
                cols = set()
            if {"name", "date", "slot", "type", "state"}.issubset(cols):
                queue_tree = widget
                break

        def open_queue_profile(_event=None) -> None:
            if queue_tree is None:
                return
            selected = queue_tree.selection()
            if not selected:
                messagebox.showinfo("Obecność", "Wybierz pracownika z listy.", parent=self.winfo_toplevel())
                return
            values = queue_tree.item(selected[0], "values") or ()
            login = _login_from_display(values[0] if values else "")
            if not login:
                return
            try:
                import profile_foreman_edit_runtime as edit_runtime
                edit_runtime.open_employee_editor(self, login, initial_tab="Obecność", on_saved=self.refresh_data)
            except Exception as exc:
                messagebox.showerror("Profil", f"Nie udało się otworzyć profilu:\n{exc}", parent=self.winfo_toplevel())

        if queue_tree is not None:
            try:
                queue_tree.unbind("<Double-1>")
                queue_tree.bind("<Double-1>", open_queue_profile, add="+")
            except Exception:
                pass

        for widget in list(_walk(parent)):
            if not isinstance(widget, ttk.Button):
                continue
            try:
                text = str(widget.cget("text"))
            except Exception:
                continue
            if text == "Korekta ręczna":
                try:
                    widget.destroy()
                except Exception:
                    pass
            elif text == "Rozstrzygnij zaznaczone":
                widget.configure(text="Edytuj w profilu", command=open_queue_profile)
        return result

    cls._render_attendance = render
    cls._wm_inline_attendance_workspace = True


def _team_detail_row(day_obj: date, row: dict) -> dict:
    item = dict(row)
    login = str(item.get("login") or "")
    selected = None
    try:
        records = attendance_service.month_records(login, day_obj.year, day_obj.month)
    except Exception:
        records = []
    for record in records:
        if str(record.get("date") or "")[:10] != day_obj.isoformat():
            continue
        selected = dict(record)
        if str(record.get("slot") or "") == str(item.get("slot") or ""):
            break
    selected = selected or {}
    hours, ot_type = _overtime_values(selected)
    item.update({
        "first_login": _first_login_text(selected) or "—",
        "day_value": f"{float(selected.get('day_value') or 0.0):g}",
        "overtime": f"{hours:g} h {ot_type}" if hours else "—",
    })
    return item


def _patch_advanced_calendar() -> None:
    """Pracownik zachowuje prosty kalendarz; Brygadzista dostaje jeden widok Zespołu."""
    import gui_profile_calendar as calendar_ui
    import profile_calendar_team_runtime as team_runtime

    cls = calendar_ui.ProfileCalendarPanel
    if getattr(cls, "_wm_single_advanced_calendar", False):
        return
    original_build = cls._build
    original_render = cls._render_calendar

    def build(self):
        original_build(self)
        if not team_runtime._is_foreman():
            return

        mode = getattr(self, "_wm_calendar_mode", None)
        if mode is not None:
            try:
                mode.set("Zespół")
            except Exception:
                pass

        # Usuń stary przełącznik Mój/Zespół — Brygadzista ma jeden kalendarz.
        for child in list(self.winfo_children()):
            try:
                radios = [w for w in child.winfo_children() if isinstance(w, ttk.Radiobutton)]
                names = {str(w.cget("text")) for w in radios}
                if {"Mój", "Zespół"}.issubset(names):
                    child.destroy()
            except Exception:
                pass

        body = getattr(self, "calendar_box", None)
        body = body.master if body is not None else None
        if body is None:
            return
        side = None
        for child in body.winfo_children():
            if child is self.calendar_box:
                continue
            try:
                info = child.grid_info()
                if int(info.get("column", -1)) == 1:
                    side = child
                    break
            except Exception:
                continue
        if side is None:
            return
        for child in side.winfo_children():
            child.destroy()

        self._render_requests = lambda: None
        self._wm_team_day_var = tk.StringVar(value="Szczegóły dnia")
        ttk.Label(side, textvariable=self._wm_team_day_var, style="WM.CardLabel.TLabel").pack(anchor="w")
        help_row = ttk.Frame(side)
        help_row.pack(fill="x", pady=(5, 7))
        ttk.Label(
            help_row,
            text="Kliknij dzień: zmiana, obecność, nieobecność i nadgodziny pojawią się tutaj.",
            wraplength=420,
        ).pack(side="left")
        add_help_button(
            help_row,
            "To jest jeden kalendarz Brygadzisty. Pracownicy nadal mają prosty kalendarz osobisty do składania wniosków urlopowych.",
        ).pack(side="left", padx=(6, 0))

        cols = ("name", "shift", "status", "first", "day", "ot", "pay")
        tree = ttk.Treeview(side, columns=cols, show="headings", height=13)
        for key, label, width, anchor in (
            ("name", "Pracownik", 145, "w"),
            ("shift", "Zmiana", 72, "center"),
            ("status", "Status", 155, "w"),
            ("first", "Wejście", 62, "center"),
            ("day", "Dn.", 45, "center"),
            ("ot", "Nadgodz.", 90, "center"),
            ("pay", "%", 48, "center"),
        ):
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor=anchor, stretch=key in {"name", "status"})
        y = ttk.Scrollbar(side, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=y.set)
        tree.pack(side="left", fill="both", expand=True)
        y.pack(side="right", fill="y")
        tree.tag_configure("bad", foreground="#ef4444")
        tree.tag_configure("warn", foreground="#f59e0b")
        tree.tag_configure("ok", foreground="#22c55e")
        tree.tag_configure("muted", foreground="#A7A9AB")
        self._wm_team_detail_tree = tree
        self._wm_team_detail_rows = {}

        actions = ttk.Frame(side)
        actions.pack(fill="x", side="bottom", pady=(8, 0))

        def open_profile(tab: str) -> None:
            selected = tree.selection()
            if not selected:
                return
            row = self._wm_team_detail_rows.get(selected[0])
            if not row:
                return
            try:
                import profile_foreman_edit_runtime as edit_runtime
                edit_runtime.open_employee_editor(self, row["login"], initial_tab=tab, on_saved=self.refresh)
            except Exception as exc:
                messagebox.showerror("Profil", f"Nie udało się otworzyć profilu:\n{exc}", parent=self.winfo_toplevel())

        ttk.Button(actions, text="Obecność", command=lambda: open_profile("Obecność")).pack(side="left")
        add_help_button(actions, "Otwiera ten sam profil pracownika od razu na pełnej edycji Obecności.").pack(side="left", padx=(4, 10))
        ttk.Button(actions, text="Urlopy", command=lambda: open_profile("Urlopy")).pack(side="left")
        add_help_button(actions, "Otwiera ten sam profil pracownika na zakładce Urlopy. Nie powstaje osobny kalendarz ani okno dnia.").pack(side="left", padx=(4, 0))
        tree.bind("<Double-1>", lambda _e: open_profile("Obecność"), add="+")

        today = date.today()
        self._wm_selected_team_day = today if (self.year, self.month) == (today.year, today.month) else date(self.year, self.month, 1)

    def refresh_day_panel(self) -> None:
        if not team_runtime._is_foreman():
            return
        tree = getattr(self, "_wm_team_detail_tree", None)
        if tree is None:
            return
        selected_day = getattr(self, "_wm_selected_team_day", None)
        if not isinstance(selected_day, date) or (selected_day.year, selected_day.month) != (self.year, self.month):
            selected_day = date(self.year, self.month, 1)
            self._wm_selected_team_day = selected_day
        self._wm_team_day_var.set(f"Zespół — {selected_day.strftime('%d-%m-%Y')}")
        tree.delete(*tree.get_children())
        self._wm_team_detail_rows.clear()
        for base in team_runtime._team_day_rows(selected_day):
            row = _team_detail_row(selected_day, base)
            code = str(row.get("status_code") or "")
            tag = "bad" if code in {"BR", "NN"} else ("warn" if code in {"DEC", "?UR", "ŚW"} else ("muted" if code == "WOLNE" else "ok"))
            iid = tree.insert("", "end", values=(
                row.get("name"), row.get("shift"), row.get("status"), row.get("first_login"),
                row.get("day_value"), row.get("overtime"), row.get("pay_label"),
            ), tags=(tag,))
            self._wm_team_detail_rows[iid] = row

    def select_day(self, day_number: int) -> None:
        self._wm_selected_team_day = date(self.year, self.month, int(day_number))
        refresh_day_panel(self)
        render(self)

    def render(self):
        if team_runtime._is_foreman():
            mode = getattr(self, "_wm_calendar_mode", None)
            if mode is not None:
                try:
                    mode.set("Zespół")
                except Exception:
                    pass
        original_render(self)
        if not team_runtime._is_foreman():
            return
        selected_day = getattr(self, "_wm_selected_team_day", None)
        for child in self.calendar_box.winfo_children():
            if not isinstance(child, tk.Button):
                continue
            try:
                day_number = int(str(child.cget("text")).splitlines()[0])
            except Exception:
                continue
            child.configure(command=lambda d=day_number: select_day(self, d))
            current = date(self.year, self.month, day_number)
            if current == selected_day:
                child.configure(relief="solid", bd=2)
            else:
                child.configure(relief="flat", bd=0)
        refresh_day_panel(self)

    cls._build = build
    cls._render_calendar = render
    cls._wm_single_advanced_calendar = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    # Backend edycji pozostaje istniejący; workspace przejmuje wyłącznie końcowe UI.
    import profile_attendance_finalize_runtime as attendance_final
    import profile_employee_editor_finish_runtime as employee_finish

    attendance_final._build_employee_attendance = _build_employee_attendance
    employee_finish._decorate_employee_attendance = lambda *args, **kwargs: None
    employee_finish._simplify_tabs = _show_all_employee_tabs

    _patch_foreman_attendance_entrypoints()
    _patch_advanced_calendar()
    _INSTALLED = True


__all__ = [
    "_ABSENCE_CHOICES",
    "_build_employee_attendance",
    "_normalize_absence",
    "_save_attendance_edit",
    "_validate_attendance_edit",
    "install",
]
