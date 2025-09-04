from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from typing import Any
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


class BackupCloudSettings(ttk.Frame):
    """Frame with controls for WebDAV backup configuration."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.cfg = ConfigManager()

        self.url_var = tk.StringVar(value=self.cfg.get("backup.cloud.url", ""))
        self.user_var = tk.StringVar(value=self.cfg.get("backup.cloud.username", ""))
        self.pass_var = tk.StringVar(value=self.cfg.get("backup.cloud.password", ""))
        self.folder_var = tk.StringVar(value=self.cfg.get("backup.cloud.folder", ""))

        ttk.Label(self, text="WebDAV URL:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.url_var, width=40).grid(row=0, column=1, pady=2, sticky="ew")

        ttk.Label(self, text="Użytkownik:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.user_var, width=40).grid(row=1, column=1, pady=2, sticky="ew")

        ttk.Label(self, text="Hasło:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.pass_var, show="*", width=40).grid(row=2, column=1, pady=2, sticky="ew")

        ttk.Label(self, text="Folder docelowy:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.folder_var, width=40).grid(row=3, column=1, pady=2, sticky="ew")

        ttk.Button(self, text="Zapisz", command=self.save).grid(row=4, column=0, columnspan=2, pady=6)

        self.columnconfigure(1, weight=1)

    def save(self) -> None:
        self.cfg.set("backup.cloud.url", self.url_var.get())
        self.cfg.set("backup.cloud.username", self.user_var.get())
        self.cfg.set("backup.cloud.password", self.pass_var.get())
        self.cfg.set("backup.cloud.folder", self.folder_var.get())
        self.cfg.save_all()


class MagazynSettings(ttk.Frame):
    """Frame with controls for warehouse and BOM options."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.cfg = ConfigManager()

        self.rez_var = tk.BooleanVar(
            value=self.cfg.get("magazyn_rezerwacje", True)
        )
        self.prec_var = tk.IntVar(
            value=self.cfg.get("magazyn_precision_mb", 3)
        )
        progi = self.cfg.get("progi_alertow_pct", [100])
        progi_surowce = self.cfg.get("progi_alertow_surowce", {})
        czynnosci = self.cfg.get("czynnosci_technologiczne", [])
        jednostki = self.cfg.get("jednostki_miary", {})

        ttk.Checkbutton(
            self, text="Włącz rezerwacje", variable=self.rez_var
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
            self, from_=0, to=6, textvariable=self.prec_var, width=5
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
        self.progi_text.grid(
            row=4, column=1, sticky="ew", padx=5, pady=5
        )
        self.progi_text.insert("1.0", "\n".join(str(p) for p in progi))
        ttk.Label(
            self,
            text=_SCHEMA_DESC.get("progi_alertow_pct", ""),
            font=("", 8),
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))

        ttk.Label(self, text="Progi alertów dla surowców (%):").grid(
            row=6, column=0, sticky="nw", padx=5, pady=5
        )
        self.progi_surowce_text = tk.Text(self, height=4)
        self.progi_surowce_text.grid(
            row=6, column=1, sticky="ew", padx=5, pady=5
        )
        self.progi_surowce_text.insert(
            "1.0", "\n".join(f"{k} = {v}" for k, v in progi_surowce.items())
        )
        ttk.Label(
            self,
            text="Każda linia: nazwa surowca = próg",
            font=("", 8),
        ).grid(row=7, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))

        ttk.Label(
            self, text="Czynności technologiczne (po jednej w linii):"
        ).grid(row=8, column=0, sticky="nw", padx=5, pady=5)
        self.czynnosci_text = tk.Text(self, height=4)
        self.czynnosci_text.grid(
            row=8, column=1, sticky="ew", padx=5, pady=5
        )
        self.czynnosci_text.insert("1.0", "\n".join(czynnosci))

        ttk.Label(
            self,
            text="Jednostki miary (skrót jednostki = pełna nazwa):",
        ).grid(row=9, column=0, sticky="nw", padx=5, pady=5)
        self.jm_text = tk.Text(self, height=4)
        self.jm_text.grid(
            row=9, column=1, sticky="ew", padx=5, pady=5
        )
        self.jm_text.insert(
            "1.0", "\n".join(f"{k} = {v}" for k, v in jednostki.items())
        )

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
        self.cfg.set("magazyn_rezerwacje", bool(self.rez_var.get()))
        self.cfg.set("magazyn_precision_mb", int(self.prec_var.get()))
        progi = [
            float(p.strip())
            for p in self.progi_text.get("1.0", "end").splitlines()
            if p.strip()
        ]
        self.cfg.set("progi_alertow_pct", progi)

        progi_surowce: dict[str, float] = {}
        for line in self.progi_surowce_text.get("1.0", "end").splitlines():
            if "=" not in line:
                continue
            mat, val = line.split("=", 1)
            try:
                progi_surowce[mat.strip()] = float(val.strip())
            except ValueError:
                continue
        self.cfg.set("progi_alertow_surowce", progi_surowce)

        czynnosci = [
            c.strip()
            for c in self.czynnosci_text.get("1.0", "end").splitlines()
            if c.strip()
        ]
        self.cfg.set("czynnosci_technologiczne", czynnosci)

        jednostki: dict[str, str] = {}
        for line in self.jm_text.get("1.0", "end").splitlines():
            if "=" not in line:
                continue
            skr, nazwa = line.split("=", 1)
            skr = skr.strip()
            nazwa = nazwa.strip()
            if skr and nazwa:
                jednostki[skr] = nazwa
        self.cfg.set("jednostki_miary", jednostki)

        self.cfg.save_all()

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Ustawienia")
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    nb.add(BackupCloudSettings(nb), text="Kopia w chmurze")
    nb.add(MagazynSettings(nb), text="Magazyn i BOM")
    root.mainloop()
