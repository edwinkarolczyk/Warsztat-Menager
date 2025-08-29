"""Simple guard for dirty state prompts."""
from __future__ import annotations

from typing import Callable
import tkinter as tk
from tkinter import messagebox

from logger import log_akcja


class DirtyGuard:
    """Guard prompting user before losing unsaved changes.

    Panels may mark themselves as dirty using :meth:`mark_dirty` and
    :meth:`mark_clean`.  Before actions that could discard changes use
    :meth:`check_before` which shows a confirmation dialog if needed.
    """

    def __init__(self) -> None:
        self._dirty = False

    def mark_dirty(self) -> None:
        self._dirty = True

    def mark_clean(self) -> None:
        self._dirty = False

    def attach_window_close(self, root: tk.Tk) -> None:
        """Intercept window close request and check for dirty state."""

        def _on_close() -> None:
            self.check_before(root.destroy)

        root.protocol("WM_DELETE_WINDOW", _on_close)

    def check_before(self, action: Callable[[], None]) -> bool:
        """Run ``action`` after confirming if there are unsaved changes.

        Returns ``True`` if the action was executed.
        """
        if not callable(action):
            return False

        if not self._dirty:
            action()
            return True

        proceed = messagebox.askyesno(
            "Niezapisane zmiany",
            "Masz niezapisane zmiany. Kontynuować?",
            icon="warning",
        )
        log_akcja(f"[WM-DBG][DIRTY] decision={'yes' if proceed else 'no'}")
        if proceed:
            self.mark_clean()
            action()
            return True
        return False
