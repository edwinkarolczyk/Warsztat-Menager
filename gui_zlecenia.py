# =============================
# FILE: gui_zlecenia.py
# VERSION: 1.1.4
# Zmiany 1.1.4:
# - Kreator zlecenia: dialog zamówienia brakujących materiałów
# - Tabela: kolumna "Tyczy nr" (zlec_wew)
# =============================

import json
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox
import logging
import traceback

import bom

from ui_theme import apply_theme_safe as apply_theme, FG as _FG, DARK_BG as _DBG
from utils import error_dialogs
from config_manager import ConfigManager
from utils.dirty_guard import DirtyGuard

logger = logging.getLogger(__name__)

try:
    from zlecenia_logika import (
        list_zlecenia,
        list_produkty,
        create_zlecenie,
        STATUSY,
        update_status,
        update_zlecenie,
        read_magazyn,
        compute_material_needs,
    )
    from logika_magazyn import rezerwuj_materialy
    try:
        from zlecenia_logika import delete_zlecenie as _delete_zlecenie
    except ImportError:
        _delete_zlecenie = None
except ImportError:
    raise

__all__ = ["panel_zlecenia"]

# Helpers

def _maybe_theme(widget):
    if isinstance(widget, (tk.Tk, tk.Toplevel)):
        apply_theme(widget)

def _fmt(v):
    return "" if v is None else str(v)


