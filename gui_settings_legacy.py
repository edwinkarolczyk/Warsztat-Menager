from __future__ import annotations

import tkinter as tk
from typing import Any, Dict
from tkinter import colorchooser, filedialog, messagebox, ttk

from config_manager import ConfigManager


def _create_widget(
    option: dict[str, Any], parent: tk.Widget
) -> tuple[ttk.Frame, tk.Variable]:
    """Return a frame containing label, widget and description for the option."""

    frame = ttk.Frame(parent)
    ttk.Label(frame, text=option.get("label", "")).grid(
        row=0, column=0, sticky="w", padx=5, pady=(5, 0)
    )

    opt_type = option.get("type")
    widget_type = option.get("widget")
    default = option.get("default")

    if opt_type == "bool":
        var = tk.BooleanVar(value=default)
        widget = ttk.Checkbutton(frame, variable=var)
    elif opt_type in {"int", "float"}:
        if opt_type == "int":
            var = tk.IntVar(value=default)
        else:
            var = tk.DoubleVar(value=default)
        spin_args: dict[str, Any] = {}
        if "min" in option:
            spin_args["from_"] = option["min"]
        if "max" in option:
            spin_args["to"] = option["max"]
        widget = ttk.Spinbox(frame, textvariable=var, **spin_args)
    elif opt_type == "enum":
        var = tk.StringVar(value=default)
        widget = ttk.Combobox(
            frame,
            textvariable=var,
            values=option.get("enum", []),
            state="readonly",
        )
    elif opt_type == "path":
        var = tk.StringVar(value=default or "")
        sub = ttk.Frame(frame)
        entry = ttk.Entry(sub, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)

        def browse() -> None:
            if widget_type == "dir":
                path = filedialog.askdirectory()
            else:
                path = filedialog.askopenfilename()
            if path:
                var.set(path)

        ttk.Button(sub, text="Przeglądaj", command=browse).pack(
            side="left", padx=2
        )
        widget = sub
    elif opt_type == "array":
        default_list = option.get("default", []) or []
        lines = "\n".join(str(x) for x in default_list)
        item_type = option.get("value_type")
        if item_type in {"float", "int"} or (
            default_list and all(isinstance(x, (int, float)) for x in default_list)
        ):
            var: tk.StringVar = FloatListVar(value=lines)
        else:
            var = StrListVar(value=lines)
        text = tk.Text(frame, height=4)
        text.insert("1.0", lines)

        def update_var(*_args: Any) -> None:
            var.set(text.get("1.0", "end").strip())

        text.bind("<KeyRelease>", update_var)
        widget = text
    elif opt_type in {"dict", "object"}:
        default_dict: Dict[str, Any] = option.get("default", {}) or {}
        lines = "\n".join(f"{k} = {v}" for k, v in default_dict.items())
        if option.get("value_type") == "float":
            var = FloatDictVar(value=lines)
        else:
            var = StrDictVar(value=lines)
        text = tk.Text(frame, height=4)
        text.insert("1.0", lines)

        def update_dict(*_args: Any) -> None:
            var.set(text.get("1.0", "end").strip())

        text.bind("<KeyRelease>", update_dict)
        widget = text
    elif opt_type == "string" and widget_type == "color":
        var = tk.StringVar(value=default or "")
        sub = ttk.Frame(frame)
        entry = ttk.Entry(sub, textvariable=var, width=10)
        entry.pack(side="left", fill="x", expand=True)

        def pick_color() -> None:
            color = colorchooser.askcolor(var.get())[1]
            if color:
                var.set(color)

        ttk.Button(sub, text="Kolor", command=pick_color).pack(
            side="left", padx=2
        )
        widget = sub
    elif opt_type == "string" and widget_type == "password":
        var = tk.StringVar(value=default or "")
        widget = ttk.Entry(frame, textvariable=var, show="*")
    else:
        var = tk.StringVar(value=default or "")
        widget = ttk.Entry(frame, textvariable=var)

    widget.grid(row=0, column=1, sticky="w", padx=5, pady=(5, 0))

    desc = option.get("description")
    if desc:
        ttk.Label(frame, text=desc, font=("", 8)).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5)
        )

    frame.columnconfigure(1, weight=1)
    return frame, var


class FloatListVar(tk.StringVar):
    """StringVar that parses lines into a list of floats."""

    def get(self) -> list[float]:  # type: ignore[override]
        vals: list[float] = []
        for line in super().get().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                vals.append(float(line))
            except ValueError:
                continue
        return vals


