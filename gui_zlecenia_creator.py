"""Okno kreatora nowych zleceń."""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from zlecenia_utils import create_order_skeleton, save_order

try:  # pragma: no cover - podczas testów motyw nie jest istotny
    from ui_theme import apply_theme_safe as apply_theme  # type: ignore
except Exception:  # pragma: no cover - fallback gdy motyw nie jest dostępny
    def apply_theme(widget):  # type: ignore
        return None


def open_order_creator(master: tk.Widget | None = None, autor: str = "system") -> tk.Toplevel:
    root = master.winfo_toplevel() if master else None
    window = tk.Toplevel(root)
    window.title("Kreator – Dodaj zlecenie")
    window.geometry("720x500")
    apply_theme(window)

    state: dict[str, Any] = {
        "step": 0,
        "kind": None,
        "widgets": {},
        "kind_var": tk.StringVar(value=""),
    }

    container = ttk.Frame(window, padding=12)
    container.pack(fill="both", expand=True)

    footer = ttk.Frame(window, padding=(10, 6))
    footer.pack(fill="x", side="bottom")

    btn_back = ttk.Button(footer, text="Wstecz", command=lambda: _go_back())
    btn_back.pack(side="left", padx=4)
    btn_next = ttk.Button(footer, text="Dalej", command=lambda: _go_next())
    btn_next.pack(side="right", padx=4)
    btn_cancel = ttk.Button(footer, text="Anuluj", command=window.destroy)
    btn_cancel.pack(side="right", padx=4)

    def _clear() -> None:
        for widget in container.winfo_children():
            widget.destroy()

    def _step0() -> None:
        _clear()
        ttk.Label(
            container,
            text="Krok 1/2 – Wybierz rodzaj zlecenia",
            style="WM.H1.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        kind_var: tk.StringVar = state["kind_var"]  # type: ignore[assignment]
        kind_var.set(state.get("kind") or "")

        def _on_select(value: str) -> None:
            state["kind"] = value

        for kind, label in (
            ("ZW", "Zlecenie wewnętrzne (ZW)"),
            ("ZN", "Zlecenie na narzędzie (ZN)"),
            ("ZM", "Naprawa/awaria maszyny (ZM)"),
        ):
            radio = ttk.Radiobutton(
                container,
                text=label,
                value=kind,
                variable=kind_var,
                command=lambda k=kind: _on_select(k),
            )
            radio.pack(anchor="w", pady=4)

    def _step1() -> None:
        _clear()
        state["widgets"] = {}
        kind = state.get("kind")

        if kind == "ZW":
            ttk.Label(
                container,
                text="Krok 2 – Szczegóły Zlecenia Wewnętrznego",
                style="WM.H1.TLabel",
            ).pack(anchor="w", pady=(0, 12))

            ttk.Label(container, text="Produkt:").pack(anchor="w")
            prod_dir = os.path.join("data", "produkty")
            try:
                products = [
                    os.path.splitext(filename)[0]
                    for filename in os.listdir(prod_dir)
                    if filename.endswith(".json")
                ]
            except FileNotFoundError:
                products = []
            cb_prod = ttk.Combobox(container, values=products, state="readonly")
            cb_prod.pack(anchor="w")
            state["widgets"]["produkt"] = cb_prod

            ttk.Label(container, text="Ilość:").pack(anchor="w")
            entry_qty = ttk.Entry(container)
            entry_qty.pack(anchor="w")
            state["widgets"]["ilosc"] = entry_qty

        elif kind == "ZN":
            ttk.Label(
                container,
                text="Krok 2 – Szczegóły Zlecenia na Narzędzie",
                style="WM.H1.TLabel",
            ).pack(anchor="w", pady=(0, 12))

            tools_dir = os.path.join("data", "narzedzia")
            try:
                tools = [
                    os.path.splitext(filename)[0]
                    for filename in os.listdir(tools_dir)
                    if filename.endswith(".json")
                    and filename.split(".")[0].isdigit()
                    and 500 <= int(filename.split(".")[0]) <= 1000
                ]
            except FileNotFoundError:
                tools = []
            ttk.Label(container, text="Wybierz narzędzie (SN 500–1000):").pack(anchor="w")
            cb_tool = ttk.Combobox(container, values=tools, state="readonly")
            cb_tool.pack(anchor="w")
            state["widgets"]["narzedzie"] = cb_tool

            ttk.Label(container, text="Komentarz co do naprawy/awarii:").pack(anchor="w")
            entry_comment = ttk.Entry(container, width=60)
            entry_comment.pack(anchor="w")
            state["widgets"]["komentarz"] = entry_comment

        elif kind == "ZM":
            ttk.Label(
                container,
                text="Krok 2 – Szczegóły Naprawy/Awarii Maszyny",
                style="WM.H1.TLabel",
            ).pack(anchor="w", pady=(0, 12))

            machines_path = os.path.join("data", "maszyny.json")
            try:
                with open(machines_path, "r", encoding="utf-8") as handle:
                    machines_data = json.load(handle)
            except Exception:
                machines_data = []

            if isinstance(machines_data, dict):
                machines_raw = machines_data.get("maszyny", []) or []
            elif isinstance(machines_data, list):
                machines_raw = machines_data
            else:
                machines_raw = []

            machines = [
                f"{machine.get('id')} - {machine.get('nazwa', '')}".strip()
                for machine in machines_raw
                if machine.get("id") is not None
            ]

            ttk.Label(container, text="Maszyna:").pack(anchor="w")
            cb_machine = ttk.Combobox(
                container,
                values=machines,
                state="readonly",
                width=40,
            )
            cb_machine.pack(anchor="w")
            state["widgets"]["maszyna"] = cb_machine

            ttk.Label(container, text="Opis awarii:").pack(anchor="w")
            entry_desc = ttk.Entry(container, width=60)
            entry_desc.pack(anchor="w")
            state["widgets"]["opis"] = entry_desc

            ttk.Label(container, text="Pilność:").pack(anchor="w")
            priority_values = ["niski", "normalny", "wysoki"]
            cb_priority = ttk.Combobox(
                container,
                values=priority_values,
                state="readonly",
                width=12,
            )
            cb_priority.pack(anchor="w")
            if priority_values:
                default_idx = 1 if len(priority_values) > 1 else 0
                cb_priority.current(default_idx)
            state["widgets"]["pilnosc"] = cb_priority

        else:
            ttk.Label(container, text="Nie wybrano rodzaju zlecenia.").pack(anchor="w")

        ttk.Button(container, text="Utwórz", command=_finish).pack(pady=20)

    def _finish() -> None:
        kind = state.get("kind")
        widgets: dict[str, Any] = state.get("widgets", {})  # type: ignore[assignment]

        try:
            if kind == "ZW":
                product = widgets["produkt"].get().strip()  # type: ignore[call-arg]
                qty_raw = widgets["ilosc"].get().strip()  # type: ignore[call-arg]
                if not product:
                    raise ValueError("Wybierz produkt.")
                if not qty_raw:
                    raise ValueError("Podaj ilość.")
                try:
                    ilosc = int(qty_raw)
                except ValueError:
                    raise ValueError("Ilość musi być liczbą całkowitą.") from None
                if ilosc <= 0:
                    raise ValueError("Ilość musi być dodatnia.")
                data = create_order_skeleton(
                    "ZW",
                    autor,
                    f"ZW na {product}",
                    {"produkt": product},
                    ilosc=ilosc,
                    produkt=product,
                )
            elif kind == "ZN":
                tool = widgets["narzedzie"].get().strip()  # type: ignore[call-arg]
                if not tool:
                    raise ValueError("Wybierz narzędzie.")
                comment = widgets["komentarz"].get().strip()  # type: ignore[call-arg]
                data = create_order_skeleton(
                    "ZN",
                    autor,
                    "ZN",
                    {"narzedzie_id": tool},
                    komentarz=comment,
                )
            elif kind == "ZM":
                machine_raw = widgets["maszyna"].get().strip()  # type: ignore[call-arg]
                if not machine_raw:
                    raise ValueError("Wybierz maszynę.")
                machine_id = machine_raw.split(" - ")[0]
                description = widgets["opis"].get().strip()  # type: ignore[call-arg]
                priority = widgets["pilnosc"].get().strip()  # type: ignore[call-arg]
                if not priority:
                    raise ValueError("Wybierz pilność.")
                data = create_order_skeleton(
                    "ZM",
                    autor,
                    "ZM",
                    {"maszyna_id": machine_id},
                    komentarz=description,
                    pilnosc=priority,
                )
            else:
                raise ValueError("Nie wybrano rodzaju zlecenia.")
        except ValueError as exc:
            messagebox.showerror("Błąd", str(exc), parent=window)
            return
        except Exception as exc:  # pragma: no cover - zabezpieczenie na wypadek błędu
            messagebox.showerror("Błąd", f"Nie udało się utworzyć zlecenia: {exc}", parent=window)
            return

        try:
            save_order(data)
        except Exception as exc:  # pragma: no cover - zapis może się nie udać
            messagebox.showerror("Błąd", f"Nie udało się zapisać zlecenia: {exc}", parent=window)
            return

        messagebox.showinfo("Sukces", f"Zlecenie {data['id']} utworzone", parent=window)
        window.destroy()

    def _go_back() -> None:
        if state["step"] > 0:
            state["step"] = int(state["step"]) - 1
        _refresh()

    def _go_next() -> None:
        if state["step"] == 0:
            if not state.get("kind"):
                messagebox.showwarning(
                    "Brak wyboru",
                    "Najpierw wybierz rodzaj zlecenia.",
                    parent=window,
                )
                return
            state["step"] = 1
        _refresh()

    def _refresh() -> None:
        if state["step"] == 0:
            btn_back.state(["disabled"])
            btn_next.state(["!disabled"])
            _step0()
        elif state["step"] == 1:
            btn_back.state(["!disabled"])
            btn_next.state(["disabled"])
            _step1()

    _refresh()
    window.transient(root)
    window.grab_set()
    return window
