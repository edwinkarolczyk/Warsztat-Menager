import tkinter as tk
from tkinter import messagebox
import logging

try:
    from config_manager import ConfigManager  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    ConfigManager = None  # type: ignore


class DirtyGuard:
    """Utility to track form edits and warn about unsaved changes.

    Parameters
    ----------
    root:
        Tk root or toplevel widget used for binding shortcuts and timers.
    save_cb, reset_cb:
        Callbacks invoked on save/reset actions (Ctrl+S / Esc shortcuts or
        programmatic triggers).
    warn_on_unsaved:
        When ``True`` the guard will prompt before closing or navigation
        if there are unsaved changes.
    autosave_draft:
        Enables automatic draft saving after changes.  Requires ``save_cb``.
    autosave_interval_ms:
        Delay for autodraft in milliseconds.
    """

    def __init__(
        self,
        root: tk.Misc,
        *,
        save_cb=None,
        reset_cb=None,
        warn_on_unsaved: bool | None = None,
        autosave_draft: bool | None = None,
        autosave_interval_ms: int | None = None,
    ) -> None:
        self.root = root
        self.save_cb = save_cb
        self.reset_cb = reset_cb

        cfg = None
        if ConfigManager is not None:
            try:
                cfg = ConfigManager()
            except Exception:
                cfg = None
        if warn_on_unsaved is None:
            warn_on_unsaved = cfg.get("ui.warn_on_unsaved", True) if cfg else True
        if autosave_draft is None:
            autosave_draft = cfg.get("ui.autosave_draft.enabled", False) if cfg else False
        if autosave_interval_ms is None:
            autosave_interval_ms = (
                cfg.get("ui.autosave_draft.ms", 30000) if cfg else 30000
            )

        self.warn_on_unsaved = bool(warn_on_unsaved)
        self.autosave_draft = bool(autosave_draft)
        self.autosave_interval_ms = int(autosave_interval_ms)

        self._dirty = False
        self._after_id = None
        self._watched = []

        # Keyboard shortcuts
        self.root.bind_all("<Control-s>", self._on_save, add=True)
        self.root.bind_all("<Escape>", self._on_reset, add=True)

    # ------------------------------------------------------------------
    # state handling
    def watch(self, var: tk.Variable | tk.Widget) -> None:
        """Track the given variable or widget for changes."""

        if var in self._watched:
            return
        self._watched.append(var)

        if isinstance(var, tk.Variable):
            var.trace_add("write", lambda *_: self.mark_dirty())
        else:
            try:
                var.bind("<Key>", lambda *_: self.mark_dirty(), add=True)
                var.bind("<FocusOut>", lambda *_: self.mark_dirty(), add=True)
            except Exception:
                pass

    def mark_dirty(self, *_args) -> None:
        if not self._dirty:
            self._dirty = True
            logging.debug("[WM-DBG][DIRTY] marked dirty")
        if self.autosave_draft:
            self._schedule_autosave()

    def mark_clean(self, *_args) -> None:
        if self._dirty:
            self._dirty = False
            logging.debug("[WM-DBG][DIRTY] marked clean")
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    # ------------------------------------------------------------------
    # autosave draft
    def _schedule_autosave(self) -> None:
        if not self.save_cb:
            return
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
        self._after_id = self.root.after(
            self.autosave_interval_ms, self._run_autosave
        )

    def _run_autosave(self) -> None:
        logging.debug("[WM-DBG][DIRTY] autosave draft")
        self._after_id = None
        if self.save_cb:
            self.save_cb()

    # ------------------------------------------------------------------
    # window / navigation helpers
    def attach_window_close(self, window: tk.Tk | tk.Toplevel | None = None) -> None:
        target = window or self.root
        target.protocol("WM_DELETE_WINDOW", lambda: self.check_before(target.destroy))

    def check_before(self, proceed_cb) -> bool:
        """Check for unsaved changes before continuing."""

        if self._dirty and self.warn_on_unsaved:
            try:
                res = messagebox.askyesnocancel(
                    "Niezapisane zmiany",
                    "Masz niezapisane zmiany. Zapisać?",
                )
            except Exception:
                res = True
            if res is None:
                logging.debug("[WM-DBG][DIRTY] action cancelled")
                return False
            if res:
                logging.debug("[WM-DBG][DIRTY] user chose save before action")
                if self.save_cb:
                    self.save_cb()
                self.mark_clean()
            else:
                logging.debug("[WM-DBG][DIRTY] user discarded changes")
                if self.reset_cb:
                    self.reset_cb()
                self.mark_clean()
        proceed_cb()
        return True

    # ------------------------------------------------------------------
    # shortcuts
    def _on_save(self, _event=None):
        if self.save_cb:
            logging.debug("[WM-DBG][DIRTY] Ctrl+S -> save")
            self.save_cb()
            self.mark_clean()

    def _on_reset(self, _event=None):
        if self.reset_cb and self._dirty:
            logging.debug("[WM-DBG][DIRTY] Esc -> reset")
            self.reset_cb()
            self.mark_clean()

