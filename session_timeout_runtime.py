# version: 1.0
"""Bezpieczny runtime automatycznego wylogowania WM.

Zasady:
- timeout nigdy nie zamyka aplikacji,
- zalogowany użytkownik po bezczynności wraca do trybu Gościa,
- w trybie Gościa timeout niczego nie zamyka i monitor pozostaje gotowy,
- zapis auth.session_timeout_min od razu przeładowuje monitor sesji.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

_GUEST_LOGINS = {"", "guest", "gość", "gosc", "niezalogowany", "niezalogowana"}
_GUEST_ROLES = {"", "guest", "gość", "gosc"}


def _normalize_minutes(value: Any, default: int = 30) -> int:
    try:
        minutes = int(float(value))
    except (TypeError, ValueError):
        minutes = int(default)
    return max(1, minutes)


def _session_root(start_mod=None):
    monitor = getattr(start_mod, "_USER_ACTIVITY_MONITOR", None) if start_mod else None
    root = getattr(monitor, "root", None)
    if root is not None:
        return root
    try:
        import tkinter as tk

        return tk._default_root
    except Exception:
        return None


def _session_values(root) -> tuple[str, str]:
    if root is None:
        return "", ""

    login = ""
    role = ""
    for attr in ("active_login", "current_user", "username", "_wm_login", "login"):
        try:
            value = str(getattr(root, attr, "") or "").strip()
        except Exception:
            value = ""
        if value:
            login = value
            break

    for attr in ("_wm_rola", "rola", "current_role", "active_role", "role"):
        try:
            value = str(getattr(root, attr, "") or "").strip()
        except Exception:
            value = ""
        if value:
            role = value
            break

    return login, role


def _is_guest_session(root) -> bool:
    login, role = _session_values(root)
    login_key = login.casefold()
    role_key = role.casefold()
    if login_key in _GUEST_LOGINS:
        return True
    if role_key in _GUEST_ROLES and not login_key:
        return True
    return False


def _timeout_minutes_from_runtime(start_mod=None) -> int:
    managers = []
    if start_mod is not None:
        managers.append(getattr(start_mod, "CONFIG_MANAGER", None))
    try:
        import gui_panel

        managers.append(getattr(gui_panel, "CONFIG_MANAGER", None))
    except Exception:
        pass
    try:
        from config_manager import ConfigManager

        managers.append(ConfigManager())
    except Exception:
        pass

    for manager in managers:
        if manager is None:
            continue
        try:
            return _normalize_minutes(manager.get("auth.session_timeout_min", 30))
        except Exception:
            continue
    return 30


def _restart_monitor(root, minutes: int | None = None) -> None:
    start_mod = sys.modules.get("start")
    if start_mod is None or root is None:
        return

    timeout_min = _normalize_minutes(
        minutes if minutes is not None else _timeout_minutes_from_runtime(start_mod)
    )
    total = timeout_min * 60

    try:
        monitor = getattr(start_mod, "_USER_ACTIVITY_MONITOR", None)
        if monitor is not None:
            restart = getattr(start_mod, "restart_user_activity_monitor", None)
            if callable(restart):
                restart(total)
                return
        starter = getattr(start_mod, "monitor_user_activity", None)
        if callable(starter):
            starter(root, total, callback=_timeout_logout)
    except Exception:
        logger.exception("[AUTH][TIMEOUT] Nie udało się przeładować monitora bezczynności.")


def _timeout_logout() -> None:
    """Callback monitora: wyloguj użytkownika, ale nigdy nie zamykaj WM."""

    start_mod = sys.modules.get("start")
    root = _session_root(start_mod)
    if root is None:
        return

    try:
        if hasattr(root, "winfo_exists") and not root.winfo_exists():
            return
    except Exception:
        return

    if _is_guest_session(root):
        # Gościa nie ma z czego wylogowywać. Ponownie uzbrajamy monitor,
        # żeby późniejsze logowanie nadal miało aktywny timeout.
        try:
            root.after_idle(lambda: _restart_monitor(root))
        except Exception:
            _restart_monitor(root)
        return

    login, role = _session_values(root)
    try:
        from presence import heartbeat

        heartbeat(login, role, logout=True)
    except Exception:
        pass

    try:
        import gui_panel

        gui_panel.uruchom_panel(root, login="Gość", rola="guest")
    except Exception:
        # Krytyczna zasada: nawet gdy przełączenie panelu się nie uda,
        # timeout nie może wywołać destroy()/quit().
        logger.exception("[AUTH][TIMEOUT] Nie udało się przełączyć do trybu Gościa.")
        return

    try:
        root.after_idle(lambda: _restart_monitor(root))
    except Exception:
        _restart_monitor(root)


def apply_session_timeout(root, minutes: Any, cfg=None) -> int:
    """Zastosuj nowy timeout od razu po zapisie Ustawień."""

    timeout_min = _normalize_minutes(minutes)

    # Ujednolicamy referencję managera używaną przez start i gui_panel,
    # aby ich istniejące callbacki czytały świeżo zapisaną wartość.
    if cfg is not None:
        start_mod = sys.modules.get("start")
        if start_mod is not None:
            try:
                start_mod.CONFIG_MANAGER = cfg
            except Exception:
                pass
        panel_mod = sys.modules.get("gui_panel")
        if panel_mod is not None:
            try:
                panel_mod.CONFIG_MANAGER = cfg
            except Exception:
                pass

    _restart_monitor(root, timeout_min)

    try:
        root.event_generate("<<AuthTimeoutChanged>>", when="tail")
    except Exception:
        pass

    logger.info("[AUTH][TIMEOUT] Zastosowano timeout sesji: %s min", timeout_min)
    return timeout_min


def _install_settings_save_hook() -> bool:
    try:
        import gui_settings
    except Exception:
        return False

    cls = getattr(gui_settings, "SettingsPanel", None)
    if cls is None:
        return False
    if getattr(cls, "_wm_session_timeout_hook", False):
        return True

    original_save = cls.save

    def _save_with_session_timeout(self, *args, **kwargs):
        try:
            before = _normalize_minutes(self.cfg.get("auth.session_timeout_min", 30))
        except Exception:
            before = 30

        result = original_save(self, *args, **kwargs)

        try:
            after = _normalize_minutes(self.cfg.get("auth.session_timeout_min", 30))
        except Exception:
            after = before

        if after != before:
            try:
                root = self.master.winfo_toplevel()
            except Exception:
                root = None
            if root is not None:
                apply_session_timeout(root, after, cfg=getattr(self, "cfg", None))
        return result

    cls.save = _save_with_session_timeout
    cls._wm_session_timeout_hook = True
    return True


def install_session_timeout_runtime() -> bool:
    """Podłącz bezpieczne wylogowanie i reakcję Ustawień."""

    start_mod = sys.modules.get("start")
    if start_mod is not None and hasattr(start_mod, "logout"):
        try:
            start_mod.logout = _timeout_logout
        except Exception:
            pass
        try:
            monitor = getattr(start_mod, "_USER_ACTIVITY_MONITOR", None)
            if monitor is not None:
                monitor.callback = _timeout_logout
        except Exception:
            pass

    _install_settings_save_hook()
    return True


__all__ = [
    "apply_session_timeout",
    "install_session_timeout_runtime",
]
