# version: 1.0
"""Data wykonania wstecz dla przeglądów maszyn - tylko Brygadzista."""

from __future__ import annotations

import datetime as dt
import logging

logger = logging.getLogger(__name__)


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
    date_entry = ttk.Entry(form, textvariable=date_var, width=24)
    date_entry.grid(row=2, column=1, sticky="w", padx=4, pady=(6, 2))
    ttk.Label(
        form,
        text="Tylko Brygadzista: dzisiejsza lub wcześniejsza data.",
    ).grid(row=3, column=1, sticky="w", padx=4, pady=(0, 4))

    original_now = getattr(gui_module, "_machine_now_iso", None)

    def _save_with_selected_date() -> None:
        selected = _parse_date(gui_module, date_var.get())
        if selected is None:
            _show_warning(gui_module, window, "Podaj poprawną datę wykonania.")
            return
        if selected > dt.date.today():
            _show_warning(
                gui_module,
                window,
                "Nie można ustawić daty wykonania w przyszłości.",
            )
            return

        now = dt.datetime.now().replace(microsecond=0)
        performed_at = dt.datetime.combine(selected, now.time()).isoformat()

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
