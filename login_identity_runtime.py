# version: 1.1
"""Spójne logowanie użytkownika po samym PIN/haśle w aktywnym panelu WM.

Runtime dotyczy osadzonego logowania z panelu Gościa:
- nie wymaga wyboru loginu,
- rozpoznaje jednoznacznie aktywnego użytkownika po PIN/haśle,
- zapisuje aktywną sesję, ostatnie logowanie i ewidencję Obecności,
- po zalogowaniu pokazuje czytelną informację o aktywnym użytkowniku,
- uruchamia istniejące podsumowanie zmian od poprzedniego logowania,
- pole PIN jest osadzone w nagłówku obok przycisku Zaloguj,
- szybki wybór Motywu jest ukryty z nagłówka.
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime, timezone
from tkinter import messagebox, ttk
from typing import Any

logger = logging.getLogger(__name__)

_GUESTS = {"", "guest", "gość", "gosc", "niezalogowany"}
_INSTALLED = False


def _profile_active(profile: dict[str, Any]) -> bool:
    active = profile.get("active")
    if isinstance(active, bool) and not active:
        return False
    if isinstance(active, str) and active.strip().casefold() in {
        "0",
        "false",
        "no",
        "nie",
        "inactive",
    }:
        return False
    status = str(profile.get("status") or "").strip().casefold()
    return status not in {
        "nieaktywny",
        "zablokowany",
        "dezaktywowany",
        "inactive",
    }


def _resolve_users_by_secret(secret: str) -> list[dict[str, Any]]:
    """Zwróć aktywnych użytkowników pasujących do PIN/hasła."""
    secret = str(secret or "").strip()
    if not secret:
        return []

    try:
        import gui_logowanie
        profiles = gui_logowanie._load_profiles()
    except Exception:
        logger.exception("[LOGIN] Nie udało się wczytać profili do identyfikacji PIN.")
        return []

    matches: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in profiles or []:
        if not isinstance(raw, dict) or not _profile_active(raw):
            continue
        login = str(raw.get("login") or "").strip()
        if not login:
            continue

        user = None
        try:
            user = gui_logowanie.authenticate(login.casefold(), secret)
        except Exception:
            user = None

        if user is None:
            stored_pin = str(raw.get("pin") or "").strip()
            stored_password = str(raw.get("haslo") or "").strip()
            if secret == stored_pin or secret == stored_password:
                user = dict(raw)

        if not isinstance(user, dict):
            continue

        final_login = str(user.get("login") or login).strip()
        key = final_login.casefold()
        if not final_login or key in seen:
            continue
        seen.add(key)

        merged = dict(raw)
        merged.update(user)
        merged["login"] = final_login
        matches.append(merged)

    return matches


def _persist_successful_login(login: str) -> None:
    """Zapisz kanoniczne ślady udanego logowania bez blokowania wejścia do WM."""
    login = str(login or "").strip()
    if not login:
        return

    try:
        from services.profile_service import ProfileService
        ProfileService.set_active_user(login)
    except Exception:
        logger.exception("[LOGIN] Nie udało się ustawić aktywnego użytkownika.")

    try:
        from config_manager import ConfigManager
        cfg = ConfigManager()
        try:
            cfg.set("ostatni_uzytkownik", login, who="logowanie")
        except TypeError:
            cfg.set("ostatni_uzytkownik", login)
        if hasattr(cfg, "save_all"):
            cfg.save_all()
        else:
            cfg.save()
    except Exception:
        logger.exception("[LOGIN] Nie udało się zapisać ostatniego użytkownika.")

    now = datetime.now()
    try:
        import gui_logowanie
        slot = gui_logowanie._slot_now(now)
        if slot in ("RANO", "POPO"):
            gui_logowanie.attendance_utils.mark_login(
                now.date().isoformat(),
                slot,
                login,
                now.isoformat(timespec="seconds"),
            )
    except Exception:
        logger.exception("[LOGIN] Nie udało się zapisać logowania w Obecności.")

    try:
        import gui_panel
        gui_panel._save_last_visit(login, datetime.now(timezone.utc))
    except Exception:
        logger.exception("[LOGIN] Nie udało się zapisać ostatniej wizyty profilu.")


def _schedule_summary(root, login: str) -> None:
    def _show() -> None:
        try:
            from login_summary_runtime import show_login_summary
            show_login_summary(root, login)
        except Exception:
            logger.exception("[LOGIN_SUMMARY] Nie udało się pokazać podsumowania.")

    try:
        root.after_idle(_show)
    except Exception:
        _show()


def _validate_login_secret(secret: str, *, parent=None) -> tuple[str, str] | None:
    secret = str(secret or "").strip()
    if not secret:
        return None

    matches = _resolve_users_by_secret(secret)
    if not matches:
        messagebox.showerror(
            "Błąd",
            "Nieprawidłowy PIN lub hasło.",
            parent=parent,
        )
        return None

    if len(matches) > 1:
        messagebox.showerror(
            "Błąd logowania",
            "Ten PIN / hasło jest przypisany do więcej niż jednego aktywnego "
            "użytkownika. Ustaw unikalne dane logowania użytkowników.",
            parent=parent,
        )
        return None

    user = matches[0]
    login = str(user.get("login") or "").strip()
    role = str(user.get("rola") or user.get("role") or "pracownik").strip()
    status = str(user.get("status") or "").strip().casefold()

    if user.get("nieobecny") or status in {"nieobecny", "urlop", "l4"}:
        messagebox.showerror(
            "Błąd",
            "Użytkownik oznaczony jako nieobecny.",
            parent=parent,
        )
        return None

    return login, role


def _open_pin_login_popup(parent, on_success):
    """Fallback popupu dla starszych wejść; główny panel używa pola w nagłówku."""
    popup = tk.Toplevel(parent)
    popup.title("Logowanie")
    popup.transient(parent)
    popup.grab_set()
    popup.resizable(False, False)

    frame = ttk.Frame(popup, padding=14)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="Podaj PIN / hasło",
        style="WM.H2.TLabel",
    ).grid(row=0, column=0, sticky="w", pady=(0, 4))
    ttk.Label(
        frame,
        text="WM rozpozna użytkownika automatycznie.",
        style="WM.Muted.TLabel",
    ).grid(row=1, column=0, sticky="w", pady=(0, 8))

    pin_var = tk.StringVar()
    pin_entry = ttk.Entry(frame, textvariable=pin_var, show="*", width=30)
    pin_entry.grid(row=2, column=0, sticky="ew", pady=(0, 10))

    def _submit(_event=None):
        secret = pin_var.get().strip()
        if not secret:
            pin_entry.focus_set()
            return

        resolved = _validate_login_secret(secret, parent=popup)
        if resolved is None:
            pin_var.set("")
            pin_entry.focus_set()
            return

        login, role = resolved
        _persist_successful_login(login)

        try:
            popup.grab_release()
        except Exception:
            pass
        popup.destroy()

        on_success(login, role, None)
        _schedule_summary(parent, login)

    ttk.Button(frame, text="Zaloguj", command=_submit).grid(
        row=3,
        column=0,
        sticky="e",
    )
    frame.columnconfigure(0, weight=1)
    pin_entry.focus_set()
    popup.bind("<Return>", _submit)
    return popup


def _walk(widget):
    yield widget
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        yield from _walk(child)


def _find_session_wrap(root):
    """Znajdź prawą część nagłówka po przycisku Zaloguj/Wyloguj."""
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Button):
                text = str(widget.cget("text") or "").strip()
                if text in {"Zaloguj", "Wyloguj"}:
                    return widget.master
        except Exception:
            continue
    return None


def _hide_header_theme_controls(session_wrap) -> None:
    """Ukryj tylko szybki wybór Motywu z nagłówka; ustawienia motywu pozostają."""
    if session_wrap is None:
        return

    children = []
    try:
        children = list(session_wrap.winfo_children())
    except Exception:
        return

    hide_combobox = False
    for widget in children:
        try:
            if isinstance(widget, ttk.Label) and str(widget.cget("text") or "") == "Motyw:":
                widget.pack_forget()
                hide_combobox = True
                continue
            if hide_combobox and isinstance(widget, ttk.Combobox):
                widget.pack_forget()
                hide_combobox = False
        except Exception:
            continue


def _ensure_session_label(root, login: str, role: str) -> None:
    """Pokaż w nagłówku jednoznaczną informację o aktywnej sesji."""
    text = f"Zalogowano: {login} ({role})"
    session_wrap = _find_session_wrap(root)
    if session_wrap is None:
        return

    candidate = None
    try:
        for widget in session_wrap.winfo_children():
            if not isinstance(widget, ttk.Label):
                continue
            shown = str(widget.cget("text") or "")
            var_name = str(widget.cget("textvariable") or "")
            if login and login.casefold() in shown.casefold():
                candidate = widget
                break
            if var_name:
                try:
                    current = str(widget.getvar(var_name) or "")
                except Exception:
                    current = ""
                if current in {"Niezalogowany / Gość", f"{login} ({role})"}:
                    candidate = widget
                    break
    except Exception:
        candidate = None

    if candidate is not None:
        try:
            var_name = str(candidate.cget("textvariable") or "")
            if var_name:
                candidate.setvar(var_name, text)
            else:
                candidate.configure(text=text)
            candidate.configure(style="WM.TLabel")
            return
        except Exception:
            pass

    existing = getattr(root, "_wm_session_identity_label", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.configure(text=text)
            return
    except Exception:
        pass

    try:
        label = ttk.Label(session_wrap, text=text, style="WM.TLabel")
        login_button = None
        for widget in session_wrap.winfo_children():
            if isinstance(widget, ttk.Button) and str(widget.cget("text") or "") == "Wyloguj":
                login_button = widget
                break
        if login_button is not None:
            label.pack(side="left", padx=(0, 8), before=login_button)
        else:
            label.pack(side="left", padx=(0, 8))
        setattr(root, "_wm_session_identity_label", label)
    except Exception:
        logger.exception("[LOGIN] Nie udało się dodać etykiety aktywnej sesji.")


def _install_inline_login(root) -> None:
    """Wstaw pole PIN obok Zaloguj i ustaw na nim fokus po uruchomieniu WM."""
    session_wrap = _find_session_wrap(root)
    if session_wrap is None:
        return

    _hide_header_theme_controls(session_wrap)

    login_button = None
    try:
        for widget in session_wrap.winfo_children():
            if isinstance(widget, ttk.Button) and str(widget.cget("text") or "") == "Zaloguj":
                login_button = widget
                break
    except Exception:
        login_button = None

    # Dla zalogowanego użytkownika nie pokazujemy pola PIN.
    if login_button is None:
        existing = getattr(root, "_wm_inline_pin_entry", None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.destroy()
        except Exception:
            pass
        return

    existing = getattr(root, "_wm_inline_pin_entry", None)
    try:
        if existing is not None and existing.winfo_exists() and existing.master is session_wrap:
            pin_entry = existing
            pin_var = getattr(root, "_wm_inline_pin_var", None)
        else:
            pin_entry = None
            pin_var = None
    except Exception:
        pin_entry = None
        pin_var = None

    if pin_entry is None:
        pin_var = tk.StringVar(master=root, value="")
        pin_entry = ttk.Entry(
            session_wrap,
            textvariable=pin_var,
            show="*",
            width=14,
        )
        pin_entry.pack(side="left", padx=(0, 6), before=login_button)
        setattr(root, "_wm_inline_pin_entry", pin_entry)
        setattr(root, "_wm_inline_pin_var", pin_var)

    def _submit(_event=None):
        secret = str(pin_var.get() if pin_var is not None else "").strip()
        if not secret:
            try:
                pin_entry.focus_set()
            except Exception:
                pass
            return

        resolved = _validate_login_secret(secret, parent=root)
        if resolved is None:
            try:
                pin_var.set("")
                pin_entry.focus_set()
            except Exception:
                pass
            return

        login, role = resolved
        _persist_successful_login(login)

        try:
            import gui_panel
            gui_panel.uruchom_panel(root, login, role)
        except Exception:
            logger.exception("[LOGIN] Nie udało się przełączyć panelu po logowaniu.")
            return

        _schedule_summary(root, login)

    try:
        login_button.configure(command=_submit)
        pin_entry.bind("<Return>", _submit)
    except Exception:
        pass

    def _focus_pin() -> None:
        try:
            if pin_entry.winfo_exists():
                pin_entry.focus_set()
                pin_entry.selection_range(0, tk.END)
        except Exception:
            pass

    try:
        root.after_idle(_focus_pin)
        root.after(120, _focus_pin)
    except Exception:
        _focus_pin()


def _install_panel_identity() -> None:
    try:
        import gui_panel
    except Exception:
        return

    current = getattr(gui_panel, "uruchom_panel", None)
    if current is None or getattr(current, "_wm_login_identity_v1", False):
        return

    original = current

    def wrapped(root, login, rola, *args, **kwargs):
        try:
            setattr(root, "_wm_login", str(login or ""))
            setattr(root, "_wm_rola", str(rola or ""))
        except Exception:
            pass

        result = original(root, login, rola, *args, **kwargs)

        login_key = str(login or "").strip().casefold()
        role_key = str(rola or "").strip().casefold()
        if login_key not in _GUESTS and role_key not in _GUESTS:
            _ensure_session_label(root, str(login), str(rola))
        return result

    setattr(wrapped, "_wm_login_identity_v1", True)
    setattr(wrapped, "_wm_login_identity_original", original)
    gui_panel.uruchom_panel = wrapped


def _install_pin_popup() -> None:
    try:
        import gui_logowanie
    except Exception:
        return

    current = getattr(gui_logowanie, "open_login_popup", None)
    if getattr(current, "_wm_pin_only_v1", False):
        return

    setattr(_open_pin_login_popup, "_wm_pin_only_v1", True)
    gui_logowanie.open_login_popup = _open_pin_login_popup


def install(root=None) -> None:
    global _INSTALLED
    _install_panel_identity()
    _install_pin_popup()

    if root is not None:
        _install_inline_login(root)
        try:
            login = str(getattr(root, "_wm_login", "") or "").strip()
            role = str(getattr(root, "_wm_rola", "") or "").strip()
            if login.casefold() not in _GUESTS and role.casefold() not in _GUESTS:
                _ensure_session_label(root, login, role)
        except Exception:
            pass

    _INSTALLED = True


__all__ = [
    "install",
    "_resolve_users_by_secret",
    "_persist_successful_login",
]
