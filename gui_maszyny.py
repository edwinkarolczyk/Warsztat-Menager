from __future__ import annotations

import json
import os
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

from config.paths import get_path
from wm_log import dbg as wm_dbg, err as wm_err


def _read_json_list(path: str) -> list:
    """Load machines JSON and normalise it to a list of rows."""

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        _read_json_list.last_error = e
        print(f"[ERROR][Maszyny] Nie można wczytać {path}: {e}")
        return []

    rows: list | None = None
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        for key in ("maszyny", "machines", "rows", "items", "data"):
            value = data.get(key)
            if isinstance(value, list):
                rows = value
                break
            if isinstance(value, dict):
                rows = list(value.values())
                break
        if rows is None:
            potential = list(data.values())
            if potential and all(isinstance(item, dict) for item in potential):
                rows = potential

    if rows is not None:
        _read_json_list.last_error = None
        return rows

    err = ValueError(f"Plik {path} nie zawiera listy, tylko {type(data).__name__}")
    _read_json_list.last_error = err
    print(f"[ERROR][Maszyny] Nie można wczytać {path}: {err}")
    return []


_read_json_list.last_error = None


def _read_machines_from_file(path: str) -> list:
    """Bezpiecznie czyta listę maszyn z pliku JSON."""
    if not path:
        wm_err("gui.maszyny", "machines file missing", path=path)
        return []
    if not os.path.isfile(path):
        wm_err("gui.maszyny", "machines file not found", path=path)
        return []
    machines = _read_json_list(path)
    if _read_json_list.last_error is None:
        wm_dbg(
            "gui.maszyny",
            "machines loaded",
            path=path,
            count=len(machines),
        )
        return machines
    err = _read_json_list.last_error
    wm_err("gui.maszyny", "machines load failed", err, path=path)
    if isinstance(err, Exception) and err.__traceback__:
        traceback.print_exception(err.__class__, err, err.__traceback__)
    return []


def _load_machines_from_config() -> tuple[list, str]:
    machines_file = _resolve_machines_path()
    machines = _read_machines_from_file(machines_file)
    return machines, machines_file

# ---------- GUI ----------
class MaszynyGUI:
    def __init__(self, parent: tk.Misc):
        self.parent = parent
        self._machines, self._path = _load_machines_from_config()
        wm_dbg("gui.maszyny", "init", path=self._path, count=len(self._machines))

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

        bar = tk.Frame(self.left, bg=bg)
        bar.pack(fill="x", padx=12, pady=(10, 6))
        lbl = tk.Label(
            bar,
            text=f"Źródło maszyn: {self._path or 'brak'}  •  (hall.machines_file)",
            anchor="w",
            fg="#cbd5e1",
            bg=bg,
        )
        lbl.pack(side="left", fill="x", expand=True)

        if not self._machines:
            tk.Label(
                bar,
                text=f"Brak danych w {self._path or 'brak'}",
                fg="red",
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
        self._machines, self._path = _load_machines_from_config()
        wm_dbg("gui.maszyny", "refresh", path=self._path, count=len(self._machines))
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


# --- Fallback resolver dla ścieżki maszyn -------------------------------
def _resolve_machines_path() -> str:
    """Zwraca najlepszą możliwą ścieżkę do pliku maszyn."""

    p = get_path("hall.machines_file", "").strip()
    if p and os.path.isfile(p):
        return p

    # 1) Spróbuj wzgl. data_root (gdy ktoś wpisał ścieżkę względną)
    if p and os.path.isfile(os.path.join(os.getcwd(), p)):
        return os.path.join(os.getcwd(), p)

    # 2) Spróbuj z sekcji 'machines.relative_path' (jeśli jest)
    rel = get_path("machines.relative_path", "").strip()
    if rel:
        candidate = rel if os.path.isabs(rel) else os.path.join(os.getcwd(), "data", rel)
        if os.path.isfile(candidate):
            return candidate

    # 3) Domyślka z config.paths (_default_paths)
    fallback = get_path(
        "hall.machines_file",
        os.path.join(get_path("paths.layout_dir", ""), "maszyny.json"),
    )
    return fallback

# ---------- uruchomienie solo (dev) ----------
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Warsztat Menager — Maszyny (DEV)")
    app = MaszynyGUI(root)
    root.mainloop()