class FloatDictVar(tk.StringVar):
    """StringVar that parses "key = value" lines into a float dictionary."""

    def get(self) -> Dict[str, float]:  # type: ignore[override]
        result: Dict[str, float] = {}
        for line in super().get().splitlines():
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if not key:
                continue
            try:
                result[key] = float(val)
            except ValueError:
                continue
        return result


class StrListVar(tk.StringVar):
    """StringVar that returns non-empty lines as a list of strings."""

    def get(self) -> list[str]:  # type: ignore[override]
        return [ln.strip() for ln in super().get().splitlines() if ln.strip()]


class StrDictVar(tk.StringVar):
    """StringVar that parses "key = value" lines into a string dictionary."""

    def get(self) -> Dict[str, str]:  # type: ignore[override]
        result: Dict[str, str] = {}
        for line in super().get().splitlines():
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key and val:
                result[key] = val
        return result


def save_all(options: Dict[str, tk.Variable], cfg: ConfigManager | None = None) -> None:
    """Persist all options from mapping using ConfigManager."""

    cfg = cfg or ConfigManager()
    for key, var in options.items():
        value = var.get()
        cfg.set(key, value)
    cfg.save_all()




class SettingsPanel:
    """Dynamic panel generated from :class:`ConfigManager` schema."""

    def __init__(self, master: tk.Misc):
        self.master = master
        self.cfg = ConfigManager()
        self.vars: Dict[str, tk.Variable] = {}
        self._initial: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}
        self._options: Dict[str, dict[str, Any]] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create notebook tabs and widgets based on current schema."""

        for child in self.master.winfo_children():
            child.destroy()

        opts = self.cfg.schema.get("options", [])
        groups: Dict[str, list[dict[str, Any]]] = {}
        order: list[str] = []
        for opt in opts:
            grp = opt.get("group", "Inne")
            if grp not in groups:
                groups[grp] = []
                order.append(grp)
            groups[grp].append(opt)

        self.nb = ttk.Notebook(self.master)
        self.nb.pack(fill="both", expand=True)

        for grp in order:
            frame = ttk.Frame(self.nb)
            self.nb.add(frame, text=grp)
            for row, option in enumerate(groups[grp]):
                key = option["key"]
                self._options[key] = option
                current = self.cfg.get(key, option.get("default"))
                opt_copy = dict(option)
                opt_copy["default"] = current
                field, var = _create_widget(opt_copy, frame)
                field.grid(row=row, column=0, sticky="ew")
                frame.columnconfigure(0, weight=1)
                self.vars[key] = var
                self._initial[key] = current
                self._defaults[key] = option.get("default")

        self.btns = ttk.Frame(self.master)
        self.btns.pack(pady=5)
        ttk.Button(self.btns, text="Zapisz", command=self.save).pack(
            side="left", padx=5
        )
        ttk.Button(
            self.btns, text="Przywróć domyślne", command=self.restore_defaults
        ).pack(side="left", padx=5)
        ttk.Button(self.btns, text="Odśwież", command=self.refresh_panel).pack(
            side="left", padx=5
        )

        self.master.winfo_toplevel().protocol("WM_DELETE_WINDOW", self.on_close)

    def restore_defaults(self) -> None:
        for key, var in self.vars.items():
            opt = self._options[key]
            default = self._defaults.get(key)
            opt_type = opt.get("type")
            widget_type = opt.get("widget")
            if opt_type == "array":
                default_list = default or []
                lines = "\n".join(str(x) for x in default_list)
                var.set(lines)
            elif opt_type in {"dict", "object"}:
                default_dict: Dict[str, Any] = default or {}
                lines = "\n".join(f"{k} = {v}" for k, v in default_dict.items())
                var.set(lines)
            elif opt_type == "string" and widget_type == "color":
                var.set(default or "")
            elif opt_type == "path":
                var.set(default or "")
            else:
                var.set(default)

    def on_close(self) -> None:
        changed = any(var.get() != self._initial[key] for key, var in self.vars.items())
        if changed:
            if messagebox.askyesno("Zapisz", "Czy zapisać zmiany?", parent=self.master):
                self.save()
        self.master.winfo_toplevel().destroy()

    def save(self) -> None:
        save_all(self.vars, self.cfg)
        for key, var in self.vars.items():
            self._initial[key] = var.get()

    def refresh_panel(self) -> None:
        """Reload configuration and rebuild widgets."""

        self.cfg = ConfigManager.refresh()
        self.vars.clear()
        self._initial.clear()
        self._defaults.clear()
        self._options.clear()
        self._build_ui()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Ustawienia")
    SettingsPanel(root)
    root.mainloop()
