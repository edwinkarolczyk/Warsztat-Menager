# version: 1.1
"""Adaptacyjny rozmiar i przewijanie kreatora Dyspozycji."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)

_TITLES = {
    "Kreator – Dodaj Dyspozycję",
    "Kreator – Edytuj Dyspozycję",
}


def _is_creator(window) -> bool:
    try:
        return str(window.title() or "") in _TITLES
    except Exception:
        return False


def _creator_frames(window):
    """Zwróć główną zawartość i dolny pasek przycisków kreatora."""
    try:
        children = list(window.winfo_children())
    except Exception:
        return None, None
    frames = [w for w in children if isinstance(w, ttk.Frame)]
    if len(frames) < 2:
        return None, None
    return frames[0], frames[-1]


def _install_adaptive_layout(window) -> None:
    if not _is_creator(window):
        return
    if getattr(window, "_wm_dysp_adaptive_layout", False):
        return

    content, buttons = _creator_frames(window)
    if content is None or buttons is None or content is buttons:
        return

    window._wm_dysp_adaptive_layout = True
    window._wm_dysp_scroll_offset = 0
    window._wm_dysp_reflow_job = None

    try:
        window.state("normal")
    except Exception:
        pass
    try:
        window.attributes("-zoomed", False)
    except Exception:
        pass

    try:
        content.pack_forget()
    except Exception:
        pass
    try:
        buttons.pack_forget()
    except Exception:
        pass

    scrollbar = ttk.Scrollbar(window, orient="vertical")
    window._wm_dysp_scrollbar = scrollbar

    def _limits() -> tuple[int, int, int, int]:
        try:
            win_w = max(1, int(window.winfo_width()))
            win_h = max(1, int(window.winfo_height()))
            button_h = max(48, int(buttons.winfo_reqheight()) + 10)
            viewport_h = max(1, win_h - button_h)
            content_h = max(viewport_h, int(content.winfo_reqheight()))
            max_offset = max(0, content_h - viewport_h)
            return win_w, win_h, viewport_h, max_offset
        except Exception:
            return 900, 600, 540, 0

    def _apply_positions() -> None:
        win_w, win_h, viewport_h, max_offset = _limits()
        offset = int(getattr(window, "_wm_dysp_scroll_offset", 0) or 0)
        offset = max(0, min(offset, max_offset))
        window._wm_dysp_scroll_offset = offset

        button_h = max(48, win_h - viewport_h)
        scroll_w = 18 if max_offset > 0 else 0
        content_w = max(1, win_w - scroll_w)
        content_h = viewport_h + max_offset

        try:
            content.place(x=0, y=-offset, width=content_w, height=content_h)
            buttons.place(x=0, y=viewport_h, width=win_w, height=button_h)
        except Exception:
            return

        if max_offset > 0:
            try:
                scrollbar.place(x=win_w - 18, y=0, width=18, height=viewport_h)
                first = offset / max(1, content_h)
                last = min(1.0, (offset + viewport_h) / max(1, content_h))
                scrollbar.set(first, last)
            except Exception:
                pass
        else:
            try:
                scrollbar.place_forget()
            except Exception:
                pass

    def _scroll_to_fraction(fraction: float) -> None:
        _win_w, _win_h, _viewport_h, max_offset = _limits()
        fraction = max(0.0, min(1.0, float(fraction)))
        window._wm_dysp_scroll_offset = int(round(max_offset * fraction))
        _apply_positions()

    def _scroll_command(*args) -> None:
        if not args:
            return
        kind = str(args[0])
        _win_w, _win_h, viewport_h, max_offset = _limits()
        current = int(getattr(window, "_wm_dysp_scroll_offset", 0) or 0)
        if kind == "moveto" and len(args) >= 2:
            _scroll_to_fraction(float(args[1]))
            return
        if kind == "scroll" and len(args) >= 3:
            amount = int(args[1])
            unit = str(args[2])
            step = max(30, viewport_h // 10)
            if unit == "pages":
                step = max(60, int(viewport_h * 0.8))
            window._wm_dysp_scroll_offset = max(
                0,
                min(max_offset, current + amount * step),
            )
            _apply_positions()

    scrollbar.configure(command=_scroll_command)

    def _wheel(event) -> None:
        _win_w, _win_h, viewport_h, max_offset = _limits()
        if max_offset <= 0:
            return
        delta = int(getattr(event, "delta", 0) or 0)
        if delta == 0:
            return
        direction = -1 if delta > 0 else 1
        current = int(getattr(window, "_wm_dysp_scroll_offset", 0) or 0)
        step = max(36, viewport_h // 12)
        window._wm_dysp_scroll_offset = max(
            0,
            min(max_offset, current + direction * step),
        )
        _apply_positions()
        return "break"

    def _schedule_reflow(_event=None) -> None:
        old = getattr(window, "_wm_dysp_reflow_job", None)
        if old:
            try:
                window.after_cancel(old)
            except Exception:
                pass
        try:
            window._wm_dysp_reflow_job = window.after_idle(_apply_positions)
        except Exception:
            pass

    try:
        window.bind("<Configure>", _schedule_reflow, add="+")
        content.bind("<Configure>", _schedule_reflow, add="+")
        window.bind("<MouseWheel>", _wheel, add="+")
    except Exception:
        pass

    # Po zbudowaniu wszystkich kontrolek dobierz początkowy rozmiar do treści,
    # ale nigdy nie zajmuj całego ekranu.
    try:
        window.update_idletasks()
        screen_w = int(window.winfo_screenwidth())
        screen_h = int(window.winfo_screenheight())
    except Exception:
        screen_w, screen_h = 1366, 768

    try:
        req_w = max(int(content.winfo_reqwidth()), int(buttons.winfo_reqwidth())) + 36
        req_h = int(content.winfo_reqheight()) + max(48, int(buttons.winfo_reqheight()) + 10)
    except Exception:
        req_w, req_h = 1080, 680

    max_w = max(760, int(screen_w * 0.90))
    max_h = max(560, int(screen_h * 0.90))
    width = min(max_w, max(900, req_w))
    height = min(max_h, max(560, req_h))
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)

    try:
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.resizable(True, True)
        window.update_idletasks()
        _apply_positions()
    except Exception:
        logger.exception("[DYSP][WINDOW] Nie udało się ustawić adaptacyjnego układu.")


def install_dysp_creator_window_behavior() -> bool:
    """Dostosuj wyłącznie kreator Dodaj/Edytuj Dyspozycję."""

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
                    _install_adaptive_layout(self)
                except Exception:
                    logger.exception("[DYSP][WINDOW] Błąd adaptacji okna kreatora.")

            try:
                self.after_idle(_apply)
            except Exception:
                pass

    tk.Toplevel = _DyspCreatorAwareToplevel
    tk._wm_dysp_creator_window_proxy = True
    return True


__all__ = ["install_dysp_creator_window_behavior"]
