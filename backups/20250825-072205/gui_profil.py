# Plik: gui_profil.py
# Wersja pliku: 1.5.2
# Data: 2025-08-24
# Patch H1 (zintegrowany): Filtry + poprawka widoczności „Przypisz do”
#  - Filtry: [Pokaż zlecenia], [Pokaż zadania z narzędzi], [Tylko przypisane do mnie], [Tylko po terminie], [Szukaj], [Odśwież].
#  - „Przypisz do (login)” widoczne dla brygadzisty, gdy:
#      * rekord ma _kind == 'order'  LUB  ID zaczyna się od 'ZLEC-'
#    oraz numer zlecenia jest brany z pola 'zlecenie' lub z ID (ZLEC-XXXX).
#  - Zmiany statusów i przypisań są trzymane w data/profil_overrides/ (bez dotykania oryginałów).
#  - Kolor OVERDUE dla zadań po terminie.
#
#  Uwagi projektowe (na chłodno):
#   • Nie zmieniamy istniejących interfejsów. Tylko rozszerzamy.
#   • Minimalny diff: tylko ten plik (gui_profil.py).

import os, json, glob
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime as _dt

try:
    from ui_theme import apply_theme
except Exception:
    def apply_theme(_): pass

# ---------- OVERRIDES STORAGE ----------
_OVR_DIR = os.path.join("data", "profil_overrides")
def _ensure_ovr_dir():
    try: os.makedirs(_OVR_DIR, exist_ok=True)
    except Exception: pass

def _status_ovr_path(login):
    return os.path.join(_OVR_DIR, f"status_{login}.json")

def _load_status_overrides(login):
    _ensure_ovr_dir()
    p = _status_ovr_path(login)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return {}
    return {}

def _save_status_override(login, task_id, status):
    _ensure_ovr_dir()
    p = _status_ovr_path(login)
    data = _load_status_overrides(login)
    data[str(task_id)] = status
    with open(p, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)

def _assign_map_path():
    return os.path.join(_OVR_DIR, "assign_orders.json")

def _load_assign_map():
    _ensure_ovr_dir()
    p = _assign_map_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return {}
    return {}

def _save_assign(order_id, login):
    _ensure_ovr_dir()
    p = _assign_map_path()
    data = _load_assign_map()
    if login:
        data[str(order_id)] = str(login)
    else:
        data.pop(str(order_id), None)
    with open(p, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)

# ---------- HELPERS ----------
def _safe_theme(widget):
    try: apply_theme(widget)
    except Exception: pass

def _shift_bounds_label():
    try:
        import gui_panel
        from datetime import datetime as _dtn
        s,e,label = gui_panel._shift_bounds(_dtn.now())
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

def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _map_status_generic(raw):
    s = (raw or "").strip().lower()
    if s in ("nowe","new","open"): return "Nowe"
    if s in ("w toku","in progress","realizacja","progress"): return "W toku"
    if s in ("pilne","urgent","overdue"): return "Pilne"
    if s in ("zrobione","done","closed","zamkniete","zamknięte","finished"): return "Zrobione"
    return "Nowe" if s=="" else raw

def _convert_order_to_task(order):
    oid = order.get("nr") or order.get("id") or "?"
    title = (order.get("tytul") or order.get("temat") or order.get("nazwa")
             or order.get("opis_short") or order.get("opis") or f"Zlecenie {oid}")
    deadline = (order.get("termin") or order.get("deadline") or order.get("data_do")
                or order.get("data_ukonczenia_plan") or order.get("data_plan") or "")
    status = _map_status_generic(order.get("status"))
    assigned = (order.get("login") or order.get("operator") or order.get("pracownik") or "")
    return {
        "id": f"ZLEC-{oid}",
        "tytul": title,
        "status": status,
        "termin": deadline,
        "opis": order.get("opis","(brak)"),
        "zlecenie": oid,
        "login": assigned,
        "_kind": "order"
    }

def _convert_tool_task(tool_num, tool_name, login, idx, item):
    status = "Zrobione" if item.get("done") else "Nowe"
    title = f"{item.get('tytul','(zadanie)')} (narz. {tool_num} – {tool_name})"
    return {
        "id": f"NARZ-{tool_num}-{idx+1}",
        "tytul": title,
        "status": status,
        "termin": "",
        "opis": item.get("opis",""),
        "zlecenie": "",
        "login": login,
        "_kind": "tooltask"
    }

