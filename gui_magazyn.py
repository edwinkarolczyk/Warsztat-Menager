# Plik: gui_magazyn.py
# Wersja pliku: 1.6.0
# Zmiany 1.6.0:
# - Dodano filtry nad tabelą:
#   * Combobox "Typ" (wartości dynamiczne z danych)
#   * Pole "Szukaj" (filtrowanie po Nazwa/Rozmiar, case-insensitive, substring)
# - Brak zmian w IO/strukturze danych; widok 6 kolumn zostaje:
#   ID | Typ | Rozmiar | Nazwa | Stan | Tech. zadania
#
# Zmiany 1.5.x:
# - Tryb osadzony (embed): open_panel_magazyn renderuje widok w panelu (bez Toplevel).
# - open_window pozostaje (Toplevel) dla zgodności.
#
# Zasada: minimalne modyfikacje, bez naruszania istniejących API.

import re
import tkinter as tk
from tkinter import ttk, messagebox

from ui_theme import apply_theme_safe as apply_theme

# I/O bezpiecznie
try:
    import magazyn_io
    HAVE_MAG_IO = True
except Exception:
    magazyn_io = None
    HAVE_MAG_IO = False

import logika_magazyn as LM
from gui_magazyn_edit import open_edit_dialog
from gui_magazyn_rezerwacje import (
    open_rezerwuj_dialog,
    open_zwolnij_rezerwacje_dialog,
)
from gui_magazyn_order import MagazynOrderDialog

try:
    from gui_orders import open_orders_window
except Exception as _e:
    open_orders_window = None
    print(
        "[ERROR][ORDERS] Nie można zaimportować gui_orders.open_orders_window – przycisk będzie nieaktywny."
    )

COLUMNS = ("id", "typ", "rozmiar", "nazwa", "stan", "zadania")


def _load_data():
    """Czyta magazyn; preferuj magazyn_io.load(), fallback do LM.load_magazyn()."""
    try:
        if HAVE_MAG_IO and hasattr(magazyn_io, "load"):
            data = magazyn_io.load()
        else:
            data = LM.load_magazyn()
    except Exception:
        data = {}
    items = data.get("items", {})
    order = (data.get("meta", {}) or {}).get("order", [])
    return items, order


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


def _open_orders_for_shortages(self):
    """
    Otwiera kreator Zamówień z prefill'em pozycji na podstawie braków/zaznaczenia w Magazynie.
    Implementacja jest defensywna – bierze 'kod/nazwa/ilosc/j' jeśli są dostępne.
    """
    rows = []
    try:
        # PRZYKŁAD 1: jeśli masz tabelę z zaznaczeniem:
        # for item in self.tree.selection():
        #     data = self.tree.item(item, "values")  # dopasuj do swojej struktury
        #     rows.append({"kod": data[0], "nazwa": data[1], "ilosc": float(data[2]), "j": data[3]})

        # PRZYKŁAD 2: jeśli masz listę braków uzyskaną z logiki:
        # shortages = self.magazyn_logic.get_shortages()  # <-- Twoja funkcja, jeśli istnieje
        # for s in shortages:
        #     rows.append({"kod": s["kod"], "nazwa": s.get("nazwa",""), "ilosc": s["brakuje"], "j": s.get("jm","szt")})

        pass
    except Exception as e:
        print(
            f"[ERROR][MAGAZYN] Nie udało się zbudować listy pozycji do zamówienia: {e}"
        )

    context = {
        "typ": "zakup",
        "pozycje": rows,
    }
    try:
        if open_orders_window:
            open_orders_window(self, context=context)
    except Exception as e:
        print(
            f"[ERROR][MAGAZYN] Nie udało się otworzyć kreatora Zamówień z kontekstem: {e}"
        )


