# version: 1.0
# Moduł: panel_tutorial_runtime
# Izolowane wejście do samouczka w panelu głównym WM.

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk


def _find_sidebar(root: tk.Misc) -> tk.Misc | None:
    """Znajdź lewy panel po jego istniejącym stylu, bez zależności od kolejności widgetów."""
    try:
        children = list(root.winfo_children())
    except Exception:
        return None
    for child in children:
        try:
            if str(child.cget("style") or "") == "WM.Side.TFrame":
                return child
        except Exception:
            continue
    return None


def _open_tutorial(root: tk.Misc) -> None:
    try:
        from gui_samouczek import open_tutorial

        open_tutorial(root)
    except Exception as exc:
        messagebox.showerror(
            "Samouczek WM",
            f"Nie można otworzyć samouczka:\n{exc}",
            parent=root,
        )


def _insert_before_alerts(button: ttk.Button, side: tk.Misc) -> None:
    """Wstaw przycisk po modułach, ale przed kartami alertów."""
    before = None
    try:
        for child in side.winfo_children():
            if child is button:
                continue
            if isinstance(child, ttk.Button):
                continue
            before = child
            break
    except Exception:
        before = None

    kwargs = {"padx": 10, "pady": (10, 6), "fill": "x"}
    if before is not None:
        try:
            button.pack(before=before, **kwargs)
            return
        except Exception:
            pass
    button.pack(**kwargs)


def install_tutorial_button(root: tk.Misc) -> ttk.Button | None:
    """Dodaj lub odtwórz przycisk Samouczek bez modyfikowania listy modułów WM."""
    side = _find_sidebar(root)
    if side is None:
        return None

    existing = getattr(root, "wm_tutorial_button", None)
    try:
        if existing is not None and existing.winfo_exists() and existing.master is side:
            button = existing
        else:
            button = ttk.Button(
                side,
                text="Samouczek",
                command=lambda: _open_tutorial(root),
                style="WM.Side.TButton",
            )
    except Exception:
        button = ttk.Button(
            side,
            text="Samouczek",
            command=lambda: _open_tutorial(root),
            style="WM.Side.TButton",
        )

    def _set_visible(visible: bool) -> None:
        try:
            if not button.winfo_exists():
                return
            if visible:
                if not button.winfo_manager():
                    _insert_before_alerts(button, side)
            elif button.winfo_manager():
                button.pack_forget()
        except Exception:
            pass

    try:
        from settings_tutorial_runtime import is_tutorial_button_enabled

        visible = bool(is_tutorial_button_enabled())
    except Exception:
        visible = True

    try:
        setattr(root, "wm_tutorial_button", button)
        setattr(root, "wm_set_tutorial_button_visible", _set_visible)
    except Exception:
        pass

    _set_visible(visible)

    if not getattr(root, "_wm_tutorial_sidebar_reload_bound", False):
        def _after_sidebar_reload(_event=None) -> None:
            try:
                root.after_idle(lambda: install_tutorial_button(root))
            except Exception:
                pass

        try:
            root.bind("<<SidebarReload>>", _after_sidebar_reload, add="+")
            setattr(root, "_wm_tutorial_sidebar_reload_bound", True)
        except Exception:
            pass

    return button


__all__ = ["install_tutorial_button"]
