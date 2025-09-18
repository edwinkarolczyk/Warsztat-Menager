# Wersja: 1.2.0
# Plik: gui_maszyny.py
"""Panel zarządzania maszynami wraz z podglądem hali."""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from ui_theme import apply_theme_safe as apply_theme
from utils.gui_helpers import clear_frame

try:
    from widok_hali.renderer import Renderer
except Exception as exc:  # pragma: no cover - zależy od środowiska
    Renderer = None
    print(f"[ERROR][Maszyny] Brak renderer'a hali: {exc}")

DATA_PATH = os.path.join("data", "maszyny.json")


class MaszynyGUI:
    """Prosty panel maszyn współpracujący z rendererem hali."""

    def __init__(self, root: tk.Misc, side_menu: dict | None = None):
        """Buduje panel we wskazanym kontenerze ``root``."""

        self.root = root
        self.side_menu = side_menu or {}
        self._machines = self._load_machines()
        self._renderer: Renderer | None = None

        self._mode_var = tk.StringVar(master=self.root, value="view")
        self._mode_buttons: list[ttk.Radiobutton] = []

        self._hide_hale_button_if_present()
        self._build_ui()

    # ---------- dane ----------
    def _load_machines(self) -> list[dict]:
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, list):
                    return data
        except Exception as exc:  # pragma: no cover - operacje IO
            print(f"[WARN][Maszyny] Nie wczytano {DATA_PATH}: {exc}")
        return []

    def _save_position(self, machine_id: str, x: int, y: int) -> None:
        """Zapis wyłącznie współrzędnych maszyny do pliku danych."""

        try:
            data = self._machines[:]
            for machine in data:
                mid = str(machine.get("id") or machine.get("nr_ewid"))
                if mid == str(machine_id):
                    machine.setdefault("pozycja", {})
                    machine["pozycja"]["x"] = int(x)
                    machine["pozycja"]["y"] = int(y)
                    break
            with open(DATA_PATH, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            self._machines = data
            print(
                f"[WM][Maszyny] Zapisano pozycję maszyny {machine_id} -> ({x},{y})"
            )
        except Exception as exc:  # pragma: no cover - operacje IO
            print(f"[ERROR][Maszyny] Zapis pozycji nieudany: {exc}")

    # ---------- UI ----------
    def _bg_color(self, widget: tk.Misc, default: str = "#111") -> str:
        try:
            return widget.cget("bg")
        except Exception:
            return default

    def _hide_hale_button_if_present(self) -> None:
        """Bezpiecznie ukrywa przycisk "Hale" jeżeli jest dostępny."""

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
                    if hasattr(hale_btn, "grid_remove"):
                        hale_btn.grid_remove()
                print("[WM][Maszyny] Ukryto przycisk 'Hale' w menu bocznym")
        except Exception as exc:  # pragma: no cover - defensywne
            print(f"[WARN][Maszyny] Nie udało się ukryć 'Hale': {exc}")

    def _build_ui(self) -> None:
        main = tk.Frame(self.root, bg=self._bg_color(self.root))
        main.pack(fill="both", expand=True)

        left = tk.Frame(main, bg=self._bg_color(main))
        left.pack(side="left", fill="both", expand=True)

        tk.Label(left, text="Panel maszyn", anchor="w").pack(
            fill="x", padx=12, pady=(10, 6)
        )

        self.tree = ttk.Treeview(
            left,
            columns=("id", "nazwa", "typ", "nastepne"),
            show="headings",
            height=16,
        )
        self.tree.heading("id", text="nr_ewid")
        self.tree.heading("nazwa", text="nazwa")
        self.tree.heading("typ", text="typ")
        self.tree.heading("nastepne", text="nastepne_zadanie")
        self.tree.column("id", width=90, anchor="center")
        self.tree.column("nazwa", width=260, anchor="w")
        self.tree.column("typ", width=140, anchor="w")
        self.tree.column("nastepne", width=160, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        btns = tk.Frame(left, bg=self._bg_color(left))
        btns.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(
            btns, text="Szczegóły", command=self._open_details_for_selected
        ).pack(side="left")
        ttk.Button(btns, text="Odśwież", command=self._refresh_all).pack(
            side="left", padx=(8, 0)
        )

        self._reload_tree()

        right = tk.Frame(main, width=460, bg=self._bg_color(main))
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        hdr = tk.Frame(right, bg=self._bg_color(right))
        hdr.pack(fill="x", padx=8, pady=(10, 6))
        tk.Label(hdr, text="Hala (podgląd/edycja)", anchor="w").pack(side="left")

        for text, value in (("Widok", "view"), ("Edycja", "edit")):
            btn = ttk.Radiobutton(
                hdr,
                text=text,
                variable=self._mode_var,
                value=value,
                command=lambda m=value: self._set_hala_mode(m),
            )
            btn.pack(side="right", padx=4)
            self._mode_buttons.append(btn)

        self._canvas = tk.Canvas(
            right,
            width=440,
            height=360,
            bg="#0f172a",
            highlightthickness=1,
            highlightbackground="#334155",
        )
        self._canvas.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        if Renderer is None:
            tk.Label(
                self._canvas,
                text="Brak modułu widok_hali/renderer.py",
                fg="#fca5a5",
                bg="#0f172a",
            ).place(x=20, y=20)
            for btn in self._mode_buttons:
                btn.configure(state="disabled")
            return

        try:
            self._renderer = Renderer(self.root, self._canvas, self._machines)
        except Exception as exc:  # pragma: no cover - zależy od środowiska
            print(f"[ERROR][Maszyny] Nie można zainicjalizować Renderer: {exc}")
            tk.Label(
                self._canvas,
                text="Błąd inicjalizacji renderer'a hali",
                fg="#fca5a5",
                bg="#0f172a",
            ).place(x=20, y=20)
            for btn in self._mode_buttons:
                btn.configure(state="disabled")
            self._renderer = None
            return

        self._renderer.on_select = self._on_hala_select
        self._renderer.on_move = self._on_hala_move

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._set_hala_mode("view")

    # ---------- akcje tabeli ----------
    def _reload_tree(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
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
        sel = self.tree.selection()
        if not sel:
            return None
        values = self.tree.item(sel[0], "values")
        return str(values[0]) if values else None

    def _open_details_for_selected(self) -> None:
        mid = self._selected_mid()
        if not mid:
            messagebox.showinfo("Maszyny", "Wybierz wiersz w tabeli.")
            return
        if not self._renderer:
            messagebox.showwarning(
                "Maszyny",
                (
                    "Brak dostępnego widoku hali – sprawdź moduł "
                    "widok_hali/renderer.py."
                ),
            )
            return
        try:
            self._renderer._open_details(mid)  # noqa: SLF001 - świadomie
        except Exception as exc:  # pragma: no cover - zależy od GUI
            messagebox.showerror("Maszyny", f"Nie można otworzyć opisu: {exc}")

    def _refresh_all(self) -> None:
        self._machines = self._load_machines()
        self._reload_tree()
        if self._renderer:
            self._renderer.reload(self._machines)

    # ---------- integracja: tabela ↔ hala ----------
    def _on_tree_select(self, event=None) -> None:  # noqa: ARG002 - sygnatura Tk
        mid = self._selected_mid()
        if not mid or not self._renderer:
            return
        try:
            if hasattr(self._renderer, "focus_machine"):
                self._renderer.focus_machine(str(mid))
        except Exception:  # pragma: no cover - zależy od renderer'a
            pass

    def _on_hala_select(self, machine_id: str) -> None:
        mid = str(machine_id)
        for iid in self.tree.get_children():
            values = self.tree.item(iid, "values")
            if values and str(values[0]) == mid:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                break

    def _on_hala_move(self, machine_id: str, new_pos: dict) -> None:
        x = int(new_pos.get("x", 0))
        y = int(new_pos.get("y", 0))
        self._save_position(machine_id, x, y)

    def _set_hala_mode(self, mode: str) -> None:
        if not self._renderer:
            self._mode_var.set("view")
            return
        on = mode == "edit"
        self._mode_var.set("edit" if on else "view")
        if hasattr(self._renderer, "set_edit_mode"):
            self._renderer.set_edit_mode(on)
        print(f"[WM][Maszyny] Tryb hali: {'Edycja' if on else 'Widok'}")


def panel_maszyny(root, frame, login=None, rola=None):  # noqa: D401 - API historyczne
    """Kompatybilna funkcja budująca panel maszyn w ``frame``."""

    clear_frame(frame)
    apply_theme(root)
    apply_theme(frame)
    gui = MaszynyGUI(frame)
    frame._maszyny_gui = gui  # type: ignore[attr-defined]
    return gui


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Warsztat Menager — Maszyny")

    side = tk.Frame(root)
    side.pack(side="left", fill="y")
    btn_hale = tk.Button(side, text="Hale")
    btn_hale.pack()
    root.btn_hale = btn_hale  # type: ignore[attr-defined]

    content = tk.Frame(root)
    content.pack(side="right", fill="both", expand=True)

    app = MaszynyGUI(content, side_menu={"Hale": btn_hale})
    root.mainloop()
