# =============================
# FILE: gui_zlecenia.py
# VERSION: 1.1.4
# Zmiany 1.1.4:
# - Kreator: dialog zamówienia brakujących materiałów
# - Tabela: nowa kolumna "Tyczy nr" (zlec_wew)
# - Szukaj: obejmuje też numer wewnętrzny
# - Kreator: pole "Tyczy się zlecenia nr (wew.)" i przekazanie do create_zlecenie(zlec_wew=...)
# - Dialog statusu: ciemne okno (highlight off) — jak wcześniej
# =============================


import tkinter as tk
from tkinter import ttk, messagebox

from ui_theme import apply_theme_safe as apply_theme, FG as _FG, DARK_BG as _DBG
from utils import error_dialogs

try:
    from zlecenia_logika import (
        list_zlecenia,
        list_produkty,
        create_zlecenie,
        STATUSY,
        update_status,
        queue_material_order,
    )
    try:
        from zlecenia_logika import delete_zlecenie as _delete_zlecenie
    except Exception:
        _delete_zlecenie = None
except Exception:
    raise

__all__ = ["panel_zlecenia"]

# Helpers

def _maybe_theme(widget):
    if isinstance(widget, (tk.Tk, tk.Toplevel)):
        apply_theme(widget)

def _fmt(v):
    return "" if v is None else str(v)

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
    except Exception:
        p = 0
    filled = p // 10
    return "■" * filled + "□" * (10 - filled)

# UI główne

def panel_zlecenia(parent, root=None, app=None, notebook=None):
    _maybe_theme(root)
    frame = ttk.Frame(parent, style="WM.TFrame")

    # H1
    header = ttk.Frame(frame, style="WM.TFrame"); header.pack(fill="x", padx=12, pady=(10, 6))
    ttk.Label(header, text="Zlecenia", style="WM.H1.TLabel").pack(side="left")

    # Pasek akcji
    actions = ttk.Frame(frame, style="WM.TFrame"); actions.pack(fill="x", padx=12, pady=(0, 8))
    btn_nowe = ttk.Button(actions, text="Nowe zlecenie"); btn_nowe.pack(side="left")
    btn_odsw = ttk.Button(actions, text="Odśwież");      btn_odsw.pack(side="left", padx=6)
    btn_usun = ttk.Button(actions, text="Usuń");         btn_usun.pack(side="left", padx=6)

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
    menu.add_command(label="Usuń zlecenie", command=lambda: _usun_zlecenie(tree, lbl_info, _odswiez))

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
    btn_usun.configure(command=lambda: _usun_zlecenie(tree, lbl_info, _odswiez))

    _odswiez()
    return frame

# Dialogi/akcje

def _kreator_zlecenia(parent: tk.Widget, lbl_info: ttk.Label, root, on_done) -> None:
    win = tk.Toplevel(parent); win.title("Nowe zlecenie produkcyjne")
    apply_theme(win)
    try:
        win.configure(bg=_DBG, highlightthickness=0, highlightbackground=_DBG)
    except Exception:
        try: win.configure(highlightthickness=0)
        except Exception: pass
    try: win.grab_set()
    except Exception: pass
    win.geometry("660x380")

    frm = ttk.Frame(win, style="WM.TFrame"); frm.pack(fill="both", expand=True, padx=12, pady=12)

    ttk.Label(frm, text="Produkt", style="WM.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
    try: produkty = list_produkty()
    except Exception: produkty = []
    kody = [p.get("kod", "") for p in produkty]
    cb_prod = ttk.Combobox(frm, values=kody, state="readonly", width=30)
    if kody: cb_prod.current(0)
    cb_prod.grid(row=0, column=1, sticky="we", padx=(8, 0), pady=(0, 6))

    ttk.Label(frm, text="Ilość", style="WM.TLabel").grid(row=1, column=0, sticky="w")
    spn = ttk.Spinbox(frm, from_=1, to=999, width=10); spn.set(1)
    spn.grid(row=1, column=1, sticky="w", padx=(8, 0))

    # NOWE: numer wewnętrzny
    ttk.Label(frm, text="Tyczy się zlecenia nr (wew.)", style="WM.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
    ent_ref = ttk.Entry(frm, width=18)
    ent_ref.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

    ttk.Label(frm, text="Uwagi", style="WM.TLabel").grid(row=3, column=0, sticky="nw", pady=(8, 0))
    txt = tk.Text(frm, height=8)
    txt.grid(row=3, column=1, sticky="nsew", padx=(8, 0), pady=(8, 0))
    try:
        txt.configure(bg=_DBG, fg=_FG, insertbackground=_FG,
                      highlightthickness=1, highlightbackground=_DBG, highlightcolor=_DBG)
    except Exception:
        pass

    frm.columnconfigure(1, weight=1)
    frm.rowconfigure(3, weight=1)

    def akcept():
        kod = cb_prod.get().strip()
        if not kod:
            messagebox.showwarning("Brak produktu", "Wybierz produkt z listy.", parent=win); return
        try:
            ilosc = int(spn.get())
        except Exception:
            messagebox.showwarning("Błędna ilość", "Podaj prawidłową liczbę.", parent=win); return
        uw = txt.get("1.0", "end").strip()
        ref_raw = (ent_ref.get() or "").strip()
        zlec_wew = int(ref_raw) if ref_raw.isdigit() else (ref_raw if ref_raw else None)
        zlec, braki = create_zlecenie(
            kod, ilosc, uwagi=uw, autor="GUI", zlec_wew=zlec_wew
        )
        if braki:
            braki_txt = ", ".join(f"{b['kod']} ({b['brakuje']})" for b in braki)
            if messagebox.askyesno(
                "Braki materiałowe",
                f"Brakuje {braki_txt} – zamówić?",
                parent=win,
            ):
                queue_material_order(kod, braki)
        messagebox.showinfo(
            "Zlecenie utworzone", f"ID: {zlec['id']}, status: {zlec['status']}", parent=win
        )
        lbl_info.config(text=f"Utworzono zlecenie {zlec['id']}")
        win.destroy(); on_done()

    btns = ttk.Frame(win, style="WM.TFrame"); btns.pack(fill="x", pady=(0, 12))
    ttk.Button(btns, text="Utwórz", command=akcept).pack(side="right", padx=6)
    ttk.Button(btns, text="Anuluj", command=win.destroy).pack(side="right")


def _edit_status_dialog(parent: tk.Widget, zlec_id: str, tree: ttk.Treeview,
                        lbl_info: ttk.Label, root, on_done) -> None:
    win = tk.Toplevel(parent); win.title(f"Status zlecenia {zlec_id}")
    _maybe_theme(win)
    try: win.configure(highlightthickness=0, highlightbackground=_DBG)
    except Exception: pass
    try: win.grab_set()
    except Exception: pass
    win.geometry("420x180")

    frm = ttk.Frame(win, style="WM.TFrame"); frm.pack(fill="both", expand=True, padx=12, pady=12)
    ttk.Label(frm, text="Nowy status", style="WM.TLabel").pack(anchor="w", pady=(0, 4))
    cb = ttk.Combobox(frm, values=STATUSY, state="readonly"); cb.pack(fill="x")
    try:
        current = tree.set(tree.selection()[0], "status")
        if current in STATUSY: cb.set(current)
        else: cb.current(0)
    except Exception:
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
        error_dialogs.show_error_dialog("Usuwanie", f"Błąd: {e}")
