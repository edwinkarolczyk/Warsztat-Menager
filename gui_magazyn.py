# Plik: gui_magazyn.py
# Wersja pliku: 1.5.0
# Zmiany 1.5.0:
# - Tryb osadzony (embed): open_panel_magazyn renderuje widok w panelu (bez Toplevel).
# - open_window pozostaje (Toplevel) dla zgodności.
# - Widok 6 kolumn: ID | Typ | Rozmiar | Nazwa | Stan | Tech. zadania.
#
# Zasada: zmieniamy tylko to, co potrzebne – brak zmian w IO/strukturze danych.

import tkinter as tk
from tkinter import ttk, messagebox

from ui_theme import apply_theme_safe as apply_theme

# I/O bezpiecznie
try:
    import magazyn_io
    HAVE_MAG_IO = True
except Exception:  # pragma: no cover - fallback
    magazyn_io = None
    HAVE_MAG_IO = False

import logika_magazyn as LM


COLUMNS = ("id", "typ", "rozmiar", "nazwa", "stan", "zadania")


def _load_data():
    """Czyta magazyn; preferuj magazyn_io.load(), fallback do LM.load_magazyn()."""
    try:
        if HAVE_MAG_IO and hasattr(magazyn_io, "load"):
            data = magazyn_io.load()
        else:
            data = LM.load_magazyn()
    except Exception:  # pragma: no cover - safe fallback
        data = {}
    return data.get("items", {}), (data.get("meta", {}) or {}).get("order", [])


def _format_row(item_id: str, item: dict):
    """Mapowanie rekordu na 6 kolumn z miękkimi fallbackami."""
    typ = (item.get("typ") or "").strip()
    rozmiar = (item.get("rozmiar") or "").strip()
    nazwa = (item.get("nazwa") or "").strip()

    # Stan + jednostka (opcjonalnie)
    stan_val = item.get("stan", "")
    try:
        stan_txt = f"{float(stan_val):g}"
    except Exception:
        stan_txt = str(stan_val)
    jm = (item.get("jednostka") or "").strip()
    if jm:
        stan_txt = f"{stan_txt} {jm}"

    # Zadania (lista lub string)
    z = item.get("zadania", [])
    if isinstance(z, list):
        zadania = ", ".join([str(x).strip() for x in z if str(x).strip()])
    else:
        zadania = str(z).strip()

    return (item_id, typ or "-", rozmiar or "-", nazwa or "-", stan_txt or "-", zadania)


