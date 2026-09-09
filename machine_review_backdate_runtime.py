# version: 1.1
"""Data wykonania wstecz dla przeglądów maszyn - tylko Brygadzista."""

from __future__ import annotations

import calendar
import datetime as dt
import logging

logger = logging.getLogger(__name__)

_MONTHS_PL = (
    "",
    "Styczeń",
    "Luty",
    "Marzec",
    "Kwiecień",
    "Maj",
    "Czerwiec",
    "Lipiec",
    "Sierpień",
    "Wrzesień",
    "Październik",
    "Listopad",
    "Grudzień",
)
_WEEKDAYS_PL = ("Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd")


def _normalize_role(value: object) -> str:
    try:
        from wm_access import normalize_role_name

        return str(normalize_role_name(str(value or "")) or "").strip().casefold()
    except Exception:
        return str(value or "").strip().casefold()


def _active_role(window) -> str:
    current = window
    while current is not None:
        for attr in ("_wm_rola", "rola", "role", "user_role"):
            try:
                value = getattr(current, attr, "")
            except Exception:
                value = ""
            if str(value or "").strip():
                return _normalize_role(value)
        current = getattr(current, "master", None)

    try:
        from services.profile_service import ProfileService, get_user

        login = ProfileService.ensure_active_user_or_none()
        if login:
            user = get_user(str(login)) or {}
            if isinstance(user, dict):
                return _normalize_role(
                    user.get("rola") or user.get("role") or user.get("ranga")
                )
    except Exception:
        logger.exception("[Maszyny][BACKDATE] Nie udało się odczytać roli użytkownika.")

    return ""


def _walk_widgets(widget):
    yield widget
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        yield from _walk_widgets(child)


def _parse_date(gui_module, raw: str) -> dt.date | None:
    parser = getattr(gui_module, "_parse_schedule_date", None)
    if callable(parser):
        try:
            parsed = parser(raw)
            if isinstance(parsed, dt.datetime):
                return parsed.date()
            if isinstance(parsed, dt.date):
                return parsed
        except Exception:
            pass

    try:
        return dt.date.fromisoformat(str(raw or "").strip())
    except Exception:
        return None


def _format_date(gui_module, value: dt.date) -> str:
    formatter = getattr(gui_module, "_format_machine_review_date", None)
    if callable(formatter):
        try:
            return str(formatter(value))
        except Exception:
            pass
    return value.isoformat()


def _show_warning(gui_module, window, text: str) -> None:
    box = getattr(gui_module, "messagebox", None)
    if box is None:
        return
    try:
        box.showwarning("Data wykonania", text, parent=window)
    except Exception:
        pass


def _open_calendar_picker(window, gui_module, date_var) -> None:
    """Pokaż mały kalendarz bez dodatkowej biblioteki zewnętrznej."""
    ttk = getattr(gui_module, "ttk", None)
    tk_module = getattr(gui_module, "tk", None)
    if ttk is None or tk_module is None:
        return

    base_tk = getattr(tk_module, "_wm_base_tk", tk_module)
    real_toplevel = getattr(base_tk, "Toplevel", None)
    if real_toplevel is None:
        return

    today = dt.date.today()
    selected = _parse_date(gui_module, date_var.get()) or today
    if selected > today:
        selected = today

    picker = real_toplevel(window)
    picker.title("Wybierz datę wykonania")
    picker.transient(window)
    picker.resizable(False, False)

    try:
        x = window.winfo_rootx() + 180
        y = window.winfo_rooty() + 120
        picker.geometry(f"+{x}+{y}")
    except Exception:
        pass

    state = {"year": selected.year, "month": selected.month}

    outer = ttk.Frame(picker, padding=8)
    outer.pack(fill="both", expand=True)

    header = ttk.Frame(outer)
    header.grid(row=0, column=0, columnspan=7, sticky="ew", pady=(0, 6))
    header.columnconfigure(1, weight=1)

    month_var = base_tk.StringVar(master=picker)

    def _set_month(delta: int) -> None:
        year = int(state["year"])
        month = int(state["month"]) + delta
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1

        candidate = dt.date(year, month, 1)
        current_month = dt.date(today.year, today.month, 1)
        if candidate > current_month:
            return

        state["year"] = year
        state["month"] = month
        _render_month()

    prev_button = ttk.Button(header, text="◀", width=3, command=lambda: _set_month(-1))
    prev_button.grid(row=0, column=0, sticky="w")
    ttk.Label(header, textvariable=month_var, anchor="center").grid(
        row=0, column=1, sticky="ew", padx=8
    )
    next_button = ttk.Button(header, text="▶", width=3, command=lambda: _set_month(1))
    next_button.grid(row=0, column=2, sticky="e")

    for column, label in enumerate(_WEEKDAYS_PL):
        ttk.Label(outer, text=label, anchor="center", width=4).grid(
            row=1, column=column, padx=1, pady=(0, 2)
        )

    day_frame = ttk.Frame(outer)
    day_frame.grid(row=2, column=0, columnspan=7)

    def _choose(day: int) -> None:
        chosen = dt.date(int(state["year"]), int(state["month"]), int(day))
        if chosen > today:
            return
        date_var.set(_format_date(gui_module, chosen))
        picker.destroy()

    def _render_month() -> None:
        for child in day_frame.winfo_children():
            child.destroy()

        year = int(state["year"])
        month = int(state["month"])
        month_var.set(f"{_MONTHS_PL[month]} {year}")

        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
        for row_idx, week in enumerate(weeks):
            for col_idx, day in enumerate(week):
                if not day:
                    ttk.Label(day_frame, text="", width=4).grid(
                        row=row_idx, column=col_idx, padx=1, pady=1
                    )
                    continue

                value = dt.date(year, month, day)
                btn = ttk.Button(
                    day_frame,
                    text=str(day),
                    width=4,
                    command=lambda d=day: _choose(d),
                )
                btn.grid(row=row_idx, column=col_idx, padx=1, pady=1)
                if value > today:
                    try:
                        btn.state(["disabled"])
                    except Exception:
                        pass

        current_month = dt.date(today.year, today.month, 1)
        shown_month = dt.date(year, month, 1)
        try:
            if shown_month >= current_month:
                next_button.state(["disabled"])
            else:
                next_button.state(["!disabled"])
        except Exception:
            pass

    _render_month()

    ttk.Button(
        outer,
        text="Dzisiaj",
        command=lambda: (
            date_var.set(_format_date(gui_module, today)),
            picker.destroy(),
        ),
    ).grid(row=3, column=0, columnspan=7, pady=(8, 0))

    try:
        picker.grab_set()
        picker.focus_set()
    except Exception:
        pass


