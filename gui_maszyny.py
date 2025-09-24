# gui_maszyny.py
# Wersja: 1.0.1 (2025-09-19)
# - Stały panel "Hala" po prawej (Widok/Edycja)
# - Drag&drop → zapis pozycji TYLKO do data/maszyny.json
# - Ukrycie przycisku "Hale" w menu bocznym (jeśli istnieje)

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from ui_theme import apply_theme_safe as apply_theme
from utils.gui_helpers import clear_frame
from utils_maszyny import SOURCE_MODES, index_by_id, save_machines, sort_machines
from widok_hali.renderer import Renderer

PRIMARY_DATA = os.path.join("data", "maszyny.json")
LEGACY_DATA = os.path.join("data", "maszyny", "maszyny.json")
MIGRATION_FLAG = os.path.join("data", ".machines_migrated.flag")


def _load_json_file(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _index_by_id(rows: list) -> dict:
    out = {}
    for r in rows or []:
        mid = str(r.get("id") or r.get("nr_ewid") or "").strip()
        if mid:
            out[mid] = r
    return out


def _merge_unique(primary_rows: list, legacy_rows: list) -> list:
    pi = _index_by_id(primary_rows)
    li = _index_by_id(legacy_rows)
    for mid, row in li.items():
        if mid not in pi:
            pi[mid] = row
    # sort po numeric/len
    def _key(s):
        return (len(s), s)

    return [pi[k] for k in sorted(pi.keys(), key=_key)]


def _save_primary(rows: list):
    os.makedirs(os.path.dirname(PRIMARY_DATA), exist_ok=True)
    with open(PRIMARY_DATA, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

class MaszynyGUI:
    """Panel zarządzania maszynami z podglądem hali."""

    def __init__(self, root: tk.Tk, side_menu: dict | None = None):
        self.root = root
        self.side_menu = side_menu or {}
        self._source_var = tk.StringVar(value="auto")
        self._source_info = tk.StringVar(value="")
        self._active_source = "auto"
        self._source = "auto"
        self._data_source_mode = "AUTO"
        self._counts: tuple[int, int] = (0, 0)
        self._machines = self._load_machines()
        self._renderer: Renderer | None = None
        self._details_btn: ttk.Button | None = None
        self._mode_var = tk.StringVar(value="view")

        self._hide_hale_button_if_present()
        self._build_ui()

    # ----- dane -----
    def _load_machines(self) -> list[dict]:
        requested = (self._source_var.get() or "auto").strip().lower()
        if requested not in SOURCE_MODES:
            requested = "auto"

        self._data_source_mode = requested.upper()

        if requested == "auto":
            machines = self._load_machines_pick_best()
        else:
            primary_rows = _load_json_file(PRIMARY_DATA)
            legacy_rows = _load_json_file(LEGACY_DATA)
            count_primary, count_legacy = len(primary_rows), len(legacy_rows)
            self._counts = (count_primary, count_legacy)

            if requested == "legacy":
                if count_legacy == 0:
                    print(
                        f"[WM][Maszyny] Wybrano LEGACY, ale brak danych → przełączam na PRIMARY ({count_primary})."
                    )
                    machines = primary_rows
                    self._active_source = "primary"
                    self._source = "primary"
                else:
                    print(f"[WM][Maszyny] Załadowano z LEGACY ({count_legacy})")
                    machines = legacy_rows
                    self._active_source = "legacy"
                    self._source = "legacy"
            else:
                print(f"[WM][Maszyny] Załadowano z PRIMARY ({count_primary})")
                machines = primary_rows
                self._active_source = "primary"
                self._source = "primary"

        machines = sort_machines(machines)

        summary = (
            f"Tryb: {requested.upper()}  →  aktywny: {self._active_source.upper()}  |  "
            f"PRIMARY: {self._counts[0]}  |  LEGACY: {self._counts[1]}"
        )
        self._source_info.set(summary)
        return machines

    def _load_machines_pick_best(self) -> list:
        """
        AUTO:
          - czyta oba pliki
          - wybiera większy lub scala
          - JEDNORAZOWO zapisuje wynik do PRIMARY (flaga migration)
        PRIMARY/LEGACY (wymuszone radiem) – czyta odpowiedni plik bez migracji.
        """
        mode = getattr(self, "_data_source_mode", "AUTO").upper()
        primary = _load_json_file(PRIMARY_DATA)
        legacy = _load_json_file(LEGACY_DATA)
        n_p, n_l = len(primary), len(legacy)

        # diagnostyka
        print(f"[DIAG][Maszyny] primary={n_p} file={PRIMARY_DATA} | legacy={n_l} file={LEGACY_DATA}")

        if mode == "PRIMARY":
            self._source = "primary"
            self._active_source = "primary"
            self._counts = (n_p, n_l)
            return primary
        if mode == "LEGACY":
            self._source = "legacy"
            self._active_source = "legacy"
            self._counts = (n_p, n_l)
            return legacy

        # AUTO
        if n_p == 0 and n_l == 0:
            self._source = "primary"
            self._active_source = "primary"
            self._counts = (0, 0)
            return []

        # jeżeli mamy flagę migracji – czytaj tylko PRIMARY (już scalone)
        if os.path.exists(MIGRATION_FLAG):
            self._source = "primary"
            self._active_source = "primary"
            self._counts = (n_p, n_l)
            return primary

        # różne wielkości → scala i zapisuje do PRIMARY
        if n_p != n_l:
            merged = _merge_unique(primary, legacy)
            _save_primary(merged)
            open(MIGRATION_FLAG, "w").close()
            self._source = "primary"
            self._active_source = "primary"
            self._counts = (len(merged), n_l)
            print(f"[WM][Maszyny] MIGRACJA: primary({n_p}) + legacy({n_l}) → primary({len(merged)}).")
            return merged

        # takie same ilości → i tak scala (dla unifikacji)
        merged = _merge_unique(primary, legacy)
        _save_primary(merged)
        open(MIGRATION_FLAG, "w").close()
        self._source = "primary"
        self._active_source = "primary"
        self._counts = (len(merged), n_l)
        print(f"[WM][Maszyny] MIGRACJA: liczby równe ({n_p}); zapis primary({len(merged)}).")
        return merged

    def _save_position(self, machine_id: str, x: int, y: int) -> None:
        try:
            machine_key = str(machine_id)
            if not machine_key:
                return

            data = _load_json_file(PRIMARY_DATA)
            legacy_rows = _load_json_file(LEGACY_DATA)
            count_legacy = len(legacy_rows)

            registry = index_by_id(data)
            row = registry.get(machine_key)
            if not row:
                row = {"id": machine_key, "nazwa": machine_key, "hala": 1}
                row["pozycja"] = {"x": int(x), "y": int(y)}
                data.append(row)
                print(
                    f"[WM][Maszyny] Dodano brakujący wpis {machine_key} przed zapisem."
                )
            else:
                row.setdefault("pozycja", {})
                row["pozycja"]["x"] = int(x)
                row["pozycja"]["y"] = int(y)

            sorted_rows = sort_machines(data)
            _save_primary(sorted_rows)

            local_registry = index_by_id(self._machines)
            local_row = local_registry.get(machine_key)
            if local_row is None:
                self._machines.append(row)
            else:
                local_row.setdefault("pozycja", {})
                local_row["pozycja"]["x"] = int(x)
                local_row["pozycja"]["y"] = int(y)

            self._machines = sort_machines(self._machines)

            new_count_primary = len(sorted_rows)
            self._counts = (new_count_primary, count_legacy)
            if self._active_source != "primary":
                print(
                    "[WM][Maszyny] MIGRACJA ZAKOŃCZONA → teraz źródłem jest "
                    "data/maszyny.json."
                )
            self._active_source = "primary"
            self._source = "primary"
            summary = (
                f"Tryb: {self._source_var.get().upper()}  →  aktywny: PRIMARY  |  "
                f"PRIMARY: {new_count_primary}  |  LEGACY: {count_legacy}"
            )
            self._source_info.set(summary)

            print(f"[WM][Maszyny] Zapisano pozycję {machine_id} -> ({x},{y})")
        except Exception as exc:  # pragma: no cover - IO
            print(f"[ERROR][Maszyny] Zapis pozycji nieudany: {exc}")

    # ----- UI -----
    def _hide_hale_button_if_present(self) -> None:
        try:
            hale_btn = None
            if isinstance(self.side_menu, dict):
                hale_btn = self.side_menu.get("Hale")
            if not hale_btn and hasattr(self.root, "btn_hale"):
                hale_btn = getattr(self.root, "btn_hale")
            if hale_btn:
                hidden = False
                for method_name in ("pack_forget", "grid_remove", "place_forget"):
                    try:
                        hide_method = getattr(hale_btn, method_name)
                    except AttributeError:
                        continue
                    try:
                        hide_method()
                        hidden = True
                        break
                    except Exception:
                        continue
                if hidden:
                    print("[WM][Maszyny] Ukryto przycisk 'Hale'")
        except Exception as exc:  # pragma: no cover - defensywne
            print(f"[WARN][Maszyny] Nie udało się ukryć 'Hale': {exc}")

    def _build_ui(self) -> None:
        main = tk.Frame(self.root)
        main.pack(fill="both", expand=True)

        left = tk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        source_frame = tk.Frame(left)
        source_frame.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(source_frame, text="Źródło danych:").pack(side="left")
        for mode in SOURCE_MODES:
            ttk.Radiobutton(
                source_frame,
                text=mode.capitalize(),
                value=mode,
                variable=self._source_var,
                command=self._on_source_change,
            ).pack(side="left", padx=(8, 0))

        info_frame = tk.Frame(left)
        info_frame.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(
            info_frame,
            textvariable=self._source_info,
            anchor="w",
            justify="left",
        ).pack(fill="x")

        tree_container = tk.Frame(left)
        tree_container.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.tree = ttk.Treeview(
            tree_container,
            columns=("id", "nazwa", "typ", "nastepne"),
            show="headings",
            height=18,
        )
        for column, label, width in (
            ("id", "nr_ewid", 90),
            ("nazwa", "nazwa", 260),
            ("typ", "typ", 140),
            ("nastepne", "nastepne_zadanie", 160),
        ):
            self.tree.heading(column, text=label)
            anchor = "center" if column in ("id", "nastepne") else "w"
            self.tree.column(column, width=width, anchor=anchor)
        scrollbar = ttk.Scrollbar(
            tree_container, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        buttons = tk.Frame(left)
        buttons.pack(fill="x", padx=12, pady=(0, 10))
        self._details_btn = ttk.Button(
            buttons, text="Szczegóły", command=self._open_details_for_selected
        )
        self._details_btn.pack(side="left")
        ttk.Button(buttons, text="Odśwież", command=self._refresh_all).pack(
            side="left", padx=(8, 0)
        )
        self._reload_tree()

        # RIGHT: hala
        right = tk.Frame(main, width=640, bg=main["bg"])
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        hdr = tk.Frame(right, bg=right["bg"]); hdr.pack(fill="x", padx=8, pady=(10, 6))
        tk.Label(hdr, text="Hala (podgląd/edycja)", anchor="w").pack(side="left")
        self._mode_var = tk.StringVar(value="view")
        ttk.Radiobutton(hdr, text="Widok", variable=self._mode_var, value="view",
                        command=lambda: self._set_hala_mode("view")).pack(side="right", padx=4)
        ttk.Radiobutton(hdr, text="Edycja", variable=self._mode_var, value="edit",
                        command=lambda: self._set_hala_mode("edit")).pack(side="right", padx=4)

        self._canvas = tk.Canvas(
            right,
            width=640,
            height=540,
            bg="#0f172a",
            highlightthickness=1,
            highlightbackground="#334155"
        )
        self._canvas.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # tylko Renderer (bez starych funkcji)
        self._renderer = Renderer(self.root, self._canvas, self._machines)

        self._renderer.on_select = self._on_hala_select
        self._renderer.on_move = self._on_hala_move
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._set_hala_mode("view")
        self._set_details_button_enabled(True)

    def _on_source_change(self) -> None:
        self._machines = self._load_machines()
        self._reload_tree()
        if self._renderer:
            self._renderer.reload(self._machines)

    def _set_details_button_enabled(self, enabled: bool) -> None:
        if not self._details_btn:
            return
        state = "normal" if enabled else "disabled"
        try:
            self._details_btn.configure(state=state)
        except Exception:  # pragma: no cover - defensywne
            pass

    # ----- tabela -----
    def _reload_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for machine in self._machines:
            mid = machine.get("id") or machine.get("nr_ewid") or ""
            nazwa = machine.get("nazwa") or machine.get("name") or ""
            typ = machine.get("typ") or ""
            nastepne = (
                machine.get("nastepne_zadanie")
                or machine.get("nastepne")
                or ""
            )
            self.tree.insert(
                "",
                "end",
                values=(mid, nazwa, typ, nastepne or ""),
            )

    def _selected_mid(self) -> str | None:
        selection = self.tree.selection()
        if not selection:
            return None
        values = self.tree.item(selection[0], "values")
        return str(values[0]) if values else None

    def _open_details_for_selected(self) -> None:
        machine_id = self._selected_mid()
        if not machine_id:
            messagebox.showinfo("Maszyny", "Wybierz maszynę z listy.")
            return
        if not self._renderer:
            messagebox.showwarning(
                "Maszyny",
                "Brak modułu widoku hali (widok_hali/renderer.py).",
            )
            return
        try:
            self._renderer._open_details(machine_id)  # noqa: SLF001 - API renderer'a
        except Exception as exc:  # pragma: no cover - zależne od renderer'a
            messagebox.showerror("Maszyny", f"Nie można otworzyć szczegółów: {exc}")

    def _refresh_all(self) -> None:
        self._machines = self._load_machines()
        self._reload_tree()
        if self._renderer:
            self._renderer.reload(self._machines)

    # ----- synchronizacja z halą -----
    def _on_tree_select(self, _event=None) -> None:  # noqa: D401,ARG002 - sygnatura Tk
        machine_id = self._selected_mid()
        if machine_id and self._renderer and hasattr(self._renderer, "focus_machine"):
            try:
                self._renderer.focus_machine(machine_id)
            except Exception:  # pragma: no cover - zależne od renderer'a
                pass

    def _on_hala_select(self, machine_id: str) -> None:
        mid = str(machine_id)
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            if values and str(values[0]) == mid:
                self.tree.selection_set(item)
                self.tree.see(item)
                break

    def _on_hala_move(self, machine_id: str, new_pos: dict) -> None:
        self._save_position(machine_id, new_pos.get("x", 0), new_pos.get("y", 0))

    def _on_machine_update(self, machine_id: str, _updated: dict | None = None) -> None:
        if not machine_id:
            return

        previous_source = self._active_source
        legacy_count = self._counts[1] if self._counts else 0

        sorted_rows = sort_machines(self._machines)
        self._machines[:] = sorted_rows
        save_machines(self._machines)

        if previous_source != "primary":
            print(
                "[WM][Maszyny] MIGRACJA ZAKOŃCZONA → teraz źródłem jest "
                "data/maszyny.json."
            )
        self._active_source = "primary"

        primary_count = len(self._machines)
        self._counts = (primary_count, legacy_count)
        summary = (
            f"Tryb: {self._source_var.get().upper()}  →  aktywny: PRIMARY  |  "
            f"PRIMARY: {primary_count}  |  LEGACY: {legacy_count}"
        )
        self._source_info.set(summary)

        self._reload_tree()
        print(f"[WM][Maszyny] Zapisano zmiany w danych maszyny {machine_id}")

    def _set_hala_mode(self, mode: str) -> None:
        if not self._renderer:
            self._mode_var.set("view")
            return
        edit = mode == "edit"
        self._mode_var.set("edit" if edit else "view")
        if hasattr(self._renderer, "set_edit_mode"):
            try:
                self._renderer.set_edit_mode(edit)
            except Exception:  # pragma: no cover - zależne od renderer'a
                pass


# ----- API zgodne wstecz -----
def panel_maszyny(root, frame, login=None, rola=None):  # noqa: D401 - API historyczne
    """Buduje panel maszyn we wskazanym kontenerze ``frame``."""

    clear_frame(frame)
    apply_theme(root)
    apply_theme(frame)
    gui = MaszynyGUI(frame)
    frame._maszyny_gui = gui  # type: ignore[attr-defined]
    return gui


if __name__ == "__main__":  # pragma: no cover - uruchomienie testowe
    root = tk.Tk()
    root.title("Warsztat Menager — Maszyny")

    sidebar = tk.Frame(root)
    sidebar.pack(side="left", fill="y")
    btn_hale = tk.Button(sidebar, text="Hale")
    btn_hale.pack()
    root.btn_hale = btn_hale  # type: ignore[attr-defined]

    content = tk.Frame(root)
    content.pack(side="right", fill="both", expand=True)

    MaszynyGUI(content, side_menu={"Hale": btn_hale})
    root.mainloop()
