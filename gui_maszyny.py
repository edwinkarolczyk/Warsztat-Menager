import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from config_manager import ConfigManager


_CFG = ConfigManager()


def _load_json_file(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except Exception as exc:  # pragma: no cover - diagnostyka
        print(f"[ERROR][Maszyny] Nie można wczytać {path}: {exc}")
        return []


class MaszynyGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._machines = self._load_machines_single_source()
        self._build_ui()

    def _get_machines_path(self) -> str:
        data_root = _CFG.get("system.data_root", os.path.join(os.getcwd(), "data"))
        relative = _CFG.get("machines.relative_path", "maszyny/maszyny.json")
        return os.path.join(data_root, relative)

    def _load_machines_single_source(self) -> list:
        path = self._get_machines_path()
        rows = _load_json_file(path)
        print(f"[WM][Maszyny] źródło: {path} | rekordy: {len(rows)}")
        if not rows:
            messagebox.showwarning(
                "Maszyny",
                f"Brak danych maszyn w {path}. Sprawdź ustawienia.",
            )
        return rows

    def _build_ui(self) -> None:
        background = self.root.cget("bg") if "bg" in self.root.keys() else "#111"
        main = tk.Frame(self.root, bg=background)
        main.pack(fill="both", expand=True)

        tk.Label(main, text="Panel maszyn", anchor="w").pack(
            fill="x", padx=12, pady=(10, 6)
        )

        self.tree = ttk.Treeview(
            main,
            columns=("id", "nazwa", "typ"),
            show="headings",
            height=16,
        )
        self.tree.heading("id", text="nr_ewid")
        self.tree.heading("nazwa", text="nazwa")
        self.tree.heading("typ", text="typ")
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        for machine in self._machines:
            machine_id = machine.get("id") or machine.get("nr_ewid") or ""
            name = machine.get("nazwa") or ""
            machine_type = machine.get("typ") or ""
            self.tree.insert("", "end", values=(machine_id, name, machine_type))


if __name__ == "__main__":
    ROOT = tk.Tk()
    ROOT.title("Warsztat Menager — Maszyny")
    APP = MaszynyGUI(ROOT)
    ROOT.mainloop()
