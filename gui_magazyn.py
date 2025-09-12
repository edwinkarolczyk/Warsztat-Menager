# Plik: gui_magazyn.py
# Wersja pliku: 1.4.0
# Zmiany 1.4.0:
# - Tabela Magazynu uproszczona do 6 kolumn zgodnie z makietą:
#   ID | Typ | Rozmiar | Nazwa | Stan | Tech. zadania
# - Brak zmian w IO ani strukturach danych; tylko prezentacja.
# - Bezpieczne odczyty pól opcjonalnych: item["rozmiar"], item["zadania"].
#
# Zgodnie z ustaleniem: zmieniamy tylko to, co potrzebne.

import tkinter as tk
from tkinter import ttk, messagebox

from ui_theme import apply_theme_safe as apply_theme

# Bezpieczne importy IO
try:
    import magazyn_io
    HAVE_MAG_IO = True
except Exception:
    magazyn_io = None
    HAVE_MAG_IO = False

import logika_magazyn as LM


# Docelowy zestaw kolumn (6)
COLUMNS = ("id", "typ", "rozmiar", "nazwa", "stan", "zadania")


def _load_data():
    """Czyta magazyn bezpiecznie (preferuj magazyn_io.load, inaczej LM.load_magazyn)."""
    try:
        if HAVE_MAG_IO and hasattr(magazyn_io, "load"):
            data = magazyn_io.load()
        else:
            data = LM.load_magazyn()
    except Exception:
        data = {}
    return data.get("items", {}), (data.get("meta", {}) or {}).get("order", [])


def _format_row(item_id: str, item: dict):
    """Mapowanie rekordu na 6 kolumn z miękkimi fallbackami."""
    typ = (item.get("typ") or "").strip()
    rozmiar = (item.get("rozmiar") or "").strip()  # opcjonalne
    nazwa = (item.get("nazwa") or "").strip()

    # Stan + jednostka (jeśli jest)
    stan_val = item.get("stan", "")
    try:
        stan_txt = f"{float(stan_val):g}"
    except Exception:
        stan_txt = str(stan_val)
    jm = (item.get("jednostka") or "").strip()
    if jm:
        stan_txt = f"{stan_txt} {jm}"

    # Zadania technologiczne (lista lub string)
    z = item.get("zadania", [])
    if isinstance(z, list):
        zadania = ", ".join([str(x).strip() for x in z if str(x).strip()])
    else:
        zadania = str(z).strip()

    return (
        item_id,
        typ or "-",
        rozmiar or "-",
        nazwa or "-",
        stan_txt or "-",
        zadania,
    )


class MagazynView:
    """Uproszczony widok Magazynu: 6 kolumn, zero zmian w IO."""

    def __init__(self, master, config=None):
        self.master = master
        self.config = config or {}

        self.win = tk.Toplevel(master)
        apply_theme(self.win)
        self.win.title("Magazyn")
        self.win.geometry(self.config.get("magazyn.window_geometry", "1024x600"))
        self.win.minsize(900, 480)

        container = ttk.Frame(self.win, padding=(8, 8, 8, 8), style="WM.TFrame")
        container.pack(fill="both", expand=True)

        # Pasek narzędzi – minimalny (tylko odśwież)
        toolbar = ttk.Frame(container, style="WM.TFrame")
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="Odśwież", command=self.refresh, style="WM.Side.TButton").pack(side="right")

        # Tabela (6 kolumn)
        self.tree = ttk.Treeview(
            container,
            columns=COLUMNS,
            show="headings",
            selectmode="browse",
            height=22,
        )
        self.tree.pack(fill="both", expand=True)

        # Nagłówki
        self.tree.heading("id", text="ID")
        self.tree.heading("typ", text="Typ")
        self.tree.heading("rozmiar", text="Rozmiar")
        self.tree.heading("nazwa", text="Nazwa")
        self.tree.heading("stan", text="Stan")
        self.tree.heading("zadania", text="Tech. zadania")

        # Szerokości startowe
        self.tree.column("id", width=110, anchor="w")
        self.tree.column("typ", width=140, anchor="w")
        self.tree.column("rozmiar", width=140, anchor="w")
        self.tree.column("nazwa", width=380, anchor="w")
        self.tree.column("stan", width=120, anchor="center")
        self.tree.column("zadania", width=280, anchor="w")

        # Scrollbar pionowy
        vsb = ttk.Scrollbar(self.tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        # Podwójny klik – szybki podgląd (read-only)
        self.tree.bind("<Double-1>", self._on_double_click)

        self.refresh()

        self.win.protocol("WM_DELETE_WINDOW", self.win.destroy)
        self.win.transient(master)
        self.win.grab_set()
        self.win.wait_window(self.win)

    # -------------------------------------------------------
    def refresh(self):
        """Przeładuj dane do tabeli (kolejność: meta.order, potem alfabetycznie po ID)."""
        items, order = _load_data()

        # wyczyść
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        seen = set(order or [])
        sorted_ids = list(order or []) + sorted([k for k in items.keys() if k not in seen])

        for item_id in sorted_ids:
            item = items.get(item_id)
            if not isinstance(item, dict):
                continue
            row = _format_row(item_id, item)
            self.tree.insert("", "end", values=row)

    def _on_double_click(self, _e):
        """Mini-podgląd wartości z wiersza."""
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        labels = ["ID", "Typ", "Rozmiar", "Nazwa", "Stan", "Tech. zadania"]
        txt = "\n".join(f"{labels[i]}: {values[i]}" for i in range(min(len(labels), len(values))))
        messagebox.showinfo("Szczegóły pozycji", txt, parent=self.win)


# Publiczne API – jak dotychczas
def open_window(parent, config=None, *args, **kwargs):
    MagazynView(parent, config or {})


# Adapter kompatybilności dla panelu (panel wywołuje open_panel_magazyn)
def open_panel_magazyn(parent, root=None, app=None, notebook=None, *args, **kwargs):
    """
    Panel w niektórych wersjach woła gui_magazyn.open_panel_magazyn(...).
    Utrzymujemy kompatybilność, przekierowując do open_window(parent, config).
    """
    cfg = kwargs.get("config")
    if not isinstance(cfg, dict):
        maybe = getattr(parent, "config", None)
        cfg = maybe if isinstance(maybe, dict) else {}
    return open_window(parent, cfg)


# ⏹ KONIEC KODU

