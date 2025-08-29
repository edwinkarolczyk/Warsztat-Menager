"""Utilities for showing standardized error dialogs."""

from __future__ import annotations

from tkinter import Button, Frame, Label, Tk, Toplevel, messagebox
from typing import Literal, Optional

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


def ask_unsaved_changes(title: str, msg: str) -> Literal["save", "discard", "cancel"]:
    """Ask the user how to handle unsaved changes.

    Displays a modal dialog with *Save*, *Discard* and *Cancel* options. The
    dialog closes when one of the buttons is pressed or the Escape key is
    used. Returns a string describing the selected action.
    """

    result: Literal["save", "discard", "cancel"] = "cancel"

    root = Tk()
    root.withdraw()

    def close(value: Literal["save", "discard", "cancel"]) -> None:
        nonlocal result
        result = value
        dialog.destroy()

    dialog = Toplevel(root)
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.transient(root)
    dialog.protocol("WM_DELETE_WINDOW", lambda: close("cancel"))
    dialog.bind("<Escape>", lambda e: close("cancel"))

    Label(dialog, text=msg, padx=20, pady=10).pack()

    btn_frame = Frame(dialog, pady=10)
    btn_frame.pack()

    Button(btn_frame, text="Zapisz", width=8,
           command=lambda: close("save")).pack(side="left", padx=5)
    Button(btn_frame, text="Odrzuć", width=8,
           command=lambda: close("discard")).pack(side="left", padx=5)
    Button(btn_frame, text="Anuluj", width=8,
           command=lambda: close("cancel")).pack(side="left", padx=5)

    root.wait_window(dialog)
    root.destroy()
    return result

