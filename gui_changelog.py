"""Simple window to display changelog."""

from __future__ import annotations

import re
from datetime import datetime
import tkinter as tk
from tkinter import scrolledtext
from pathlib import Path

from ui_theme import ensure_theme_applied


def show_changelog(
    path: str = "CHANGELOG.md",
    master: tk.Misc | None = None,
    last_seen: str | None = None,
) -> tk.Misc:
    """Display contents of ``path`` in a scrollable window.

    Parameters
    ----------
    path:
        Ścieżka do pliku changeloga.
    master:
        Jeśli podany, tworzony jest ``Toplevel`` zamiast ``Tk``.
    last_seen:
        ISO timestamp ostatniego obejrzenia. Sekcje nowsze zostaną
        podświetlone.
    """

    own = master is None
    root = tk.Tk() if own else tk.Toplevel(master)
    ensure_theme_applied(root)
    root.title("Nowości")

    text = scrolledtext.ScrolledText(root, width=80, height=25)
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines(True)
    except FileNotFoundError:
        lines = [f"Nie znaleziono pliku {path}."]

    last_dt = None
    if last_seen:
        try:
            last_dt = datetime.fromisoformat(last_seen)
        except ValueError:
            last_dt = None

    current_date = None
    for line in lines:
        if line.startswith("##"):
            m = re.search(r"-\s*(\d{4}-\d{2}-\d{2})", line)
            if m:
                try:
                    current_date = datetime.fromisoformat(m.group(1))
                except ValueError:
                    current_date = None
        start_idx = text.index("end-1c")
        text.insert("end", line)
        end_idx = text.index("end-1c")
        if last_dt and current_date and current_date > last_dt:
            text.tag_add("new", start_idx, end_idx)

    text.configure(state="disabled")
    text.tag_config("new", background="#fff2b2")
    text.pack(fill="both", expand=True)

    tk.Button(root, text="Zamknij", command=root.destroy).pack(pady=5)
    if own:
        root.mainloop()
    return root
