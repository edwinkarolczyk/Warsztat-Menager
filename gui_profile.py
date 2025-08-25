"""GUI moduł profilu użytkownika.

Publiczne funkcje:

* :func:`uruchom_panel` – buduje i wypełnia widok profilu w podanej ramce.
* :data:`panel_profil` – alias zachowujący zgodność wsteczną.

Widoczność danych:

* użytkownik widzi tylko swoje zlecenia/narzędzia (źródła lub override),
* brygadzista widzi wszystkie zlecenia/narzędzia.

Override'y:

* ``data/profil_overrides/assign_orders.json``  – przypisania zleceń (klucz = numer zlecenia),
* ``data/profil_overrides/assign_tools.json``   – przypisania zadań narzędzi (klucz = ``ID: NARZ-<nr>-<idx>``),
* ``data/profil_overrides/status_<login>.json`` – statusy zadań.

Danych źródłowych w ``data/*`` nie modyfikujemy.
"""

# Plik: gui_profile.py
# Wersja: 1.6.4 (H2c FULL)

import os, json, glob, re
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime as _dt

# ====== Theme ======
def _apply_theme_safe(widget):
    try:
        from ui_theme import apply_theme
        apply_theme(widget)
    except Exception:
        try:
            style = ttk.Style(widget)
            # fallback tylko lokalnie – nie zmieniamy globalnie
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

# ====== Override utils ======
_OVR_DIR = os.path.join("data","profil_overrides")
def _ensure_dir(): 
    try: os.makedirs(_OVR_DIR, exist_ok=True)
    except Exception: pass

def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path,"r",encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _save_json(path, data):
    _ensure_dir()
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2,ensure_ascii=False)

def _status_path(login):      return os.path.join(_OVR_DIR,f"status_{login}.json")
def _assign_orders_path():    return os.path.join(_OVR_DIR,"assign_orders.json")
def _assign_tools_path():     return os.path.join(_OVR_DIR,"assign_tools.json")

def _load_status_overrides(login): return _load_json(_status_path(login), {})
def _save_status_override(login, task_id, status):
    data = _load_status_overrides(login)
    data[str(task_id)] = status
    _save_json(_status_path(login), data)

def _load_assign_orders(): return _load_json(_assign_orders_path(), {})
def _save_assign_order(order_no, login):
    data = _load_assign_orders()
    if login:
        data[str(order_no)] = str(login)
    else:
        data.pop(str(order_no), None)
    _save_json(_assign_orders_path(), data)

def _load_assign_tools(): return _load_json(_assign_tools_path(), {})
def _save_assign_tool(task_id, login):
    data = _load_assign_tools()
    if login:
        data[str(task_id)] = str(login)
    else:
        data.pop(str(task_id), None)
    _save_json(_assign_tools_path(), data)

# ====== Helpers ======
def _valid_login(s): return bool(re.match(r'^[A-Za-z0-9_.-]{2,32}$', str(s)))

def _login_list():
    """Zbiera loginy: users.json > avatars > *_<login>.json; filtruje śmieci."""
    s=set()
    ufile=os.path.join("data","users.json")
    if os.path.exists(ufile):
        try:
            data=json.load(open(ufile,encoding="utf-8"))
            if isinstance(data,list):
                for it in data:
                    if isinstance(it,str) and _valid_login(it): s.add(it)
                    elif isinstance(it,dict) and _valid_login(it.get("login","")): s.add(it["login"])
        except Exception: pass
    if os.path.isdir("avatars"):
        for p in glob.glob("avatars/*.png"):
            nm=os.path.splitext(os.path.basename(p))[0]
            if _valid_login(nm): s.add(nm)
    for pat in ("data/zadania_*.json","data/zlecenia_*.json"):
        for p in glob.glob(pat):
            nm=os.path.basename(p).split("_",1)[-1].replace(".json","")
            if _valid_login(nm): s.add(nm)
    return sorted(s)

def _map_status_generic(raw):
    s=(raw or "").strip().lower()
    if s in ("","new","open"): return "Nowe"
    if s in ("w toku","in progress","realizacja","progress"): return "W toku"
    if s in ("pilne","urgent","overdue"): return "Pilne"
    if s in ("zrobione","done","zamkniete","zamknięte","finished","close","closed"): return "Zrobione"
    return raw or "Nowe"

def _parse_date(s):
    try: return _dt.strptime(s,"%Y-%m-%d").date()
    except Exception: return None

def _is_overdue(task):
    if str(task.get("status","")).lower()=="zrobione": return False
    d=_parse_date(task.get("termin",""))
    return bool(d and d<_dt.now().date())

# ====== Converters ======
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

