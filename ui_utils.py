"""Utility helpers for Tkinter popups."""

from __future__ import annotations

from typing import Any
import tkinter as tk
from tkinter import messagebox


def _ensure_topmost(toplevel: tk.Toplevel, parent: tk.Misc) -> None:
    """Ensure ``toplevel`` window stays above its ``parent``."""
    try:
        toplevel.transient(parent)
        toplevel.lift()
        toplevel.focus_force()
        toplevel.attributes('-topmost', True)
        toplevel.after_idle(lambda: toplevel.attributes('-topmost', False))
    except Exception:
        pass


def _msg_info(parent: tk.Misc, title: str, message: str, **kwargs: Any) -> str:
    """Show an informational message box bound to ``parent``."""
    return messagebox.showinfo(title, message, parent=parent, **kwargs)


def _msg_warning(parent: tk.Misc, title: str, message: str, **kwargs: Any) -> str:
    """Show a warning message box bound to ``parent``."""
    return messagebox.showwarning(title, message, parent=parent, **kwargs)


def _msg_error(parent: tk.Misc, title: str, message: str, **kwargs: Any) -> str:
    """Show an error message box bound to ``parent``."""
    return messagebox.showerror(title, message, parent=parent, **kwargs)