class MagazynFrame(ttk.Frame):
    """Widok Magazynu osadzony w kontenerze (bez Toplevel)."""

    def __init__(self, master, config=None):
        super().__init__(master, padding=(8, 8, 8, 8), style="WM.TFrame")
        self.config_obj = config or {}

        # stan filtrów
        self._filter_typ = tk.StringVar(value="(wszystkie)")
        self._filter_query = tk.StringVar(value="")

        self._build_ui()
        self.refresh()

    # UI ----------------------------------------------------
    def _build_ui(self):
        # Pasek narzędzi (filtry + odśwież)
        toolbar = ttk.Frame(self, style="WM.TFrame")
        toolbar.pack(fill="x", pady=(0, 6))

        # Typ (dynamicznie, wartości ustawimy przy refresh)
        ttk.Label(toolbar, text="Typ:", style="WM.TLabel").pack(side="left", padx=(0, 6))
        self.cbo_typ = ttk.Combobox(toolbar, textvariable=self._filter_typ, state="readonly", width=22)
        self.cbo_typ.pack(side="left", padx=(0, 10))
        self.cbo_typ.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())

        # Szukaj
        ttk.Label(toolbar, text="Szukaj (Nazwa/Rozmiar):", style="WM.TLabel").pack(side="left", padx=(0, 6))
        self.ent_q = ttk.Entry(toolbar, textvariable=self._filter_query, width=28)
        self.ent_q.pack(side="left", padx=(0, 6))
        self.ent_q.bind("<KeyRelease>", lambda _e: self._apply_filters())

        btn_orders = ttk.Button(
            toolbar,
            text="Zamówienia",
            command=lambda: open_orders_window(self) if open_orders_window else None,
        )
        btn_orders.pack(side="left", padx=(6, 0))
        if open_orders_window is None:
            try:
                btn_orders.state(["disabled"])
            except Exception:
                pass
        print("[WM-DBG][MAGAZYN] Dodano przycisk 'Zamówienia' w toolbarze")

        btn_orders_prefill = ttk.Button(
            toolbar,
            text="Zamów brakujące",
            command=lambda: _open_orders_for_shortages(self),
        )
        btn_orders_prefill.pack(side="left", padx=(6, 0))

        ttk.Button(
            toolbar,
            text="Do zamówień",
            command=self._order_if_low,
        ).pack(side="left", padx=(6, 0))

        # Przyciski
        ttk.Button(
            toolbar,
            text="Rezerwuj",
            command=self._rez_do_polproduktu,
            style="WM.Side.TButton",
        ).pack(side="right", padx=(0, 6))
        ttk.Button(
            toolbar,
            text="Zwolnij rez.",
            command=self._rez_release,
            style="WM.Side.TButton",
        ).pack(side="right", padx=(0, 6))
        ttk.Button(
            toolbar,
            text="Wyczyść",
            command=self._clear_filters,
            style="WM.Side.TButton",
        ).pack(side="right")
        ttk.Button(
            toolbar,
            text="Odśwież",
            command=self.refresh,
            style="WM.Side.TButton",
        ).pack(side="right", padx=(0, 6))

        # Tabela
        self.tree = ttk.Treeview(self, columns=COLUMNS, show="headings", selectmode="browse", height=22)
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
        self.tree.column("rozmiar", width=160, anchor="w")
        self.tree.column("nazwa", width=380, anchor="w")
        self.tree.column("stan", width=120, anchor="center")
        self.tree.column("zadania", width=280, anchor="w")

        # Scrollbar pionowy
        vsb = ttk.Scrollbar(self.tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        # Double-click → edycja
        self.tree.bind("<Double-1>", self._on_double_click)
        menu = tk.Menu(self.tree, tearoff=0)
        menu.add_command(label="Do zamówień", command=self._order_if_low)
        self.tree.bind("<Button-3>", lambda e: self._on_right_click(e, menu))

    # Logika ------------------------------------------------
    def _clear_filters(self):
        self._filter_typ.set("(wszystkie)")
        self._filter_query.set("")
        self._apply_filters()

    def refresh(self):
        # wczytaj dane
        items, order = _load_data()

        # cache do filtrowania
        self._all_rows = []  # lista krotek (id, dict_item)
        seen = set(order or [])
        sorted_ids = list(order or []) + sorted([k for k in items.keys() if k not in seen])

        for item_id in sorted_ids:
            item = items.get(item_id)
            if isinstance(item, dict):
                self._all_rows.append((item_id, item))

        # wartości do combobox Typ
        typy = ["(wszystkie)"]
        bucket = set()
        for _id, it in self._all_rows:
            t = str(it.get("typ", "")).strip()
            if t:
                bucket.add(t)
        typy.extend(sorted(bucket, key=lambda s: s.lower()))
        # zachowaj wybór jeśli istnieje
        cur = self._filter_typ.get()
        self.cbo_typ["values"] = typy
        if cur not in typy:
            self._filter_typ.set("(wszystkie)")

        # wypełnij widok z filtrami
        self._apply_filters()

    def _apply_filters(self):
        # wyczyść widok
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        q = self._filter_query.get().strip().lower()
        t = self._filter_typ.get()

        # przygotuj regex „q” bezpiecznie (opcjonalne)
        rx = None
        if q:
            try:
                rx = re.compile(re.escape(q))
            except Exception:
                rx = None

        for item_id, item in getattr(self, "_all_rows", []):
            # filtr po typie
            typ_val = str(item.get("typ", "")).strip()
            if t != "(wszystkie)" and typ_val.lower() != t.lower():
                continue

            # filtr po szukajce (Nazwa/Rozmiar)
            nazwa = str(item.get("nazwa", "")).lower()
            rozmiar = str(item.get("rozmiar", "")).lower()
            hay = f"{nazwa} {rozmiar}"
            if q:
                if rx:
                    if rx.search(hay) is None:
                        continue
                else:
                    if q not in hay:
                        continue

            # dodaj wiersz
            self.tree.insert("", "end", values=_format_row(item_id, item))

    def _on_double_click(self, _e):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        item_id = values[0]
        open_edit_dialog(self, item_id, on_saved=lambda _id=item_id: self.refresh())

    def _selected_item_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")[0]

    def _rez_do_polproduktu(self):
        item_id = self._selected_item_id()
        if not item_id:
            return
        open_rezerwuj_dialog(self, item_id)
        self.refresh()

    def _rez_release(self):
        item_id = self._selected_item_id()
        if not item_id:
            return
        open_zwolnij_rezerwacje_dialog(self, item_id)
        self.refresh()

    def _order_if_low(self):
        item_id = self._selected_item_id()
        if not item_id:
            return
        item = next((it for iid, it in getattr(self, "_all_rows", []) if iid == item_id), None)
        if not isinstance(item, dict):
            return
        try:
            stan = float(item.get("stan", 0))
            min_poziom = float(item.get("min_poziom", 0))
        except Exception:
            return
        if stan <= min_poziom:
            MagazynOrderDialog(self, config=self.config_obj, preselect_id=item_id)
        else:
            messagebox.showinfo("Magazyn", "Stan powyżej minimum.")

    def _on_right_click(self, event, menu):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()


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
    Znajduje kontener (widget) do osadzenia widoku:
    - jeśli podano bezpośrednio widget (Frame/Toplevel) -> zwróć
    - jeśli podano string -> potraktuj jako nazwę atrybutu (np. "content")
    - jeśli podano notebook (ttk.Notebook) -> zwróć
    - inaczej spróbuj typowych nazw w parent: content/main_frame/body/container
    - fallback: parent (jeśli jest widgetem)
    """
    # 1) Jawnie przekazany widget
    if isinstance(container, (tk.Widget, ttk.Frame)):
        return container

    # 2) Przekazany notebook
    if isinstance(notebook, (tk.Widget, ttk.Frame)):
        return notebook

    # 3) Jeśli 'container' to string -> spróbuj znaleźć atrybut o tej nazwie
    if isinstance(container, str):
        maybe = getattr(parent, container, None)
        if isinstance(maybe, (tk.Widget, ttk.Frame)):
            return maybe

    # 4) Typowe atrybuty na parent
    for name in ("content", "main_frame", "body", "container"):
        maybe = getattr(parent, name, None)
        if isinstance(maybe, (tk.Widget, ttk.Frame)):
            return maybe

    # 5) Fallback: parent sam w sobie jest widgetem?
    if isinstance(parent, (tk.Widget, ttk.Frame)):
        return parent

    # 6) Ostatecznie: zwróć None (wywołujący obsłuży błąd)
    return None


def open_panel_magazyn(parent, root=None, app=None, notebook=None, *args, **kwargs):
    """
    Renderuje widok Magazynu **wewnątrz programu** (embed).
    Przyjmuje:
     - parent: obiekt ekranu głównego/panelu (ma atrybuty typu 'content' itp.)
     - notebook: opcjonalny ttk.Notebook
     - container: widget **albo** nazwa atrybutu (str), np. "content"
    """
    # Config
    cfg = kwargs.get("config")
    if not isinstance(cfg, dict):
        maybe = getattr(parent, "config", None)
        cfg = maybe if isinstance(maybe, dict) else {}

    # Rozwiąż kontener
    container = _resolve_container(parent, notebook=notebook, container=kwargs.get("container"))

    if container is None:
        # twardy, czytelny komunikat – bez wysypywania się na .tk
        try:
            from tkinter import messagebox
            messagebox.showerror(
                "Magazyn",
                "Nie znaleziono kontenera do osadzenia widoku Magazynu.\n"
                "Przekaż widget lub nazwę atrybutu, np. container='content'.",
            )
        except Exception:
            pass
        return None

    # Notebook -> dodaj zakładkę
    try:
        if hasattr(container, "add") and hasattr(container, "tabs"):
            # usuń starą instancję, jeśli była
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
    except Exception:
        # jeśli to nie notebook – lecimy dalej
        pass

    # Standardowy embed w ramce
    old = getattr(parent, "_magazyn_embed", None)
    if isinstance(old, tk.Widget) and old.winfo_exists():
        try:
            old.destroy()
        except Exception:
            pass

    frame = MagazynFrame(container, config=cfg)
    frame.pack(fill="both", expand=True)
    parent._magazyn_embed = frame
    return frame
# ⏹ KONIEC KODU

