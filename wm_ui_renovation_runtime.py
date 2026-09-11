# version: 1.0
"""Kosmetyczny pakiet remontowy WM 1.0.9.

Zakres jest celowo mały:
- edycja Obecności pozostaje otwarta po zapisie,
- tabela Obecności obsługuje wielozaznaczenie i wspólną korektę,
- szerokości kolumn są czytelniejsze,
- główny panel pokazuje informację o trwającym remoncie WM,
- komunikat można wyłączyć w Ustawienia -> Ogólne.

Nie zmienia modelu danych ani istniejących reguł walidacji Obecności.
"""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any, Callable

from ui_context_help import add_help_button

NOTICE_KEY = "ui.show_renovation_notice"
NOTICE_DEFAULT = True
NOTICE_TEXT = (
    "Program jest w trakcie remontu. Nie wszystko może jeszcze działać idealnie.\n\n"
    "Proszę o opinię w module „Wyślij opinię”. Każda opinia się liczy — "
    "zła czy dobra. Robimy to dla wspólnego dobra.\n\n"
    "Edwin K."
)

_SETTINGS_PATCHED = False
_PROFILE_HOOK_PATCHED = False


def _coerce_bool(value: Any, default: bool = NOTICE_DEFAULT) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, str):
        raw = value.strip().casefold()
        if raw in {"1", "true", "yes", "y", "on", "tak"}:
            return True
        if raw in {"0", "false", "no", "n", "off", "nie"}:
            return False
        return bool(default)
    return bool(value)


def _walk(widget) -> list[Any]:
    out: list[Any] = []
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        out.append(child)
        out.extend(_walk(child))
    return out


def _widget_value(widget) -> str:
    try:
        return str(widget.get())
    except Exception:
        return ""


def _grid_widget(parent, row: int, column: int, cls=None):
    for widget in parent.winfo_children():
        if cls is not None and not isinstance(widget, cls):
            continue
        try:
            info = widget.grid_info()
            if int(info.get("row", -1)) == row and int(info.get("column", -1)) == column:
                return widget
        except Exception:
            pass
    return None


def _find_attendance_editor(frame):
    for widget in _walk(frame):
        if not isinstance(widget, ttk.LabelFrame):
            continue
        try:
            if str(widget.cget("text")) == "Edycja zaznaczonego dnia":
                return widget
        except Exception:
            pass
    return None


def _find_attendance_tree(frame):
    for widget in _walk(frame):
        if not isinstance(widget, ttk.Treeview):
            continue
        try:
            columns = set(widget.cget("columns") or ())
        except Exception:
            columns = set()
        if {"date", "slot", "day", "absence", "ot"}.issubset(columns):
            return widget
    return None


def _find_button(parent, text: str):
    for widget in _walk(parent):
        if not isinstance(widget, ttk.Button):
            continue
        try:
            if str(widget.cget("text")) == text:
                return widget
        except Exception:
            pass
    return None


def _state_label(editor):
    for widget in editor.winfo_children():
        if not isinstance(widget, ttk.Label):
            continue
        try:
            info = widget.grid_info()
            if int(info.get("row", -1)) == 4:
                return widget
        except Exception:
            pass
    return None


def _set_label_variable(label, text: str) -> None:
    if label is None:
        return
    try:
        variable = str(label.cget("textvariable") or "")
        if variable:
            label.setvar(variable, text)
        else:
            label.configure(text=text)
    except Exception:
        pass


