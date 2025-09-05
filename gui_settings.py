from __future__ import annotations

import json
import os
import tkinter as tk
from pathlib import Path
from typing import Any, Dict
from tkinter import colorchooser, filedialog, ttk

from config_manager import ConfigManager
from grafiki.shifts_schedule import (
    TRYBY,
    _load_users,
    set_anchor_monday,
    set_user_mode,
)
from utils import error_dialogs

SCHEMA_PATH = Path(__file__).with_name("settings_schema.json")
with SCHEMA_PATH.open(encoding="utf-8") as f:
    _SCHEMA_OPTS = json.load(f)["options"]

MODES_FILE = os.path.join("data", "grafiki", "tryby_userow.json")


def _load_modes() -> dict:
    try:
        with open(MODES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"anchor_monday": "2025-01-06", "modes": {}}


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


class ShiftsModesTab(ttk.Frame):
    """Table of users with configurable shift modes."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        cols = ("id", "name", "mode")
        self.tree = ttk.Treeview(
            self, columns=cols, show="headings", selectmode="browse"
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Użytkownik")
        self.tree.heading("mode", text="Tryb")
        self.tree.column("id", width=100)
        self.tree.column("name", width=200)
        self.tree.column("mode", width=80, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=5)
        ttk.Button(btns, text="Odśwież", command=self._populate).pack(
            side="left", padx=5
        )

        self.tree.bind("<Double-1>", self._edit_mode)
        self._populate()

    def _populate(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        modes = _load_modes().get("modes", {})
        for u in _load_users():
            if not u.get("active"):
                continue
            mode = modes.get(u["id"], "B")
            self.tree.insert("", "end", iid=u["id"], values=(u["id"], u["name"], mode))

    def _edit_mode(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        if not item:
            return
        x, y, width, height = self.tree.bbox(item, column="mode")
        value = self.tree.set(item, "mode")
        cb = ttk.Combobox(self.tree, values=TRYBY, state="readonly")
        cb.set(value)
        cb.place(x=x, y=y, width=width, height=height)
        cb.focus()

        def _on_select(_: tk.Event) -> None:
            new_mode = cb.get()
            set_user_mode(item, new_mode)
            cb.destroy()
            self._populate()

        cb.bind("<<ComboboxSelected>>", _on_select)
        cb.bind("<FocusOut>", lambda _e: cb.destroy())




class SettingsPanel(ttk.Frame):
    """Dynamic panel generated from settings schema."""

    def __init__(self, master: tk.Misc, initial_tab: str | None = None):
        super().__init__(master)
        self.cfg = ConfigManager()
        self.vars: Dict[str, tk.Variable] = {}

        groups: Dict[str, list[dict[str, Any]]] = {}
        for opt in _SCHEMA_OPTS:
            groups.setdefault(opt.get("group", "Inne"), []).append(opt)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        self._tab_frames: Dict[str, ttk.Frame] = {}

        for group, opts in groups.items():
            frame = ttk.Frame(self.nb)
            self.nb.add(frame, text=group)
            self._tab_frames[group] = frame
            row = 0
            for option in opts:
                if option.get("widget") == "hidden":
                    continue
                key = option["key"]
                opt_copy = dict(option)
                opt_copy["default"] = self.cfg.get(key, option.get("default"))
                field, var = _create_widget(opt_copy, frame)
                field.grid(row=row, column=0, sticky="ew")
                self.vars[key] = var
                row += 1
            if group == "Grafik":
                tab = ShiftsModesTab(frame)
                tab.grid(row=row, column=0, sticky="nsew")
                frame.rowconfigure(row, weight=1)
            frame.columnconfigure(0, weight=1)

        if initial_tab:
            tab = self._tab_frames.get(initial_tab)
            if tab is not None:
                self.nb.select(tab)

        ttk.Button(self, text="Zapisz", command=self.save).pack(pady=5)

    def save(self) -> None:
        anchor_var = self.vars.get("rotacja_anchor_monday")
        if anchor_var:
            try:
                set_anchor_monday(anchor_var.get())
            except ValueError as exc:
                error_dialogs.show_error_dialog("Błąd", str(exc))
                return
        save_all(self.vars, self.cfg)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Ustawienia")
    panel = SettingsPanel(root)
    panel.pack(fill="both", expand=True, padx=10, pady=10)
    root.mainloop()
