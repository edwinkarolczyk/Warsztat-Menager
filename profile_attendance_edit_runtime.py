# version: 1.0
"""Edycja zapisanej zmiany i rodzaju dniówki w Profilu WM."""
from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Any, Callable

import profile_attendance_finalize_runtime as final
from services import attendance_service, workforce_profile_service
from ui_context_help import add_help_button

_INSTALLED = False


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
                "Możesz poprawić zmianę już zapisanego dnia. WM przeniesie istniejący wpis zamiast tworzyć drugi rekord.",
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
            text="⚠ Ten dzień ma sprzeczne dane. Wybierz, czy prawidłowa jest nieobecność, czy dniówka.",
            style="WM.Muted.TLabel",
        ).pack(side="left")
        add_help_button(
            warning,
            "Zachowanie nieobecności wyzeruje dniówkę i ustawi właściwy powód. Zapis dniówki anuluje aktywną nieobecność, ale pozostawi ją w Historii.",
        ).pack(side="left", padx=(6, 0))
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
        "Przy ręcznej decyzji wpisz krótki powód. Pozwala to później odtworzyć, dlaczego dniówka lub zmiana zostały poprawione.",
        row=row_no,
        column=2,
        padx=(6, 0),
    )

    row_no += 1
    current_text = str(case.get("decision_label") or final._status_text(case) or "—")
    original_day_text = final._fmt(original_day)
    preview_var = tk.StringVar(value="")
    preview = ttk.Frame(frame)
    preview.grid(row=row_no, column=0, columnspan=3, sticky="ew", pady=(8, 2))
    ttk.Label(preview, text="Podgląd zmiany:", style="WM.Muted.TLabel").pack(side="left")
    ttk.Label(preview, textvariable=preview_var).pack(side="left", padx=(6, 0))
    add_help_button(
        preview,
        "Przed zapisem WM pokazuje zmianę zmiany roboczej i wartości dniówki. Dane zmienią się dopiero po użyciu Zapisz decyzję.",
    ).pack(side="left", padx=(6, 0))

    def refresh_preview(*_args) -> None:
        parts: list[str] = []
        target_slot = str(slot_var.get() or original_slot)
        if target_slot != original_slot:
            parts.append(f"zmiana {original_slot} → {target_slot}")
        if save_day_var.get():
            parts.append(f"dniówka {original_day_text} → {final._fmt(value_var.get())}")
        if ot_var.get():
            parts.append(f"{final._fmt(hours_var.get())} h nadgodzin ({ot_type_var.get()})")
        preview_var.set(f"{current_text} | {' | '.join(parts) if parts else 'bez zmiany'}")

    for var in (slot_var, save_day_var, value_var, ot_var, hours_var, ot_type_var):
        try:
            var.trace_add("write", refresh_preview)
        except Exception:
            pass
    refresh_preview()

    def finish() -> None:
        win.destroy()
        if callable(on_saved):
            on_saved()

    def keep_absence() -> None:
        note = note_var.get().strip()
        if not note:
            messagebox.showinfo("Obecność", "Wpisz powód lub krótką uwagę.", parent=win)
            return
        reason = final._absence_label(case.get("conflict_reason"))
        if reason not in {"L4", "UR", "UŻ", "ŚW", "NN"}:
            messagebox.showerror("Obecność", "Nie udało się ustalić rodzaju nieobecności.", parent=win)
            return
        try:
            attendance_service.set_reason(
                day_var.get(),
                original_slot,
                login,
                final._actor(owner),
                reason,
                datetime.now().astimezone().isoformat(timespec="seconds"),
            )
        except Exception as exc:
            messagebox.showerror("Obecność", f"Nie udało się zachować nieobecności:\n{exc}", parent=win)
            return
        finish()

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
                    day_var.get(),
                    slot_var.get(),
                    login,
                    float(value_var.get()),
                    final._actor(owner),
                    note,
                    replace_absence=replace_absence,
                    original_slot=original_slot,
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
    if case.get("is_conflict"):
        ttk.Button(actions, text="Zachowaj nieobecność", command=keep_absence).pack(side="right", padx=(0, 8))


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
        "Wybierz zapisany dzień. Następnie możesz zmienić jego zmianę RANO/POPO i rodzaj dniówki bez tworzenia drugiego wpisu.",
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
    final._open_case_dialog = _open_case_dialog
    final._manual_correction = _manual_correction
    _INSTALLED = True


__all__ = ["install"]