def _clean_first_login(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text in {"", "—", "-"} else text


def _parse_overtime_text(value: Any) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text or text in {"—", "-"}:
        return "0", "zwykle"
    parts = text.replace(" h ", " ").replace("h ", " ").split()
    hours = parts[0] if parts else "0"
    kind = parts[1] if len(parts) > 1 else "zwykle"
    return hours, kind


def _merge_batch_values(
    base: dict[str, Any],
    edits: dict[str, Any],
    dirty_fields: set[str],
) -> dict[str, Any]:
    """Nałóż na dzień tylko pola jawnie zmienione w trybie grupowym."""
    result = dict(base)
    for key in dirty_fields:
        if key in edits:
            result[key] = edits[key]
    return result


def _tree_rows(tree, selected: tuple[str, ...] | list[str]) -> list[dict[str, str]]:
    try:
        columns = list(tree.cget("columns") or ())
    except Exception:
        return []
    out: list[dict[str, str]] = []
    for iid in selected:
        try:
            values = list(tree.item(iid, "values") or ())
        except Exception:
            continue
        row = {
            str(column): str(values[index]) if index < len(values) else ""
            for index, column in enumerate(columns)
        }
        row["_iid"] = str(iid)
        out.append(row)
    return out


def _batch_base_values(login: str, row: dict[str, str]) -> dict[str, Any]:
    from services import attendance_service
    import profile_foreman_workspace_runtime as workspace

    day_text = str(row.get("date") or "")[:10]
    source_slot = str(row.get("slot") or attendance_service.RANO)
    record: dict[str, Any] = {}
    try:
        parsed = date.fromisoformat(day_text)
        for item in attendance_service.month_records(login, parsed.year, parsed.month):
            if str(item.get("date") or "")[:10] != day_text:
                continue
            if str(item.get("slot") or "") != source_slot:
                continue
            record = dict(item)
            break
    except Exception:
        record = {}

    try:
        day_value = f"{float(record.get('day_value', row.get('day') or 0)):g}"
    except Exception:
        day_value = str(row.get("day") or "0")
    try:
        absence = workspace._display_absence(
            workspace._absence_for_day(login, day_text, record)
        )
    except Exception:
        absence = str(row.get("absence") or "Brak")
    try:
        hours, overtime_type = workspace._overtime_values(record)
        overtime = f"{hours:g}"
    except Exception:
        overtime, overtime_type = _parse_overtime_text(row.get("ot"))

    return {
        "date": day_text,
        "source_slot": source_slot,
        "slot": source_slot,
        "first_login": _clean_first_login(row.get("first")),
        "day_value": day_value,
        "absence": absence,
        "overtime": overtime,
        "overtime_type": overtime_type,
        "note": str(record.get("manual_note") or ""),
    }


def _batch_specs(
    login: str,
    rows: list[dict[str, str]],
    edits: dict[str, Any],
    dirty_fields: set[str],
) -> list[dict[str, Any]]:
    """Przygotuj korekty wielu dni, zachowując niezmienione wartości każdego dnia."""
    import profile_foreman_workspace_runtime as workspace

    specs: list[dict[str, Any]] = []
    for row in rows:
        base = _batch_base_values(login, row)
        merged = _merge_batch_values(base, edits, dirty_fields)
        payload = workspace._validate_attendance_edit(
            base["date"],
            merged["slot"],
            merged["day_value"],
            merged["absence"],
            merged["overtime"],
            base["first_login"],
        )
        payload["overtime_type"] = merged["overtime_type"]
        specs.append(
            {
                "payload": payload,
                "source_slot": base["source_slot"],
                "original_first_login": base["first_login"],
                "note": merged.get("note") or "",
            }
        )
    return specs


def _editor_controls(editor) -> dict[str, Any]:
    slot = _grid_widget(editor, 0, 4, ttk.Combobox)
    day_value = _grid_widget(editor, 1, 4, ttk.Combobox)
    absence = _grid_widget(editor, 2, 1, ttk.Combobox)
    note = _grid_widget(editor, 3, 1, ttk.Entry)
    overtime_wrap = _grid_widget(editor, 2, 4, ttk.Frame)
    overtime = None
    overtime_type = None
    if overtime_wrap is not None:
        for widget in overtime_wrap.winfo_children():
            if isinstance(widget, ttk.Entry) and overtime is None:
                overtime = widget
            elif isinstance(widget, ttk.Combobox) and overtime_type is None:
                overtime_type = widget
    return {
        "slot": slot,
        "day_value": day_value,
        "absence": absence,
        "overtime": overtime,
        "overtime_type": overtime_type,
        "note": note,
    }


def _offday_override(editor) -> bool:
    for widget in _walk(editor):
        if not isinstance(widget, ttk.Checkbutton):
            continue
        try:
            if str(widget.cget("text")) != "Praca w dniu wolnym":
                continue
            variable = str(widget.cget("variable") or "")
            return bool(widget.getvar(variable)) if variable else False
        except Exception:
            return False
    return False


def _apply_attendance_widths(tree) -> None:
    widths = {
        "date": (102, 86, False),
        "weekday": (62, 52, False),
        "slot": (76, 66, False),
        "first": (102, 88, False),
        "status": (250, 180, True),
        "day": (68, 58, False),
        "absence": (100, 82, False),
        "ot": (132, 96, False),
        "source": (112, 90, False),
    }
    try:
        columns = list(tree.cget("columns") or ())
    except Exception:
        return
    for key in columns:
        if key not in widths:
            continue
        width, minimum, stretch = widths[key]
        try:
            tree.column(key, width=width, minwidth=minimum, stretch=stretch)
        except Exception:
            pass


def _reselect_after_rebuild(frame, wanted: set[tuple[str, str]]) -> None:
    tree = _find_attendance_tree(frame)
    if tree is None:
        return
    try:
        columns = list(tree.cget("columns") or ())
        date_idx = columns.index("date")
        slot_idx = columns.index("slot")
    except Exception:
        return
    selected: list[str] = []
    for iid in tree.get_children(""):
        try:
            values = tree.item(iid, "values") or ()
            key = (str(values[date_idx])[:10], str(values[slot_idx]))
        except Exception:
            continue
        if key in wanted:
            selected.append(iid)
    if selected:
        try:
            tree.selection_set(selected)
            tree.see(selected[0])
        except Exception:
            pass


def _decorate_attendance_batch(frame, login: str) -> None:
    editor = _find_attendance_editor(frame)
    tree = _find_attendance_tree(frame)
    if editor is None or tree is None:
        return
    if getattr(editor, "_wm_renovation_batch_v1", False):
        return

    save_button = _find_button(editor, "Zapisz wszystko")
    if save_button is None:
        return
    original_command = str(save_button.cget("command") or "")
    if not original_command:
        return

    try:
        tree.configure(selectmode="extended")
    except Exception:
        pass
    try:
        tree.after_idle(lambda current=tree: _apply_attendance_widths(current))
    except Exception:
        _apply_attendance_widths(tree)

    controls = _editor_controls(editor)
    dirty_fields: set[str] = set()

    def mark(field: str):
        def _handler(_event=None) -> None:
            if len(tree.selection()) > 1:
                dirty_fields.add(field)
        return _handler

    for field in ("slot", "day_value", "absence", "overtime_type"):
        widget = controls.get(field)
        if widget is not None:
            widget.bind("<<ComboboxSelected>>", mark(field), add="+")
    for field in ("overtime", "note"):
        widget = controls.get(field)
        if widget is not None:
            widget.bind("<KeyRelease>", mark(field), add="+")

    status = _state_label(editor)

    def selection_changed(_event=None) -> None:
        dirty_fields.clear()
        count = len(tree.selection())
        if count > 1:
            _set_label_variable(
                status,
                f"Zaznaczono {count} dni. Zmień wybrane pola i kliknij „Zapisz wszystko”; "
                "daty i pierwsze logowanie pozostaną bez zmian.",
            )

    tree.bind("<<TreeviewSelect>>", selection_changed, add="+")

    try:
        actions = save_button.master
        ttk.Label(actions, text="Kilka dni: Ctrl/Shift + klik").pack(
            side="left", padx=(8, 4)
        )
        add_help_button(
            actions,
            "Zaznacz kilka dni klawiszem Ctrl lub Shift, a potem zmień tylko pola, które mają dostać wspólną wartość. "
            "WM zachowa osobne daty i pierwsze logowanie każdego zaznaczonego dnia.",
        ).pack(side="left", padx=(0, 4))
    except Exception:
        pass

    def save_batch_or_single() -> None:
        selected = tuple(tree.selection())
        if len(selected) <= 1:
            save_button.tk.call(original_command)
            return
        if not dirty_fields:
            messagebox.showinfo(
                "Obecność",
                "Zaznaczono kilka dni, ale nie zmieniono żadnego pola. "
                "Wybierz wspólną wartość i spróbuj ponownie.",
                parent=frame.winfo_toplevel(),
            )
            return

        rows = _tree_rows(tree, selected)
        edits = {
            key: _widget_value(widget)
            for key, widget in controls.items()
            if widget is not None
        }
        try:
            specs = _batch_specs(login, rows, edits, set(dirty_fields))
            target_keys = [
                (str(spec["payload"]["date"]), str(spec["payload"]["slot"]))
                for spec in specs
            ]
            if len(target_keys) != len(set(target_keys)):
                raise ValueError(
                    "Dwa zaznaczone wpisy tego samego dnia nie mogą zostać przeniesione "
                    "na tę samą zmianę jednocześnie."
                )

            import profile_foreman_workspace_runtime as workspace
            try:
                import profile_workday_policy_runtime as policy
            except Exception:
                policy = None

            allow_offday = _offday_override(editor)
            policy_key = None
            previous = object()
            previous_value: Any = previous
            if policy is not None:
                try:
                    policy_key = policy._key(login)
                    previous_value = policy._ACTIVE_OVERRIDE.get(policy_key, previous)
                    policy._ACTIVE_OVERRIDE[policy_key] = allow_offday
                    for spec in specs:
                        policy._ensure_allowed(
                            login,
                            spec["payload"],
                            allow_offday=allow_offday,
                        )
                except Exception:
                    if policy_key is not None:
                        if previous_value is previous:
                            policy._ACTIVE_OVERRIDE.pop(policy_key, None)
                        else:
                            policy._ACTIVE_OVERRIDE[policy_key] = previous_value
                    raise

            try:
                actor = workspace._actor(frame)
                for spec in specs:
                    workspace._save_attendance_edit(
                        login,
                        spec["payload"],
                        source_slot=spec["source_slot"],
                        original_first_login=spec["original_first_login"],
                        actor=actor,
                        note=spec["note"],
                    )
            finally:
                if policy is not None and policy_key is not None:
                    if previous_value is previous:
                        policy._ACTIVE_OVERRIDE.pop(policy_key, None)
                    else:
                        policy._ACTIVE_OVERRIDE[policy_key] = previous_value
        except Exception as exc:
            messagebox.showerror(
                "Obecność",
                f"Nie udało się zapisać zaznaczonych dni:\n{exc}",
                parent=frame.winfo_toplevel(),
            )
            return

        wanted = {
            (str(spec["payload"]["date"]), str(spec["payload"]["slot"]))
            for spec in specs
        }
        try:
            import profile_attendance_finalize_runtime as attendance_final
            attendance_final._build_employee_attendance(
                frame,
                login,
                on_saved=None,
            )
            frame.after_idle(
                lambda current=frame, keys=wanted: _reselect_after_rebuild(
                    current, keys
                )
            )
        except Exception:
            pass

    save_button.configure(command=save_batch_or_single)
    editor._wm_renovation_batch_v1 = True


def _wrap_attendance_builder(base: Callable):
    """Nie propaguj zapisu Obecności do przebudowy okna nadrzędnego."""
    if getattr(base, "_wm_renovation_builder_v1", False):
        return base

    def build(frame, login: str, *, on_saved=None) -> None:
        base(frame, login, on_saved=None)
        _decorate_attendance_batch(frame, login)

    build._wm_renovation_builder_v1 = True
    build._wm_renovation_base = base
    return build


def _install_attendance_ui() -> None:
    try:
        import profile_attendance_finalize_runtime as attendance_final
        import profile_foreman_workspace_runtime as workspace
    except Exception:
        return

    current = workspace._build_employee_attendance
    wrapped = _wrap_attendance_builder(current)
    workspace._build_employee_attendance = wrapped
    attendance_final._build_employee_attendance = wrapped


def _patch_profile_extension_loader() -> None:
    global _PROFILE_HOOK_PATCHED
    if _PROFILE_HOOK_PATCHED:
        return
    try:
        import profile_admin_foreman_runtime as profile_admin
    except Exception:
        return
    original = profile_admin._install_workforce_extensions
    if getattr(original, "_wm_renovation_loader_v1", False):
        _PROFILE_HOOK_PATCHED = True
        return

    def install_extensions() -> None:
        original()
        _install_attendance_ui()

    install_extensions._wm_renovation_loader_v1 = True
    profile_admin._install_workforce_extensions = install_extensions
    _PROFILE_HOOK_PATCHED = True


def _notice_enabled() -> bool:
    try:
        from start import CONFIG_MANAGER
        return _coerce_bool(CONFIG_MANAGER.get(NOTICE_KEY, NOTICE_DEFAULT))
    except Exception:
        return NOTICE_DEFAULT


def _find_feedback_button(root):
    for widget in _walk(root):
        if not isinstance(widget, ttk.Button):
            continue
        try:
            text = str(widget.cget("text") or "")
            state = str(widget.cget("state") or "normal")
        except Exception:
            continue
        if text.startswith("Wyślij opinię") and state != "disabled":
            return widget
    return None


def _show_notice(root) -> None:
    if getattr(root, "_wm_renovation_notice_shown", False):
        return
    try:
        login = str(getattr(root, "active_login", "") or "").strip().casefold()
    except Exception:
        login = ""
    if login in {"", "gość", "gosc", "guest"}:
        return
    if not _notice_enabled():
        return

    root._wm_renovation_notice_shown = True
    win = tk.Toplevel(root)
    win.title("Warsztat Menager — remont programu")
    win.resizable(False, False)
    try:
        win.transient(root)
    except Exception:
        pass

    body = ttk.Frame(win, padding=18)
    body.pack(fill="both", expand=True)
    ttk.Label(
        body,
        text="Warsztat Menager — program w trakcie remontu",
        font=("TkDefaultFont", 12, "bold"),
    ).pack(anchor="w", pady=(0, 12))
    ttk.Label(
        body,
        text=NOTICE_TEXT,
        justify="left",
        wraplength=520,
    ).pack(anchor="w")
    ttk.Label(
        body,
        text="Ten komunikat możesz wyłączyć w Ustawienia → Ogólne.",
    ).pack(anchor="w", pady=(12, 0))

    actions = ttk.Frame(body)
    actions.pack(fill="x", pady=(16, 0))

    def open_feedback() -> None:
        button = _find_feedback_button(root)
        if button is None:
            messagebox.showinfo(
                "Wyślij opinię",
                "Otwórz moduł „Wyślij opinię” z lewego menu.",
                parent=win,
            )
            return
        try:
            win.destroy()
        finally:
            button.invoke()

    ttk.Button(
        actions,
        text="Wyślij opinię",
        command=open_feedback,
    ).pack(side="left")
    add_help_button(
        actions,
        "Otwiera istniejący formularz „Wyślij opinię”, więc opinia trafia dokładnie w to samo miejsce co dotychczas. "
        "Komunikat o remoncie można wyłączyć w Ustawieniach.",
    ).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Zamknij", command=win.destroy).pack(side="right")

    try:
        win.update_idletasks()
        x = root.winfo_rootx() + max(0, (root.winfo_width() - win.winfo_width()) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - win.winfo_height()) // 3)
        win.geometry(f"+{x}+{y}")
        win.lift()
    except Exception:
        pass


def _patch_settings() -> None:
    global _SETTINGS_PATCHED
    if _SETTINGS_PATCHED:
        return
    try:
        import gui_settings
    except Exception:
        return
    cls = gui_settings.SettingsPanel
    original = cls._build_ui
    if getattr(original, "_wm_renovation_settings_v1", False):
        _SETTINGS_PATCHED = True
        return

    def build_ui(self) -> None:
        original(self)
        parent = getattr(self, "_general_container", None)
        if parent is None:
            return
        box = ttk.LabelFrame(parent, text="Remont Warsztat Menager", padding=10)
        box.pack(fill="x", padx=8, pady=8)
        variable = tk.BooleanVar(
            master=self.master,
            value=_coerce_bool(self.cfg.get(NOTICE_KEY, NOTICE_DEFAULT)),
        )

        def save_notice_setting() -> None:
            try:
                self.cfg.set(NOTICE_KEY, bool(variable.get()))
                self.cfg.save_all()
            except Exception as exc:
                messagebox.showerror(
                    "Ustawienia",
                    f"Nie udało się zapisać ustawienia:\n{exc}",
                    parent=self.master,
                )
                return

        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Checkbutton(
            row,
            text="Pokazuj komunikat o trwającym remoncie WM po zalogowaniu",
            variable=variable,
            command=save_notice_setting,
        ).pack(side="left")
        add_help_button(
            row,
            "Po wyłączeniu komunikat o remoncie nie będzie pojawiał się przy kolejnych uruchomieniach. "
            "Nie wpływa to na moduł „Wyślij opinię” ani na działanie programu.",
        ).pack(side="left", padx=(6, 0))
        ttk.Label(
            box,
            text="Ustawienie działa tylko na komunikat startowy; sam moduł opinii pozostaje dostępny.",
        ).pack(anchor="w", pady=(6, 0))
        self._wm_renovation_notice_var = variable

    build_ui._wm_renovation_settings_v1 = True
    cls._build_ui = build_ui
    _SETTINGS_PATCHED = True


def install(root) -> None:
    """Dopnij kosmetyczny pakiet remontowy do gotowego głównego panelu."""
    _patch_profile_extension_loader()
    _install_attendance_ui()
    _patch_settings()
    try:
        root.after_idle(lambda current=root: _show_notice(current))
    except Exception:
        _show_notice(root)


__all__ = [
    "NOTICE_DEFAULT",
    "NOTICE_KEY",
    "NOTICE_TEXT",
    "_coerce_bool",
    "_merge_batch_values",
    "_wrap_attendance_builder",
    "install",
]
