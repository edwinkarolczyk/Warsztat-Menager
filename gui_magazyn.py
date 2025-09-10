# Plik: gui_magazyn.py
# Wersja pliku: 1.3.1
# Zmiany 1.3.1:
# - Dodano __all__ (PanelMagazyn, open_panel_magazyn, panel_ustawien_magazyn, attach_magazyn_button)
# - Helper attach_magazyn_button(root, toolbar) do łatwego podpięcia przycisku "Magazyn" w głównym GUI
# - Drobne utwardzenia i kosmetyka (bez zmian logiki)
#
# Zmiany 1.3.0:
# - Uprawnienia: _resolve_role(...) wyciąga rolę z parametru, atrybutów okna lub tytułu ("(...ROLA)")
#   -> gwarantuje dostęp dla Edwin=brygadzista
# - Formularz w Ustawieniach: dodano pole "Dł. jednostkowa (mm)" + live przelicznik sumy długości
# - Tabela panelu: nowe kolumny "Dł. [mm]" i "Suma [m]" (dla rur/profili)
#
# Zmiany 1.2.1:
# - _has_priv: {'brygadzista','brygadzista_serwisant','admin','kierownik'}
# - Zarządzanie typami + dynamiczny combobox Typ
#
# Zmiany 1.1.1: Podpowiedz ID
# ⏹ KONIEC KODU

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import re
from pathlib import Path

from ui_theme import apply_theme_safe as apply_theme, COLORS
from utils.gui_helpers import clear_frame
from utils import error_dialogs
from logger import log_akcja
from ui_utils import _ensure_topmost

# Uwaga: korzystamy z istniejącego modułu logiki magazynu w projekcie
import logika_magazyn as LM
from config_manager import ConfigManager
from services.profile_service import authenticate

try:  # pragma: no cover - dialog modules optional in tests
    from gui_magazyn_add import MagazynAddDialog
except ImportError:  # pragma: no cover - fallback stub
    class MagazynAddDialog:
        def __init__(self, master, *_args, **_kwargs):
            tk.Toplevel(master)

try:  # pragma: no cover - dialog modules optional in tests
    from gui_magazyn_pz import MagazynPZDialog
except ImportError:  # pragma: no cover - fallback stub
    class MagazynPZDialog:
        def __init__(self, master, *_args, **_kwargs):
            tk.Toplevel(master)

_CFG = ConfigManager()


def _attach_tooltip(widget: tk.Misc, text: str):
    """Attach a simple text tooltip to ``widget``."""
    tip: dict[str, tk.Toplevel | None] = {"w": None}

    def _show(_=None):
        if tip["w"] or not text:
            return
        x = widget.winfo_rootx() + 16
        y = widget.winfo_rooty() + 20
        tw = tk.Toplevel(widget)
        _ensure_topmost(tw, widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            tw,
            text=text,
            bg="#2A2F37",
            fg="#E8E8E8",
            bd=1,
            relief="solid",
            justify="left",
        )
        lbl.pack(ipadx=8, ipady=6)
        tip["w"] = tw

    def _hide(_=None):
        if tip["w"]:
            tip["w"].destroy()
            tip["w"] = None

    widget.bind("<Enter>", _show, add="+")
    widget.bind("<Leave>", _hide, add="+")
    return tip


def _fmt(num: float) -> str:
    prec = _CFG.get("magazyn_precision_mb", 3)
    return f"{float(num):.{prec}f}"

try:  # obsługa opcjonalnego modułu drukarki
    from escpos import printer as escpos_printer
except Exception:  # pragma: no cover - środowisko bez biblioteki
    escpos_printer = None

__all__ = [
    "PanelMagazyn",
    "panel_magazyn",
    "open_panel_magazyn",
    "panel_ustawien_magazyn",
    "attach_magazyn_button",
    "drukuj_etykiete",
]

# ----- uprawnienia -----
def _has_priv(rola: str | None) -> bool:
    r = (rola or "").strip().lower()
    return r in {"brygadzista", "brygadzista_serwisant", "admin", "kierownik"}

def _resolve_role(parent, rola_hint=None):
    # 1) z parametru
    if rola_hint and isinstance(rola_hint, str) and rola_hint.strip():
        return rola_hint.strip()
    # 2) z atrybutów głównego okna
    try:
        top = parent.winfo_toplevel()
        r = getattr(top, "rola", None)
        if isinstance(r, str) and r.strip():
            return r.strip()
    except Exception:
        pass
    # 3) z tytułu okna: "... (ROLA)"
    try:
        top = parent.winfo_toplevel()
        t = str(top.title())
        m = re.search(r"\(([^)]+)\)\s*$", t)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return None


