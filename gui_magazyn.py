# Plik: gui_magazyn.py
# version: 1.0
# Zmiany 1.7.0:
# - Integracja z kreatorem zleceń (`open_order_creator`) zamiast lokalnego dialogu zamówień.
# - Usunięto zależność od `gui_magazyn_order` (stary kreator zamówień).
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

import json
import re
import tkinter as tk
from tkinter import messagebox, ttk

from core.settings_manager import Settings
from gui_magazyn_autobind import (
    ensure_magazyn_kreator_binding,
    register_magazyn_widgets,
)
from rc1_magazyn_fix import ensure_magazyn_toolbar_once
from gui_magazyn_kreator_bind import invoke_creator_from_magazyn

try:
    import magazyn_io  # type: ignore[attr-defined]

    HAVE_MAG_IO = True
except Exception:  # pragma: no cover - optional dependency
    magazyn_io = None
    HAVE_MAG_IO = False

from config.paths import get_path
from gui_magazyn_bridge import refresh_inventory
from wm_log import dbg as wm_dbg, err as wm_err

from ui_theme import apply_theme_safe as apply_theme

import logika_magazyn as LM
from gui_magazyn_edit import open_edit_dialog
from gui_magazyn_rezerwacje import (
    open_rezerwuj_dialog,
    open_zwolnij_rezerwacje_dialog,
)

try:
    from gui_orders import open_orders_window
except Exception as _e:
    open_orders_window = None
    print(
        "[ERROR][ORDERS] Nie można zaimportować gui_orders.open_orders_window – przycisk będzie nieaktywny."
    )

from logika_zakupy import auto_order_missing

COLUMNS = ("id", "typ", "rozmiar", "nazwa", "stan", "zadania")


ROLE_PERMS = {
    "view": "",
    "add": "",
    "edit": "",
    "pz": "",
    "reserve": "",
    "unreserve": "",
    "to_orders": "",
}


def _magazyn_runtime_paths() -> dict:
    out = {
        "root": "",
        "data": "",
        "warehouse": "",
        "bom": "",
        "warehouse_exists": False,
        "bom_exists": False,
    }

    try:
        from core import root_paths as wm_root_paths

        out["root"] = str(wm_root_paths.get_root_anchor())
        out["data"] = str(wm_root_paths.get_data_root())
        out["warehouse"] = str(wm_root_paths.path_warehouse())
        out["bom"] = str(wm_root_paths.path_bom())
    except Exception:
        pass

    try:
        from config_manager import ConfigManager, resolve_rel

        cfg = ConfigManager().load()
        if not out["data"]:
            out["data"] = str(ConfigManager().path_data())
        if not out["warehouse"]:
            out["warehouse"] = str(resolve_rel(cfg, "warehouse_stock"))
    except Exception:
        pass

    try:
        if not out["warehouse"]:
            out["warehouse"] = str(get_path("warehouse.stock_source"))
    except Exception:
        pass

    try:
        import os

        out["warehouse_exists"] = bool(
            out["warehouse"] and os.path.exists(out["warehouse"])
        )
        out["bom_exists"] = bool(out["bom"] and os.path.exists(out["bom"]))
    except Exception:
        pass

    return out


def _log_magazyn_paths(context: str = "") -> None:
    paths = _magazyn_runtime_paths()
    try:
        print("[WM-ROOT][MAGAZYN]", context)
        print(f"[WM-ROOT][MAGAZYN] ROOT      = {paths.get('root')}")
        print(f"[WM-ROOT][MAGAZYN] DATA      = {paths.get('data')}")
        print(
            "[WM-ROOT][MAGAZYN] WAREHOUSE = "
            f"{paths.get('warehouse')} "
            f"exists={int(paths.get('warehouse_exists'))}"
        )
        print(
            "[WM-ROOT][MAGAZYN] BOM       = "
            f"{paths.get('bom')} exists={int(paths.get('bom_exists'))}"
        )
    except Exception:
        pass


