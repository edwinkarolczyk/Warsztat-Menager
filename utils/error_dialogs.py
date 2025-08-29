"""Utilities for showing standardized error dialogs."""

from __future__ import annotations

from tkinter import messagebox
from typing import Optional

_DEFAULT_SUGGESTION = "Spróbuj ponownie lub skontaktuj się z administratorem."


def show_error_dialog(title: str, description: str, suggestion: Optional[str] = None) -> None:
    """Display an error dialog with description and optional suggestions.

    Parameters
    ----------
    title:
        Dialog window title.
    description:
        Detailed description of the error.
    suggestion:
        Suggested user actions. If ``None``, a default suggestion is used.
    """
    if suggestion is None:
        suggestion = _DEFAULT_SUGGESTION
    message = f"{description}"
    if suggestion:
        message += f"\n\nSugerowane działania:\n{suggestion}"
    messagebox.showerror(title, message)