def drukuj_etykiete(item_id: str, host: str = "127.0.0.1", port: int = 9100) -> None:
    """Drukuje etykietę z kodem kreskowym dla wskazanej pozycji."""
    if escpos_printer is None:
        raise RuntimeError("Moduł python-escpos nie jest dostępny.")
    it = LM.get_item(item_id)
    if not it:
        raise ValueError(f"Pozycja {item_id} nie istnieje.")
    p = escpos_printer.Network(host, port=port)
    p.text(f"{it['nazwa']}\n")
    p.barcode(it["id"], "CODE39", width=2, height=64, function_type="B")
    p.text(f"{it['id']}\n")
    p.cut()

class PanelMagazyn(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, style="WM.Card.TFrame")
        self.root = master
        self.config = getattr(master, "config", None)
        self.profiles = getattr(master, "profiles", None)
        apply_theme(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        lock_path = Path("data/magazyn/magazyn.json.lock")
        if lock_path.exists():
            print("[WM-DBG] magazyn.json.lock detected")
            try:
                self.master.tab(self, text="Magazyn LOCK")
            except Exception:
                pass

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Pasek narzędzi
        bar = ttk.Frame(self, style="WM.TFrame")
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8,4))
        bar.columnconfigure(3, weight=1)

        ttk.Label(bar, text="Szukaj:", style="WM.Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.var_szukaj = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.var_szukaj)
        ent.grid(row=0, column=1, sticky="ew", padx=6)
        ent.bind("<KeyRelease>", lambda e: self._filter())

        ttk.Button(bar, text="Odśwież", command=self._load, style="WM.Side.TButton").grid(row=0, column=2, padx=6)

        self._tooltips: list[dict[str, tk.Toplevel | None]] = []

        btn_dodaj = ttk.Button(bar, text="+ Dodaj", command=self._act_dodaj, style="WM.Side.TButton")
        btn_dodaj.grid(row=0, column=4, padx=3)
        self._tooltips.append(_attach_tooltip(btn_dodaj, "Dodaj nową pozycję do magazynu"))

        btn_przyjecie = ttk.Button(
            bar, text="Przyjęcie (PZ)", command=self._act_przyjecie, style="WM.Side.TButton"
        )
        btn_przyjecie.grid(row=0, column=5, padx=3)
        self._tooltips.append(
            _attach_tooltip(btn_przyjecie, "Zarejestruj przyjęcie towaru (PZ)")
        )

        btn_zuzyj = ttk.Button(bar, text="Zużyj", command=self._act_zuzyj, style="WM.Side.TButton")
        btn_zuzyj.grid(row=0, column=6, padx=3)
        self._tooltips.append(
            _attach_tooltip(btn_zuzyj, "Odnotuj zużycie materiału")
        )

        btn_zwrot = ttk.Button(bar, text="Zwrot", command=self._act_zwrot, style="WM.Side.TButton")
        btn_zwrot.grid(row=0, column=7, padx=3)
        self._tooltips.append(
            _attach_tooltip(btn_zwrot, "Przyjmij zwrot na magazyn")
        )

        btn_rezerwuj = ttk.Button(
            bar, text="Rezerwuj", command=self._act_rezerwuj, style="WM.Side.TButton"
        )
        btn_rezerwuj.grid(row=0, column=8, padx=3)
        self._tooltips.append(
            _attach_tooltip(btn_rezerwuj, "Zarezerwuj materiał dla zlecenia")
        )

        btn_zwolnij = ttk.Button(
            bar, text="Zwolnij rez.", command=self._act_zwolnij, style="WM.Side.TButton"
        )
        btn_zwolnij.grid(row=0, column=9, padx=3)
        self._tooltips.append(
            _attach_tooltip(btn_zwolnij, "Zwolnij zarezerwowany materiał")
        )

        btn_historia = ttk.Button(
            bar, text="Historia", command=self._show_historia, style="WM.Side.TButton"
        )
        btn_historia.grid(row=0, column=10, padx=6)
        self._tooltips.append(
            _attach_tooltip(btn_historia, "Pokaż historię operacji")
        )

        btn_etykieta = ttk.Button(
            bar,
            text="Etykieta",
            command=self._act_drukuj_etykiete,
            style="WM.Side.TButton",
        )
        btn_etykieta.grid(row=0, column=11, padx=6)
        self._tooltips.append(
            _attach_tooltip(btn_etykieta, "Drukuj etykietę z kodem")
        )

        btn_do_zam = ttk.Button(
            bar,
            text="Do zam.",
            command=self._act_do_zam,
            style="WM.Side.TButton",
        )
        btn_do_zam.grid(row=0, column=12, padx=3)
        self._tooltips.append(
            _attach_tooltip(
                btn_do_zam, "Dodaj pozycję do listy zamówień."
            )
        )

        self.bind_all("<Control-n>", lambda _e: self._act_dodaj(), add="+")
        self.bind_all("<Control-p>", lambda _e: self._act_przyjecie(), add="+")

        # Notebook z widokami tabel
        self.nb = ttk.Notebook(self, style="WM.TNotebook")
        self.nb.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0,8))

        frm_all = ttk.Frame(self.nb, style="WM.TFrame")
        frm_all.columnconfigure(0, weight=1)
        frm_all.rowconfigure(0, weight=1)
        frm_low = ttk.Frame(self.nb, style="WM.TFrame")
        frm_low.columnconfigure(0, weight=1)
        frm_low.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            frm_all,
            style="WM.Treeview",
            columns=("id","nazwa","typ","jed","stan","min","rez","dl_mm","suma_m"),
            show="headings",
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        self.tree_low = ttk.Treeview(
            frm_low,
            style="WM.Treeview",
            columns=("id","nazwa","typ","jed","stan","min","rez","dl_mm","suma_m"),
            show="headings",
        )
        self.tree_low.grid(row=0, column=0, sticky="nsew")

        for cid, txt, w in [
            ("id","ID",100), ("nazwa","Nazwa",220), ("typ","Typ",100),
            ("jed","J.m.",70), ("stan","Stan",90), ("min","Min",80), ("rez","Rezerw.",90),
            ("dl_mm","Dł. [mm]",90), ("suma_m","Suma [m]",100)
        ]:
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, anchor="w")
            self.tree_low.heading(cid, text=txt)
            self.tree_low.column(cid, width=w, anchor="w")

        self.nb.add(frm_all, text="Wszystkie")
        self.nb.add(frm_low, text="Do zamówienia")

        self.tree.bind("<Double-1>", lambda e: self._show_historia())
        self.tree.bind("<ButtonPress-1>", self._drag_start)
        self.tree.bind("<B1-Motion>", self._drag_motion)
        self.tree.bind("<ButtonRelease-1>", self._drag_release)
        self.tree_low.bind("<Double-1>", lambda e: self._show_historia())

        # Pasek alertów
        self.var_alerty = tk.StringVar()
        lab = ttk.Label(self, textvariable=self.var_alerty, style="WM.Muted.TLabel")
        lab.grid(row=2, column=0, sticky="ew", padx=8, pady=(0,8))

    def _load(self):
        self._all = LM.lista_items()
        self._refresh()
        self._low = [
            it
            for it in self._all
            if float(it.get("stan", 0)) <= float(it.get("min_poziom", 0))
        ]
        self._refresh_low()
        self._update_alerts()

    def _reload_data(self):
        """Reload warehouse data and refresh tables."""
        self._load()

    def _refresh(self, items=None):
        items = items if items is not None else self._all
        self.tree.delete(*self.tree.get_children())
        for it in items:
            dl_mm = float(it.get("dl_jednostkowa_mm", 0) or 0.0)
            suma_m = LM.calc_total_length_m(it) if hasattr(LM, "calc_total_length_m") else 0.0
            col = self._color_for(it)
            self.tree.insert("", "end", values=(
                it["id"], it["nazwa"], it.get("typ","komponent"),
                it.get("jednostka","szt"),
                _fmt(it.get("stan", 0)),
                _fmt(it.get("min_poziom", 0)),
                _fmt(it.get("rezerwacje", 0)),
                f'{dl_mm:.0f}' if dl_mm > 0 else "",
                _fmt(suma_m) if suma_m > 0 else ""
            ), tags=(col,))
        self.tree.tag_configure("#stock_low", background=COLORS.get("stock_low", "#c0392b"))
        self.tree.tag_configure("#stock_warn", background=COLORS.get("stock_warn", "#d35400"))
        self.tree.tag_configure("#stock_ok", background=COLORS.get("stock_ok", "#2d6a4f"))

    def _refresh_low(self):
        self.tree_low.delete(*self.tree_low.get_children())
        for it in getattr(self, "_low", []):
            dl_mm = float(it.get("dl_jednostkowa_mm", 0) or 0.0)
            suma_m = (
                LM.calc_total_length_m(it)
                if hasattr(LM, "calc_total_length_m")
                else 0.0
            )
            col = self._color_for(it)
            self.tree_low.insert(
                "",
                "end",
                values=(
                    it["id"],
                    it["nazwa"],
                    it.get("typ", "komponent"),
                    it.get("jednostka", "szt"),
                    _fmt(it.get("stan", 0)),
                    _fmt(it.get("min_poziom", 0)),
                    _fmt(it.get("rezerwacje", 0)),
                    f"{dl_mm:.0f}" if dl_mm > 0 else "",
                    _fmt(suma_m) if suma_m > 0 else "",
                ),
                tags=(col,),
            )
        self.tree_low.tag_configure(
            "#stock_low", background=COLORS.get("stock_low", "#c0392b")
        )
        self.tree_low.tag_configure(
            "#stock_warn", background=COLORS.get("stock_warn", "#d35400")
        )
        self.tree_low.tag_configure(
            "#stock_ok", background=COLORS.get("stock_ok", "#2d6a4f")
        )

    def _drag_start(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self._dragging = item
            # zapamiętaj indeks początkowy oraz zresetuj flagę ruchu
            self._drag_start_index = self.tree.index(item)
            self._drag_moved = False

    def _drag_motion(self, event):
        item = getattr(self, "_dragging", None)
        if not item:
            return
        target = self.tree.identify_row(event.y)
        if target and target != item:
            idx = self.tree.index(target)
            self.tree.move(item, "", idx)
            # oznacz jako przesunięte tylko, jeśli zmieniło się położenie
            self._drag_moved = idx != getattr(self, "_drag_start_index", idx)

    def _drag_release(self, _event):
        item = getattr(self, "_dragging", None)
        if not item:
            return
        if getattr(self, "_drag_moved", False):
            order = [self.tree.set(ch, "id") for ch in self.tree.get_children("")]
            self._all.sort(key=lambda x: order.index(x["id"]))
            LM.set_order(order)
            self._refresh()
            self._low = [
                it
                for it in self._all
                if float(it.get("stan", 0)) <= float(it.get("min_poziom", 0))
            ]
            self._refresh_low()
        self._dragging = None
        self._drag_moved = False

    def _filter(self):
        q = (self.var_szukaj.get() or "").strip().lower()
        if not q:
            self._refresh(self._all); return
        out = []
        for it in self._all:
            if (q in it["id"].lower()
                or q in it["nazwa"].lower()
                or q in it.get("typ","").lower()):
                out.append(it)
        self._refresh(out)

    def _color_for(self, it):
        stan = float(it.get("stan",0))
        minp = float(it.get("min_poziom",0))
        if stan <= minp:
            return "#stock_low"
        if stan <= (minp*1.5 if minp>0 else 0):
            return "#stock_warn"
        return "#stock_ok"

    def _sel_id(self):
        tree = self.tree if self.nb.index(self.nb.select()) == 0 else self.tree_low
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Magazyn", "Zaznacz pozycję.")
            return None
        vals = tree.item(sel[0], "values")
        return vals[0]

    def _ask_float(self, tytul, pytanie):
        val = simpledialog.askstring(tytul, pytanie, parent=self)
        if val is None: return None
        try:
            x = float(val.replace(",", "."))  # akceptuj przecinek
            if x <= 0: raise ValueError
            return x
        except Exception:
            error_dialogs.show_error_dialog("Błąd", "Podaj dodatnią liczbę.")
            return None

    def _act_zuzyj(self):
        iid = self._sel_id()
        if not iid: return
        il = self._ask_float("Zużycie", "Ilość do zużycia:")
        if il is None: return
        try:
            LM.zuzyj(iid, il, uzytkownik="system", kontekst="GUI Magazyn")
            self._load()
        except Exception as e:
            error_dialogs.show_error_dialog("Błąd", str(e))

    def _act_zwrot(self):
        iid = self._sel_id()
        if not iid: return
        il = self._ask_float("Zwrot", "Ilość do zwrotu:")
        if il is None: return
        try:
            LM.zwrot(iid, il, uzytkownik="system", kontekst="GUI Magazyn")
            self._load()
        except Exception as e:
            error_dialogs.show_error_dialog("Błąd", str(e))

    def _act_rezerwuj(self):
        iid = self._sel_id()
        if not iid: return
        il = self._ask_float("Rezerwacja", "Ilość do rezerwacji:")
        if il is None: return
        try:
            LM.rezerwuj(iid, il, uzytkownik="system", kontekst="GUI Magazyn")
            self._load()
        except Exception as e:
            error_dialogs.show_error_dialog("Błąd", str(e))

    def _act_zwolnij(self):
        iid = self._sel_id()
        if not iid: return
        il = self._ask_float("Zwolnienie rezerwacji", "Ilość do zwolnienia:")
        if il is None: return
        try:
            LM.zwolnij_rezerwacje(iid, il, uzytkownik="system", kontekst="GUI Magazyn")
            self._load()
        except Exception as e:
            error_dialogs.show_error_dialog("Błąd", str(e))

    def _act_do_zam(self):
        """Dodaj pozycję do listy zamówień."""
        pass

    def _act_drukuj_etykiete(self):
        iid = self._sel_id()
        if not iid:
            return
        try:
            drukuj_etykiete(iid)
            messagebox.showinfo("Magazyn", "Etykieta wysłana do drukarki.")
        except Exception as e:
            messagebox.showerror("Magazyn", f"Błąd drukowania: {e}")

    def _act_dodaj(self):
        """Open dialog for adding a warehouse item and wait until it closes."""
        dlg = MagazynAddDialog(
            self.root, self.config, self.profiles, on_saved=self._reload_data
        )
        self.root.wait_window(dlg.top)

    def _act_przyjecie(self):
        """Open dialog for registering a goods receipt (PZ) and wait until it closes."""
        selected = self.tree.selection()
        selected_id = selected[0] if selected else None
        dlg = MagazynPZDialog(
            self.root,
            self.config,
            self.profiles,
            preselect_id=selected_id,
            on_saved=self._reload_data,
        )
        self.root.wait_window(dlg.top)

    def _show_historia(self):
        iid = self._sel_id()
        if not iid: return
        hist = LM.historia_item(iid, limit=200)
        win = tk.Toplevel(self)
        win.title(f"Historia: {iid}")
        apply_theme(win)
        tv = ttk.Treeview(win, columns=("czas","op","ile","kto","ctx"), show="headings", style="WM.Treeview")
        tv.pack(fill="both", expand=True, padx=8, pady=8)
        for c, t, w in [("czas","Czas",150),("op","Operacja",120),("ile","Ilość",80),("kto","Użytkownik",140),("ctx","Kontekst",300)]:
            tv.heading(c, text=t); tv.column(c, width=w, anchor="w")
        for h in hist:
            tv.insert("", "end", values=(h["czas"], h["operacja"], h["ilosc"], h["uzytkownik"], h.get("kontekst","")))
        ttk.Button(win, text="Zamknij", command=win.destroy).pack(pady=(0,8))

    def _update_alerts(self):
        al = LM.sprawdz_progi()
        if not al:
            self.var_alerty.set("Brak alertów magazynowych.")
        else:
            txt = "ALERTY: " + "; ".join([f"{a['item_id']} ({a['nazwa']}) stan={a['stan']} ≤ min={a['min_poziom']}" for a in al])
            self.var_alerty.set(txt)

def panel_magazyn(root, frame, login=None, rola=None):
    apply_theme(root.winfo_toplevel())
    clear_frame(frame)
    PanelMagazyn(frame).pack(fill="both", expand=True)

def open_panel_magazyn(root):
    """Otwiera Toplevel z panelem Magazynu."""
    win = tk.Toplevel(root)
    win.title("Magazyn")
    win.geometry("980x540+120+120")
    apply_theme(win)
    PanelMagazyn(win).pack(fill="both", expand=True)
    return win

def attach_magazyn_button(root, toolbar):
    """Dodaje przycisk 'Magazyn' do przekazanego toolbara (Frame).

    Użycie w gui_panel.py: ``attach_magazyn_button(root, toolbar_frame)``
    """
    btn = ttk.Button(toolbar, text="Magazyn", command=lambda: open_panel_magazyn(root))
    try:
        btn.pack(side="left", padx=4)
    except Exception:
        btn.grid(row=0, column=99, padx=4)
    return btn

def panel_ustawien_magazyn(parent, rola=None):
    apply_theme(parent.winfo_toplevel())
    frm = ttk.Frame(parent, style="WM.Card.TFrame")
    frm.pack(fill="both", expand=True, padx=12, pady=12)

    # wykryj rolę (fallbacki)
    resolved_role = _resolve_role(parent, rola)
    is_priv = _has_priv(resolved_role)

    # Nagłówek + rola
    hdr = ttk.Frame(frm)
    hdr.grid(row=0, column=0, columnspan=3, sticky="ew")
    ttk.Label(hdr, text="Ścieżka pliku magazynu:", style="WM.Card.TLabel").grid(row=0, column=0, sticky="w", padx=8, pady=(8,4))
    ttk.Label(
        hdr,
        text=LM.MAGAZYN_PATH,
        style="WM.Muted.TLabel",
    ).grid(row=0, column=1, sticky="w", padx=8, pady=(8, 4))
    ttk.Label(hdr, text=f"Twoja rola: {resolved_role or 'nieznana'}", style="WM.Muted.TLabel").grid(row=0, column=2, sticky="e", padx=8, pady=(8,4))

    ttk.Label(frm, text="Folder BOM (produkty):", style="WM.Card.TLabel").grid(row=1, column=0, sticky="w", padx=8, pady=4)
    ttk.Label(frm, text="data/produkty/", style="WM.Muted.TLabel").grid(row=1, column=1, sticky="w", padx=8, pady=4)

    def _napraw():
        try:
            m = LM.load_magazyn()
            LM.save_magazyn(m)
            messagebox.showinfo("Magazyn", "Struktura magazyn.json OK (items/meta uzupełnione).")
        except Exception as e:
            error_dialogs.show_error_dialog("Magazyn", f"Błąd sprawdzania/naprawy: {e}")

    ttk.Button(frm, text="Sprawdź/napraw magazyn.json", command=_napraw, style="WM.Side.TButton").grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(10,12))

    # ===== Formularz pozycji (z wymiarem) =====
    box = ttk.LabelFrame(frm, text="Dodaj / aktualizuj pozycję", style="WM.Card.TFrame")
    box.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(6,10))
    for c in range(6):
        box.columnconfigure(c, weight=1)

    var_id  = tk.StringVar()
    var_nm  = tk.StringVar()
    var_typ = tk.StringVar(value="komponent")
    var_jed = tk.StringVar(value="szt")
    var_st  = tk.StringVar(value="0")
    var_min = tk.StringVar(value="0")
    var_len = tk.StringVar(value="0")  # mm

    ttk.Label(box, text="ID:", style="WM.Card.TLabel").grid(row=0, column=0, sticky="w", padx=8, pady=6)
    ent_id = ttk.Entry(box, textvariable=var_id, width=24)
    ent_id.grid(row=0, column=1, sticky="ew", padx=8, pady=6)

    def _extract_prefix(txt: str) -> str:
        s = (txt or "").strip()
        if not s: return "MAT"
        m = re.match(r"^([A-Za-z0-9]+)", s)
        return m.group(1) if m else "MAT"

    def _suggest_id():
        pref = _extract_prefix(var_id.get())
        items = LM.lista_items()
        nums = []; width_guess = 3
        pat = re.compile(rf"^{re.escape(pref)}[-_]?(\d+)$", re.IGNORECASE)
        for it in items:
            iid = it.get("id","")
            mm = pat.match(iid)
            if mm:
                sfx = mm.group(1)
                nums.append(int(sfx))
                width_guess = max(width_guess, len(sfx))
        next_num = (max(nums) + 1) if nums else 1
        existing = {it.get("id","") for it in items}
        candidate = f"{pref}-{next_num:0{width_guess}d}"
        while candidate in existing:
            next_num += 1
            candidate = f"{pref}-{next_num:0{width_guess}d}"
        var_id.set(candidate)

    ttk.Button(box, text="Podpowiedz ID", command=_suggest_id, style="WM.Side.TButton").grid(row=0, column=5, sticky="w", padx=8, pady=6)

    ttk.Label(box, text="Nazwa:", style="WM.Card.TLabel").grid(row=0, column=2, sticky="w", padx=8, pady=6)
    ttk.Entry(box, textvariable=var_nm, width=28).grid(row=0, column=3, columnspan=2, sticky="ew", padx=8, pady=6)

    ttk.Label(box, text="Typ:", style="WM.Card.TLabel").grid(row=1, column=0, sticky="w", padx=8, pady=6)
    cb_typ = ttk.Combobox(box, textvariable=var_typ, values=[], state="readonly")
    cb_typ.grid(row=1, column=1, sticky="ew", padx=8, pady=6)

    ttk.Label(box, text="J.m.:", style="WM.Card.TLabel").grid(row=1, column=2, sticky="w", padx=8, pady=6)
    ttk.Entry(box, textvariable=var_jed, width=12).grid(row=1, column=3, sticky="w", padx=8, pady=6)

    ttk.Label(box, text="Stan (szt):", style="WM.Card.TLabel").grid(row=2, column=0, sticky="w", padx=8, pady=6)
    ttk.Entry(box, textvariable=var_st, width=12).grid(row=2, column=1, sticky="w", padx=8, pady=6)

    ttk.Label(box, text="Min. poziom:", style="WM.Card.TLabel").grid(row=2, column=2, sticky="w", padx=8, pady=6)
    ttk.Entry(box, textvariable=var_min, width=12).grid(row=2, column=3, sticky="w", padx=8, pady=6)

    ttk.Label(box, text="Dł. jednostkowa (mm):", style="WM.Card.TLabel").grid(row=2, column=4, sticky="w", padx=8, pady=6)
    ttk.Entry(box, textvariable=var_len, width=12).grid(row=2, column=5, sticky="w", padx=8, pady=6)

    sum_lbl = ttk.Label(box, text="Suma długości: 0.000 m", style="WM.Muted.TLabel")
    sum_lbl.grid(row=3, column=0, columnspan=6, sticky="w", padx=8, pady=(2,8))

    def _reload_types():
        types = LM.get_item_types()
        try:
            cb_typ.config(values=types)
        except Exception:
            pass
        types_tree.delete(*types_tree.get_children())
        for t in types:
            types_tree.insert('', 'end', values=(t,))
        if (var_typ.get() or "") not in types:
            var_typ.set(types[0] if types else "komponent")

    def _update_sum_label(*_):
        try:
            szt = float((var_st.get() or "0").replace(",", "."))
            mm  = float((var_len.get() or "0").replace(",", "."))
            m   = (szt * mm) / 1000.0 if szt > 0 and mm > 0 else 0.0
            sum_lbl.configure(text=f"Suma długości: {_fmt(m)} m")
        except Exception:
            sum_lbl.configure(text="Suma długości: -")

    var_st.trace_add("write", _update_sum_label)
    var_len.trace_add("write", _update_sum_label)

    info_lbl = ttk.Label(box, text="", style="WM.Muted.TLabel")
    info_lbl.grid(row=4, column=0, columnspan=6, sticky="w", padx=8, pady=(2,8))

    def _submit():
        iid = (var_id.get() or "").strip()
        if not iid:
            messagebox.showwarning("Magazyn", "Wpisz ID pozycji."); return
        nm  = (var_nm.get() or "").strip()
        if not nm:
            messagebox.showwarning("Magazyn", "Wpisz nazwę pozycji."); return
        typ = (var_typ.get() or "").strip()
        if typ not in (LM.get_item_types() or []):
            messagebox.showwarning("Magazyn", "Ten typ nie jest na liście. Najpierw dodaj go w 'Typy magazynowe'."); return
        jed = (var_jed.get() or "szt").strip()
        try:
            st  = float((var_st.get() or "0").replace(",", "."))
            mn  = float((var_min.get() or "0").replace(",", "."))
            ln  = float((var_len.get() or "0").replace(",", "."))
            if st < 0 or mn < 0 or ln < 0: raise ValueError
        except Exception:
            error_dialogs.show_error_dialog("Magazyn", "Wartości 'Stan', 'Min.' i 'Dł.' muszą być liczbami ≥ 0.")
            return

        try:
            payload = {"id": iid, "nazwa": nm, "typ": typ, "jednostka": jed, "stan": st, "min_poziom": mn}
            if ln > 0:
                payload["dl_jednostkowa_mm"] = ln
            LM.upsert_item(payload)
            messagebox.showinfo("Magazyn", f"Zapisano pozycję: {iid} – {nm}")
            var_id.set(""); var_nm.set(""); var_jed.set("szt"); var_st.set("0"); var_min.set("0"); var_len.set("0")
            _update_sum_label()
        except Exception as e:
            error_dialogs.show_error_dialog("Magazyn", f"Błąd zapisu: {e}")

    btn = ttk.Button(box, text="Dodaj / aktualizuj pozycję", command=_submit, style="WM.Side.TButton")
    btn.grid(row=5, column=0, columnspan=6, sticky="w", padx=8, pady=(4,8))

    if not is_priv:
        try:
            btn.state(["disabled"])
        except Exception as e:
            log_akcja(f"[MAGAZYN] Nie można zablokować przycisku dodawania: {e}")
        info_lbl.configure(text="Dodawanie dostępne tylko dla uprawnionych (brygadzista/admin/kierownik).")

    # ===== Typy magazynowe =====
    types_box = ttk.LabelFrame(frm, text="Typy magazynowe", style="WM.Card.TFrame")
    types_box.grid(row=4, column=0, columnspan=3, sticky="ew", padx=6, pady=(0,10))
    for c in range(4):
        types_box.columnconfigure(c, weight=1)

    ttk.Label(types_box, text="Lista typów:", style="WM.Card.TLabel").grid(row=0, column=0, sticky="w", padx=8, pady=(8,4))
    types_tree = ttk.Treeview(types_box, columns=("typ",), show="headings", height=6, style="WM.Treeview")
    types_tree.heading("typ", text="Typ")
    types_tree.column("typ", width=280, anchor="w")
    types_tree.grid(row=1, column=0, columnspan=4, sticky="ew", padx=8, pady=(0,8))

    var_new_type = tk.StringVar()
    ttk.Label(types_box, text="Nowy typ:", style="WM.Card.TLabel").grid(row=2, column=0, sticky="w", padx=8, pady=6)
    ent_new_type = ttk.Entry(types_box, textvariable=var_new_type, width=24)
    ent_new_type.grid(row=2, column=1, sticky="w", padx=8, pady=6)

    def _add_type():
        name = (var_new_type.get() or "").strip()
        if not name:
            messagebox.showwarning("Typy", "Podaj nazwę typu."); return
        try:
            ok = LM.add_item_type(name, uzytkownik="ustawienia")
            if ok:
                messagebox.showinfo("Typy", f"Dodano typ: {name}")
                var_new_type.set("")
                _reload_types()
            else:
                messagebox.showinfo("Typy", f"Typ '{name}' już jest na liście.")
        except Exception as e:
            error_dialogs.show_error_dialog("Typy", f"Błąd dodawania typu: {e}")

    def _get_selected_type():
        sel = types_tree.selection()
        if not sel: return None
        vals = types_tree.item(sel[0], "values")
        if not vals: return None
        return vals[0]

    def _remove_type():
        name = _get_selected_type()
        if not name:
            messagebox.showwarning("Typy", "Zaznacz typ do usunięcia.")
            return
        if not messagebox.askyesno("Typy", f"Czy na pewno usunąć typ '{name}'?"):
            return
        try:
            ok = LM.remove_item_type(name, uzytkownik="ustawienia")
            if ok:
                messagebox.showinfo("Typy", f"Usunięto typ: {name}")
                _reload_types()
            else:
                messagebox.showwarning("Typy", f"Nie można usunąć typu '{name}' (nie istnieje lub jest w użyciu).")
        except Exception as e:
            error_dialogs.show_error_dialog("Typy", f"Błąd usuwania typu: {e}")

    btn_add_type = ttk.Button(types_box, text="➕ Dodaj typ", command=_add_type, style="WM.Side.TButton")
    btn_add_type.grid(row=2, column=2, sticky="w", padx=8, pady=6)
    btn_del_type = ttk.Button(types_box, text="🗑 Usuń zaznaczony", command=_remove_type, style="WM.Side.TButton")
    btn_del_type.grid(row=2, column=3, sticky="w", padx=8, pady=6)

    if not is_priv:
        for b in (btn_add_type, btn_del_type, ent_new_type):
            try:
                b.state(["disabled"]) if hasattr(b, "state") else b.configure(state="disabled")
            except Exception:
                pass
        ttk.Label(types_box, text="Zarządzanie typami dostępne tylko dla uprawnionych (brygadzista/admin/kierownik).",
                  style="WM.Muted.TLabel").grid(row=3, column=0, columnspan=4, sticky="w", padx=8, pady=(0,8))

    # Start: załaduj typy i ustaw obliczenia
    def _init_lists():
        _reload_types()
        _update_sum_label()
    _init_lists()