def _convert_tool_task(tool_num, tool_name, worker_login, idx, item):
    status = "Zrobione" if item.get("done") else _map_status_generic(item.get("status") or "Nowe")
    title = f"{item.get('tytul','(zadanie)')} (narz. {tool_num} – {tool_name})"
    return {
        "id": f"NARZ-{tool_num}-{idx+1}",
        "tytul": title,
        "status": status,
        "termin": item.get("termin",""),
        "opis": item.get("opis",""),
        "zlecenie": "",
        "login": worker_login,   # z pliku narzędzia
        "_kind": "tooltask"
    }

# ====== Widoczność ======
def _order_visible_for(order, login, rola):
    if rola=="brygadzista": return True
    # przypisanie bezpośrednie
    for key in ("login","operator","pracownik","przydzielono","assigned_to"):
        val = order.get(key)
        if isinstance(val,str)  and val.lower()==str(login).lower(): return True
        if isinstance(val,list) and str(login).lower() in [str(v).lower() for v in val]: return True
    # override
    oid = order.get("nr") or order.get("id")
    if oid and str(_load_assign_orders().get(str(oid),"")).lower()==str(login).lower(): return True
    return False

def _tool_visible_for(tool_task, login, rola):
    if rola=="brygadzista": return True
    if str(tool_task.get("login","")).lower()==str(login).lower(): return True
    if str(_load_assign_tools().get(tool_task["id"],"")).lower()==str(login).lower(): return True
    return False

# ====== Czytanie zadań ======
def _read_tasks(login, rola=None):
    tasks = []

    # a) zadania_<login>.json
    p = os.path.join("data", f"zadania_{login}.json")
    if os.path.exists(p):
        try: tasks.extend(_load_json(p, []))
        except Exception: pass

    # b) zadania.json
    p = os.path.join("data", "zadania.json")
    if os.path.exists(p):
        try:
            zlist = _load_json(p, [])
            tasks.extend([z for z in zlist if str(z.get("login"))==str(login)])
        except Exception: pass

    # c) zadania_narzedzia.json
    p = os.path.join("data", "zadania_narzedzia.json")
    if os.path.exists(p):
        try:
            zlist = _load_json(p, [])
            tasks.extend([z for z in zlist if str(z.get("login"))==str(login)])
        except Exception: pass

    # d) zadania_zlecenia.json
    p = os.path.join("data", "zadania_zlecenia.json")
    if os.path.exists(p):
        try:
            zlist = _load_json(p, [])
            tasks.extend([z for z in zlist if str(z.get("login"))==str(login)])
        except Exception: pass

    # e) zlecenia_<login>.json
    p = os.path.join("data", f"zlecenia_{login}.json")
    if os.path.exists(p):
        try:
            for z in _load_json(p, []):
                tasks.append(_convert_order_to_task(z))
        except Exception: pass

    # f) zlecenia.json (globalne)
    p = os.path.join("data", "zlecenia.json")
    if os.path.exists(p):
        try:
            for z in _load_json(p, []):
                if _order_visible_for(z, login, rola):
                    tasks.append(_convert_order_to_task(z))
        except Exception: pass

    # g) katalog data/zlecenia/*.json
    orders_dir = os.path.join("data", "zlecenia")
    if os.path.isdir(orders_dir):
        for path in glob.glob(os.path.join(orders_dir, "*.json")):
            z = _load_json(path, {})
            if isinstance(z, dict) and _order_visible_for(z, login, rola):
                tasks.append(_convert_order_to_task(z))

    # h) katalog data/narzedzia/*.json – generuj zadania per narzędzie
    tools_dir = os.path.join("data", "narzedzia")
    if os.path.isdir(tools_dir):
        for path in glob.glob(os.path.join(tools_dir, "*.json")):
            tool = _load_json(path, {})
            if not isinstance(tool, dict): 
                continue
            num  = tool.get("numer") or os.path.splitext(os.path.basename(path))[0]
            name = tool.get("nazwa","narzędzie")
            worker = tool.get("pracownik","")
            items = tool.get("zadania", [])
            for i, it in enumerate(items):
                t = _convert_tool_task(num, name, worker, i, it)
                if _tool_visible_for(t, login, rola):
                    tasks.append(t)

    # i) status overrides
    ovr = _load_status_overrides(login)
    for t in tasks:
        ov = ovr.get(str(t.get("id")))
        if ov: t["status"]=ov

    return tasks