class MagazynFrame(ttk.Frame):
    """Widok Magazynu osadzony w kontenerze (bez Toplevel)."""

    def __init__(self, master, config=None):
        super().__init__(master, padding=(8, 8, 8, 8), style="WM.TFrame")
        self.config_obj = config or {}
        self._build_ui()
        self.refresh()

    # UI ----------------------------------------------------
    def _build_ui(self):
        # Pasek narzędzi (odśwież)
        toolbar = ttk.Frame(self, style="WM.TFrame")
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="Odśwież", command=self.refresh, style="WM.Side.TButton").pack(
            side="right"
        )

        # Tabela
        self.tree = ttk.Treeview(
            self, columns=COLUMNS, show="headings", selectmode="browse", height=22
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

        # Podwójny klik – podgląd
        self.tree.bind("<Double-1>", self._on_double_click)

    # Logika ------------------------------------------------
    def refresh(self):
        items, order = _load_data()
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        seen = set(order or [])
        sorted_ids = list(order or []) + sorted([k for k in items.keys() if k not in seen])
        for item_id in sorted_ids:
            item = items.get(item_id)
            if not isinstance(item, dict):
                continue
            self.tree.insert("", "end", values=_format_row(item_id, item))

    def _on_double_click(self, _e):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        labels = ["ID", "Typ", "Rozmiar", "Nazwa", "Stan", "Tech. zadania"]
        txt = "\n".join(
            f"{labels[i]}: {values[i]}" for i in range(min(len(labels), len(values)))
        )
        # Szukamy okna-rodzica, żeby dialog był modalny do głównego okna
        root = self.winfo_toplevel()
        messagebox.showinfo("Szczegóły pozycji", txt, parent=root)


# Tryb Toplevel (dla zgodności) -----------------------------
class MagazynWindow:
    """Stary tryb: okno Toplevel otwierane niezależnie."""

    def __init__(self, master, config=None):
        self.master = master
        self.config = config or {}

        self.win = tk.Toplevel(master)
        apply_theme(self.win)
        self.win.title("Magazyn")
        self.win.geometry(self.config.get("magazyn.window_geometry", "1024x600"))
        self.win.minsize(900, 480)

        # Osadzamy ramkę wewnątrz okna
        frame = MagazynFrame(self.win, config=self.config)
        frame.pack(fill="both", expand=True)

        self.win.protocol("WM_DELETE_WINDOW", self.win.destroy)
        self.win.transient(master)
        self.win.grab_set()
        self.win.wait_window(self.win)


# Publiczne API ---------------------------------------------
def open_window(parent, config=None, *args, **kwargs):
    """Zachowanie jak dawniej: otwórz Magazyn w Toplevel."""
    MagazynWindow(parent, config or {})


def _resolve_container(parent, notebook=None, container=None):
    """
    Znajduje kontener do osadzenia:
    - jawnie podany 'container' lub 'notebook'
    - atrybuty parenta: 'content', 'main_frame', 'body', 'container'
    - fallback: parent (jeśli to Frame/okno)
    """
    if container is not None:
        return container
    if notebook is not None:
        return notebook
    for name in ("content", "main_frame", "body", "container"):
        maybe = getattr(parent, name, None)
        if isinstance(maybe, (tk.Widget, ttk.Frame)):
            return maybe
    return parent


def open_panel_magazyn(parent, root=None, app=None, notebook=None, *args, **kwargs):
    """
    Adapter dla panelu: renderuje widok Magazynu **wewnątrz programu**.
    - Próbuje osadzić w przekazanym kontenerze/notebooku lub w parent.content itp.
    - Zamyka poprzednią instancję, jeśli była (parent._magazyn_embed).
    """
    # Config
    cfg = kwargs.get("config")
    if not isinstance(cfg, dict):
        maybe = getattr(parent, "config", None)
        cfg = maybe if isinstance(maybe, dict) else {}

    # Kontener docelowy
    container_arg = kwargs.get("container")
    if container_arg is None and isinstance(root, (tk.Widget, ttk.Frame)):
        container_arg = root
    container = _resolve_container(parent, notebook=notebook, container=container_arg)

    # Jeżeli panel ma notebook i chcemy zakładkę, można użyć:
    # - jeżeli container ma metodę 'add', potraktuj jako ttk.Notebook
    try:
        if hasattr(container, "add") and hasattr(container, "tabs"):
            # zakładka w notebooku
            # usuń starą zakładkę, jeśli istnieje
            old = getattr(parent, "_magazyn_embed", None)
            if isinstance(old, tk.Widget) and old.winfo_exists():
                try:
                    container.forget(old)
                except Exception:
                    try:
                        old.destroy()
                    except Exception:
                        pass
            frame = MagazynFrame(container, config=cfg)
            container.add(frame, text="Magazyn")
            container.select(frame)
            parent._magazyn_embed = frame
            return frame
    except Exception:  # pragma: no cover - notebook failures
        pass

    # Standard: osadź jako Frame w kontenerze (zastępując poprzedni)
    old = getattr(parent, "_magazyn_embed", None)
    if isinstance(old, tk.Widget) and old.winfo_exists():
        try:
            old.destroy()
        except Exception:
            pass

    frame = MagazynFrame(container, config=cfg)
    if hasattr(frame, "pack"):
        frame.pack(fill="both", expand=True)
    parent._magazyn_embed = frame
    return frame


# ⏹ KONIEC KODU

