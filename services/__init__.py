"""Usługi Warsztat Menager.

WMM API startuje dopiero po ustawieniu WM_ROOT, żeby zawsze używać właściwych
danych instalacji. Serwer jest lekki, idempotentny i nie blokuje GUI.
Panel WMM montuje się z callbacków wykonywanych już w głównym wątku Tk.
Można wyłączyć API przez WM_DISABLE_WMM_API=1.
"""

from __future__ import annotations

import functools
import os
import sys
import threading
import time


def _wmm_api_enabled() -> bool:
    value = str(os.environ.get("WM_DISABLE_WMM_API", "") or "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return False
    if "pytest" in sys.modules:
        return False
    return True


def _start_wmm_after_root() -> None:
    """Poczekaj na aktywny WM_ROOT i dopiero wtedy uruchom samo API WMM."""
    for _ in range(240):  # maks. około 2 minuty na wybór ROOT przy starcie
        if str(os.environ.get("WM_ROOT", "") or "").strip():
            try:
                from .wmm_api import start_wmm_api

                start_wmm_api()
            except Exception:
                pass
            return
        time.sleep(0.5)


def _schedule_mount_from_root(root) -> None:
    """Zaplanuj montaż WMM; wywołuj wyłącznie z głównego wątku Tk."""
    if threading.current_thread() is not threading.main_thread():
        return
    try:
        from .wmm_panel import mount_wmm_from_root

        root.after_idle(lambda r=root: mount_wmm_from_root(r))
    except Exception as exc:
        try:
            print(f"[WM-WMM][GUI][WARN] Nie udało się zaplanować WMM: {exc}")
        except Exception:
            pass


def _wrap_clear_frame(original):
    """Po clear_frame spróbuj zamontować WMM na gotowym Panelu głównym."""
    if not callable(original):
        return original
    if getattr(original, "_wmm_sidebar_hook", False):
        return original

    @functools.wraps(original)
    def clear_frame_with_wmm(frame, *args, **kwargs):
        result = original(frame, *args, **kwargs)
        if threading.current_thread() is not threading.main_thread():
            return result
        try:
            root = frame.winfo_toplevel()
            _schedule_mount_from_root(root)
        except Exception:
            pass
        return result

    clear_frame_with_wmm._wmm_sidebar_hook = True  # type: ignore[attr-defined]
    return clear_frame_with_wmm


def _wrap_uruchom_panel(original):
    """Po pełnym zbudowaniu gui_panel zamontuj WMM bez zgadywania momentu."""
    if not callable(original):
        return original
    if getattr(original, "_wmm_panel_hook", False):
        return original

    @functools.wraps(original)
    def uruchom_panel_with_wmm(root, *args, **kwargs):
        result = original(root, *args, **kwargs)
        _schedule_mount_from_root(root)
        return result

    uruchom_panel_with_wmm._wmm_panel_hook = True  # type: ignore[attr-defined]
    return uruchom_panel_with_wmm


def _wrap_module_source(original):
    """Awaryjny punkt montażu przy pierwszym odświeżeniu źródła modułu."""
    if not callable(original):
        return original
    if getattr(original, "_wmm_source_hook", False):
        return original

    @functools.wraps(original)
    def wm_set_module_source_with_wmm(root, *args, **kwargs):
        result = original(root, *args, **kwargs)
        _schedule_mount_from_root(root)
        return result

    wm_set_module_source_with_wmm._wmm_source_hook = True  # type: ignore[attr-defined]
    return wm_set_module_source_with_wmm


def _install_wmm_sidebar_mount_hook() -> None:
    """Podepnij wyłącznie istniejące funkcje WM; wątek nie dotyka Tkintera."""
    try:
        from utils import gui_helpers

        gui_helpers.clear_frame = _wrap_clear_frame(gui_helpers.clear_frame)
    except Exception:
        pass

    # gui_panel może być w trakcie importu. Wątek jedynie podmienia referencje
    # funkcji; wszystkie operacje na widgetach wykonują dopiero ich wywołania
    # w głównym wątku GUI.
    def patch_gui_panel_reference() -> None:
        for _ in range(480):
            module = sys.modules.get("gui_panel")
            if module is not None:
                clear_ref = getattr(module, "clear_frame", None)
                run_ref = getattr(module, "uruchom_panel", None)
                source_ref = getattr(module, "wm_set_module_source", None)

                if callable(clear_ref):
                    try:
                        setattr(module, "clear_frame", _wrap_clear_frame(clear_ref))
                    except Exception:
                        pass
                if callable(run_ref):
                    try:
                        setattr(module, "uruchom_panel", _wrap_uruchom_panel(run_ref))
                    except Exception:
                        pass
                if callable(source_ref):
                    try:
                        setattr(module, "wm_set_module_source", _wrap_module_source(source_ref))
                    except Exception:
                        pass

                if callable(run_ref) and callable(source_ref):
                    try:
                        print("[WM-WMM][GUI] Hook Panelu głównego WMM aktywny")
                    except Exception:
                        pass
                    return
            time.sleep(0.05)

    threading.Thread(
        target=patch_gui_panel_reference,
        name="wm-wmm-gui-hook",
        daemon=True,
    ).start()


if _wmm_api_enabled():
    _install_wmm_sidebar_mount_hook()

    threading.Thread(
        target=_start_wmm_after_root,
        name="wm-wmm-bootstrap",
        daemon=True,
    ).start()