def _add_orders_button(toolbar: ttk.Frame, owner):
    if False:  # DISABLED: używamy natywnego przycisku „Dodaj zlecenie (Kreator)”
        btn_orders = ttk.Button(
            toolbar,
            text="Zamówienia",
            command=lambda: open_orders_window(owner) if open_orders_window else None,
        )
        btn_orders.pack(side="left", padx=(6, 0))
        if open_orders_window is None:
            try:
                btn_orders.state(["disabled"])
            except Exception:
                pass
        print("[WM-DBG][MAGAZYN] Dodano przycisk 'Zamówienia' w toolbarze")
        return btn_orders
    return None


@ensure_magazyn_toolbar_once
def build_magazyn_toolbar(toolbar: ttk.Frame, owner):
    ttk.Label(toolbar, text="Typ:", style="WM.TLabel").pack(side="left", padx=(0, 6))
    owner.cbo_typ = ttk.Combobox(
        toolbar,
        textvariable=owner._filter_typ,
        state="readonly",
        width=22,
    )
    owner.cbo_typ.pack(side="left", padx=(0, 10))
    owner.cbo_typ.bind("<<ComboboxSelected>>", lambda _e: owner._apply_filters())

    ttk.Label(toolbar, text="Szukaj (Nazwa/Rozmiar):", style="WM.TLabel").pack(
        side="left", padx=(0, 6)
    )
    owner.ent_q = ttk.Entry(
        toolbar, textvariable=owner._filter_query, width=28
    )
    owner.ent_q.pack(side="left", padx=(0, 6))
    owner.ent_q.bind("<KeyRelease>", lambda _e: owner._apply_filters())

    _add_orders_button(toolbar, owner)

    btn_orders_prefill = ttk.Button(
        toolbar,
        text="Zamów brakujące",
        command=lambda: _open_orders_for_shortages(owner),
    )
    btn_orders_prefill.pack(side="left", padx=(6, 0))

    btn_creator = ttk.Button(toolbar, text="Kreator zleceń")
    btn_creator.configure(command=owner._quick_add_to_orders)
    btn_creator.pack(side="left", padx=4)
    owner.btn_creator = btn_creator

    ttk.Button(
        toolbar,
        text="Rezerwuj",
        command=owner._rez_do_polproduktu,
        style="WM.Side.TButton",
    ).pack(side="right", padx=(0, 6))
    ttk.Button(
        toolbar,
        text="Edytuj",
        command=owner._edit_selected_item,
        style="WM.Side.TButton",
    ).pack(side="right", padx=(0, 6))
    ttk.Button(
        toolbar,
        text="Dodaj",
        command=owner._add_item,
        style="WM.Side.TButton",
    ).pack(side="right", padx=(0, 6))
    ttk.Button(
        toolbar,
        text="Zwolnij rez.",
        command=owner._rez_release,
        style="WM.Side.TButton",
    ).pack(side="right", padx=(0, 6))
    ttk.Button(
        toolbar,
        text="Wyczyść",
        command=owner._clear_filters,
        style="WM.Side.TButton",
    ).pack(side="right")
    ttk.Button(
        toolbar,
        text="Odśwież",
        command=owner.refresh,
        style="WM.Side.TButton",
    ).pack(side="right", padx=(0, 6))


def _role_rank(role: str) -> int:
    order = ["", "brygadzista", "magazynier"]
    role = (role or "").lower()
    return order.index(role) if role in order else 0


def _can(self, action: str) -> bool:
    required = ROLE_PERMS.get(action, "brygadzista")
    user_role = getattr(self, "user_role", "") or getattr(self, "role", "")
    return _role_rank(user_role) >= _role_rank(required)


def _resolve_order_author(widget) -> str:
    """Spróbuj ustalić nazwę autora dla kreatora zleceń."""

    attrs = ("user_login", "user_name", "username", "login", "autor", "author")
    for attr in attrs:
        value = getattr(widget, attr, None)
        if value:
            return str(value)

    try:
        top = widget.winfo_toplevel()
    except Exception:
        top = None

    if top and top is not widget:
        for attr in attrs:
            value = getattr(top, attr, None)
            if value:
                return str(value)

    return "magazyn"


def _detect_panel_role(panel_root: tk.Misc) -> str:
    for attr in ("user_role", "role"):
        value = getattr(panel_root, attr, None)
        if value:
            return str(value)

    try:
        top = panel_root.winfo_toplevel()
    except Exception:
        top = None

    if top and top is not panel_root:
        for attr in ("user_role", "role"):
            value = getattr(top, attr, None)
            if value:
                return str(value)

    return "brygadzista"