def _is_order_assigned_to(order, login, rola):
    # direct in file
    for key in ("login","operator","pracownik","przydzielono","assigned_to"):
        val = order.get(key)
        if val:
            if isinstance(val, str) and val.lower()==str(login).lower():
                return True
            if isinstance(val, list) and str(login).lower() in [str(v).lower() for v in val]:
                return True
    # overrides map
    oid = order.get("nr") or order.get("id")
    if oid:
        amap = _load_assign_map()
        if str(amap.get(str(oid),"")).lower() == str(login).lower():
            return True
    # unassigned → only foreman
    if rola == "brygadzista":
        return True
    return False

def _parse_date(s):
    try:
        return _dt.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def _is_overdue(task):
    if task.get("status","").lower()=="zrobione": return False
    d = _parse_date(task.get("termin",""))
    return bool(d and d < _dt.now().date())

def _is_task_assigned_to(task, login):
    if task.get("_kind")=="order":
        if str(task.get("login","")).lower()==str(login).lower():
            return True
        amap = _load_assign_map()
        if str(amap.get(str(task.get("zlecenie")), "")).lower()==str(login).lower():
            return True
        return False
    return str(task.get("login","")).lower()==str(login).lower()

# ---------- LOADING SOURCES ----------
def _read_tasks(login, rola=None):
    all_tasks = []

    # a) zadania_<login>.json
    p_personal = os.path.join("data", f"zadania_{login}.json")
    if os.path.exists(p_personal):
        all_tasks.extend(_read_json(p_personal))

    # b) zadania.json
    p_central = os.path.join("data", "zadania.json")
    if os.path.exists(p_central):
        all_tasks.extend([z for z in _read_json(p_central) if str(z.get("login")) == str(login)])

    # c) zadania_narzedzia.json
    p_tools = os.path.join("data", "zadania_narzedzia.json")
    if os.path.exists(p_tools):
        all_tasks.extend([z for z in _read_json(p_tools) if str(z.get("login")) == str(login)])

    # d) zadania_zlecenia.json
    p_orders_tasks = os.path.join("data", "zadania_zlecenia.json")
    if os.path.exists(p_orders_tasks):
        all_tasks.extend([z for z in _read_json(p_orders_tasks) if str(z.get("login")) == str(login)])

    # e) zlecenia_<login>.json
    p_orders_personal = os.path.join("data", f"zlecenia_{login}.json")
    if os.path.exists(p_orders_personal):
        for z in _read_json(p_orders_personal):
            all_tasks.append(_convert_order_to_task(z))

    # f) zlecenia.json
    p_orders_global = os.path.join("data", "zlecenia.json")
    if os.path.exists(p_orders_global):
        for z in _read_json(p_orders_global):
            if _is_order_assigned_to(z, login, rola):
                all_tasks.append(_convert_order_to_task(z))

    # g) katalog data/narzedzia/*.json
    tools_dir = os.path.join("data", "narzedzia")
    if os.path.isdir(tools_dir):
        for path in glob.glob(os.path.join(tools_dir, "*.json")):
            tool = _read_json(path)
            if isinstance(tool, dict) and str(tool.get("pracownik","")) == str(login):
                num = tool.get("numer") or os.path.splitext(os.path.basename(path))[0]
                name = tool.get("nazwa","narzędzie")
                items = tool.get("zadania", [])
                for i, it in enumerate(items):
                    all_tasks.append(_convert_tool_task(num, name, login, i, it))

    # h) katalog data/zlecenia/*.json
    orders_dir = os.path.join("data", "zlecenia")
    if os.path.isdir(orders_dir):
        for path in glob.glob(os.path.join(orders_dir, "*.json")):
            order = _read_json(path)
            if isinstance(order, dict) and _is_order_assigned_to(order, login, rola):
                all_tasks.append(_convert_order_to_task(order))

    # --- apply status overrides ---
    ovr = _load_status_overrides(login)
    for t in all_tasks:
        ov = ovr.get(str(t.get("id")))
        if ov:
            t["status"] = ov

    return all_tasks

