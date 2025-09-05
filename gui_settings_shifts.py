"""Thin wrapper opening the global settings panel on the shifts tab."""

from __future__ import annotations

import tkinter as tk

from gui_settings import SettingsPanel


def main() -> None:
    root = tk.Tk()
    root.title("Ustawienia grafiku")
    panel = SettingsPanel(root, initial_tab="Grafik")
    panel.pack(fill="both", expand=True, padx=10, pady=10)
    root.mainloop()


if __name__ == "__main__":
    main()

