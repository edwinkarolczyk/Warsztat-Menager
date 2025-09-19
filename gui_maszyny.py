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

try:
    from widok_hali.renderer import Renderer
except Exception as exc:  # pragma: no cover - zależne od środowiska
    Renderer = None
    print(f"[ERROR][Maszyny] Brak renderer'a hali: {exc}")

DATA_PATH = os.path.join("data", "maszyny.json")


class MaszynyGUI:
    """Panel zarządzania maszynami z podglądem hali."""

    def __init__(self, root: tk.Tk, side_menu: dict | None = None):
        self.root = root
        self.side_menu = side_menu or {}
        self._machines = self._load_machines()
        self._renderer: Renderer | None = None
        self._mode_var = tk.StringVar(value="view")

        self._hide_hale_button_if_present()
        self._build_ui()

    # ----- dane -----
    def _load_machines(self) -> list[dict]:
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as source:
                data = json.load(source)
                return data if isinstance(data, list) else []
        except Exception as exc:  # pragma: no cover - IO
            print(f"[WARN][Maszyny] Nie wczytano {DATA_PATH}: {exc}")
            return []

    def _save_position(self, machine_id: str, x: int, y: int) -> None:
        try:
            data = self._machines[:]
            for machine in data:
                mid = str(machine.get("id") or machine.get("nr_ewid"))
                if mid == str(machine_id):
                    machine.setdefault("pozycja", {})
                    machine["pozycja"]["x"] = int(x)
                    machine["pozycja"]["y"] = int(y)
                    break
            with open(DATA_PATH, "w", encoding="utf-8") as target:
                json.dump(data, target, ensure_ascii=False, indent=2)
            self._machines = data
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
                hale_btn.pack_forget()
                print("[WM][Maszyny] Ukryto przycisk 'Hale'")
        except Exception as exc:  # pragma: no cover - defensywne
            print(f"[WARN][Maszyny] Nie udało się ukryć 'Hale': {exc}")

    def _build_ui(self) -> None:
        main = tk.Frame(self.root)
        main.pack(fill="both", expand=True)

        left = tk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        self.tree = ttk.Treeview(
            left,
            columns=("id", "nazwa", "typ", "nastepne"),
            show="headings",
            height=16,
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
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        buttons = tk.Frame(left)
        buttons.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(buttons, text="Szczegóły", command=self._open_details_for_selected).pack(
            side="left"
        )
        ttk.Button(buttons, text="Odśwież", command=self._refresh_all).pack(
            side="left", padx=(8, 0)
        )
        self._reload_tree()

        right = tk.Frame(main, width=460)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        header = tk.Frame(right)
        header.pack(fill="x", padx=8, pady=(10, 6))
        tk.Label(header, text="Hala (podgląd/edycja)").pack(side="left")

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
            width=440,
            height=360,
            bg="#0f172a",
            highlightthickness=1,
            highlightbackground="#334155",
        )
        self._canvas.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        if Renderer:
            try:
                self._renderer = Renderer(self.root, self._canvas, self._machines)
            except Exception as exc:  # pragma: no cover - zależne od renderer'a
                self._renderer = None
                print(f"[ERROR][Maszyny] Nie udało się zainicjalizować Renderer: {exc}")
            else:
                self._renderer.on_select = self._on_hala_select
                self._renderer.on_move = self._on_hala_move
                self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
                self._set_hala_mode("view")
        else:
            tk.Label(self._canvas, text="Brak renderer.py", fg="red").place(x=20, y=20)

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
