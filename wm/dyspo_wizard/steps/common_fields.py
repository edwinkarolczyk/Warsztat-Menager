import tkinter as tk
from tkinter import ttk


class CommonFieldsStep(ttk.Frame):
    def __init__(self, parent, context):
        super().__init__(parent)
        self.context = context

        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Opis *").grid(
            row=0,
            column=0,
            sticky="nw",
            padx=8,
            pady=4,
        )

        self.desc_text = tk.Text(
            self,
            height=8,
            wrap="word",
        )

        self.desc_text.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=8,
            pady=4,
        )

        self.desc_text.insert(
            "1.0",
            context.get("description", ""),
        )

        ttk.Label(self, text="Priorytet").grid(
            row=1,
            column=0,
            sticky="w",
            padx=8,
            pady=4,
        )

        self.priority_var = tk.StringVar()

        self.priority_box = tk.OptionMenu(
            self,
            self.priority_var,
            "średnio pilne",
            "pilne",
            "średnio pilne",
            "czas jest",
        )

        self.priority_box.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=8,
            pady=4,
        )

        self.priority_var.trace_add(
            "write",
            self._update_priority_color,
        )

        current_priority = (
            context.get("priority")
            or "średnio pilne"
        )

        self.priority_var.set(current_priority)

        self._update_priority_color()

    def _update_priority_color(self, *_args):
        value = str(self.priority_var.get()).strip().lower()

        if value == "pilne":
            fg = "#ff3b30"
            bg = "#3a0d0d"
        elif value == "średnio pilne":
            fg = "#ffd60a"
            bg = "#3a3200"
        else:
            fg = "#5ac8fa"
            bg = "#0b2530"

        try:
            self.priority_box.config(
                fg=fg,
                bg=bg,
                activeforeground=fg,
                activebackground=bg,
                highlightbackground=bg,
            )
        except Exception:
            pass

    def collect_data(self):
        self.context["description"] = (
            self.desc_text.get("1.0", "end")
            .strip()
        )

        self.context["priority"] = (
            self.priority_var.get().strip()
        )

        # kompatybilność starego modelu danych
        # część kodu może nadal oczekiwać title
        if not self.context.get("title"):
            desc = self.context["description"]
            self.context["title"] = (
                desc[:60] if desc else "Dyspozycja"
            )
