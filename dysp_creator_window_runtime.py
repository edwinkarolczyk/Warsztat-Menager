# version: 1.0
"""Normalny, wyśrodkowany rozmiar okna kreatora Dyspozycji."""

from __future__ import annotations

import logging
import tkinter as tk

logger = logging.getLogger(__name__)


def _normalize_creator_window(window) -> None:
    try:
        title = str(window.title() or "")
    except Exception:
        return

    if title not in {
        "Kreator – Dodaj Dyspozycję",
        "Kreator – Edytuj Dyspozycję",
    }:
        return

    try:
        window.state("normal")
    except Exception:
        pass
    try:
        window.attributes("-zoomed", False)
    except Exception:
        pass

    try:
        screen_w = int(window.winfo_screenwidth())
        screen_h = int(window.winfo_screenheight())
    except Exception:
        screen_w, screen_h = 1366, 768

    width = min(1080, max(760, screen_w - 120))
    height = min(680, max(560, screen_h - 140))
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)

    try:
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.resizable(True, True)
    except Exception:
        logger.exception("[DYSP][WINDOW] Nie udało się ustawić geometrii kreatora.")


def install_dysp_creator_window_behavior() -> bool:
    """Zmień geometrię wyłącznie kreatora Dodaj/Edytuj Dyspozycję."""

    if getattr(tk, "_wm_dysp_creator_window_proxy", False):
        return True

    real_toplevel = getattr(tk, "Toplevel", None)
    if real_toplevel is None:
        return False

    class _DyspCreatorAwareToplevel(real_toplevel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            def _apply() -> None:
                try:
                    _normalize_creator_window(self)
                except Exception:
                    logger.exception("[DYSP][WINDOW] Błąd normalizacji okna kreatora.")

            try:
                self.after_idle(_apply)
            except Exception:
                pass

    tk.Toplevel = _DyspCreatorAwareToplevel
    tk._wm_dysp_creator_window_proxy = True
    return True


__all__ = ["install_dysp_creator_window_behavior"]
