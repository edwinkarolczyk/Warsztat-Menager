from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk

# -- bezpieczny import konfiguracji (działa także w testach/offline) --
try:
    from config_manager import ConfigManager
except Exception:  # pragma: no cover - fallback tylko w środowiskach testowych
    class _DummyCfg(dict):
        def get(self, key, default=None):
            return default

    ConfigManager = lambda: _DummyCfg()


_CFG = ConfigManager()

# Domyślna lokalizacja pliku z maszynami (relatywnie do katalogu danych)
DEFAULT_MACHINES_REL = os.path.join("maszyny", "maszyny.json")


# ----------------- helpers: rozwiązywanie ścieżek + czytanie JSON -----------------

def _pick_data_root() -> tuple[str, str]:
    """Wybierz katalog danych na podstawie konfiguracji."""

    for key in (
        "paths.data_root",
        "system.data_dir",
        "system.data_path",
        "system.data_root",
    ):
        value = _CFG.get(key)
        if value:
            return str(value), key
    return os.path.join(os.getcwd(), "data"), "fallback:cwd/data"


def _resolve_machines_path() -> dict:
    """Zbuduj meta informacje o pliku maszyn."""

    data_root, picked_key = _pick_data_root()
    machines_rel = _CFG.get("hall.machines_file", DEFAULT_MACHINES_REL)
    machines_abs = (
        machines_rel
        if os.path.isabs(machines_rel)
        else os.path.join(data_root, machines_rel)
    )
    return {
        "data_root": data_root,
        "picked_key": picked_key,
        "machines_rel": machines_rel,
        "machines_abs": machines_abs,
        "exists": os.path.isfile(machines_abs),
    }


def _read_json_list(path: str) -> list:
    """Czytaj listę maszyn z pliku JSON."""

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except Exception:
        return []


# ----------------- GUI: tylko dodajemy baner diagnostyczny -----------------


class MaszynyGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._meta = _resolve_machines_path()

        # Próba wczytania DOKŁADNIE z tego pliku, który pokazujemy w banerze
        self._machines = _read_json_list(self._meta["machines_abs"])
        self._count = len(self._machines)

        print(
            "[WM][Maszyny] file=%s | exists=%s | count=%s | data_root=%s (via %s)"
            % (
                self._meta["machines_abs"],
                self._meta["exists"],
                self._count,
                self._meta["data_root"],
                self._meta["picked_key"],
            )
        )

        self._build_ui()

    def _build_ui(self):
        bg = self.root["bg"] if "bg" in self.root.keys() else "#111214"
        main = tk.Frame(self.root, bg=bg)
        main.pack(fill="both", expand=True)

        # 1) BANER DIAGNOSTYCZNY NA GÓRZE
        self._build_diag_banner(main, bg)

        # 2) Tabela maszyn (prezentacja danych)
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
            mid = machine.get("id") or machine.get("nr_ewid") or ""
            nazwa = machine.get("nazwa") or machine.get("name") or ""
            typ = machine.get("typ") or ""
            nastepne = machine.get("nastepne_zadanie") or machine.get("nastepne") or ""
            self.tree.insert("", "end", values=(mid, nazwa, typ, nastepne))

        if not self._machines:
            message = tk.Label(
                main,
                text="Brak danych maszyn — sprawdź ustawienia ścieżek i plik JSON.",
                fg="#fca5a5",
                bg=bg,
                anchor="w",
            )
            message.pack(fill="x", padx=12, pady=(0, 8))

    def _build_diag_banner(self, parent: tk.Widget, bg: str):
        exists = self._meta["exists"]
        count = self._count

        if exists and count > 0:
            color = "#22c55e"
            status_txt = "OK"
        elif exists and count == 0:
            color = "#eab308"
            status_txt = "Pusty plik"
        else:
            color = "#ef4444"
            status_txt = "Brak pliku"

        bar = tk.Frame(parent, bg=bg)
        bar.pack(fill="x", padx=12, pady=(10, 6))

        dot = tk.Canvas(bar, width=12, height=12, bg=bg, highlightthickness=0)
        dot.pack(side="left", padx=(0, 8))
        dot.create_oval(2, 2, 10, 10, fill=color, outline=color)

        path_lbl = tk.Label(
            bar,
            text=(
                "Źródło maszyn: "
                f"{self._meta['machines_abs']}  •  rekordów: {count}  •  "
                f"data_root: {self._meta['data_root']} (via {self._meta['picked_key']})"
            ),
            bg=bg,
            fg="#d1d5db",
            anchor="w",
            justify="left",
        )
        path_lbl.pack(side="left", fill="x", expand=True)

        status_lbl = tk.Label(
            bar,
            text=status_txt,
            bg=bg,
            fg=color,
            font=("TkDefaultFont", 10, "bold"),
        )
        status_lbl.pack(side="right")


# --- Uruchomienie testowe (lokalne) ---
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Warsztat Menager — Maszyny (diag banner)")
    app = MaszynyGUI(root)
    root.mainloop()
