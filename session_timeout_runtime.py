# version: 1.1
"""Bezpieczny runtime automatycznego wylogowania WM.

Zasady:
- timeout nigdy nie zamyka aplikacji,
- zalogowany użytkownik po bezczynności wraca do trybu Gościa,
- w trybie Gościa timeout niczego nie zamyka,
- aktywny jest jeden rzeczywisty timer bezczynności (start._InactivityMonitor),
- licznik w panelu tylko prezentuje stan tego timera w formacie MM:SS,SSS,
- zapis auth.session_timeout_min jest utrwalany od razu i działa bez restartu,
- wartość 1 min jest dozwolona do testów i normalnego użycia.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_GUEST_LOGINS = {"", "guest", "gość", "gosc", "niezalogowany", "niezalogowana"}
_GUEST_ROLES = {"", "guest", "gość", "gosc"}

_PANEL_TIMER_NEUTRAL_MIN = 525600
_COUNTDOWN_REFRESH_MS = 25


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


def _is_guest_values(login: Any, role: Any) -> bool:
    login_key = str(login or "").strip().casefold()
    role_key = str(role or "").strip().casefold()
    if login_key in _GUEST_LOGINS:
        return True
    if role_key in _GUEST_ROLES and not login_key:
        return True
    return False


def _is_guest_session(root) -> bool:
    login, role = _session_values(root)
    return _is_guest_values(login, role)


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


def _patch_monitor_precision(start_mod) -> None:
    cls = getattr(start_mod, "_InactivityMonitor", None)
    if cls is None or getattr(cls, "_wm_precise_timeout_tick", False):
        return

    def _tick_precise(self):
        if datetime.now() >= self._deadline:
            self._job = None
            self.callback()
            return
        self._job = self.root.after(_COUNTDOWN_REFRESH_MS, self._tick)

    try:
        cls._tick = _tick_precise
        cls._wm_precise_timeout_tick = True
    except Exception:
        logger.exception("[AUTH][TIMEOUT] Nie udało się zwiększyć precyzji monitora.")


def _restart_monitor(root, minutes: int | None = None) -> None:
    start_mod = sys.modules.get("start")
    if start_mod is None or root is None:
        return
    _patch_monitor_precision(start_mod)
    timeout_min = _normalize_minutes(
        minutes if minutes is not None else _timeout_minutes_from_runtime(start_mod)
    )
    total = timeout_min * 60
    try:
        monitor = getattr(start_mod, "_USER_ACTIVITY_MONITOR", None)
        if monitor is not None:
            monitor.callback = _timeout_logout
            restart = getattr(start_mod, "restart_user_activity_monitor", None)
            if callable(restart):
                restart(total)
                new_monitor = getattr(start_mod, "_USER_ACTIVITY_MONITOR", None)
                if new_monitor is not None:
                    new_monitor.callback = _timeout_logout
                return
        starter = getattr(start_mod, "monitor_user_activity", None)
        if callable(starter):
            starter(root, total, callback=_timeout_logout)
    except Exception:
        logger.exception("[AUTH][TIMEOUT] Nie udało się przeładować monitora bezczynności.")


def _timeout_logout() -> None:
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
        logger.exception("[AUTH][TIMEOUT] Nie udało się przełączyć do trybu Gościa.")
        return

    try:
        root.after_idle(lambda: _restart_monitor(root))
    except Exception:
        _restart_monitor(root)


def _allow_one_minute_timeout(cfg=None) -> None:
    managers = []
    if cfg is not None:
        managers.append(cfg)
    try:
        from config_manager import ConfigManager
        managers.append(ConfigManager())
    except Exception:
        pass
    seen: set[int] = set()
    for manager in managers:
        if manager is None or id(manager) in seen:
            continue
        seen.add(id(manager))
        try:
            idx = getattr(manager, "_schema_idx", {}) or {}
            field = idx.get("auth.session_timeout_min")
            if isinstance(field, dict):
                field["min"] = 1
        except Exception:
            pass


def _flush_pending_save(cfg) -> None:
    if cfg is None:
        return
    try:
        pending = bool(getattr(cfg, "_pending_save", False))
    except Exception:
        pending = False
    if not pending:
        return
    try:
        timer = getattr(cfg, "_debounce_timer", None)
        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass
            cfg._debounce_timer = None
        cfg._pending_save = False
        performer = getattr(cfg, "_perform_save_all", None)
        if callable(performer):
            performer()
    except Exception:
        logger.exception("[AUTH][TIMEOUT] Nie udało się wymusić zapisu timeoutu.")


def apply_session_timeout(root, minutes: Any, cfg=None) -> int:
    timeout_min = _normalize_minutes(minutes)
    _allow_one_minute_timeout(cfg)
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
    _flush_pending_save(cfg)
    _restart_monitor(root, timeout_min)
    _install_countdown_display(root)
    logger.info("[AUTH][TIMEOUT] Zastosowano timeout sesji: %s min", timeout_min)
    return timeout_min


class _PanelConfigProxy:
    def __init__(self, manager):
        self._manager = manager

    def get(self, key: str, default=None):
        if key == "auth.session_timeout_min":
            return _PANEL_TIMER_NEUTRAL_MIN
        manager = self._manager
        if manager is None:
            return default
        return manager.get(key, default)

    def __getattr__(self, name: str):
        manager = object.__getattribute__(self, "_manager")
        if manager is None:
            raise AttributeError(name)
        return getattr(manager, name)


def _walk_widgets(widget):
    try:
        children = list(widget.winfo_children())
    except Exception:
        return
    for child in children:
        yield child
        yield from _walk_widgets(child)


def _find_timeout_widgets(root):
    label = None
    reset_btn = None
    for widget in _walk_widgets(root):
        try:
            text = str(widget.cget("text") or "")
        except Exception:
            continue
        if text.startswith("Automatyczne wylogowanie za:"):
            label = widget
        elif text == "Zresetuj licznik":
            reset_btn = widget
    return label, reset_btn


def _cancel_countdown_display(root) -> None:
    job = getattr(root, "_wm_session_countdown_job", None)
    if job:
        try:
            root.after_cancel(job)
        except Exception:
            pass
    try:
        root._wm_session_countdown_job = None
    except Exception:
        pass


def _format_remaining_ms(delta_seconds: float) -> str:
    total_ms = max(0, int(delta_seconds * 1000))
    minutes, rem_ms = divmod(total_ms, 60_000)
    seconds, millis = divmod(rem_ms, 1_000)
    return f"{minutes:02d}:{seconds:02d},{millis:03d}"


def _install_countdown_display(root) -> None:
    if root is None:
        return
    _cancel_countdown_display(root)
    label, reset_btn = _find_timeout_widgets(root)
    guest = _is_guest_session(root)

    if reset_btn is not None:
        try:
            reset_btn.configure(command=lambda: _restart_monitor(root))
        except Exception:
            pass

    if label is None:
        return

    if guest:
        try:
            label.pack_forget()
        except Exception:
            try:
                label.configure(text="")
            except Exception:
                pass
        return

    def _tick_display() -> None:
        try:
            if not root.winfo_exists() or not label.winfo_exists():
                root._wm_session_countdown_job = None
                return
        except Exception:
            try:
                root._wm_session_countdown_job = None
            except Exception:
                pass
            return

        start_mod = sys.modules.get("start")
        monitor = getattr(start_mod, "_USER_ACTIVITY_MONITOR", None) if start_mod else None
        deadline = getattr(monitor, "_deadline", None)
        if deadline is None:
            text = "--:--,---"
        else:
            try:
                remaining = (deadline - datetime.now()).total_seconds()
            except Exception:
                remaining = 0.0
            text = _format_remaining_ms(remaining)

        try:
            label.configure(text=f"Automatyczne wylogowanie za: {text}")
        except Exception:
            root._wm_session_countdown_job = None
            return

        try:
            root._wm_session_countdown_job = root.after(
                _COUNTDOWN_REFRESH_MS, _tick_display
            )
        except Exception:
            root._wm_session_countdown_job = None

    _tick_display()


def _install_panel_hook() -> bool:
    panel_mod = sys.modules.get("gui_panel")
    if panel_mod is None:
        return False
    original = getattr(panel_mod, "uruchom_panel", None)
    if not callable(original):
        return False
    if getattr(panel_mod, "_wm_session_timeout_panel_hook", False):
        return True

    def _panel_with_single_timeout(root, login, rola, *args, **kwargs):
        manager = getattr(panel_mod, "CONFIG_MANAGER", None)
        proxy = _PanelConfigProxy(manager)
        try:
            panel_mod.CONFIG_MANAGER = proxy
            result = original(root, login, rola, *args, **kwargs)
        finally:
            panel_mod.CONFIG_MANAGER = manager

        if _is_guest_values(login, rola):
            _restart_monitor(root)
        else:
            _restart_monitor(root, _timeout_minutes_from_runtime(sys.modules.get("start")))

        try:
            root.after_idle(lambda: _install_countdown_display(root))
        except Exception:
            _install_countdown_display(root)
        return result

    panel_mod.uruchom_panel = _panel_with_single_timeout
    panel_mod._wm_session_timeout_panel_hook = True
    return True


def _schedule_panel_hook_retry(start_mod=None) -> None:
    root = _session_root(start_mod)
    if root is None:
        return
    try:
        if getattr(root, "_wm_session_panel_hook_retry", False):
            return
        root._wm_session_panel_hook_retry = True
    except Exception:
        pass

    def _retry(attempt: int = 0) -> None:
        if _install_panel_hook():
            try:
                root._wm_session_panel_hook_retry = False
            except Exception:
                pass
            return
        if attempt >= 50:
            try:
                root._wm_session_panel_hook_retry = False
            except Exception:
                pass
            return
        try:
            root.after(100, lambda: _retry(attempt + 1))
        except Exception:
            pass

    try:
        root.after_idle(_retry)
    except Exception:
        _retry()


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
        _allow_one_minute_timeout(getattr(self, "cfg", None))
        requested = None
        try:
            var = getattr(self, "vars", {}).get("auth.session_timeout_min")
            if var is not None:
                requested = _normalize_minutes(var.get())
        except Exception:
            requested = None

        result = original_save(self, *args, **kwargs)
        cfg = getattr(self, "cfg", None)
        try:
            after = _normalize_minutes(
                requested if requested is not None else cfg.get("auth.session_timeout_min", 30)
            )
        except Exception:
            after = requested if requested is not None else 30

        _flush_pending_save(cfg)
        try:
            root = self.master.winfo_toplevel()
        except Exception:
            root = None
        if root is not None:
            apply_session_timeout(root, after, cfg=cfg)
        return result

    cls.save = _save_with_session_timeout
    cls._wm_session_timeout_hook = True
    return True


def install_session_timeout_runtime() -> bool:
    start_mod = sys.modules.get("start")
    if start_mod is not None:
        _patch_monitor_precision(start_mod)
        if hasattr(start_mod, "logout"):
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

    _allow_one_minute_timeout()
    _install_settings_save_hook()
    if not _install_panel_hook():
        _schedule_panel_hook_retry(start_mod)
    return True


__all__ = [
    "apply_session_timeout",
    "install_session_timeout_runtime",
]