def _setup_magazyn_autobind(panel_root: tk.Misc) -> None:
    if not isinstance(panel_root, tk.Misc):
        return
    if getattr(panel_root, "_mag_autobind_ready", False):
        return

    panel_root._mag_autobind_ready = True
    cfg_obj = Settings(path="config.json", project_root=__file__)

    def _role() -> str:
        return _detect_panel_role(panel_root)

    def _on_panel_mapped(event=None):
        target = getattr(event, "widget", panel_root) if event else panel_root
        try:
            ensure_magazyn_kreator_binding(
                target,
                get_user_role=_role,
                get_cfg=lambda: cfg_obj,
            )
        except Exception as exc:
            print("[Magazyn] autobind error:", exc)

    try:
        panel_root.bind("<Map>", _on_panel_mapped)
    except Exception:
        try:
            panel_root.after(
                150,
                lambda: ensure_magazyn_kreator_binding(
                    panel_root,
                    get_user_role=_role,
                    get_cfg=lambda: cfg_obj,
                ),
            )
        except Exception:
            pass


def load_stock():
    path = get_path("warehouse.stock_source")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        wm_dbg("gui.magazyn", "stock loaded", path=path)
        return data
    except Exception as e:  # pragma: no cover - log + fallback handled below
        wm_err("gui.magazyn", "stock load failed", e, path=path)
        return {}


def _normalize_magazyn_payload(data):
    """Normalizuje różne formaty magazynu do (items, order, format_name)."""

    if not isinstance(data, (dict, list)):
        return {}, [], type(data).__name__

    if isinstance(data, list):
        items = {}
        order = []
        for idx, rec in enumerate(data):
            if not isinstance(rec, dict):
                continue
            item_id = str(
                rec.get("id")
                or rec.get("kod")
                or rec.get("symbol")
                or rec.get("nr")
                or f"poz_{idx + 1:04d}"
            ).strip()
            if not item_id:
                continue
            copy = dict(rec)
            copy.setdefault("id", item_id)
            items[item_id] = copy
            order.append(item_id)
        return items, order, "list"

    if isinstance(data.get("items"), dict):
        items = data.get("items") or {}
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        order = meta.get("order") if isinstance(meta.get("order"), list) else []
        return items, order, "items"

    if isinstance(data.get("pozycje"), dict):
        items = data.get("pozycje") or {}
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        order = meta.get("order") if isinstance(meta.get("order"), list) else []
        return items, order, "pozycje"

    if isinstance(data.get("items"), list):
        items, order, _format_name = _normalize_magazyn_payload(
            data.get("items") or []
        )
        return items, order, "items_list"

    if isinstance(data.get("pozycje"), list):
        items, order, _format_name = _normalize_magazyn_payload(
            data.get("pozycje") or []
        )
        return items, order, "pozycje_list"

    flat_items = {}
    flat_order = []
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        copy = dict(value)
        copy.setdefault("id", key)
        flat_items[str(key)] = copy
        flat_order.append(str(key))
    if flat_items:
        return flat_items, flat_order, "flat_dict"

    return {}, [], "empty" if not data else "unknown_dict"


def _load_data():
    """Czyta magazyn; preferuje ``magazyn_io`` z fallbackiem na plik."""
    path = get_path("warehouse.stock_source")
    _log_magazyn_paths("_load_data")
    print(f"[WM-ROOT][MAGAZYN] loader path from config.paths = {path}")
    data = {}
    if HAVE_MAG_IO and hasattr(magazyn_io, "load"):
        try:
            if path:
                try:
                    data = magazyn_io.load(path)
                except TypeError:
                    data = magazyn_io.load()
            else:
                data = magazyn_io.load()
        except Exception:
            data = {}

    if not isinstance(data, dict) or not data:
        data = load_stock()

    if not isinstance(data, dict) or not data:
        try:
            data = LM.load_magazyn()
        except Exception:
            data = {}

    items, order, format_name = _normalize_magazyn_payload(data)
    try:
        print(
            "[WM-DBG][MAGAZYN] normalized "
            f"format={format_name} items={len(items)} order={len(order)}"
        )
    except Exception:
        pass
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
    """Automatycznie dodaje pozycje poniżej progu do oczekujących zamówień."""

    try:
        added = auto_order_missing()
    except Exception as exc:
        messagebox.showerror(
            "Zamów brakujące", f"Nie udało się wygenerować zamówień: {exc}"
        )
        return

    if added:
        messagebox.showinfo(
            "Zamów brakujące",
            f"Dodano {added} pozycji do oczekujących zamówień.",
        )
    else:
        messagebox.showinfo(
            "Zamów brakujące", "Brak pozycji poniżej progów minimalnych."
        )
