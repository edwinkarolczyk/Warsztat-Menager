from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

# nowość: konfiguracja
try:
    from config_manager import ConfigManager
except Exception:
    ConfigManager = None

# domyślne, gdy brak ustawień
DEFAULT_PRIMARY = os.path.join("data", "maszyny.json")
DEFAULT_LEGACY = os.path.join("data", "maszyny", "maszyny.json")
MIGRATION_FLAG = os.path.join("data", ".machines_migrated.flag")


def _load_json_file(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _index_by_id(rows: list) -> dict:
    out: dict[str, dict] = {}
    for row in rows or []:
        machine_id = str(row.get("id") or row.get("nr_ewid") or "").strip()
        if machine_id:
            out[machine_id] = row
    return out


def _merge_unique(first: list, second: list) -> list:
    first_index = _index_by_id(first)
    second_index = _index_by_id(second)
    for machine_id, row in second_index.items():
        if machine_id not in first_index:
            first_index[machine_id] = row
    return [
        first_index[key]
        for key in sorted(first_index.keys(), key=lambda value: (len(value), value))
    ]

def _save_list(path: str, rows: list) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)

def _exists_nonempty(path: str) -> bool:
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except Exception:
        return False


def _count_items(path: str) -> int:
    try:
        return len(_load_json_file(path))
    except Exception:
        return 0

# --------- NOWE: rozpoznanie ścieżek z ustawień ----------
def _candidates_from_settings() -> dict:
    """Zbierz potencjalne ścieżki plików PRIMARY i LEGACY."""

    cfg = None
    if ConfigManager:
        try:
            cfg = ConfigManager()
        except Exception:
            cfg = None

    def get_value(key, default=None):
        return cfg.get(key, default) if cfg else default

    primary_candidates: list[str] = []
    legacy_candidates: list[str] = []

    # 1) wskazany plik
    for key in ("hall.machines_file", "machines.file", "maszyny.file"):
        value = get_value(key)
        if value and isinstance(value, str):
            primary_candidates.append(value)

    # 2) wskazany katalog
    machines_dir = get_value("hall.machines_dir")
    if machines_dir and isinstance(machines_dir, str):
        primary_candidates.append(os.path.join(machines_dir, "maszyny.json"))
        legacy_candidates.append(
            os.path.join(machines_dir, "maszyny", "maszyny.json")
        )

    # 3) system.data_path
    data_path = get_value("system.data_path")
    if data_path and isinstance(data_path, str):
        primary_candidates.append(os.path.join(data_path, "maszyny.json"))
        legacy_candidates.append(
            os.path.join(data_path, "maszyny", "maszyny.json")
        )

    # 4) fallback repo (bieżący projekt)
    primary_candidates.append(DEFAULT_PRIMARY)
    legacy_candidates.append(DEFAULT_LEGACY)

    def dedupe(seq):
        out, seen = [], set()
        for candidate in seq:
            candidate = os.path.abspath(candidate)
            if candidate not in seen:
                seen.add(candidate)
                out.append(candidate)
        return out

    return {
        "primary_candidates": dedupe(primary_candidates),
        "legacy_candidates": dedupe(legacy_candidates),
    }

def _pick_best_paths() -> tuple[str, str]:
    candidates = _candidates_from_settings()
    primaries = candidates["primary_candidates"]
    legacies = candidates["legacy_candidates"]

    # wybierz PRIMARY: najpierw istniejący z największą liczbą rekordów
    best_primary = None
    best_count = -1
    for path in primaries:
        if _exists_nonempty(path):
            count = _count_items(path)
            print(f"[DIAG][Maszyny] PRIMARY kandydat: {path} → {count} rek.")
            if count > best_count:
                best_count = count
                best_primary = path
    if not best_primary:
        # jeśli żaden nie istnieje, bierz pierwszy z listy (utworzymy później)
        best_primary = primaries[0]
        print(
            "[WARN][Maszyny] Brak istniejącego PRIMARY, używam domyślnego: "
            f"{best_primary}"
        )

    # wybierz LEGACY: pierwszy istniejący i nie ten sam co PRIMARY
    best_legacy = None
    for path in legacies:
        if os.path.abspath(path) == os.path.abspath(best_primary):
            continue
        if _exists_nonempty(path):
            best_legacy = path
            print(
                f"[DIAG][Maszyny] LEGACY kandydat: {path} → {_count_items(path)} rek."
            )
            break

    if not best_legacy:
        # ostateczny fallback
        best_legacy = DEFAULT_LEGACY

    return best_primary, best_legacy

# ---------------------------------------------------------

try:
    from widok_hala.renderer import Renderer
