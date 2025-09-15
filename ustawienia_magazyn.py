# ===============================================
# PLIK: ustawienia_magazyn.py
# ===============================================

import json
import os
from pathlib import Path
from tkinter import ttk
import tkinter as tk

import magazyn_slowniki as S
import config_manager as cfg


DEFAULT_UNITS = ["szt", "mb"]
DEFAULT_TYPES = ["surowiec", "półprodukt", "profil", "rura"]


def _ensure_defaults():
    sl_path = Path("data/magazyn/slowniki.json")
    try:
        data = json.loads(sl_path.read_text(encoding="utf-8")) if sl_path.exists() else {}
    except Exception:
        data = {}
    units = data.get("jednostki") or []
    types = data.get("typy") or data.get("types") or []

    changed = False
    if not units:
        data["jednostki"] = DEFAULT_UNITS[:]
        changed = True
    if not types:
        data["typy"] = DEFAULT_TYPES[:]
        changed = True
    if changed:
        sl_path.parent.mkdir(parents=True, exist_ok=True)
        sl_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class MagazynSettingsPane(ttk.Frame):
    def __init__(self, master, config, **kw):
        super().__init__(master, **kw)
        self.config = config
        _ensure_defaults()

        grp_rules = ttk.LabelFrame(self, text="Reguły magazynu")
        grp_rules.pack(fill="x", padx=8, pady=8)

        self.var_enforce = tk.BooleanVar(
            value=cfg.get("magazyn.enforce_surowiec_to_polprodukt", True)
        )
        ttk.Checkbutton(
            grp_rules,
            text="Wymuszaj: surowiec → tylko do półproduktu",
            variable=self.var_enforce,
            command=self._on_enforce_toggle,
        ).pack(anchor="w", padx=8, pady=4)

        grp_dict = ttk.LabelFrame(self, text="Słowniki (podgląd)")
        grp_dict.pack(fill="both", expand=True, padx=8, pady=8)

        ttk.Label(grp_dict, text="Jednostki:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.txt_units = tk.Text(grp_dict, height=3, width=40)
        self.txt_units.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(grp_dict, text="Typy:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.txt_types = tk.Text(grp_dict, height=3, width=40)
        self.txt_types.grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        grp_dict.columnconfigure(1, weight=1)

        sl = S.load_slowniki()
        self.txt_units.insert("1.0", ", ".join(sl.get("jednostki") or DEFAULT_UNITS))
        tp = sl.get("typy") or sl.get("types") or DEFAULT_TYPES
        self.txt_types.insert("1.0", ", ".join(tp))

        ttk.Label(
            self,
            text=(
                "Edycja słowników pełna jest w osobnym edytorze; tu tylko podgląd"
                " i automatyczne wartości domyślne."
            ),
        ).pack(anchor="w", padx=8, pady=(0, 8))

    def _on_enforce_toggle(self):
        cfg.set(
            "magazyn.enforce_surowiec_to_polprodukt",
            bool(self.var_enforce.get()),
        )
        cfg.save()