def _tag_low_stock(self, node, item_dict):
    try:
        stan = float(item_dict.get("stan", 0) or 0)
        minp = float(item_dict.get("min_poziom", 0) or 0)
        if minp > 0 and stan <= minp:
            if "low" not in self.tree.tag_names():
                self.tree.tag_configure("low", foreground="#C62828")
            self.tree.item(node, tags=("low",))
    except Exception:
        pass


def _get_selected_item(self):
    sel = self.tree.selection()
    if not sel:
        return None, None
    node = sel[0]
    item_id = (
        self.tree.set(node, "id")
        if "id" in self.tree["columns"]
        else self.tree.item(node, "text")
    )
    data = getattr(self, "_items_map", None) or {}
    return item_id, data.get(item_id)


def _quick_add_to_orders(self):
    if not _can(self, "to_orders"):
        messagebox.showwarning(
            "Uprawnienia", "Brak uprawnień do dodawania do zamówień."
        )
        return
    try:
        invoke_creator_from_magazyn(
            self, get_user_role=lambda: _resolve_order_author(self)
        )
    except Exception as exc:  # pragma: no cover - GUI fallback
        messagebox.showerror(
            "Magazyn",
            f"Nie udało się otworzyć kreatora zleceń: {exc}",
        )


def init_magazyn_panel(parent, tree_widget=None):
    """Załaduj dane magazynu i wypełnij przekazany ``Treeview``."""

    if not tree_widget or not hasattr(tree_widget, "insert"):
        return None

    cfg = Settings(path="config.json", project_root=__file__)

    try:
        refresh_inventory(tree_widget, cfg)
    except Exception as exc:  # pragma: no cover - GUI fallback
        print("[Magazyn] Błąd ładowania:", exc)

    def _mag_refresh_event(_evt=None):
        try:
            cnt = refresh_inventory(tree_widget, cfg)
            print(f"[Magazyn] Odświeżono: {cnt} pozycji")
        except Exception as exc:  # pragma: no cover - GUI fallback
            print("[Magazyn] Błąd odświeżania:", exc)

    binder = getattr(parent, "bind", None)
    if callable(binder):
        try:
            binder("<F5>", _mag_refresh_event)
        except Exception:  # pragma: no cover - optional binding
            pass

    if hasattr(tree_widget, "bind"):
        try:
            tree_widget.bind("<F5>", _mag_refresh_event)
        except Exception:  # pragma: no cover - optional binding
            pass

    return tree_widget


