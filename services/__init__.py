"""Usługi Warsztat Menager.

WMM API startuje dopiero po ustawieniu WM_ROOT, żeby zawsze używać właściwych
danych instalacji. Serwer jest lekki, idempotentny i nie blokuje GUI.
Panel WMM jest montowany po przebudowie właściwego sidebara gui_panel.
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


def _install_wmm_sidebar_mount_hook() -> None:
    """Po clear_frame(side) zaplanuj WMM na gotowym sidebarze gui_panel.

    To nie jest hook Tkintera. Owijamy wyłącznie istniejący helper WM,
    dzięki czemu panel powstaje po zakończeniu _build_sidebar() i zawsze
    w głównym wątku Tk. Inne ramki są ignorowane po stylu.
    """
    try:
        from utils import gui_helpers
    except Exception:
        return

    original = getattr(gui_helpers, "clear_frame", None)
    if not callable(original) or getattr(original, "_wmm_sidebar_hook", False):
        return

    @functools.wraps(original)
    def clear_frame_with_wmm(frame, *args, **kwargs):
        result = original(frame, *args, **kwargs)
        try:
            if threading.current_thread() is not threading.main_thread():
                return result
            style = str(frame.cget("style") or "")
            if style != "WM.Side.TFrame":
                return result
            root = frame.winfo_toplevel()

            def mount() -> None:
                try:
                    from .wmm_panel import mount_wmm_panel

                    mount_wmm_panel(root, frame)
                except Exception as exc:
                    try:
                        print(f"[WM-WMM][GUI][WARN] Nie udało się osadzić WMM: {exc}")
                    except Exception:
                        pass

            root.after_idle(mount)
        except Exception:
            pass
        return result

    clear_frame_with_wmm._wmm_sidebar_hook = True  # type: ignore[attr-defined]
    gui_helpers.clear_frame = clear_frame_with_wmm


if _wmm_api_enabled():
    # Instalujemy przed importem gui_panel.clear_frame, aby gui_panel dostał
    # już bezpieczną wersję helpera. Nie modyfikujemy żadnej klasy Tkintera.
    _install_wmm_sidebar_mount_hook()

    threading.Thread(
        target=_start_wmm_after_root,
        name="wm-wmm-bootstrap",
        daemon=True,
    ).start()
