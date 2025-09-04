from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from typing import Any, Dict
from tkinter import colorchooser, filedialog, ttk

from config_manager import ConfigManager
from ui_theme import apply_theme_safe as apply_theme
from gui_magazyn_bom import MagazynBOM

SCHEMA_PATH = Path(__file__).with_name("settings_schema.json")
with SCHEMA_PATH.open(encoding="utf-8") as f:
    _SCHEMA_DESC = {
        opt["key"]: opt.get("description", "")
        for opt in json.load(f)["options"]
    }


def _create_widget(
    option: dict[str, Any], parent: tk.Widget
) -> tuple[tk.Widget, tk.Variable]:
    """Return widget and variable for given schema option."""

    opt_type = option.get("type")
    widget_type = option.get("widget")
    default = option.get("default")

    if opt_type == "bool":
        var = tk.BooleanVar(value=default)
        widget = ttk.Checkbutton(parent, variable=var)
    elif opt_type in {"int", "float"}:
        if opt_type == "int":
            var: tk.Variable = tk.IntVar(value=default)
        else:
            var = tk.DoubleVar(value=default)
        spin_args: dict[str, Any] = {}
        if "min" in option:
            spin_args["from_"] = option["min"]
        if "max" in option:
            spin_args["to"] = option["max"]
        widget = ttk.Spinbox(parent, textvariable=var, **spin_args)
    elif opt_type == "enum":
        var = tk.StringVar(value=default)
        widget = ttk.Combobox(
            parent,
            textvariable=var,
            values=option.get("enum", []),
            state="readonly",
        )
    elif opt_type == "path":
        var = tk.StringVar(value=default or "")
        frame = ttk.Frame(parent)
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)

        def browse() -> None:
            path = filedialog.askopenfilename()
            if path:
                var.set(path)

        ttk.Button(frame, text="Przeglądaj", command=browse).pack(
            side="left", padx=2
        )
        widget = frame
    elif opt_type == "array":
        var = tk.StringVar(value="\n".join(option.get("default", [])))
        text = tk.Text(parent, height=4)
        text.insert("1.0", var.get())

        def update_var(*_args: Any) -> None:
            var.set(text.get("1.0", "end").strip())

        text.bind("<KeyRelease>", update_var)
        widget = text
    elif opt_type == "string" and widget_type == "color":
        var = tk.StringVar(value=default or "")
        frame = ttk.Frame(parent)
        entry = ttk.Entry(frame, textvariable=var, width=10)
        entry.pack(side="left", fill="x", expand=True)

        def pick_color() -> None:
            color = colorchooser.askcolor(var.get())[1]
            if color:
                var.set(color)

        ttk.Button(frame, text="Kolor", command=pick_color).pack(
            side="left", padx=2
        )
        widget = frame
    else:
        var = tk.StringVar(value=default or "")
        widget = ttk.Entry(parent, textvariable=var)
    return widget, var


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
        cfg.set(key, var.get())
    cfg.save_all()