# ---------- UI ----------
def _open_zlecenie(root, frame, login, rola, zlec_id):
    try:
        import gui_zlecenia as mod
        fn = getattr(mod, "panel_zlecenia", None) or getattr(mod, "uruchom_panel", None)
        if fn: return fn(root, frame, login, rola)
    except Exception as e:
        messagebox.showerror("Zlecenia", f"Błąd otwierania zlecenia {zlec_id}: {e}")

def _show_task_details(root, frame, login, rola, task, all_tasks, after_save=None):
    win = tk.Toplevel(root); win.title(f"Zadanie {task.get('id','')} – szczegóły")
    try: apply_theme(win)
    except Exception: pass

    ttk.Label(win, text=f"ID: {task.get('id','')}").pack(anchor="w", padx=8, pady=2)
    ttk.Label(win, text=f"Tytuł: {task.get('tytul','')}").pack(anchor="w", padx=8, pady=2)
    ttk.Label(win, text=f"Opis: {task.get('opis','(brak)')}").pack(anchor="w", padx=8, pady=2)

    status_var = tk.StringVar(value=task.get("status",""))
    ttk.Label(win, text="Status:").pack(anchor="w", padx=8, pady=(6,0))
    cb = ttk.Combobox(win, textvariable=status_var, values=["Nowe","W toku","Pilne","Zrobione"], state="readonly")
    cb.pack(anchor="w", padx=8, pady=2)

    ttk.Label(win, text=f"Termin: {task.get('termin','')}").pack(anchor="w", padx=8, pady=2)

    # ---- H1: rozpoznanie zlecenia ----
    is_order_like = str(task.get("id","")).startswith("ZLEC-") or task.get("_kind")=="order"
    # wyciągnij numer zlecenia z ID, jeśli brak
    if is_order_like and not task.get("zlecenie"):
        tid = str(task.get("id",""))
        if tid.startswith("ZLEC-"):
            task["zlecenie"] = tid[5:]

    assign_var = tk.StringVar(value="")
    if is_order_like and rola=="brygadzista":
        frm = ttk.Frame(win); frm.pack(fill="x", padx=8, pady=6)
        ttk.Label(frm, text="Przypisz do (login):").pack(side="left")

        # prosta lista loginów z avatarów i plików *_<login>.json
        s=set()
        if os.path.isdir("avatars"):
            for p in glob.glob("avatars/*.png"):
                s.add(os.path.splitext(os.path.basename(p))[0])
        for pat in ("data/zadania_*.json","data/zlecenia_*.json"):
            for p in glob.glob(pat):
                s.add(os.path.basename(p).split("_",1)[-1].replace(".json",""))
        user_list = sorted(s)

        ent = ttk.Combobox(frm, textvariable=assign_var, values=user_list, state="normal")
        ent.pack(side="left", padx=6)

        cur = task.get("login") or _load_assign_map().get(str(task.get("zlecenie")), "") or ""
        assign_var.set(cur)

    def _save_and_close():
        # status
        _save_status_override(login, task.get("id",""), status_var.get())
        task["status"] = status_var.get()

        # przypisanie
        if is_order_like and rola=="brygadzista":
            new_owner = assign_var.get().strip()
            _save_assign(task.get("zlecenie"), new_owner if new_owner else None)

        if callable(after_save):
            after_save()
        win.destroy()

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

# ----------- FILTRY -----------
def _apply_filters(all_tasks, login, show_orders, show_tools, only_mine, only_overdue, q):
    def match_kind(t):
        if t.get("_kind")=="order" or str(t.get("id","")).startswith("ZLEC-"):
            return show_orders
        if t.get("_kind")=="tooltask":
            return show_tools
        return True
    def match_owner(t):
        return (not only_mine) or _is_task_assigned_to(t, login)
    def match_overdue(t):
        return (not only_overdue) or _is_overdue(t)
    def match_query(t):
        if not q: return True
        ql=q.lower()
        return ql in str(t.get("id","")).lower() or ql in str(t.get("tytul","")).lower()
    return [t for t in all_tasks if match_kind(t) and match_owner(t) and match_overdue(t) and match_query(t)]

