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


def _wrap_clear_frame(original):
    """Owiń clear_frame tak, aby po zbudowaniu sidebara zamontować WMM.

    Wrapper sam wykonuje się w wątku GUI; wątek instalacyjny jedynie podmienia
    referencję funkcji i nigdy nie dotyka widgetów Tk.
    """
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

            def mount() -> None:
                try:
                    from .wmm_panel import mount_wmm_panel

                    mount_wmm_panel(root, frame)
                except Exception as exc:
                    try:
                        print(f"[WM-WMM][GUI][WARN] Nie udało się osadzić WMM: {exc}")
                    except Exception:
                        pass

            # Każdy clear_frame może tu trafić. Sam mount_wmm_panel rozpoznaje
            # właściwy sidebar po realnych przyciskach modułów i ignoruje resztę.
            root.after_idle(mount)
        except Exception:
            pass
        return result

    clear_frame_with_wmm._wmm_sidebar_hook = True  # type: ignore[attr-defined]
    return clear_frame_with_wmm


def _install_wmm_sidebar_mount_hook() -> None:
    """Podepnij helper oraz dokładną referencję clear_frame używaną przez gui_panel."""
    try:
        from utils import gui_helpers

        gui_helpers.clear_frame = _wrap_clear_frame(gui_helpers.clear_frame)
    except Exception:
        pass

    # gui_panel może być zaimportowany wcześniej i mieć własną referencję
    # ``from utils.gui_helpers import clear_frame``. Czekamy wyłącznie na tę
    # referencję i podmieniamy ją; nie wykonujemy żadnych operacji Tk w tym wątku.
    def patch_gui_panel_reference() -> None:
        for _ in range(240):
            module = sys.modules.get("gui_panel")
            if module is not None:
                current = getattr(module, "clear_frame", None)
                if callable(current):
                    try:
                        setattr(module, "clear_frame", _wrap_clear_frame(current))
                        print("[WM-WMM][GUI] Hook clear_frame gui_panel aktywny")
                    except Exception:
                        pass
                    return
            time.sleep(0.25)

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