# ====== UI ======
def _show_task_details(root, frame, login, rola, task, after_save=None):
    win = tk.Toplevel(root)
    win.title(f"Zadanie {task.get('id','')}")
    _apply_theme_safe(win)

    # Nagłówki
    ttk.Label(win, text=f"ID: {task.get('id','')}").pack(anchor="w", padx=8, pady=(8,2))
    ttk.Label(win, text=f"Tytuł: {task.get('tytul','')}").pack(anchor="w", padx=8, pady=2)

    # Opis
    frm_opis = ttk.Frame(win); frm_opis.pack(fill="x", padx=8, pady=2)
    ttk.Label(frm_opis, text="Opis:").pack(side="left")
    txt = tk.Text(frm_opis, height=4, width=60)
    txt.pack(side="left", fill="x", expand=True)
    txt.insert("1.0", task.get("opis",""))

    # Status
    status_var = tk.StringVar(value=task.get("status","Nowe"))
    ttk.Label(win, text="Status:").pack(anchor="w", padx=8, pady=(6,0))
    cb = ttk.Combobox(win, textvariable=status_var, values=["Nowe","W toku","Pilne","Zrobione"], state="readonly")
    cb.pack(anchor="w", padx=8, pady=2)

    ttk.Label(win, text=f"Termin: {task.get('termin','')}").pack(anchor="w", padx=8, pady=(2,8))

    # Przypisz do
    is_order = str(task.get("id","")).startswith("ZLEC-") or task.get("_kind")=="order"
    is_tool  = str(task.get("id","")).startswith("NARZ-") or task.get("_kind")=="tooltask"
    assign_var = tk.StringVar(value="")
    if rola=="brygadzista" and (is_order or is_tool):
        frm = ttk.Frame(win); frm.pack(fill="x", padx=8, pady=6)
        ttk.Label(frm, text="Przypisz do (login):").pack(side="left")
        ent = ttk.Combobox(frm, textvariable=assign_var, values=_login_list(), state="normal", width=24)
        ent.pack(side="left", padx=6)
        if is_order:
            if not task.get("zlecenie"):
                tid=str(task.get("id",""))
                if tid.startswith("ZLEC-"): task["zlecenie"]=tid[5:]
            cur = task.get("login") or _load_assign_orders().get(str(task.get("zlecenie")),"")
            assign_var.set(cur)
        if is_tool:
            cur = _load_assign_tools().get(task.get("id"),"")
            assign_var.set(cur)

    def _save():
        # status override
        new_status = status_var.get()
        _save_status_override(login, task.get("id",""), new_status)
        task["status"] = new_status

        # przypisania
        if rola=="brygadzista":
            who = assign_var.get().strip() or None
            if is_order:
                _save_assign_order(task.get("zlecenie"), who)
            if is_tool:
                _save_assign_tool(task.get("id"), who)

        if callable(after_save): after_save()
        win.destroy()

    ttk.Button(win, text="Zapisz", command=_save).pack(pady=(8,10))