def _decorate_complete_dialog(window, gui_module) -> None:
    if getattr(window, "_wm_backdate_decorated", False):
        return

    try:
        title = str(window.title() or "")
    except Exception:
        return
    if "Oznacz przegląd / serwis jako wykonany" not in title:
        return

    role = _active_role(window)
    if role != "brygadzista":
        window._wm_backdate_decorated = True
        return

    button = None
    for child in _walk_widgets(window):
        try:
            if str(child.cget("text") or "") == "Zapisz wykonanie":
                button = child
                break
        except Exception:
            continue
    if button is None:
        return

    try:
        original_tcl_command = str(button.cget("command") or "")
    except Exception:
        original_tcl_command = ""
    if not original_tcl_command:
        return

    ttk = getattr(gui_module, "ttk", None)
    tk = getattr(gui_module, "tk", None)
    if ttk is None or tk is None:
        return

    buttons_frame = getattr(button, "master", None)
    form = getattr(buttons_frame, "master", None)
    if form is None:
        return

    try:
        buttons_frame.grid_configure(row=4)
    except Exception:
        return

    today = dt.date.today()
    date_var = tk.StringVar(
        master=window,
        value=_format_date(gui_module, today),
    )

    ttk.Label(form, text="Data wykonania:").grid(
        row=2, column=0, sticky="e", padx=4, pady=(6, 2)
    )

    date_row = ttk.Frame(form)
    date_row.grid(row=2, column=1, sticky="w", padx=4, pady=(6, 2))
    date_entry = ttk.Entry(date_row, textvariable=date_var, width=20)
    date_entry.pack(side="left")
    ttk.Button(
        date_row,
        text="📅",
        width=3,
        command=lambda: _open_calendar_picker(window, gui_module, date_var),
    ).pack(side="left", padx=(4, 0))

    ttk.Label(
        form,
        text="Tylko Brygadzista: dzisiejsza lub wcześniejsza data.",
    ).grid(row=3, column=1, sticky="w", padx=4, pady=(0, 4))

    original_now = getattr(gui_module, "_machine_now_iso", None)

    def _save_with_selected_date() -> None:
        selected_date = _parse_date(gui_module, date_var.get())
        if selected_date is None:
            _show_warning(gui_module, window, "Podaj poprawną datę wykonania.")
            return
        if selected_date > dt.date.today():
            _show_warning(
                gui_module,
                window,
                "Nie można ustawić daty wykonania w przyszłości.",
            )
            return

        now = dt.datetime.now().replace(microsecond=0)
        performed_at = dt.datetime.combine(selected_date, now.time()).isoformat()

        if callable(original_now):
            setattr(gui_module, "_machine_now_iso", lambda: performed_at)
        try:
            button.tk.call(original_tcl_command)
        finally:
            if callable(original_now):
                setattr(gui_module, "_machine_now_iso", original_now)

    button.configure(command=_save_with_selected_date)
    button._wm_backdate_command_wrapped = True
    window._wm_backdate_decorated = True


def install_machine_review_backdate(gui_module) -> bool:
    """Dodaj pole daty wykonania wyłącznie użytkownikowi z rolą Brygadzista."""
    if gui_module is None:
        return False

    tk_module = getattr(gui_module, "tk", None)
    if tk_module is None:
        return False
    if getattr(tk_module, "_wm_machine_backdate_proxy", False):
        return True

    real_toplevel = getattr(tk_module, "Toplevel", None)
    if real_toplevel is None:
        return False

    class _BackdateAwareToplevel(real_toplevel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            def _decorate() -> None:
                try:
                    _decorate_complete_dialog(self, gui_module)
                except Exception:
                    logger.exception(
                        "[Maszyny][BACKDATE] Błąd dekorowania okna wykonania."
                    )

            try:
                self.after_idle(_decorate)
            except Exception:
                _decorate()

    class _TkBackdateProxy:
        _wm_machine_backdate_proxy = True
        _wm_docx_runtime_proxy = bool(
            getattr(tk_module, "_wm_docx_runtime_proxy", False)
        )
        _wm_base_tk = getattr(tk_module, "_wm_base_tk", tk_module)
        Toplevel = _BackdateAwareToplevel

        def __getattr__(self, name: str):
            return getattr(tk_module, name)

    gui_module.tk = _TkBackdateProxy()
    return True


__all__ = ["install_machine_review_backdate"]
