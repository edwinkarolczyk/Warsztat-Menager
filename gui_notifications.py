# version: 1.1
"""Helpery do wyświetlania powiadomień toast w aplikacji Tkinter."""

from __future__ import annotations

import tkinter as tk
from typing import Iterable, List, Optional, Tuple

__all__ = [
    "NotificationPopup",
    "register_notification_root",
    "show_notification",
]

_DEFAULT_DURATION = 5.0
_LEVEL_STYLES = {
    "info": {"bg": "#212529", "fg": "#f8f9fa"},
    "warning": {"bg": "#ffb300", "fg": "#212121"},
    "error": {"bg": "#d32f2f", "fg": "#fafafa"},
}
_LEVEL_DURATIONS = {"warning": 6.0, "error": 7.0}
_PENDING: List[Tuple[str, str, float, bool]] = []
_DEFAULT_MASTER: Optional[tk.Misc] = None


class NotificationPopup(tk.Toplevel):
    """Małe powiadomienie toast; opcjonalnie może pulsować dla alertu krytycznego."""

    def __init__(
        self,
        master: tk.Misc,
        message: str,
        duration: float = _DEFAULT_DURATION,
        *,
        level: str = "info",
        blink: bool = False,
    ) -> None:
        super().__init__(master)
        self.duration = max(0.5, float(duration))
        self.message = message
        self.level = level if level in _LEVEL_STYLES else "info"
        self.blink = bool(blink and self.level == "error")
        self._blink_job = None
        self._close_job = None
        self._blink_state = False
        self._label: tk.Label | None = None
        self._build_ui()
        if self.blink:
            self._blink_tick()
        self._close_job = self.after(int(self.duration * 1000), self.destroy)

    def _build_ui(self) -> None:
        colors = _LEVEL_STYLES.get(self.level, _LEVEL_STYLES["info"])
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=colors["bg"])

        self._label = tk.Label(
            self,
            text=self.message,
            bg=colors["bg"],
            fg=colors["fg"],
            font=("Segoe UI", 10, "bold" if self.blink else "normal"),
            wraplength=380,
            justify="left",
            padx=12,
            pady=10,
        )
        self._label.pack(fill="both", expand=True)

        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        x = screen_width - width - 20
        y = screen_height - height - 70
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _blink_tick(self) -> None:
        if not self.blink:
            return
        try:
            if not self.winfo_exists() or self._label is None or not self._label.winfo_exists():
                self._blink_job = None
                return
        except tk.TclError:
            self._blink_job = None
            return

        self._blink_state = not self._blink_state
        bg = "#7f1d1d" if self._blink_state else _LEVEL_STYLES["error"]["bg"]
        try:
            self.configure(bg=bg)
            self._label.configure(bg=bg)
            self._blink_job = self.after(450, self._blink_tick)
        except tk.TclError:
            self._blink_job = None

    def destroy(self) -> None:
        for job in (self._blink_job, self._close_job):
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self._blink_job = None
        self._close_job = None
        try:
            super().destroy()
        except tk.TclError:
            pass


def _schedule_popup(
    master: tk.Misc,
    message: str,
    level: str,
    duration: float,
    blink: bool = False,
) -> None:
    def _show() -> None:
        NotificationPopup(master, message, duration, level=level, blink=blink)

    master.after(0, _show)


def _flush_pending(master: tk.Misc) -> None:
    if not _PENDING:
        return
    pending: Iterable[Tuple[str, str, float, bool]] = tuple(_PENDING)
    _PENDING.clear()
    for message, level, duration, blink in pending:
        _schedule_popup(master, message, level, duration, blink)


def register_notification_root(master: tk.Misc) -> None:
    """Set the default Tk widget used for toast notifications."""

    global _DEFAULT_MASTER
    if master is None:
        return
    _DEFAULT_MASTER = master
    try:
        _flush_pending(master)
    except tk.TclError:
        pass


def show_notification(
    message: str,
    level: str = "info",
    *,
    master: Optional[tk.Misc] = None,
    duration: Optional[float] = None,
    blink: bool = False,
) -> bool:
    """Zaplanuj powiadomienie; przed startem GUI wpis trafia do kolejki."""

    resolved_master = master or _DEFAULT_MASTER
    resolved_level = level if level in _LEVEL_STYLES else "info"
    resolved_duration = (
        max(0.5, float(duration))
        if duration is not None
        else _LEVEL_DURATIONS.get(resolved_level, _DEFAULT_DURATION)
    )
    resolved_blink = bool(blink and resolved_level == "error")

    if resolved_master is None:
        _PENDING.append((message, resolved_level, resolved_duration, resolved_blink))
        return False

    try:
        _schedule_popup(
            resolved_master,
            message,
            resolved_level,
            resolved_duration,
            resolved_blink,
        )
    except tk.TclError:
        _PENDING.append((message, resolved_level, resolved_duration, resolved_blink))
        return False

    return True


if __name__ == "__main__":  # pragma: no cover - manualne uruchomienie
    root = tk.Tk()
    root.withdraw()
    register_notification_root(root)
    show_notification("🔔 Jarvis: Wykryto długi przestój maszyny M-02.", level="warning")
    root.mainloop()