def _append_pending_order(kod_produktu, braki):
    zam_path = Path("data") / "zamowienia_oczekujace.json"
    try:
        with open(zam_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.exception("Failed to read pending orders: %s", e)
        data = []
    entry = {
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "produkt": kod_produktu,
        "braki": {b.get("nazwa") or b["kod"]: b["brakuje"] for b in braki},
        "status": "do_zamowienia",
    }
    data.append(entry)
    with open(zam_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

_STATUS_TO_PCT = {
    "nowe": 0,
    "oczekujące": 0,
    "wstrzymane": 0,
    "w przygotowaniu": 20,
    "w trakcie": 60,
    "w realizacji": 70,
    "zakończone": 100,
    "anulowane": 0,
}

def _bar10(percent: int) -> str:
    try:
        p = max(0, min(100, int(percent)))
    except (TypeError, ValueError):
        p = 0
    filled = p // 10
    return "■" * filled + "□" * (10 - filled)

# UI główne

def panel_zlecenia(parent, root=None, app=None, notebook=None):
    _maybe_theme(root)
    frame = ttk.Frame(parent, style="WM.TFrame")

    cm = ConfigManager()

    # H1
    header = ttk.Frame(frame, style="WM.TFrame"); header.pack(fill="x", padx=12, pady=(10, 6))
    ttk.Label(header, text="Zlecenia", style="WM.H1.TLabel").pack(side="left")

    # Pasek akcji
    actions = ttk.Frame(frame, style="WM.TFrame"); actions.pack(fill="x", padx=12, pady=(0, 8))
    btn_nowe = ttk.Button(actions, text="Nowe zlecenie"); btn_nowe.pack(side="left")
    btn_odsw = ttk.Button(actions, text="Odśwież");      btn_odsw.pack(side="left", padx=6)
    btn_edyt = ttk.Button(actions, text="Edytuj");       btn_edyt.pack(side="left", padx=6)
    btn_usun = ttk.Button(actions, text="Usuń");         btn_usun.pack(side="left", padx=6)
    btn_rez  = ttk.Button(actions, text="Rezerwuj");     btn_rez.pack(side="left", padx=6)

    right = ttk.Frame(actions, style="WM.TFrame"); right.pack(side="right")
    ttk.Label(right, text="Status:", style="WM.TLabel").pack(side="left", padx=(0, 6))
    cb_status = ttk.Combobox(right, state="readonly", values=["(wszystkie)"] + STATUSY, width=18)
    cb_status.current(0); cb_status.pack(side="left")
    ttk.Label(right, text="Szukaj:", style="WM.TLabel").pack(side="left", padx=(12, 6))
    ent_search = ttk.Entry(right, width=28); ent_search.pack(side="left")

    # Info bar
    info_bar = ttk.Frame(frame, style="WM.TFrame"); info_bar.pack(fill="x", padx=12, pady=(0, 6))
    lbl_info = ttk.Label(info_bar, text="Panel Zleceń – odświeżono listę", style="WM.Muted.TLabel")
    lbl_info.pack(side="left")

    # Tabela – dodana kolumna zlec_wew (Tyczy nr)
    cols = ("id", "zlec_wew", "produkt", "ilosc", "status", "utworzono", "postep")
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=18, style="WM.Treeview")
    tree.heading("id", text="ID");                 tree.column("id", width=110, anchor="center")
    tree.heading("zlec_wew", text="Tyczy nr");      tree.column("zlec_wew", width=110, anchor="center")
    tree.heading("produkt", text="Produkt");       tree.column("produkt", width=240, anchor="w")
    tree.heading("ilosc", text="Ilość");           tree.column("ilosc", width=80, anchor="center")
    tree.heading("status", text="Status");         tree.column("status", width=170, anchor="center")
    tree.heading("utworzono", text="Utworzono");    tree.column("utworzono", width=180, anchor="center")
    tree.heading("postep", text="Postęp (10 kratek)"); tree.column("postep", width=180, anchor="center")
    tree.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    # Menu PPM + Delete
    menu = tk.Menu(tree, tearoff=False)
    menu.add_command(
        label="Edytuj zlecenie",
        command=lambda: _edit_zlecenie(tree, lbl_info, root, _odswiez),
    )
    menu.add_command(
        label="Usuń zlecenie",
        command=lambda: _usun_zlecenie(tree, lbl_info, _odswiez),
    )

    def _refresh_permissions():
        allowed = {str(r).lower() for r in cm.get("zlecenia.edit_roles", [])}
        role = str(getattr(root, "_wm_rola", "")).lower()
        can = role in allowed if allowed else False
        for btn in (btn_nowe, btn_edyt, btn_usun, btn_rez):
            try:
                btn.state(["!disabled"] if can else ["disabled"])
            except tk.TclError:
                btn.configure(state="normal" if can else "disabled")
        try:
            menu.entryconfig("Edytuj zlecenie", state="normal" if can else "disabled")
            menu.entryconfig("Usuń zlecenie", state="normal" if can else "disabled")
        except tk.TclError:
            pass
        return can

    _refresh_permissions()
    if root is not None:
        root.after(0, _refresh_permissions)

    def _popup(e):
        iid = tree.identify_row(e.y)
        if iid:
            tree.selection_set(iid)
            try:
                menu.tk_popup(e.x_root, e.y_root)
            finally:
                menu.grab_release()

    tree.bind("<Button-3>", _popup)
    tree.bind("<Delete>", lambda e: _usun_zlecenie(tree, lbl_info, _odswiez))

    # Odświeżanie + filtr
    def _odswiez(*_):
        for i in tree.get_children():
            tree.delete(i)
        rows = list_zlecenia()
        q  = (ent_search.get() or "").strip().lower()
        st = cb_status.get() or "(wszystkie)"

        def _match(row):
            if st != "(wszystkie)" and _fmt(row.get("status")) != st:
                return False
            if not q:
                return True
            sid  = _fmt(row.get("id")).lower()
            prod = _fmt(row.get("produkt")).lower()
            zwf  = _fmt(row.get("zlec_wew")).lower()
            return (q in sid) or (q in prod) or (q in zwf)

        rows = [r for r in rows if _match(r)]

        if not rows:
            tree.insert("", "end", values=("— brak zleceń —", "", "", "", "", "", _bar10(0)))
            lbl_info.config(text="Panel Zleceń – brak wyników")
            return

        for z in rows:
            pid = _fmt(z.get("id")); zw = _fmt(z.get("zlec_wew")); prod = _fmt(z.get("produkt")); ilo = _fmt(z.get("ilosc"))
            stat = _fmt(z.get("status")); utw = _fmt(z.get("utworzono"))
            pct  = z.get("postep") if isinstance(z.get("postep"), int) else _STATUS_TO_PCT.get(stat, 0)
            tree.insert("", "end", values=(pid, zw, prod, ilo, stat, utw, _bar10(pct)))
        lbl_info.config(text=f"Panel Zleceń – odświeżono listę ({len(rows)})")

    def _on_dbl(_):
        item = tree.selection()
        if not item: return
        zid = tree.set(item[0], "id")
        if not zid or zid.strip() == "— brak zleceń —": return
        _edit_status_dialog(frame, zid, tree, lbl_info, root, _odswiez)

    tree.bind("<Double-1>", _on_dbl)

    # Enter filtr, combo filtr
    ent_search.bind("<Return>",   lambda e: _odswiez())
    ent_search.bind("<KP_Enter>", lambda e: _odswiez())
    cb_status.bind("<<ComboboxSelected>>", _odswiez)

    # Akcje
    btn_nowe.configure(command=lambda: _kreator_zlecenia(frame, lbl_info, root, _odswiez))
    btn_odsw.configure(command=_odswiez)
    btn_edyt.configure(command=lambda: _edit_zlecenie(tree, lbl_info, root, _odswiez))
    btn_usun.configure(command=lambda: _usun_zlecenie(tree, lbl_info, _odswiez))
    btn_rez.configure(command=lambda: _rezerwuj_materialy(tree, lbl_info, root))

    _odswiez()
    return frame

# Dialogi/akcje

def _kreator_zlecenia(parent: tk.Widget, lbl_info: ttk.Label, root, on_done) -> None:
    win = tk.Toplevel(parent)
    win.title("Nowe zlecenie produkcyjne")
    apply_theme(win)
    try:
        win.configure(bg=_DBG, highlightthickness=0, highlightbackground=_DBG)
    except tk.TclError:
        try:
            win.configure(highlightthickness=0)
        except tk.TclError:
            logger.exception("Unable to configure creator window")
    try:
        win.grab_set()
    except tk.TclError:
        logger.exception("grab_set failed for creator window")
    win.geometry("620x420")

    frm = ttk.Frame(win, style="WM.TFrame")
    frm.pack(fill="both", expand=True, padx=12, pady=12)

    ttk.Label(frm, text="Produkt", style="WM.TLabel").grid(
        row=0, column=0, sticky="w", pady=(0, 6)
    )
    try:
        produkty = list_produkty()
    except Exception as e:
        logger.exception("list_produkty failed: %s", e)
        produkty = []
    kody = [p.get("kod", "") for p in produkty]
    cb_prod = ttk.Combobox(frm, values=kody, state="readonly", width=30)
    if kody:
        cb_prod.current(0)
    cb_prod.grid(row=0, column=1, sticky="we", padx=(8, 0), pady=(0, 6))

    ttk.Label(frm, text="Ilość", style="WM.TLabel").grid(
        row=1, column=0, sticky="w"
    )
    spn = ttk.Spinbox(frm, from_=1, to=999, width=10)
    spn.set(1)
    spn.grid(row=1, column=1, sticky="w", padx=(8, 0))

    ttk.Label(
        frm, text="Zapotrzebowanie", style="WM.TLabel"
    ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
    cols = ("kod", "potrzeba", "dostepne", "brakuje")
    tv = ttk.Treeview(
        frm, columns=cols, show="headings", height=8, style="WM.Treeview"
    )
    tv.heading("kod", text="Składnik")
    tv.column("kod", width=140, anchor="w")
    tv.heading("potrzeba", text="Potrzeba")
    tv.column("potrzeba", width=80, anchor="center")
    tv.heading("dostepne", text="Dostępne")
    tv.column("dostepne", width=80, anchor="center")
    tv.heading("brakuje", text="Brakuje")
    tv.column("brakuje", width=80, anchor="center")
    tv.grid(row=3, column=0, columnspan=2, sticky="nsew")

    frm.columnconfigure(1, weight=1)
    frm.rowconfigure(3, weight=1)

    def refresh(*_):
        for i in tv.get_children():
            tv.delete(i)
        kod = cb_prod.get().strip()
        if not kod:
            tv._bom = {}
            tv._needs = []
            return
        try:
            ilosc = int(spn.get())
        except ValueError:
            ilosc = 1
        try:
            potrzeby, bom_sr = compute_material_needs(kod, ilosc)
        except Exception as e:
            logger.exception("compute_material_needs failed for %s: %s", kod, e)
            potrzeby, bom_sr = [], {}
        for row in potrzeby:
            tv.insert(
                "",
                "end",
                values=(
                    row["kod"],
                    row["potrzeba"],
                    row["dostepne"],
                    row["brakuje"],
                ),
            )
        tv._bom = bom_sr
        tv._needs = potrzeby

    cb_prod.bind("<<ComboboxSelected>>", refresh)
    spn.bind("<KeyRelease>", refresh)
    spn.bind("<FocusOut>", refresh)
    refresh()

    def start_order():
        kod = cb_prod.get().strip()
        if not kod:
            messagebox.showwarning("Brak produktu", "Wybierz produkt z listy.", parent=win)
            return
        try:
            ilosc = int(spn.get())
        except ValueError:
            messagebox.showwarning("Błędna ilość", "Podaj prawidłową liczbę.", parent=win)
            return
        potrzeby = getattr(tv, "_needs", [])
        bom_sr = getattr(tv, "_bom", {})
        braki = [r for r in potrzeby if r["brakuje"] > 0]
        rezerwuj_materialy(bom_sr, ilosc)
        if braki:
            msg = ", ".join(f"{b['kod']} ({b['brakuje']})" for b in braki)
            if messagebox.askyesno(
                "Braki materiałowe",
                f"Brakuje {msg} – zamówić?",
                parent=win,
            ):
                _append_pending_order(kod, braki)
        zlec, _ = create_zlecenie(kod, ilosc, autor="GUI", reserve=False)
        messagebox.showinfo(
            "Zlecenie utworzone",
            f"ID: {zlec['id']}, status: {zlec['status']}",
            parent=win,
        )
        lbl_info.config(text=f"Utworzono zlecenie {zlec['id']}")
        win.destroy()
        on_done()

    btns = ttk.Frame(win, style="WM.TFrame")
    btns.pack(fill="x", pady=(0, 12))
    ttk.Button(
        btns,
        text="Zarezerwuj materiały i rozpocznij",
        command=start_order,
    ).pack(side="right", padx=6)
    ttk.Button(btns, text="Anuluj", command=win.destroy).pack(side="right")


def _edit_zlecenie(tree: ttk.Treeview, lbl_info: ttk.Label, root, on_done) -> None:
    item = tree.selection()
    if not item:
        messagebox.showinfo("Edycja", "Wybierz zlecenie z listy.")
        return
    zid = tree.set(item[0], "id")
    if not zid or zid.strip() == "— brak zleceń —":
        return
    rows = list_zlecenia()
    data = next((r for r in rows if str(r.get("id")) == zid), None)
    if not data:
        messagebox.showerror("Edycja", f"Nie znaleziono zlecenia {zid}.")
        return

    win = tk.Toplevel(root)
    base_title = f"Edytuj zlecenie {zid}"
    win.title(base_title)
    _maybe_theme(win)
    win.geometry("480x300")

    frm = ttk.Frame(win, style="WM.TFrame"); frm.pack(fill="both", expand=True, padx=12, pady=12)
    ttk.Label(frm, text="Ilość", style="WM.TLabel").grid(row=0, column=0, sticky="w")
    spn = ttk.Spinbox(frm, from_=1, to=999, width=10)
    spn.set(data.get("ilosc", 1))
    spn.grid(row=0, column=1, sticky="w", padx=(8, 0))

    ttk.Label(frm, text="Tyczy nr", style="WM.TLabel").grid(row=1, column=0, sticky="w", pady=(8,0))
    ent_ref = ttk.Entry(frm, width=18)
    if data.get("zlec_wew") is not None:
        ent_ref.insert(0, str(data.get("zlec_wew")))
    ent_ref.grid(row=1, column=1, sticky="w", padx=(8,0), pady=(8,0))

    ttk.Label(frm, text="Uwagi", style="WM.TLabel").grid(row=2, column=0, sticky="nw", pady=(8,0))
    txt = tk.Text(frm, height=8)
    txt.grid(row=2, column=1, sticky="nsew", padx=(8,0), pady=(8,0))
    try:
        txt.configure(bg=_DBG, fg=_FG, insertbackground=_FG,
                      highlightthickness=1, highlightbackground=_DBG, highlightcolor=_DBG)
    except tk.TclError:
        logger.exception("Text widget configure failed")
    txt.insert("1.0", data.get("uwagi", ""))

    frm.columnconfigure(1, weight=1)
    frm.rowconfigure(2, weight=1)

    def _load():
        spn.set(data.get("ilosc", 1))
        ent_ref.delete(0, tk.END)
        if data.get("zlec_wew") is not None:
            ent_ref.insert(0, str(data.get("zlec_wew")))
        txt.delete("1.0", "end")
        txt.insert("1.0", data.get("uwagi", ""))

    def zapisz():
        try:
            ilosc = int(spn.get())
        except ValueError:
            messagebox.showwarning("Błędna ilość", "Podaj prawidłową liczbę.", parent=win)
            return
        uw = txt.get("1.0", "end").strip()
        ref_raw = (ent_ref.get() or "").strip()
        zw = int(ref_raw) if ref_raw.isdigit() else (ref_raw if ref_raw else None)
        update_zlecenie(zid, ilosc=ilosc, uwagi=uw, zlec_wew=zw, kto="GUI")
        lbl_info.config(text=f"Zmieniono zlecenie {zid}")
        win.destroy(); on_done()

    guard = DirtyGuard(
        base_title,
        on_save=lambda: (zapisz(), guard.reset()),
        on_reset=lambda: (_load(), guard.reset()),
        on_dirty_change=lambda d: win.title(base_title + (" *" if d else "")),
    )
    guard.watch(frm)
    guard.reset()

    def check_dirty():
        if guard.dirty:
            return messagebox.askyesno(
                "Niezapisane zmiany",
                "Porzucić niezapisane zmiany?",
                parent=win,
            )
        return True

    guard.check_dirty = check_dirty

    def on_close():
        if guard.check_dirty():
            win.destroy()

    btns = ttk.Frame(win, style="WM.TFrame"); btns.pack(fill="x", padx=12, pady=(0,12))
    ttk.Button(btns, text="Zapisz", command=guard.on_save).pack(side="right", padx=6)
    ttk.Button(btns, text="Anuluj", command=on_close).pack(side="right")

    win.protocol("WM_DELETE_WINDOW", on_close)

def _edit_status_dialog(parent: tk.Widget, zlec_id: str, tree: ttk.Treeview,
                        lbl_info: ttk.Label, root, on_done) -> None:
    win = tk.Toplevel(parent); win.title(f"Status zlecenia {zlec_id}")
    _maybe_theme(win)
    try:
        win.configure(highlightthickness=0, highlightbackground=_DBG)
    except tk.TclError:
        logger.exception("edit_status_dialog configure failed")
    try:
        win.grab_set()
    except tk.TclError:
        logger.exception("edit_status_dialog grab_set failed")
    win.geometry("420x180")

    frm = ttk.Frame(win, style="WM.TFrame"); frm.pack(fill="both", expand=True, padx=12, pady=12)
    ttk.Label(frm, text="Nowy status", style="WM.TLabel").pack(anchor="w", pady=(0, 4))
    cb = ttk.Combobox(frm, values=STATUSY, state="readonly"); cb.pack(fill="x")
    try:
        current = tree.set(tree.selection()[0], "status")
        if current in STATUSY:
            cb.set(current)
        else:
            cb.current(0)
    except tk.TclError:
        cb.current(0)

    btns = ttk.Frame(win, style="WM.TFrame"); btns.pack(fill="x", padx=12, pady=(0, 12))
    def ok():
        st = cb.get(); update_status(zlec_id, st, kto="GUI")
        lbl_info.config(text=f"Zmieniono status {zlec_id} -> {st}")
        win.destroy(); on_done()
    ttk.Button(btns, text="Zapisz", command=ok).pack(side="right", padx=6)
    ttk.Button(btns, text="Zamknij", command=win.destroy).pack(side="right")


def _usun_zlecenie(tree: ttk.Treeview, lbl_info: ttk.Label, on_done):
    item = tree.selection()
    if not item: return
    zid = tree.set(item[0], "id")
    if not zid or zid.strip() == "— brak zleceń —": return
    if _delete_zlecenie is None:
        messagebox.showinfo("Usuń zlecenie", "Funkcja usuwania nieaktywna (brak delete_zlecenie w zlecenia_logika.py).")
        return
    if not messagebox.askyesno("Usuwanie zlecenia", f"Na pewno usunąć zlecenie {zid}?", icon="warning"):
        return
    try:
        ok = _delete_zlecenie(zid)
        if ok:
            lbl_info.config(text=f"Usunięto zlecenie {zid}")
            on_done()
        else:
            messagebox.showwarning("Usuwanie", f"Nie znaleziono pliku zlecenia {zid}")
    except Exception as e:
        logger.exception("delete_zlecenie failed: %s", e)
        error_dialogs.show_error_dialog("Usuwanie", f"Błąd: {e}\n{traceback.format_exc()}")


def _rezerwuj_materialy(tree: ttk.Treeview, lbl_info: ttk.Label, root) -> None:
    item = tree.selection()
    if not item:
        messagebox.showinfo("Rezerwacja", "Wybierz zlecenie z listy.")
        return
    prod = tree.set(item[0], "produkt")
    ilosc_raw = tree.set(item[0], "ilosc") or "1"
    try:
        ilosc = int(ilosc_raw)
    except ValueError:
        ilosc = 1
    try:
        sr_unit = bom.compute_sr_for_prd(prod, 1)
    except Exception as e:
        logger.exception("compute_sr_for_prd failed for %s: %s", prod, e)
        messagebox.showerror("BOM", f"Błąd: {e}")
        return
    if not sr_unit:
        messagebox.showinfo("Rezerwacja", "Brak surowców w BOM.")
        return

    mag = read_magazyn()
    win = tk.Toplevel(root)
    win.title(f"Rezerwacja materiałów {prod}")
    _maybe_theme(win)
    win.geometry("560x360")

    frame = ttk.Frame(win, style="WM.TFrame"); frame.pack(fill="both", expand=True, padx=12, pady=12)
    cols = ("kod", "potrzeba", "dostepne", "dostepne_po")
    tv = ttk.Treeview(frame, columns=cols, show="headings", height=12, style="WM.Treeview")
    tv.heading("kod", text="Składnik");      tv.column("kod", width=140, anchor="w")
    tv.heading("potrzeba", text="Potrzeba"); tv.column("potrzeba", width=80, anchor="center")
    tv.heading("dostepne", text="Dostępne"); tv.column("dostepne", width=80, anchor="center")
    tv.heading("dostepne_po", text="Dostępne po"); tv.column("dostepne_po", width=100, anchor="center")
    tv.pack(fill="both", expand=True)

    for kod, info in sr_unit.items():
        req = info["ilosc"] * ilosc
        stan = mag.get(kod, {}).get("stan", 0)
        tv.insert("", "end", values=(kod, req, stan, stan))

    btns = ttk.Frame(win, style="WM.TFrame"); btns.pack(fill="x", padx=12, pady=(0, 12))

    def do_reserve():
        ok, braki, zlec = rezerwuj_materialy(sr_unit, ilosc)
        mag_new = read_magazyn()
        for iid in tv.get_children():
            kod = tv.set(iid, "kod")
            if kod in mag_new:
                tv.set(iid, "dostepne_po", str(mag_new[kod]["stan"]))
        lbl_info.config(text=f"Zarezerwowano materiały dla {prod}")
        if zlec:
            messagebox.showinfo(
                "Zlecenie zakupów",
                f"Utworzono zlecenie {zlec['nr']}\n{zlec['sciezka']}",
            )
        btn_res.configure(state="disabled")

    btn_res = ttk.Button(btns, text="Rezerwuj", command=do_reserve)
    btn_res.pack(side="right", padx=6)
    ttk.Button(btns, text="Zamknij", command=win.destroy).pack(side="right")
