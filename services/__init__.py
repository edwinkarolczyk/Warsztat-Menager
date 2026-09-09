"""Usługi Warsztat Menager.

WMM API startuje dopiero po ustawieniu WM_ROOT, żeby zawsze używać właściwych
danych instalacji. Okno połączenia WMM otwiera się po uruchomieniu Panelu głównego.
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
    """Poczekaj na aktywny WM_ROOT i dopiero wtedy uruchom API WMM."""
    for _ in range(240):
        if str(os.environ.get("WM_ROOT", "") or "").strip():
            try:
                from .wmm_api import start_wmm_api

                start_wmm_api()
            except Exception:
                pass
            return
        time.sleep(0.5)


def _schedule_popup(root) -> None:
    """Zaplanuj okno WMM wyłącznie z głównego wątku Tk."""
    if threading.current_thread() is not threading.main_thread():
        return
    try:
        from .wmm_panel import show_wmm_popup

        root.after(250, lambda r=root: show_wmm_popup(r))
    except Exception as exc:
        try:
            print(f"[WM-WMM][GUI][WARN] Nie udało się zaplanować okna WMM: {exc}")
        except Exception:
            pass


def _wrap_uruchom_panel(original):
    """Po pełnym zbudowaniu gui_panel pokaż jedno okno połączenia WMM."""
    if not callable(original):
        return original
    if getattr(original, "_wmm_popup_hook", False):
        return original

    @functools.wraps(original)
    def uruchom_panel_with_wmm(root, *args, **kwargs):
        result = original(root, *args, **kwargs)
        _schedule_popup(root)
        return result

    uruchom_panel_with_wmm._wmm_popup_hook = True  # type: ignore[attr-defined]
    return uruchom_panel_with_wmm


def _wrap_module_source(original):
    """Awaryjnie pokaż WMM przy pierwszym realnym otwarciu modułu.

    gui_panel bywa już w trakcie uruchamiania, gdy wątek instalacyjny zdąży
    podmienić ``uruchom_panel``. ``wm_set_module_source`` jest natomiast wołane
    chwilę później przez faktycznie otwierany moduł i działa w głównym wątku Tk.
    """
    if not callable(original):
        return original
    if getattr(original, "_wmm_popup_source_hook", False):
        return original

    @functools.wraps(original)
    def wm_set_module_source_with_wmm(root, *args, **kwargs):
        result = original(root, *args, **kwargs)
        try:
            if not getattr(root, "_wmm_popup_scheduled", False):
                root._wmm_popup_scheduled = True
                _schedule_popup(root)
        except Exception:
            pass
        return result

    wm_set_module_source_with_wmm._wmm_popup_source_hook = True  # type: ignore[attr-defined]
    return wm_set_module_source_with_wmm


def _install_wmm_popup_hook() -> None:
    """Podepnij tylko bezpieczne funkcje gui_panel; bez hooków widgetów."""

    def patch_gui_panel_reference() -> None:
        for _ in range(480):
            module = sys.modules.get("gui_panel")
            if module is not None:
                run_ref = getattr(module, "uruchom_panel", None)
                source_ref = getattr(module, "wm_set_module_source", None)
                patched = False
                if callable(run_ref):
                    try:
                        setattr(module, "uruchom_panel", _wrap_uruchom_panel(run_ref))
                        patched = True
                    except Exception:
                        pass
                if callable(source_ref):
                    try:
                        setattr(module, "wm_set_module_source", _wrap_module_source(source_ref))
                        patched = True
                    except Exception:
                        pass
                if patched:
                    try:
                        print("[WM-WMM][GUI] Hook okna WMM aktywny")
                    except Exception:
                        pass
                    return
            time.sleep(0.05)

    threading.Thread(
        target=patch_gui_panel_reference,
        name="wm-wmm-popup-hook",
        daemon=True,
    ).start()


if _wmm_api_enabled():
    _install_wmm_popup_hook()

    threading.Thread(
        target=_start_wmm_after_root,
        name="wm-wmm-bootstrap",
        daemon=True,
    ).start()