class MagazynFrame(ttk.Frame):
    """Widok Magazynu osadzony w kontenerze (bez Toplevel)."""

    def __init__(self, master, config=None):
        super().__init__(master, padding=(8, 8, 8, 8), style="WM.TFrame")
        self.config_obj = config or {}
        self.user_role = (
            getattr(self.master.winfo_toplevel(), "role", "")
            or getattr(self.master, "role", "")
        )
        self._quick_add_to_orders = _quick_add_to_orders.__get__(self, self.__class__)

        # stan filtrów
        self._filter_typ = tk.StringVar(value="(wszystkie)")
        self._filter_query = tk.StringVar(value="")

        self._build_ui()
        _setup_magazyn_autobind(self)
        self.refresh()

    # UI ----------------------------------------------------
    def _build_ui(self):
        # Pasek narzędzi (filtry + odśwież)
        toolbar = ttk.Frame(self, style="WM.TFrame")
        toolbar.pack(fill="x", pady=(0, 6))

        build_magazyn_toolbar(toolbar, self)

        if not hasattr(self, "cbo_typ"):
            container = ttk.Frame(self, style="WM.TFrame")
            container.pack(fill="x", pady=(0, 6))
            self.cbo_typ = ttk.Combobox(
                container,
                values=["surowce", "półprodukty", "produkty"],
                state="readonly",
                textvariable=self._filter_typ,
            )
            try:
                self.cbo_typ.current(0)
            except Exception:
                self._filter_typ.set("surowce")
            self.cbo_typ.grid(row=0, column=0, padx=6, pady=6, sticky="w")
            self.cbo_typ.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())

        # Tabela
        self.tree = ttk.Treeview(
            self,
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
        menu.add_command(
            label="Dodaj zlecenie (Kreator)",
            command=self._quick_add_to_orders,
        )
        self.tree.bind("<Button-3>", lambda e: self._on_right_click(e, menu))

        register_magazyn_widgets(
            self,
            tree_widget=self.tree,
            btn_kreator=getattr(self, "btn_creator", None),
        )

    # Logika ------------------------------------------------
    def _clear_filters(self):
        self._filter_typ.set("(wszystkie)")
        self._filter_query.set("")
        cbo = getattr(self, "cbo_typ", None)
        if cbo is not None:
            try:
                cbo.set(self._filter_typ.get())
            except Exception:
                pass
        self._apply_filters()

    def refresh(self):
        # wczytaj dane
        items, order = _load_data()

        # cache do filtrowania
        self._all_rows = []  # lista krotek (id, dict_item)
        self._items_map = {}
        seen = set(order or [])
        sorted_ids = list(order or []) + sorted([k for k in items.keys() if k not in seen])

        for item_id in sorted_ids:
            item = items.get(item_id)
            if isinstance(item, dict):
                item.setdefault("id", item_id)
                item.setdefault("nazwa", item.get("kod") or item_id)
                item.setdefault("typ", item.get("type") or item.get("rodzaj") or "")
                item.setdefault("rozmiar", item.get("wymiar") or item.get("size") or "")
                item.setdefault("stan", item.get("ilosc", item.get("ilość", 0)))
                self._all_rows.append((item_id, item))
                self._items_map[item_id] = item

        try:
            print(f"[WM-DBG][MAGAZYN] rows={len(self._all_rows)}")
        except Exception:
            pass

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
        cbo = getattr(self, "cbo_typ", None)
        if cbo is not None:
            try:
                cbo["values"] = typy
            except Exception:
                pass
            if cur not in typy:
                self._filter_typ.set("(wszystkie)")
                try:
                    cbo.set(self._filter_typ.get())
                except Exception:
                    pass
        else:
            self._filter_typ.set("(wszystkie)")

        # wypełnij widok z filtrami
        self._apply_filters()

    def _apply_filters(self):
        # wyczyść widok
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        q = self._filter_query.get().strip().lower()
        cbo = getattr(self, "cbo_typ", None)
        if cbo is None:
            return
        try:
            t = cbo.get()
        except Exception:
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
            node = self.tree.insert("", "end", values=_format_row(item_id, item))
            _tag_low_stock(self, node, item)

    def _on_double_click(self, _e):
        self._edit_selected_item()

    def _add_item(self):
        open_edit_dialog(self, None, on_saved=lambda _id=None: self.refresh())

    def _edit_selected_item(self):
        item_id = self._selected_item_id()
        if not item_id:
            messagebox.showinfo(
                "Magazyn",
                "Najpierw wybierz pozycję magazynową do edycji.",
                parent=self,
            )
            return
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
    _log_magazyn_paths("open_panel_magazyn")

    try:
        from gui_panel import wm_set_module_source
        from config_manager import ConfigManager, resolve_rel

        cfg = {}
        try:
            cfg = ConfigManager().load()
        except Exception:
            cfg = {}
        paths = _magazyn_runtime_paths()
        stock_path = paths.get("warehouse") or resolve_rel(cfg, "warehouse_stock")
        target_root = root if root is not None else parent.winfo_toplevel()
        wm_set_module_source(target_root, "Magazyn", stock_path)
    except Exception:
        pass

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
