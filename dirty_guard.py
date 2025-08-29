"""Utility for tracking unsaved changes and prompting before navigation."""
from __future__ import annotations
from typing import Callable, Optional

class DirtyGuard:
    """Helper class to track dirty state and confirm before navigation."""

    def __init__(self,
                 on_dirty_change: Optional[Callable[[bool], None]] = None,
                 logger: Optional[Callable[[str], None]] = None) -> None:
        self._dirty = False
        self.on_dirty_change = on_dirty_change
        self._logger = logger or print

    @property
    def dirty(self) -> bool:
        """Return current dirty state."""
        return self._dirty

    def _log(self, msg: str) -> None:
        self._logger(f"[WM-DBG][DIRTY] {msg}")

    def mark_dirty(self) -> None:
        """Mark the guard as dirty and notify listener."""
        if not self._dirty:
            self._dirty = True
            self._log("dirty")
            if self.on_dirty_change:
                self.on_dirty_change(True)

    def mark_clean(self) -> None:
        """Mark the guard as clean and notify listener."""
        if self._dirty:
            self._dirty = False
            self._log("clean")
            if self.on_dirty_change:
                self.on_dirty_change(False)

    def check_before(self,
                     dialog: Callable[[], str],
                     on_save: Optional[Callable[[], None]] = None,
                     on_discard: Optional[Callable[[], None]] = None) -> bool:
        """Check before navigation.

        The *dialog* callback should return one of ``"save"``, ``"discard"``
        or ``"cancel"``. Depending on the answer appropriate callback is
        triggered. The method returns ``True`` if navigation may proceed.
        """
        if not self._dirty:
            return True

        answer = dialog()
        self._log(f"dialog={answer}")

        if answer == "save":
            if on_save:
                on_save()
            self.mark_clean()
            return True
        if answer == "discard":
            if on_discard:
                on_discard()
            self.mark_clean()
            return True
        # cancel or unknown answer
        return False