def _build_tasks(frame, root, login, rola, tasks):
    # toolbar filtrów
    toolbar = ttk.Frame(frame); toolbar.pack(fill="x", padx=12, pady=(4,6))
    show_orders = tk.BooleanVar(value=True)
    show_tools  = tk.BooleanVar(value=True)
    only_mine   = tk.BooleanVar(value=False)
    only_over   = tk.BooleanVar(value=False)
    q = tk.StringVar(value="")

    ttk.Checkbutton(toolbar, text="Pokaż zlecenia", variable=show_orders).pack(side="left", padx=(0,8))
    ttk.Checkbutton(toolbar, text="Pokaż zadania z narzędzi", variable=show_tools).pack(side="left", padx=(0,8))
    ttk.Checkbutton(toolbar, text="Tylko przypisane do mnie", variable=only_mine).pack(side="left", padx=(0,8))
    ttk.Checkbutton(toolbar, text="Tylko po terminie", variable=only_over).pack(side="left", padx=(0,8))

    ttk.Label(toolbar, text="Szukaj:").pack(side="left", padx=(16,4))
    ent = ttk.Entry(toolbar, textvariable=q, width=24); ent.pack(side="left")

    # tabela
    container = ttk.Frame(frame); container.pack(fill="both", expand=True, padx=12, pady=(0,12))
    cols=("id","tytul","status","termin")
    tv = ttk.Treeview(container, columns=cols, show="headings", height=14)
    for c,w in zip(cols,(180,520,160,160)):
        tv.heading(c, text=c.capitalize()); tv.column(c, width=w, anchor="w")
    tv.pack(fill="both", expand=True)

    tv.tag_configure("NOWE", foreground="#60a5fa")
    tv.tag_configure("WTOKU", foreground="#f59e0b")
    tv.tag_configure("PILNE", foreground="#ef4444")
    tv.tag_configure("DONE", foreground="#22c55e")
    tv.tag_configure("OVERDUE", foreground="#dc2626")

    def tag_for(t):
        s=(t.get("status","") or '').lower()
        if _is_overdue(t): return "OVERDUE"
        if "nowe" in s: return "NOWE"
        if "toku" in s: return "WTOKU"
        if "pilne" in s: return "PILNE"
        if "zrobione" in s: return "DONE"
        return ""

    def reload_table(*_):
        tv.delete(*tv.get_children())
        filtered = _apply_filters(tasks, login, show_orders.get(), show_tools.get(), only_mine.get(), only_over.get(), q.get())
        for z in filtered:
            tv.insert("", "end", values=(z.get("id",""),z.get("tytul",""),z.get("status",""),z.get("termin","")), tags=(tag_for(z),))

    ttk.Button(toolbar, text="Odśwież", command=reload_table).pack(side="left", padx=8)
    ent.bind("<Return>", lambda *_: reload_table())
    for var in (show_orders, show_tools, only_mine, only_over):
        var.trace_add("write", lambda *_: reload_table())

    def on_dbl(event):
        sel=tv.selection()
        if sel:
            filtered = _apply_filters(tasks, login, show_orders.get(), show_tools.get(), only_mine.get(), only_over.get(), q.get())
            idx=tv.index(sel[0])
            if 0 <= idx < len(filtered):
                _show_task_details(root, frame, login, rola, filtered[idx], tasks, after_save=reload_table)
                reload_table()
    tv.bind("<Double-1>", on_dbl)

    reload_table()

# ---------- ENTRY POINT ----------
def uruchom_panel(root, frame, login=None, rola=None):
    for w in frame.winfo_children():
        try: w.destroy()
        except: pass
    try: apply_theme(root); apply_theme(frame)
    except Exception: pass

    head = ttk.Frame(frame); head.pack(fill="x", padx=12, pady=12)
    _load_avatar(head, login).pack(side="left", padx=8)
    info = ttk.Frame(head); info.pack(side="left", padx=12)
    ttk.Label(info, text=login or "-", font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
    ttk.Label(info, text=f"Rola: {rola or '-'}").pack(anchor="w")
    try:
        import gui_panel as _gp
        from datetime import datetime as _d2
        s,e,label = _gp._shift_bounds(_d2.now())
        ttk.Label(info, text=f"Zmiana: {label} ({s.strftime('%H:%M')}–{e.strftime('%H:%M')})").pack(anchor="w")
    except Exception:
        ttk.Label(info, text="Zmiana: I (06:00–14:00)").pack(anchor="w")

    tasks = _read_tasks(login, rola)
    _build_stats(frame, tasks)
    _build_tasks(frame, root, login, rola, tasks)
    return frame

panel_profil = uruchom_panel
