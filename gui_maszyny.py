from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk

try:
    from config_manager import ConfigManager
except Exception:  # pragma: no cover - diagnostyka środowiska
    class _DummyCfg(dict):
        def get(self, key, default=None):
            return default

    ConfigManager = lambda: _DummyCfg()  # type: ignore[misc]


_CFG = ConfigManager()

# Stała — względna ścieżka pliku maszyn w katalogu data
MACHINES_REL_PATH = os.path.join("maszyny", "maszyny.json")


# --- helpers ------------------------------------------------------------------


def _read_json_list(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return data
        print(
            f"[ERROR][Maszyny] {path} nie zawiera listy (typ={type(data).__name__})."
        )
        return []
    except Exception as exc:  # pragma: no cover - diagnostyka
        print(f"[ERROR][Maszyny] Nie można wczytać {path}: {exc}")
        return []


def _get_data_root() -> str:
    """
    Jedno źródło prawdy: 'system.data_dir'.
    Dla zgodności wstecznej honorujemy też 'system.data_path' i 'system.data_root'.
    """

    value = _CFG.get("system.data_dir", None)
    if value:
        return str(value)

    for legacy_key in ("system.data_path", "system.data_root"):
        value = _CFG.get(legacy_key, None)
        if value:
            print(
                "[WARN][Maszyny] Brak system.data_dir — używam "
                f"{legacy_key}='{value}' (legacy)."
            )
            return str(value)

    fallback = os.path.join(os.getcwd(), "data")
    print(
        "[WARN][Maszyny] Brak ustawień katalogu danych — fallback: "
        f"{fallback}"
    )
    return fallback


def _machines_path() -> str:
    root = _get_data_root()
    return os.path.join(root, MACHINES_REL_PATH)


# --- GUI ----------------------------------------------------------------------


class MaszynyGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._path = _machines_path()
        self._machines = _read_json_list(self._path)

        print(f"[WM][Maszyny] źródło: {self._path} | rekordy: {len(self._machines)}")

        self._build_ui()

    def _build_ui(self) -> None:
        background = self.root["bg"] if "bg" in self.root.keys() else "#111"
        main = tk.Frame(self.root, bg=background)
        main.pack(fill="both", expand=True)

        # Pasek informacyjny z aktywną ścieżką
        bar = tk.Frame(main, bg=background)
        bar.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(bar, text=f"Źródło maszyn: {self._path}", anchor="w").pack(
            side="left", fill="x", expand=True
        )
        if not self._machines:
            tk.Label(
                bar,
                text="Brak danych — sprawdź Ustawienia ➝ System ➝ system.data_dir",
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
