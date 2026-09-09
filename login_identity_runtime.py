# version: 1.0
"""Spójne logowanie użytkownika po samym PIN/haśle w aktywnym panelu WM.

Runtime dotyczy osadzonego logowania z panelu Gościa:
- nie wymaga wyboru loginu,
- rozpoznaje jednoznacznie aktywnego użytkownika po PIN/haśle,
- zapisuje aktywną sesję, ostatnie logowanie i ewidencję Obecności,
- po zalogowaniu pokazuje czytelną informację o aktywnym użytkowniku,
- uruchamia istniejące podsumowanie zmian od poprzedniego logowania.
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


def _open_pin_login_popup(parent, on_success):
    """Popup logowania: jedno pole PIN/hasło, użytkownik rozpoznawany automatycznie."""
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
            messagebox.showerror("Błąd", "Podaj PIN / hasło.", parent=popup)
            pin_entry.focus_set()
            return

        matches = _resolve_users_by_secret(secret)
        if not matches:
            messagebox.showerror(
                "Błąd",
                "Nieprawidłowy PIN lub hasło.",
                parent=popup,
            )
            pin_var.set("")
            pin_entry.focus_set()
            return

        if len(matches) > 1:
            messagebox.showerror(
                "Błąd logowania",
                "Ten PIN / hasło jest przypisany do więcej niż jednego aktywnego "
                "użytkownika. Ustaw unikalne dane logowania użytkowników.",
                parent=popup,
            )
            pin_var.set("")
            pin_entry.focus_set()
            return

        user = matches[0]
        login = str(user.get("login") or "").strip()
        role = str(user.get("rola") or user.get("role") or "pracownik").strip()
        status = str(user.get("status") or "").strip().casefold()

        if user.get("nieobecny") or status in {"nieobecny", "urlop", "l4"}:
            messagebox.showerror(
                "Błąd",
                "Użytkownik oznaczony jako nieobecny.",
                parent=popup,
            )
            return

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


def _ensure_session_label(root, login: str, role: str) -> None:
    """Pokaż w nagłówku jednoznaczną informację o aktywnej sesji."""
    text = f"Zalogowano: {login} ({role})"
    theme_label = None
    candidate = None

    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Label):
                shown = str(widget.cget("text") or "")
                if shown == "Motyw:":
                    theme_label = widget
                if login and login.casefold() in shown.casefold():
                    candidate = widget
        except Exception:
            continue

    if theme_label is None:
        return

    session_wrap = theme_label.master
    if candidate is not None and candidate.master is session_wrap:
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
        label.pack(side="left", padx=(0, 8), before=theme_label)
        setattr(root, "_wm_session_identity_label", label)
    except Exception:
        logger.exception("[LOGIN] Nie udało się dodać etykiety aktywnej sesji.")


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
