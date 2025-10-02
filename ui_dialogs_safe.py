"""Safe wrappers for tkinter dialogs used across the UI.

The helpers in this module prevent dialogs from showing up while the
application is still in the bootstrap phase. They also centralise the
configuration for common dialog types so that other modules do not have to
interact with :mod:`tkinter.filedialog` or :mod:`tkinter.messagebox`
directly.
"""

from __future__ import annotations

import logging
from tkinter import filedialog, messagebox

logger = logging.getLogger(__name__)


def _bootstrap_active() -> bool:
    """Return ``True`` when the application is still bootstrapping."""

    try:
        from start import BOOTSTRAP_ACTIVE  # pylint: disable=import-outside-toplevel

        return bool(BOOTSTRAP_ACTIVE)
    except Exception:
        return False


def safe_open_json(owner=None, title: str = "Wybierz plik JSON", reason: str = "") -> str | None:
    """Open a file dialog for JSON files unless the bootstrap is active."""

    if _bootstrap_active():
        logger.info("[FILEDIALOG][BLOCK] askopenfilename zablokowany (reason=%s)", reason or "-")
        return None
    path = filedialog.askopenfilename(
        parent=owner, title=title, filetypes=[("Plik JSON", "*.json")]
    )
    return path or None


def safe_save_json(
    owner=None,
    default_name: str = "export.json",
    title: str = "Zapisz jako…",
    reason: str = "",
) -> str | None:
    """Open a save file dialog for JSON files unless blocked."""

    if _bootstrap_active():
        logger.info("[FILEDIALOG][BLOCK] asksaveasfilename zablokowany (reason=%s)", reason or "-")
        return None
    path = filedialog.asksaveasfilename(
        parent=owner,
        title=title,
        defaultextension=".json",
        initialfile=default_name,
        filetypes=[("Plik JSON", "*.json")],
    )
    return path or None


def safe_open_any(
    owner=None,
    patterns: tuple[tuple[str, str], ...] = (("Wszystkie pliki", "*.*"),),
    title: str = "Wybierz plik",
    reason: str = "",
) -> str | None:
    """Open a generic file dialog unless bootstrap blocks dialogs."""

    if _bootstrap_active():
        logger.info("[FILEDIALOG][BLOCK] askopenfilename zablokowany (reason=%s)", reason or "-")
        return None
    path = filedialog.askopenfilename(parent=owner, title=title, filetypes=list(patterns))
    return path or None


def safe_open_dir(owner=None, title: str = "Wybierz folder", reason: str = "") -> str | None:
    """Open a directory picker unless blocked by bootstrap."""

    if _bootstrap_active():
        logger.info("[FILEDIALOG][BLOCK] askdirectory zablokowany (reason=%s)", reason or "-")
        return None
    path = filedialog.askdirectory(parent=owner, title=title)
    return path or None


def info_ok(owner=None, title: str = "Informacja", text: str = "") -> None:
    """Show an informational message unless bootstrap is active."""

    if _bootstrap_active():
        logger.info("[MSGBOX][BLOCK] info podczas bootstrapa: %s", text)
        return
    messagebox.showinfo(title, text, parent=owner)


def warning_box(owner=None, title: str = "Ostrzeżenie", text: str = "") -> None:
    """Show a warning message in a safe manner."""

    if _bootstrap_active():
        logger.warning("[MSGBOX][BLOCK] warning podczas bootstrapa: %s", text)
        return
    messagebox.showwarning(title, text, parent=owner)


def error_box(owner=None, title: str = "Błąd", text: str = "") -> None:
    """Show an error dialog unless bootstrap blocks dialogs."""

    if _bootstrap_active():
        logger.error("[MSGBOX][BLOCK] error podczas bootstrapa: %s", text)
        return
    messagebox.showerror(title, text, parent=owner)