class BackupCloudSettings(ttk.Frame):
    """Frame with controls for WebDAV backup configuration."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.cfg = ConfigManager()

        self.vars: Dict[str, tk.Variable] = {
            "backup.cloud.url": tk.StringVar(
                value=self.cfg.get("backup.cloud.url", "")
            ),
            "backup.cloud.username": tk.StringVar(
                value=self.cfg.get("backup.cloud.username", "")
            ),
            "backup.cloud.password": tk.StringVar(
                value=self.cfg.get("backup.cloud.password", "")
            ),
            "backup.cloud.folder": tk.StringVar(
                value=self.cfg.get("backup.cloud.folder", "")
            ),
        }

        ttk.Label(self, text="WebDAV URL:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.vars["backup.cloud.url"], width=40).grid(
            row=0, column=1, pady=2, sticky="ew"
        )

        ttk.Label(self, text="Użytkownik:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.vars["backup.cloud.username"], width=40).grid(
            row=1, column=1, pady=2, sticky="ew"
        )

        ttk.Label(self, text="Hasło:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(
            self,
            textvariable=self.vars["backup.cloud.password"],
            show="*",
            width=40,
        ).grid(row=2, column=1, pady=2, sticky="ew")

        ttk.Label(self, text="Folder docelowy:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.vars["backup.cloud.folder"], width=40).grid(
            row=3, column=1, pady=2, sticky="ew"
        )

        ttk.Button(self, text="Zapisz", command=self.save).grid(
            row=4, column=0, columnspan=2, pady=6
        )

        self.columnconfigure(1, weight=1)

    def save(self) -> None:
        save_all(self.vars, self.cfg)


class MagazynSettings(ttk.Frame):
    """Frame with controls for warehouse and BOM options."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.cfg = ConfigManager()

        progi = self.cfg.get("progi_alertow_pct", [100])
        progi_surowce = self.cfg.get("progi_alertow_surowce", {})
        czynnosci = self.cfg.get("czynnosci_technologiczne", [])
        jednostki = self.cfg.get("jednostki_miary", {})

        progi_str = "\n".join(str(p) for p in progi)
        progi_surowce_str = "\n".join(
            f"{k} = {v}" for k, v in progi_surowce.items()
        )
        czynnosci_str = "\n".join(czynnosci)
        jm_str = "\n".join(f"{k} = {v}" for k, v in jednostki.items())

        self.vars: Dict[str, tk.Variable] = {
            "magazyn_rezerwacje": tk.BooleanVar(
                value=self.cfg.get("magazyn_rezerwacje", True)
            ),
            "magazyn_precision_mb": tk.IntVar(
                value=self.cfg.get("magazyn_precision_mb", 3)
            ),
            "progi_alertow_pct": FloatListVar(value=progi_str),
            "progi_alertow_surowce": FloatDictVar(value=progi_surowce_str),
            "czynnosci_technologiczne": StrListVar(value=czynnosci_str),
            "jednostki_miary": StrDictVar(value=jm_str),
        }

        ttk.Checkbutton(
            self,
            text="Włącz rezerwacje",
            variable=self.vars["magazyn_rezerwacje"],
        ).grid(row=0, column=0, sticky="w", padx=5, pady=(5, 0))
        ttk.Label(
            self,
            text=_SCHEMA_DESC.get("magazyn_rezerwacje", ""),
            font=("", 8),
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))

        ttk.Label(self, text="Miejsca po przecinku:").grid(
            row=2, column=0, sticky="w", padx=5, pady=5
        )
        ttk.Spinbox(
            self,
            from_=0,
            to=6,
            textvariable=self.vars["magazyn_precision_mb"],
            width=5,
        ).grid(row=2, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(
            self,
            text=_SCHEMA_DESC.get("magazyn_precision_mb", ""),
            font=("", 8),
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))

        ttk.Label(self, text="Domyślne progi alertów magazynowych (%):").grid(
            row=4, column=0, sticky="nw", padx=5, pady=5
        )
        self.progi_text = tk.Text(self, height=4)
        self.progi_text.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
        self.progi_text.insert("1.0", progi_str)

        def _sync_progi(*_args: Any) -> None:
            self.vars["progi_alertow_pct"].set(
                self.progi_text.get("1.0", "end").strip()
            )

        self.progi_text.bind("<KeyRelease>", _sync_progi)
        ttk.Label(
            self,
            text=_SCHEMA_DESC.get("progi_alertow_pct", ""),
            font=("", 8),
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))

        ttk.Label(self, text="Progi alertów dla surowców (%):").grid(
            row=6, column=0, sticky="nw", padx=5, pady=5
        )
        self.progi_surowce_text = tk.Text(self, height=4)
        self.progi_surowce_text.grid(row=6, column=1, sticky="ew", padx=5, pady=5)
        self.progi_surowce_text.insert("1.0", progi_surowce_str)

        def _sync_progi_surowce(*_args: Any) -> None:
            self.vars["progi_alertow_surowce"].set(
                self.progi_surowce_text.get("1.0", "end").strip()
            )

        self.progi_surowce_text.bind("<KeyRelease>", _sync_progi_surowce)
        ttk.Label(
            self,
            text="Każda linia: nazwa surowca = próg",
            font=("", 8),
        ).grid(row=7, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))

        ttk.Label(
            self, text="Czynności technologiczne (po jednej w linii):"
        ).grid(row=8, column=0, sticky="nw", padx=5, pady=5)
        self.czynnosci_text = tk.Text(self, height=4)
        self.czynnosci_text.grid(row=8, column=1, sticky="ew", padx=5, pady=5)
        self.czynnosci_text.insert("1.0", czynnosci_str)

        def _sync_czynnosci(*_args: Any) -> None:
            self.vars["czynnosci_technologiczne"].set(
                self.czynnosci_text.get("1.0", "end").strip()
            )

        self.czynnosci_text.bind("<KeyRelease>", _sync_czynnosci)

        ttk.Label(
            self,
            text="Jednostki miary (skrót jednostki = pełna nazwa):",
        ).grid(row=9, column=0, sticky="nw", padx=5, pady=5)
        self.jm_text = tk.Text(self, height=4)
        self.jm_text.grid(row=9, column=1, sticky="ew", padx=5, pady=5)
        self.jm_text.insert("1.0", jm_str)

        def _sync_jm(*_args: Any) -> None:
            self.vars["jednostki_miary"].set(
                self.jm_text.get("1.0", "end").strip()
            )

        self.jm_text.bind("<KeyRelease>", _sync_jm)

        ttk.Button(self, text="Zapisz", command=self.save).grid(
            row=10, column=0, columnspan=2, pady=6
        )

        nb_bom = ttk.Notebook(self)
        nb_bom.grid(
            row=11, column=0, columnspan=2, sticky="nsew", padx=5, pady=5
        )
        mag_bom = MagazynBOM(nb_bom)
        nb_bom.add(mag_bom, text="Magazyn")
        apply_theme(mag_bom)

        self.columnconfigure(1, weight=1)
        self.rowconfigure(11, weight=1)

    def save(self) -> None:
        save_all(self.vars, self.cfg)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Ustawienia")
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    nb.add(BackupCloudSettings(nb), text="Kopia w chmurze")
    nb.add(MagazynSettings(nb), text="Magazyn i BOM")
    root.mainloop()