def _build_table(frame, root, login, rola, tasks):
    # Toolbar
    bar = ttk.Frame(frame); bar.pack(fill="x", padx=12, pady=(8,6))
    show_orders = tk.BooleanVar(value=True)
    show_tools  = tk.BooleanVar(value=True)
    only_mine   = tk.BooleanVar(value=False)   # dla brygadzisty filtruje do jego zadań
    only_over   = tk.BooleanVar(value=False)
    q = tk.StringVar(value="")

    ttk.Checkbutton(bar,text="Pokaż zlecenia",variable=show_orders).pack(side="left")
    ttk.Checkbutton(bar,text="Pokaż zadania z narzędzi",variable=show_tools).pack(side="left", padx=(8,0))
    ttk.Checkbutton(bar,text="Tylko przypisane do mnie",variable=only_mine).pack(side="left", padx=(8,0))
    ttk.Checkbutton(bar,text="Tylko po terminie",variable=only_over).pack(side="left", padx=(8,0))
    ttk.Label(bar,text="Szukaj:").pack(side="left", padx=(12,4))
    ent = ttk.Entry(bar,textvariable=q,width=28); ent.pack(side="left")
    btn = ttk.Button(bar,text="Odśwież"); btn.pack(side="left", padx=8)

    # Tabela
    container = ttk.Frame(frame); container.pack(fill="both",expand=True, padx=12, pady=(0,12))
    cols = ("id","tytul","status","termin")
    tv = ttk.Treeview(container, columns=cols, show="headings", height=18)
    for c,w in zip(cols,(180,600,160,160)):
        tv.heading(c, text=c.capitalize())
        tv.column(c, width=w, anchor="w")
    tv.pack(fill="both", expand=True)

    # Kolorowanie
    tv.tag_configure("OVERDUE", foreground="#dc2626")  # czerwony
    tv.tag_configure("NOWE",    foreground="#60a5fa")  # niebieski
    tv.tag_configure("WTOKU",   foreground="#f59e0b")  # pomarańczowy
    tv.tag_configure("PILNE",   foreground="#ef4444")  # czerwony 2
    tv.tag_configure("DONE",    foreground="#22c55e")  # zielony

    def tag_for(t):
        s=(t.get("status","") or "").lower()
        if _is_overdue(t): return "OVERDUE"
        if "nowe" in s: return "NOWE"
        if "toku" in s: return "WTOKU"
        if "pilne" in s: return "PILNE"
        if "zrobione" in s: return "DONE"
        return ""

    def _assigned_to_login(t):
        """Zwraca login do którego zadanie jest przypisane (z danych lub override)."""
        is_order = t.get("_kind")=="order" or str(t.get("id","")).startswith("ZLEC-")
        is_tool  = t.get("_kind")=="tooltask" or str(t.get("id","")).startswith("NARZ-")
        if is_order:
            if t.get("login"): return t.get("login")
            return _load_assign_orders().get(str(t.get("zlecenie")))
        if is_tool:
            if t.get("login"): return t.get("login")
            return _load_assign_tools().get(t.get("id"))
        return t.get("login")

    def filtered():
        arr=[]
        for t in tasks:
            is_order = t.get("_kind")=="order" or str(t.get("id","")).startswith("ZLEC-")
            is_tool  = t.get("_kind")=="tooltask" or str(t.get("id","")).startswith("NARZ-")
            if is_order and not show_orders.get(): continue
            if is_tool  and not show_tools.get():  continue
            if only_mine.get():
                ass = (_assigned_to_login(t) or "").lower()
                if ass != str(login).lower():
                    continue
            if only_over.get() and not _is_overdue(t): continue
            qq = q.get().lower().strip()
            if qq and (qq not in str(t.get("id","")).lower() and qq not in str(t.get("tytul","")).lower()): 
                continue
            arr.append(t)
        return arr

    def reload_table(*_):
        tv.delete(*tv.get_children())
        for z in filtered():
            tv.insert("", "end", values=(z.get("id",""),z.get("tytul",""),z.get("status",""),z.get("termin","")), tags=(tag_for(z),))

    btn.configure(command=reload_table)
    ent.bind("<Return>", lambda *_: reload_table())
    for var in (show_orders, show_tools, only_mine, only_over):
        var.trace_add("write", lambda *_: reload_table())

    def on_dbl(_ev):
        sel=tv.selection()
        if not sel: return
        idx=tv.index(sel[0])
        arr=filtered()
        if 0<=idx<len(arr):
            _show_task_details(root, frame, login, rola, arr[idx], reload_table)

    tv.bind("<Double-1>", on_dbl)
    reload_table()

def uruchom_panel(root, frame, login=None, rola=None):
    """Wypełnia podaną *frame* widokiem profilu użytkownika.

    Parameters
    ----------
    root : tk.Widget
        Główny obiekt aplikacji (potrzebny do okien modalnych).
    frame : ttk.Frame
        Kontener, który zostanie wyczyszczony i zapełniony widokiem.
    login : str, optional
        Login użytkownika, którego profil ma zostać pokazany.
    rola : str, optional
        Rola użytkownika – wpływa na zakres widocznych danych.

    Returns
    -------
    ttk.Frame
        Ta sama ramka *frame* z dobudowanymi widżetami.
    """

    # wyczyść
    for w in list(frame.winfo_children()):
        try: w.destroy()
        except: pass

    _apply_theme_safe(root)
    _apply_theme_safe(frame)

    # Nagłówek
    head = ttk.Frame(frame); head.pack(fill="x", padx=12, pady=10)
    ttk.Label(head, text=str(login or "-"), font=("TkDefaultFont", 14, "bold")).pack(side="left", padx=(0,12))
    ttk.Label(head, text=f"Rola: {rola or '-'}").pack(side="left")

    # Dane
    tasks = _read_tasks(login, rola)

    # Pasek statystyk
    stats = ttk.Frame(frame); stats.pack(fill="x", padx=12, pady=(0,6))
    total = len(tasks)
    open_cnt = sum(1 for t in tasks if t.get("status") in ("Nowe","W toku","Pilne"))
    urgent = sum(1 for t in tasks if t.get("status")=="Pilne")
    done   = sum(1 for t in tasks if t.get("status")=="Zrobione")
    for txt in (f"Zadania: {total}", f"Otwarte: {open_cnt}", f"Pilne: {urgent}", f"Zrobione: {done}"):
        ttk.Label(stats, text=txt, relief="groove").pack(side="left", padx=4)

    # Tabela + filtry
    _build_table(frame, root, login, rola, tasks)
    return frame

# API zgodne z wcześniejszymi wersjami:
panel_profil = uruchom_panel
