import tkinter as tk
from tkinter import messagebox


class DirtyGuard:
    """Utility to track form dirtiness and guard record changes."""

    def __init__(self, name, on_save, on_reset, on_dirty_change=None):
        self.name = name
        self.on_save = on_save
        self.on_reset = on_reset
        self.on_dirty_change = on_dirty_change or (lambda dirty: None)
        self.dirty = False

    def set_dirty(self, state=True):
        if self.dirty != state:
            self.dirty = state
            try:
                self.on_dirty_change(self.dirty)
            except Exception:
                pass

    def _mark_dirty(self, *_):
        self.set_dirty(True)

    def _bind_widget(self, widget):
        try:
            widget.bind("<KeyRelease>", self._mark_dirty, add="+")
            widget.bind("<<ComboboxSelected>>", self._mark_dirty, add="+")
            widget.bind("<<Modified>>", self._mark_dirty, add="+")
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_widget(child)

    def watch(self, widget):
        self._bind_widget(widget)
        try:
            widget.bind_all("<Control-s>", lambda e: self.on_save())
            widget.bind_all("<Escape>", lambda e: self.check_before(lambda: None))
        except Exception:
            pass

    def reset(self):
        self.set_dirty(False)

    def check_before(self, action, *args, **kwargs):
        if not self.dirty:
            return action(*args, **kwargs)
        res = messagebox.askyesnocancel(
            "Niezapisane zmiany",
            f"{self.name}: zapisać zmiany?",
        )
        if res is None:
            return None
        if res:
            if self.on_save() is False:
                return None
        else:
            if self.on_reset() is False:
                return None
        self.reset()
        return action(*args, **kwargs)
