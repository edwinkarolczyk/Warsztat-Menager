import tkinter as tk
from tkinter import ttk

try:
    # Nasz ciemny motyw
    from ui_theme import apply_theme_safe as apply_theme
except Exception:
    def apply_theme(widget):  # defensywnie
        pass


def open_orders_window(master=None, context=None):
    """
    Otwiera osobne okno 'Zamówienia'.
    'context' to opcjonalny słownik (np. prefill pozycji z braków).
    """
    root = None
    try:
        root = master.winfo_toplevel() if master else None
    except Exception:
        root = None

    win = tk.Toplevel(root or master)
    win.title("Zamówienia")
    win.geometry("720x480")
    apply_theme(win)

    # Nagłówek
    header = ttk.Frame(win, padding=(10, 10, 10, 4))
    header.pack(fill="x")
    ttk.Label(header, text="Zamówienia (w przygotowaniu: kreator)", style="WM.H1.TLabel").pack(side="left")

    # Informacja o kontekście (prefill)
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)

    if isinstance(context, dict) and context:
        ttk.Label(body, text="Przekazany kontekst:", style="WM.TLabel").pack(anchor="w")
        box = tk.Text(body, height=8)
        box.pack(fill="both", expand=False, pady=(6, 12))
        try:
            import json

            box.insert("1.0", json.dumps(context, ensure_ascii=False, indent=2))
        except Exception:
            box.insert("1.0", str(context))
        box.configure(state="disabled")
    else:
        ttk.Label(
            body,
            text="Brak wstępnych danych. Wersja podstawowa – do rozbudowy.",
            style="WM.TLabel",
        ).pack(anchor="w")

    # Stopka (na przyszłość: Dalej/Wstecz/Zapisz)
    footer = ttk.Frame(win, padding=(10, 6))
    footer.pack(fill="x", side="bottom")
    ttk.Button(footer, text="Zamknij", command=win.destroy, style="WM.Side.TButton").pack(side="right")

    try:
        win.transient(root)
        win.grab_set()
        win.focus_set()
    except Exception:
        pass

    return win
