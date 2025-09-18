"""Prosty kreator tworzenia zleceń (wersja szkieletowa)."""

import tkinter as tk
from tkinter import ttk

try:
    from ui_theme import apply_theme_safe as apply_theme
except Exception:
    def apply_theme(widget):
        """Fallback gdy motyw nie jest dostępny."""
        return None


def open_order_creator(master=None):
    """Otwiera okno Kreatora Zleceń (ZW / ZN / ZM)."""
    root = master.winfo_toplevel() if master else None
    win = tk.Toplevel(root)
    win.title("Kreator – Dodaj zlecenie")
    win.geometry("640x480")
    apply_theme(win)

    state: dict[str, object] = {
        "step": 0,
        "kind": None,
    }
    kind_var = tk.StringVar(value=state.get("kind") or "")

    container = ttk.Frame(win, padding=12)
    container.pack(fill="both", expand=True)

    footer = ttk.Frame(win, padding=(10, 6))
    footer.pack(fill="x", side="bottom")

    btn_back = ttk.Button(footer, text="Wstecz", command=lambda: _go_back())
    btn_back.pack(side="left", padx=4)
    btn_next = ttk.Button(footer, text="Dalej", command=lambda: _go_next())
    btn_next.pack(side="right", padx=4)
    btn_cancel = ttk.Button(footer, text="Anuluj", command=win.destroy)
    btn_cancel.pack(side="right", padx=4)

    def _clear():
        for widget in container.winfo_children():
            widget.destroy()

    def _step0():
        _clear()
        kind_var.set(state.get("kind") or "")
        ttk.Label(
            container,
            text="Krok 1/2 – Wybierz rodzaj zlecenia",
            style="WM.H1.TLabel",
        ).pack(anchor="w", pady=(0, 12))
        options = [
            ("ZW", "Zlecenie wewnętrzne (ZW)"),
            ("ZN", "Zlecenie na narzędzie (ZN)"),
            ("ZM", "Naprawa/awaria maszyny (ZM)"),
        ]
        for kind, label in options:
            radio = ttk.Radiobutton(
                container,
                text=label,
                value=kind,
                variable=kind_var,
                command=lambda k=kind: state.update({"kind": k}),
            )
            radio.pack(anchor="w", pady=4)

    def _step1():
        _clear()
        kind = state.get("kind")
        if kind == "ZW":
            ttk.Label(
                container,
                text="Krok 2/2 – Szczegóły Zlecenia Wewnętrznego",
                style="WM.H1.TLabel",
            ).pack(anchor="w", pady=(0, 12))
            ttk.Label(
                container,
                text="(tu w kolejnych iteracjach: wybór produktu, ilości, BOM)",
            ).pack(anchor="w")
        elif kind == "ZN":
            ttk.Label(
                container,
                text="Krok 2/2 – Szczegóły Zlecenia na Narzędzie",
                style="WM.H1.TLabel",
            ).pack(anchor="w", pady=(0, 12))
            ttk.Label(
                container,
                text="(tu: wybór starego narzędzia SN, opis co do naprawy)",
            ).pack(anchor="w")
        elif kind == "ZM":
            ttk.Label(
                container,
                text="Krok 2/2 – Szczegóły Naprawy/Awarii Maszyny",
                style="WM.H1.TLabel",
            ).pack(anchor="w", pady=(0, 12))
            ttk.Label(
                container,
                text="(tu: wybór maszyny, opis awarii, pilność)",
            ).pack(anchor="w")
        else:
            ttk.Label(
                container,
                text="Nie wybrano rodzaju zlecenia.",
                style="WM.TLabel",
            ).pack(anchor="w")

        ttk.Button(
            container,
            text="Utwórz (na razie placeholder)",
            command=lambda: _finish(),
        ).pack(pady=20)

    def _finish():
        print("[WM-DBG][ZLECENIA] Utworzono szkic zlecenia (placeholder)")
        win.destroy()

    def _go_back():
        if state["step"] > 0:
            state["step"] -= 1
        _refresh()

    def _go_next():
        if state["step"] == 0:
            if not state.get("kind"):
                print("[WM-DBG][ZLECENIA] Brak wyboru rodzaju – nie można przejść dalej")
                return
            state["step"] = 1
        _refresh()

    def _refresh():
        if state["step"] == 0:
            btn_back["state"] = "disabled"
            _step0()
        elif state["step"] == 1:
            btn_back["state"] = "normal"
            _step1()

    _refresh()
    win.transient(root)
    win.grab_set()
    return win
