from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk

try:
    from config_manager import ConfigManager
except Exception:
    class _DummyCfg(dict):
        def get(self, k, d=None):
            return d

    ConfigManager = lambda: _DummyCfg()

_CFG = ConfigManager()

MACHINES_REL_PATH = os.path.join("maszyny", "maszyny.json")


# ---------- helpers ----------


def _read_json_list(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        print(f"[ERROR][Maszyny] {path} nie zawiera listy (typ={type(data).__name__}).")
        return []
    except Exception as e:
        print(f"[ERROR][Maszyny] Nie można wczytać {path}: {e}")
        return []


def _get_data_root() -> tuple[str, str]:
    """
    Priorytet:
      1) paths.data_root   <-- docelowy, jeden klucz
      2) system.data_dir   <-- zgodność wsteczna
      3) system.data_path  <-- zgodność wsteczna
      4) system.data_root  <-- zgodność wsteczna
      5) ./data            <-- fallback w repo
    Zwraca (root, picked_key).
    """

    for key in ("paths.data_root", "system.data_dir", "system.data_path", "system.data_root"):
        v = _CFG.get(key, None)
        if v:
            return str(v), key
    return os.path.join(os.getcwd(), "data"), "fallback:cwd/data"


def _machines_path() -> tuple[str, dict]:
    root, picked = _get_data_root()
    path = os.path.join(root, MACHINES_REL_PATH)
    return path, {"root": root, "picked_key": picked, "rel": MACHINES_REL_PATH}


# --- GUI ----------------------------------------------------------------------


class MaszynyGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._path, self._meta = _machines_path()
        self._machines = _read_json_list(self._path)

        print(
            "[WM][Maszyny] źródło: "
            f"{self._path} (root={self._meta['root']} via {self._meta['picked_key']}) "
            f"| rekordy: {len(self._machines)}"
        )

        self._build_ui()

    def _build_ui(self) -> None:
        background = self.root["bg"] if "bg" in self.root.keys() else "#111"
        main = tk.Frame(self.root, bg=background)
        main.pack(fill="both", expand=True)

        # Pasek informacyjny z aktywną ścieżką
        bar = tk.Frame(main, bg=background)
        bar.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(
            bar,
            text=(
                "Źródło maszyn: "
                f"{self._path}  •  ({self._meta['picked_key']})"
            ),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        if not self._machines:
            tk.Label(
                bar,
                text=(
                    "Brak danych — sprawdź Ustawienia ➝ System ➝ paths.data_root"
                ),
                fg="#fca5a5",
                bg=background,
            ).pack(side="right")

        # Tabela
        self.tree = ttk.Treeview(
            main,
            columns=("id", "nazwa", "typ", "nastepne"),
            show="headings",
            height=18,
        )
        self.tree.heading("id", text="nr_ewid")
        self.tree.column("id", width=90, anchor="center")
        self.tree.heading("nazwa", text="nazwa")
        self.tree.column("nazwa", width=280, anchor="w")
        self.tree.heading("typ", text="typ")
        self.tree.column("typ", width=150, anchor="w")
        self.tree.heading("nastepne", text="nastepne_zadanie")
        self.tree.column("nastepne", width=180, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        for machine in self._machines:
            machine_id = machine.get("id") or machine.get("nr_ewid") or ""
            name = machine.get("nazwa") or machine.get("name") or ""
            machine_type = machine.get("typ") or ""
            next_task = machine.get("nastepne_zadanie") or machine.get("nastepne") or ""
            self.tree.insert(
                "",
                "end",
                values=(machine_id, name, machine_type, next_task),
            )


# Uruchomienie testowe
if __name__ == "__main__":
    ROOT = tk.Tk()
    ROOT.title("Warsztat Menager — Maszyny")
    APP = MaszynyGUI(ROOT)
    ROOT.mainloop()
