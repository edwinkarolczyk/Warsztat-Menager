from __future__ import annotations

import tkinter as tk
from collections import defaultdict
from tkinter import ttk

from config_manager import ConfigManager


class SettingsUI(ttk.Frame):
    """Dynamic settings editor generated from ``settings_schema.json``."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.cfg = ConfigManager()
        self._opts: dict[str, dict] = {}
        self._vars: dict[str, tk.Variable] = {}

        # Load full settings schema via ConfigManager
        schema = self.cfg.schema
        groups: dict[str, list[dict]] = defaultdict(list)
        for opt in schema.get("options", []):
            groups[opt.get("group", "Inne")].append(opt)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        for group, options in groups.items():
            tab = ttk.Frame(nb)
            nb.add(tab, text=group)
            for row, opt in enumerate(options):
                key = opt["key"]
                label = opt.get("label", key)
                otype = opt.get("type")
                default = opt.get("default")
                current = self.cfg.get(key, default)

                if otype == "bool":
                    var = tk.BooleanVar(value=bool(current))
                    ttk.Checkbutton(tab, text=label, variable=var).grid(
                        row=row, column=0, sticky="w", padx=5, pady=5
                    )
                elif otype == "enum":
                    var = tk.StringVar(value=str(current))
                    ttk.Label(tab, text=label).grid(
                        row=row, column=0, sticky="w", padx=5, pady=5
                    )
                    ttk.Combobox(
                        tab,
                        textvariable=var,
                        values=opt.get("enum", []),
                        state="readonly",
                    ).grid(row=row, column=1, sticky="ew", padx=5, pady=5)
                else:
                    var_cls = tk.IntVar if otype == "int" else tk.StringVar
                    var = var_cls(value=current)
                    ttk.Label(tab, text=label).grid(
                        row=row, column=0, sticky="w", padx=5, pady=5
                    )
                    ttk.Entry(tab, textvariable=var).grid(
                        row=row, column=1, sticky="ew", padx=5, pady=5
                    )

                self._vars[key] = var
                self._opts[key] = opt
                tab.columnconfigure(1, weight=1)

        ttk.Button(self, text="Zapisz", command=self.save).pack(pady=10)

    def save(self) -> None:
        """Persist current values using ConfigManager."""
        for key, var in self._vars.items():
            opt = self._opts.get(key, {})
            otype = opt.get("type")
            val = var.get()
            if otype == "int":
                val = int(val)
            elif otype == "bool":
                val = bool(val)
            self.cfg.set(key, val)
        self.cfg.save_all()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Ustawienia")
    SettingsUI(root).pack(fill="both", expand=True, padx=10, pady=10)
    root.mainloop()
