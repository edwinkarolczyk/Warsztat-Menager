from __future__ import annotations

import json
import os
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

# ---------- Config ----------
try:
    from config_manager import ConfigManager
except Exception:
    class _DummyCfg(dict):
        def get(self, key, default=None):
            return default

    def ConfigManager():  # type: ignore[override]
        return _DummyCfg()

_CFG = ConfigManager()

# Relatywna lokalizacja pliku z maszynami w obrębie katalogu danych:
MACHINES_REL_PATH = os.path.join("maszyny", "maszyny.json")

# ---------- Helpers ----------
def _read_json_list(path: str) -> list:
    """Bezpiecznie czyta listę z JSON. W razie błędu zwraca [] i loguje powód."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        print(f"[ERROR][Maszyny] {path} nie zawiera listy (typ={type(data).__name__}).")
        return []
    except FileNotFoundError:
        print(f"[ERROR][Maszyny] Brak pliku: {path}")
        return []
    except Exception as e:
        print(f"[ERROR][Maszyny] Nie można wczytać {path}: {e}")
        traceback.print_exc()
        return []

def _get_data_root() -> tuple[str, str]:
    """
    Priorytet klucza:
      1) paths.data_root   ← docelowy, jeden klucz (ustawienia/System już go mają)
      2) system.data_dir   ← kompatybilność wsteczna
      3) system.data_path  ← kompatybilność wsteczna
      4) system.data_root  ← kompatybilność wsteczna
      5) ./data            ← fallback (repo)
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

# ---------- GUI ----------
class MaszynyGUI:
    def __init__(self, parent: tk.Misc):
        self.parent = parent
        self._path, self._meta = _machines_path()
        self._machines = _read_json_list(self._path)

        print(
            f"[WM][Maszyny] źródło: {self._path} "
            f"(root={self._meta['root']} via {self._meta['picked_key']}) | rekordy: {len(self._machines)}"
        )

        # Layout główny
        self._build_left_list(parent)
        self._build_right_hall(parent)   # renderer opcjonalny – UI nie zależy od niego

        # Załaduj dane do tabeli
        self._reload_tree()

    # ---------- LEFT: tabela maszyn ----------
    def _build_left_list(self, root: tk.Misc):
        bg = "#111214"
        self.left = tk.Frame(root, bg=bg)
        self.left.pack(side="left", fill="both", expand=True)

        top = tk.Frame(self.left, bg=bg)
        top.pack(fill="x", padx=12, pady=(10, 6))
        lbl = tk.Label(
            top,
            text=f"Źródło maszyn: {self._path}  •  ({self._meta['picked_key']})",
            anchor="w",
            fg="#cbd5e1",
            bg=bg,
        )
        lbl.pack(side="left", fill="x", expand=True)

        if not self._machines:
            tk.Label(
                top,
                text="Brak danych — sprawdź Ustawienia ➝ System ➝ paths.data_root",
                fg="#fca5a5",
                bg=bg,
            ).pack(side="right")

        # Tabela
        self.tree = ttk.Treeview(
            self.left,
            columns=("id", "nazwa", "typ", "nastepne"),
            show="headings",
            height=22,
        )
        self.tree.heading("id", text="nr_ewid")
        self.tree.column("id", width=90, anchor="center")
        self.tree.heading("nazwa", text="nazwa")
        self.tree.column("nazwa", width=300, anchor="w")
        self.tree.heading("typ", text="typ")
        self.tree.column("typ", width=160, anchor="w")
        self.tree.heading("nastepne", text="nastepne")
        self.tree.column("nastepne", width=180, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Przyciski
        btns = tk.Frame(self.left, bg=bg)
        btns.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(btns, text="Odśwież", command=self._refresh_all).pack(side="left")
        ttk.Button(btns, text="Szczegóły", command=self._open_selected_details).pack(
            side="left", padx=(8, 0)
        )

    def _reload_tree(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for m in self._machines:
            mid = m.get("id") or m.get("nr_ewid") or ""
            nazwa = m.get("nazwa") or m.get("name") or ""
            typ = m.get("typ") or ""
            nastepne = m.get("nastepne_zadanie") or m.get("nastepne") or ""
            self.tree.insert("", "end", values=(mid, nazwa, typ, nastepne))

    def _refresh_all(self):
        self._path, self._meta = _machines_path()
        self._machines = _read_json_list(self._path)
        print(f"[WM][Maszyny] REFRESH: {self._path} (via {self._meta['picked_key']}) → {len(self._machines)} szt.")
        self._reload_tree()
        # odśwież prawy panel, jeśli renderer jest dostępny
        if hasattr(self, "_renderer") and hasattr(self._renderer, "reload"):
            try:
                self._renderer.reload(self._machines)
            except Exception:
                traceback.print_exc()

    def _selected_mid(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        return str(vals[0]) if vals else None

    def _open_selected_details(self):
        mid = self._selected_mid()
        if not mid:
            messagebox.showinfo("Maszyny", "Wybierz maszynę z listy.")
            return
        # jeżeli renderer istnieje i ma okno opisu – użyj go
        if hasattr(self, "_renderer") and hasattr(self._renderer, "_open_details"):
            try:
                self._renderer._open_details(mid)
                return
            except Exception:
                traceback.print_exc()
        # fallback
        messagebox.showinfo("Maszyna", f"Szczegóły maszyny nr_ewid: {mid}")

    # ---------- RIGHT: hala (opcjonalna) ----------
    def _build_right_hall(self, root: tk.Misc):
        bg = "#0f172a"
        self.right = tk.Frame(root, width=560, bg=bg)
        self.right.pack(side="right", fill="y")
        self.right.pack_propagate(False)

        header = tk.Frame(self.right, bg=bg)
        header.pack(fill="x", padx=8, pady=(10, 6))
        tk.Label(header, text="Hala (podgląd/edycja)", fg="#e2e8f0", bg=bg).pack(side="left")

        # Płótno
        self._canvas = tk.Canvas(
            self.right,
            width=540,
            height=420,
            bg=bg,
            highlightthickness=1,
            highlightbackground="#334155",
        )
        self._canvas.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # Renderer jest opcjonalny – brak modułu nie psuje listy po lewej
        self._renderer = None
        try:
            from widok_hala.renderer import Renderer
            # wczytany – uruchom
            self._renderer = Renderer(root, self._canvas, self._machines)
            if hasattr(self._renderer, "set_edit_mode"):
                self._renderer.set_edit_mode(False)
        except Exception as e:
            # Nie zatrzymuj UI; pokaż delikatny komunikat w prawym panelu
            msg = f"Brak lub błąd renderer'a hali: {e}"
            print(f"[WARN][Maszyny] {msg}")
            self._canvas.create_text(
                16,
                16,
                text=msg,
                anchor="nw",
                fill="#fca5a5",
                font=("Arial", 9),
            )

# ---------- uruchomienie solo (dev) ----------
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Warsztat Menager — Maszyny (DEV)")
    app = MaszynyGUI(root)
    root.mainloop()
