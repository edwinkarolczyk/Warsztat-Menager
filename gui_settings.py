"""Simple settings GUI for restoring backups."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

from backup import restore_backup


def restore_wizard() -> None:
    """Display a dialog allowing the user to choose and restore a backup file.

    A file selection dialog is opened in the ``backups`` directory. When the
    user selects a file, :func:`backup.restore_backup` is invoked. A message box
    informs about success or failure. The function returns ``None`` and closes
    the temporary tkinter root window.
    """

    root = tk.Tk()
    root.withdraw()
    try:
        path = filedialog.askopenfilename(
            title="Wybierz plik kopii", initialdir="backups"
        )
        if not path:
            return
        try:
            dest = restore_backup(path)
        except Exception as exc:  # pragma: no cover - defensive
            messagebox.showerror("Błąd przywracania", str(exc))
            return
        messagebox.showinfo("Przywrócono", f"Przywrócono: {dest}")
    finally:
        root.destroy()


if __name__ == "__main__":  # pragma: no cover - manual use
    restore_wizard()
