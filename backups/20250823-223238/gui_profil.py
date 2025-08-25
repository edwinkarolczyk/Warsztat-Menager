# Plik: gui_profil.py
# Wersja pliku: 1.2.1
# Data: 2025-08-23
# Zmiana: FIX avatara – usunięto bg="" z Canvas (powodowało 'unknown color name ""').
#         Reszta jak w 1.2.0: avatar/login/rola/zmiana, statystyki zadań, lista z kolorami, alias panel_profil.
# Zgodność: gui_panel.py 1.6.16 (uruchom_panel(root, frame, login, rola) / panel_profil)

import os, json
import tkinter as tk
from tkinter import ttk

try:
    from ui_theme import apply_theme
except Exception:
    def apply_theme(_): pass

def _safe_theme(widget):
    try: apply_theme(widget)
    except Exception: pass

def _shift_bounds_label():
    try:
        import gui_panel
        from datetime import datetime as _dt
        s,e,label = gui_panel._shift_bounds(_dt.now())
        return f"{label} ({s.strftime('%H:%M')}–{e.strftime('%H:%M')})"
    except Exception:
        return "I (06:00–14:00)"

def _load_avatar(parent, login):
    # PNG avatars/<login>.png
    if login:
        p = os.path.join("avatars", f"{login}.png")
        if os.path.exists(p):
            try:
                img = tk.PhotoImage(file=p)
                lbl = ttk.Label(parent, image=img)
                lbl.image = img
                return lbl
            except Exception:
                pass
    # Fallback – inicjały (UWAGA: brak bg="", by uniknąć błędu 'unknown color name ""')
    c = tk.Canvas(parent, width=64, height=64, highlightthickness=0)
    c.create_oval(2,2,62,62, fill="#1f2937", outline="#93a3af")
    initials = ((login[:1] + (login[1:2] if login else '')).upper()) if login else "--"
    c.create_text(32,32, text=initials, fill="#e5e7eb", font=("TkDefaultFont", 13, "bold"))
    return c

def _read_tasks(login):
    if not login:
        return []
    p1 = os.path.join("data", f"zadania_{login}.json")
    if os.path.exists(p1):
        try:
            with open(p1, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    p2 = os.path.join("data", "zadania.json")
    if os.path.exists(p2):
        try:
            with open(p2, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [z for z in data if str(z.get("login")) == str(login)]
        except Exception:
            pass
    return []

def _open_zlecenia(root, frame, login, rola):
    try:
        import gui_zlecenia as mod
        for fn_name in ("panel_zlecenia","uruchom_panel","uruchom","open_panel","start","main"):
            fn = getattr(mod, fn_name, None)
            if callable(fn):
                try: return fn(root, frame, login, rola)
                except TypeError:
                    try: return fn(root, frame)
                    except TypeError:
                        try: return fn(frame)
                        except TypeError:
                            return fn()
        tk.messagebox.showinfo("Zlecenia", "Brak kompatybilnej funkcji w gui_zlecenia.")
    except Exception as e:
        try: tk.messagebox.showerror("Zlecenia", f"Błąd importu gui_zlecenia: {e}")
        except Exception: print("[PROFIL] Błąd importu gui_zlecenia:", e)

def _build_header(frame, login, rola):
    head = ttk.Frame(frame); head.pack(fill="x", padx=12, pady=12)
    ph = ttk.Frame(head); ph.pack(side="left")
    _load_avatar(ph, login).pack()
    info = ttk.Frame(head); info.pack(side="left", padx=12)
    ttk.Label(info, text=str(login or "-"), font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
    ttk.Label(info, text=f"Rola: {rola or '-'}").pack(anchor="w")
    ttk.Label(info, text=f"Zmiana: {_shift_bounds_label()}").pack(anchor="w")
    return head

def _stats_from_tasks(tasks):
    total = len(tasks)
    def _is_open(st):
        s=(st or '').strip().lower()
        return s in ("nowe","w toku","new","in progress","progress","pilne","urgent")
    def _is_urgent(st):
        s=(st or '').strip().lower()
        return s in ("pilne","urgent")
    open_cnt = sum(1 for t in tasks if _is_open(t.get("status")))
    urgent_cnt = sum(1 for t in tasks if _is_urgent(t.get("status")))
    done_cnt = sum(1 for t in tasks if (t.get("status","")).strip().lower() in ("zrobione","done","closed","zamknięte"))
    return total, open_cnt, urgent_cnt, done_cnt

def _build_stats(frame, tasks):
    total, open_cnt, urgent_cnt, done_cnt = _stats_from_tasks(tasks)
    bar = ttk.Frame(frame); bar.pack(fill="x", padx=12, pady=(0,8))
    def chip(text):
        c = ttk.Label(bar, text=text, relief="groove"); c.pack(side="left", padx=4); return c
    chip(f"Zadania: {total}"); chip(f"Otwarte: {open_cnt}"); chip(f"Pilne: {urgent_cnt}"); chip(f"Zrobione: {done_cnt}")

def _build_tasks(frame, root, login, rola):
    container = ttk.Frame(frame); container.pack(fill="both", expand=True, padx=12, pady=(0,12))
    header = ttk.Frame(container); header.pack(fill="x", pady=(0,6))
    ttk.Label(header, text="Twoje zadania", font=("TkDefaultFont", 11, "bold")).pack(side="left")

    tasks = _read_tasks(login)
    ttk.Label(header, text=f"({len(tasks)})").pack(side="left", padx=(6,0))

    if not tasks:
        ttk.Label(container, text="Brak przypisanych zadań.").pack(anchor="w")
        ttk.Button(container, text="Otwórz Zlecenia", command=lambda:_open_zlecenia(root, frame, login, rola)).pack(anchor="w", pady=6)
        return

    cols=("id","tytul","status","termin")
    tv = ttk.Treeview(container, columns=cols, show="headings", height=10)
    for c,w in zip(cols,(90,420,130,130)):
        tv.heading(c, text=c.capitalize()); tv.column(c, width=w, anchor="w")
    tv.pack(fill="both", expand=True)

    tv.tag_configure("NOWE", foreground="#60a5fa")
    tv.tag_configure("WTOKU", foreground="#f59e0b")
    tv.tag_configure("PILNE", foreground="#ef4444")
    tv.tag_configure("DONE", foreground="#22c55e")

    def _tag(status):
        s=(status or '').strip().lower()
        if s in ("nowe","new"): return "NOWE"
        if s in ("w toku","in progress","progress"): return "WTOKU"
        if s in ("pilne","urgent"): return "PILNE"
        if s in ("zrobione","done","closed","zamknięte"): return "DONE"
        return ""

    for z in tasks:
        tv.insert("", "end",
                  values=(z.get("id",""), z.get("tytul",""), z.get("status",""), z.get("termin","")),
                  tags=(_tag(z.get("status")),))

def uruchom_panel(root, frame, login=None, rola=None):
    print(f"[WM-DBG][PROFIL] start login={login} rola={rola}")
    for w in frame.winfo_children():
        try: w.destroy()
        except Exception: pass
    _safe_theme(root); _safe_theme(frame)
    _build_header(frame, login, rola)
    tasks = _read_tasks(login)
    _build_stats(frame, tasks)
    _build_tasks(frame, root, login, rola)
    return frame

# Alias dla kompatybilności ze starym wywołaniem w gui_panel.py 1.6.16
panel_profil = uruchom_panel
