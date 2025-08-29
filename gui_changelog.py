"""Simple window to display changelog."""

import tkinter as tk
from tkinter import scrolledtext
from pathlib import Path


def show_changelog(path: str = "CHANGELOG.md") -> None:
    """Display contents of ``path`` in a scrollable window."""
    root = tk.Tk()
    root.title("Nowości")

    text = scrolledtext.ScrolledText(root, width=80, height=25)
    try:
        content = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        content = f"Nie znaleziono pliku {path}."
    text.insert("1.0", content)
    text.configure(state="disabled")
    text.pack(fill="both", expand=True)

    tk.Button(root, text="Zamknij", command=root.destroy).pack(pady=5)
    root.mainloop()