except Exception as e:
    Renderer = None
    print(f"[ERROR][Maszyny] Brak renderer'a hali: {e}")

class MaszynyGUI:
    def __init__(self, root: tk.Tk, side_menu: dict | None = None):
        self.root = root
        self.side_menu = side_menu or {}

        # wyznacz ścieżki z ustawień
        self.PRIMARY_DATA, self.LEGACY_DATA = _pick_best_paths()
        print(f"[WM][Maszyny] PRIMARY path = {self.PRIMARY_DATA}")
        print(f"[WM][Maszyny] LEGACY  path = {self.LEGACY_DATA}")

        self._source = "AUTO"
        self._machines = self._load_and_migrate()
        self._hide_hale_button_if_present()
        self._build_ui()

    def _load_and_migrate(self) -> list:
        primary = _load_json_file(self.PRIMARY_DATA)
        legacy = _load_json_file(self.LEGACY_DATA)
        n_p, n_l = len(primary), len(legacy)

        print(f"[DIAG][Maszyny] {self.PRIMARY_DATA}: {n_p} rekordów")
        print(f"[DIAG][Maszyny] {self.LEGACY_DATA}: {n_l} rekordów")

        # po migracji trzymajmy się PRIMARY
        flag_dir = os.path.dirname(self.PRIMARY_DATA) or "."
        migration_flag = os.path.join(flag_dir, ".machines_migrated.flag")

        if os.path.exists(migration_flag):
            self._source = "primary"
            print(f"[WM][Maszyny] source=PRIMARY file={self.PRIMARY_DATA} cnt={n_p}")
            return primary

        # AUTO→MERGE: bierz większy zbiór jako bazę i dołącz unikalne z drugiego
        base = legacy if n_l > n_p else primary
        merged = _merge_unique(base, primary if base is legacy else legacy)
        # zapis do WYBRANEGO PRIMARY (z ustawieñ!)
        _save_list(self.PRIMARY_DATA, merged)
        open(migration_flag, "w").close()

        self._source = "primary"
        print(
            "[WM][Maszyny] AUTO→MERGE "
            f"primary={n_p} legacy={n_l} → save PRIMARY={len(merged)} "
            f"@ {self.PRIMARY_DATA}"
        )
        return merged

    def _save_position(self, machine_id: str, x: int, y: int):
        try:
            disk = _load_json_file(self.PRIMARY_DATA)
            if not disk:
                disk = _merge_unique(
                    _load_json_file(self.PRIMARY_DATA),
                    _load_json_file(self.LEGACY_DATA),
                )
            mid = str(machine_id)
            found = False
            for m in disk:
                if str(m.get("id") or m.get("nr_ewid")) == mid:
                    m.setdefault("pozycja", {})
                    m["pozycja"]["x"] = int(x)
                    m["pozycja"]["y"] = int(y)
                    found = True
                    break
            if not found:
                disk.append(
                    {
                        "id": mid,
                        "nazwa": mid,
                        "hala": 1,
                        "pozycja": {"x": int(x), "y": int(y)},
                    }
                )
            _save_list(self.PRIMARY_DATA, _merge_unique(disk, []))
            self._machines = _load_json_file(self.PRIMARY_DATA)
            self._source = "primary"
            print(
                "[WM][Maszyny] Zapisano pozycję "
                f"{mid} → ({x},{y}) do PRIMARY: {self.PRIMARY_DATA}"
            )
        except Exception as e:
            print(f"[ERROR][Maszyny] Zapis pozycji nieudany: {e}")

    def _hide_hale_button_if_present(self):
        try:
            hale_btn = None
            if isinstance(self.side_menu, dict):
                hale_btn = self.side_menu.get("Hale")
            if not hale_btn and hasattr(self.root, "btn_hale"):
                hale_btn = getattr(self.root, "btn_hale")
            if hale_btn:
                try:
                    hale_btn.pack_forget()
                except Exception:
                    try:
                        hale_btn.grid_remove()
                    except Exception:
                        pass
        except Exception:
            pass

    def _build_ui(self):
        background = self.root.cget("bg") if "bg" in self.root.keys() else "#111214"
        main = tk.Frame(self.root, bg=background)
        main.pack(fill="both", expand=True)

        # lewy panel (lista)
        left = tk.Frame(main, bg=background)
        left.pack(side="left", fill="both", expand=True)

        tk.Label(left, text="Panel maszyn", anchor="w").pack(
            fill="x", padx=12, pady=(10, 6)
        )
        self.tree = ttk.Treeview(
            left,
            columns=("id", "nazwa", "typ", "nastepne"),
            show="headings",
            height=18,
        )
        self.tree.heading("id", text="nr_ewid")
        self.tree.column("id", width=90, anchor="center")
        self.tree.heading("nazwa", text="nazwa")
        self.tree.column("nazwa", width=260, anchor="w")
        self.tree.heading("typ", text="typ")
        self.tree.column("typ", width=140, anchor="w")
        self.tree.heading("nastepne", text="nastepne_zadanie")
        self.tree.column("nastepne", width=160, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        buttons = tk.Frame(left, bg=background)
        buttons.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(
            buttons,
            text="Szczegóły",
            command=self._open_details_for_selected,
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Odśwież",
            command=self._refresh_all,
        ).pack(side="left", padx=(8, 0))

        self._reload_tree()

        # prawy panel (hala) — szeroki
        right = tk.Frame(main, width=720, bg=background)
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        header = tk.Frame(right, bg=background)
        header.pack(fill="x", padx=8, pady=(10, 6))
        tk.Label(header, text="Hala (podgląd/edycja)", anchor="w").pack(side="left")

        self._mode_var = tk.StringVar(value="view")
        ttk.Radiobutton(
            header,
            text="Widok",
            variable=self._mode_var,
            value="view",
            command=lambda: self._set_hala_mode("view"),
        ).pack(side="right", padx=4)
        ttk.Radiobutton(
            header,
            text="Edycja",
            variable=self._mode_var,
            value="edit",
            command=lambda: self._set_hala_mode("edit"),
        ).pack(side="right", padx=4)

        self._canvas = tk.Canvas(
            right,
            width=700,
            height=520,
            bg="#0f172a",
            highlightthickness=1,
            highlightbackground="#334155",
        )
        self._canvas.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        try:
            from widok_hala.renderer import Renderer

            self._renderer = Renderer(self.root, self._canvas, self._machines)
            self._renderer.on_select = self._on_hala_select
            self._renderer.on_move = self._on_hala_move
            self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
            self._set_hala_mode("view")
        except Exception as e:
            tk.Label(
                self._canvas,
                text=f"Brak widok_hala/renderer.py: {e}",
                fg="#fca5a5",
                bg="#0f172a",
            ).place(x=20, y=20)

    def _reload_tree(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for machine in self._machines:
            machine_id = machine.get("id") or machine.get("nr_ewid") or ""
            nazwa = machine.get("nazwa") or machine.get("name") or ""
            typ = machine.get("typ") or ""
            nastepne = (
                machine.get("nastepne_zadanie")
                or machine.get("nastepne")
                or ""
            )
            self.tree.insert("", "end", values=(machine_id, nazwa, typ, nastepne))

    def _selected_mid(self) -> str | None:
        selection = self.tree.selection()
        if not selection:
            return None
        values = self.tree.item(selection[0], "values")
        return str(values[0]) if values else None

    def _open_details_for_selected(self):
        machine_id = self._selected_mid()
        if not machine_id:
            messagebox.showinfo("Maszyny", "Wybierz wiersz w tabeli.")
            return
        try:
            if hasattr(self._renderer, "_open_details"):
                self._renderer._open_details(machine_id)
        except Exception as e:
            messagebox.showerror("Maszyny", f"Nie można otworzyć opisu: {e}")

    def _refresh_all(self):
        # ponownie odczytaj ścieżki (gdyby użytkownik zmienił w Ustawieniach)
        self.PRIMARY_DATA, self.LEGACY_DATA = _pick_best_paths()
        print(f"[WM][Maszyny] REFRESH PRIMARY = {self.PRIMARY_DATA}")
        print(f"[WM][Maszyny] REFRESH LEGACY  = {self.LEGACY_DATA}")
        self._machines = self._load_and_migrate()
        self._reload_tree()
        if hasattr(self, "_renderer"):
            self._renderer.reload(self._machines)

    def _on_tree_select(self, _=None):
        mid = self._selected_mid()
        if mid and hasattr(self, "_renderer") and hasattr(self._renderer, "focus_machine"):
            self._renderer.focus_machine(str(mid))

    def _on_hala_select(self, mid: str):
        mid = str(mid)
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            if vals and str(vals[0]) == mid:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                break

    def _on_hala_move(self, machine_id: str, pos: dict):
        self._save_position(
            str(machine_id),
            int(pos.get("x", 0)),
            int(pos.get("y", 0)),
        )

    def _set_hala_mode(self, mode: str):
        if hasattr(self, "_renderer") and hasattr(self._renderer, "set_edit_mode"):
            self._renderer.set_edit_mode(mode == "edit")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Warsztat Menager — Maszyny")
    content = tk.Frame(root)
    content.pack(fill="both", expand=True)
    MaszynyGUI(content)
    root.mainloop()
