# Plik: gui_profil.py
# Wersja pliku: 1.3.2
# Patch E (23.08.2025): dodano obsługę zleceń w Profilu
# - Łączy zadania z: zadania_<login>.json, zadania.json, zadania_narzedzia.json, zadania_zlecenia.json
#   + NOWE: zlecenia_<login>.json, zlecenia.json (przypisane do login)
# - Konwertuje wpisy zleceń na format 'task' widoczny w Profilu
# - Dwuklik i edycja statusu działa tak samo
# - Alias: panel_profil = uruchom_panel

import os, json
import tkinter as tk
from tkinter import ttk, messagebox

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
    if login:
        p = os.path.join("avatars", f"{login}.png")
        if os.path.exists(p):
            try:
                img = tk.PhotoImage(file=p)
                lbl = ttk.Label(parent, image=img); lbl.image = img
                return lbl
            except Exception:
                pass
    c = tk.Canvas(parent, width=96, height=96, highlightthickness=0)
    c.create_oval(2,2,94,94, fill="#1f2937", outline="#93a3af")
    initials = ((login[:1] + (login[1:2] if login else '')).upper()) if login else "--"
    c.create_text(48,48, text=initials, fill="#e5e7eb", font=("TkDefaultFont", 16, "bold"))
    return c

# ---- PATCH E: konsolidacja zadań + zlecenia ----
def _read_tasks(login):
    def read_json(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    all_tasks = []

    # 1) indywidualne
    p_personal = os.path.join("data", f"zadania_{login}.json")
    if os.path.exists(p_personal):
        all_tasks.extend(read_json(p_personal))

    # 2) centralne zadania
    p_central = os.path.join("data", "zadania.json")
    if os.path.exists(p_central):
        all_tasks.extend([z for z in read_json(p_central) if str(z.get("login")) == str(login)])

    # 3) z Narzędzi
    p_tools = os.path.join("data", "zadania_narzedzia.json")
    if os.path.exists(p_tools):
        all_tasks.extend([z for z in read_json(p_tools) if str(z.get("login")) == str(login)])

    # 4) ze Zleceń (zadania)
    p_orders_tasks = os.path.join("data", "zadania_zlecenia.json")
    if os.path.exists(p_orders_tasks):
        all_tasks.extend([z for z in read_json(p_orders_tasks) if str(z.get("login")) == str(login)])

    # 5) zlecenia_<login>.json
    p_orders_personal = os.path.join("data", f"zlecenia_{login}.json")
    if os.path.exists(p_orders_personal):
        for z in read_json(p_orders_personal):
            all_tasks.append(_convert_order_to_task(z))

    # 6) globalne zlecenia.json (tylko przypisane do login)
    p_orders_global = os.path.join("data", "zlecenia.json")
    if os.path.exists(p_orders_global):
        for z in read_json(p_orders_global):
            if _is_order_assigned_to(z, login):
                all_tasks.append(_convert_order_to_task(z))

    return all_tasks

def _is_order_assigned_to(order, login):
    for key in ("login","operator","pracownik","przydzielono","assigned_to"):
        val = order.get(key)
        if val:
            if isinstance(val, str) and val.lower()==str(login).lower():
                return True
            if isinstance(val, list) and str(login) in [str(v).lower() for v in val]:
                return True
    return False

def _convert_order_to_task(order):
    oid = order.get("nr") or order.get("id") or "?"
    title = order.get("tytul") or order.get("temat") or order.get("nazwa") or order.get("opis_short") or order.get("opis") or f"Zlecenie {oid}"
    status = order.get("status") or "Nowe"
    # mapowanie statusów
    s = status.lower()
    if s in ("nowe","new","open"): status="Nowe"
    elif s in ("w toku","in progress","realizacja"): status="W toku"
    elif s in ("pilne","urgent","overdue"): status="Pilne"
    elif s in ("zrobione","done","closed","zamkniete","finished"): status="Zrobione"
    deadline = order.get("termin") or order.get("deadline") or order.get("data_do") or order.get("data_ukonczenia_plan") or order.get("data_plan") or ""
    return {
        "id": f"ZLEC-{oid}",
        "tytul": title,
        "status": status,
        "termin": deadline,
        "opis": order.get("opis","(brak)"),
        "zlecenie": oid,
        "login": order.get("login") or order.get("operator") or order.get("pracownik") or ""
    }

# --- reszta bez zmian (jak 1.3.0/D) ---
def _save_tasks(login, tasks):
    p1 = os.path.join("data", f"zadania_{login}.json")
    try:
        with open(p1, "w", encoding="utf-8") as f: json.dump(tasks, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("[WM-DBG][PROFIL] błąd zapisu:", e)

def _open_zlecenie(root, frame, login, rola, zlec_id):
    try:
        import gui_zlecenia as mod
        fn = getattr(mod, "panel_zlecenia", None) or getattr(mod, "uruchom_panel", None)
        if fn: return fn(root, frame, login, rola)
    except Exception as e:
        messagebox.showerror("Zlecenia", f"Błąd otwierania zlecenia {zlec_id}: {e}")

def _show_task_details(root, frame, login, rola, task, all_tasks):
    win = tk.Toplevel(root); win.title(f"Zadanie {task.get('id','')} – szczegóły")
    _safe_theme(win)
    ttk.Label(win, text=f"ID: {task.get('id','')}").pack(anchor="w", padx=8, pady=2)
    ttk.Label(win, text=f"Tytuł: {task.get('tytul','')}").pack(anchor="w", padx=8, pady=2)
    ttk.Label(win, text=f"Opis: {task.get('opis','(brak)')}").pack(anchor="w", padx=8, pady=2)
    status_var = tk.StringVar(value=task.get("status",""))
    ttk.Label(win, text="Status:").pack(anchor="w", padx=8, pady=(6,0))
    cb = ttk.Combobox(win, textvariable=status_var, values=["Nowe","W toku","Pilne","Zrobione"], state="readonly"); cb.pack(anchor="w", padx=8, pady=2)
    ttk.Label(win, text=f"Termin: {task.get('termin','')}").pack(anchor="w", padx=8, pady=2)
    if task.get("zlecenie"):
        fr = ttk.Frame(win); fr.pack(fill="x", pady=4)
        ttk.Label(fr, text=f"Powiązane zlecenie nr {task['zlecenie']}").pack(side="left")
        ttk.Button(fr, text="Otwórz", command=lambda:_open_zlecenie(root, frame, login, rola, task["zlecenie"])).pack(side="left", padx=6)
    def _save_and_close():
        task["status"] = status_var.get()
        _save_tasks(login, all_tasks); win.destroy()
    ttk.Button(win, text="Zapisz", command=_save_and_close).pack(pady=6)

def _stats_from_tasks(tasks):
    total=len(tasks)
    open_cnt=sum(1 for t in tasks if str(t.get("status","")) in ("Nowe","W toku","Pilne"))
    urgent_cnt=sum(1 for t in tasks if str(t.get("status",""))=="Pilne")
    done_cnt=sum(1 for t in tasks if str(t.get("status",""))=="Zrobione")
    return total, open_cnt, urgent_cnt, done_cnt

def _build_stats(frame, tasks):
    total, open_cnt, urgent_cnt, done_cnt = _stats_from_tasks(tasks)
    bar = ttk.Frame(frame); bar.pack(fill="x", padx=12, pady=(0,8))
    for txt in [f"Zadania: {total}",f"Otwarte: {open_cnt}",f"Pilne: {urgent_cnt}",f"Zrobione: {done_cnt}"]:
        ttk.Label(bar, text=txt, relief="groove").pack(side="left", padx=4)

def _build_tasks(frame, root, login, rola, tasks):
    container = ttk.Frame(frame); container.pack(fill="both", expand=True, padx=12, pady=(0,12))
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
        s=(status or '').lower()
        if "nowe" in s: return "NOWE"
        if "toku" in s: return "WTOKU"
        if "pilne" in s: return "PILNE"
        if "zrobione" in s: return "DONE"
        return ""
    for z in tasks:
        tv.insert("", "end", values=(z.get("id",""),z.get("tytul",""),z.get("status",""),z.get("termin","")), tags=(_tag(z.get("status")),))
    def on_dbl(event):
        sel=tv.selection()
        if sel:
            idx=tv.index(sel[0]); _show_task_details(root, frame, login, rola, tasks[idx], tasks)
    tv.bind("<Double-1>", on_dbl)

def uruchom_panel(root, frame, login=None, rola=None):
    for w in frame.winfo_children():
        try: w.destroy()
        except: pass
    _safe_theme(root); _safe_theme(frame)
    head = ttk.Frame(frame); head.pack(fill="x", padx=12, pady=12)
    _load_avatar(head, login).pack(side="left", padx=8)
    info = ttk.Frame(head); info.pack(side="left", padx=12)
    ttk.Label(info, text=login or "-", font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
    ttk.Label(info, text=f"Rola: {rola or '-'}").pack(anchor="w")
    ttk.Label(info, text=f"Zmiana: {_shift_bounds_label()}").pack(anchor="w")
    tasks = _read_tasks(login)
    _build_stats(frame, tasks)
    _build_tasks(frame, root, login, rola, tasks)
    return frame

panel_profil = uruchom_panel
