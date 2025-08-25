
# gui_profil.py — v1.6.4 (H2c + user files + theme safe)
# Minimalny patch zgodnie z ustaleniami:
# 1) Zasada widoczności: uzytkownik widzi tylko swoje; brygadzista widzi wszystko
# 2) „Przypisz do” także dla NARZ-…
# 3) Statusy i przypisania w data/profil_overrides/*
# 4) NOWE: auto-plik profilu użytkownika w data/user/<login>.json (tworzy się przy wejściu)
# 5) NOWE: bezpieczne ładowanie motywu (apply_theme jeśli jest; fallback na 'clam')

import os, json, glob, re
import tkinter as tk
from tkinter import ttk
from datetime import datetime as _dt

# --- Theme (bez zmian w istniejącym ui_theme; tylko bezpieczne użycie) ---
try:
    from ui_theme import apply_theme as _apply_theme_external
except Exception:
    _apply_theme_external = None

def _apply_theme_safe(widget):
    """Spróbuj załadować motyw z ui_theme, a jak się nie uda, włącz 'clam'."""
    try:
        if _apply_theme_external:
            _apply_theme_external(widget)
        else:
            raise RuntimeError("no external theme")
    except Exception:
        try:
            style = ttk.Style(widget)
            # jeśli nic nie ustawione, przełącz na 'clam' (stabilna wbudowana)
            cur = style.theme_use()
            if not cur:
                style.theme_use('clam')
        except Exception:
            pass

# --- Ścieżki override ---
_OVR_DIR = os.path.join("data","profil_overrides")
def _ensure_dir(): 
    try: os.makedirs(_OVR_DIR, exist_ok=True)
    except Exception: pass

def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path,"r",encoding="utf-8") as f: return json.load(f)
    except Exception:
        pass
    return default

def _save_json(path, data):
    _ensure_dir()
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2,ensure_ascii=False)

def _p_status(login):   return os.path.join(_OVR_DIR,f"status_{login}.json")
def _p_ass_orders():    return os.path.join(_OVR_DIR,"assign_orders.json")
def _p_ass_tools():     return os.path.join(_OVR_DIR,"assign_tools.json")

def _status_get(login): return _load_json(_p_status(login),{})
def _status_set(login, task_id, status):
    d=_status_get(login); d[str(task_id)]=status; _save_json(_p_status(login),d)

def _ass_orders():      return _load_json(_p_ass_orders(),{})
def _ass_tools():       return _load_json(_p_ass_tools(),{})

# --- Pliki użytkownika: data/user/<login>.json ---
_USER_DIR = os.path.join("data","user")
def _user_path(login):  return os.path.join(_USER_DIR, f"{login}.json")

def _ensure_user_file(login, rola=None):
    os.makedirs(_USER_DIR, exist_ok=True)
    p = _user_path(login)
    if not os.path.exists(p):
        # domyślki – bez dotykania danych biznesowych
        data = {
            "login": login,
            "rola": rola or "",
            "stanowisko": "",
            "dzial": "",
            "zmiana": "I",
            "zmiana_godz": "06:00-14:00",
            "telefon": "",
            "email": "",
            "avatar": "",      # nazwa pliku w avatars/ (opcjonalnie)
            "odpowiedzialnosci": []  # np. ["magazyn", "narzedzia"]
        }
        with open(p,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)
    # zwróć zawartość
    try:
        return json.load(open(p,encoding="utf-8"))
    except Exception:
        return {"login": login, "rola": rola or ""}

# --- Pomocnicze ---
def _valid_login(s): return bool(re.match(r'^[A-Za-z0-9_.-]{2,32}$', str(s)))

def _login_list():
    s=set()
    p_users=os.path.join("data","users.json")
    if os.path.exists(p_users):
        try:
            arr=json.load(open(p_users,encoding="utf-8"))
            if isinstance(arr,list):
                for el in arr:
                    if isinstance(el,str) and _valid_login(el): s.add(el)
                    elif isinstance(el,dict) and _valid_login(el.get("login","")): s.add(el["login"])
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

def _map_status(s):
    s=(s or "").strip().lower()
    if s in ("","new","open"): return "Nowe"
    if s in ("w toku","in progress","realizacja","progress"): return "W toku"
    if s in ("pilne","urgent","overdue"): return "Pilne"
    if s in ("zrobione","done","finished","closed","zamknięte","zamkniete"): return "Zrobione"
    return s.capitalize()

def _parse_date(s):
    try: return _dt.strptime(s,"%Y-%m-%d").date()
    except Exception: return None

def _overdue(t):
    if str(t.get("status","")).lower()=="zrobione": return False
    d=_parse_date(t.get("termin","")); return bool(d and d<_dt.now().date())

# --- Konwersje ---
def _order_to_task(z):
    oid = z.get("nr") or z.get("id") or "?"
    title = z.get("tytul") or z.get("temat") or z.get("nazwa") or z.get("opis_short") or z.get("opis") or f"Zlecenie {oid}"
    deadline = z.get("termin") or z.get("deadline") or z.get("data_do") or z.get("data_ukonczenia_plan") or z.get("data_plan") or ""
    status = _map_status(z.get("status"))
    assigned = z.get("login") or z.get("operator") or z.get("pracownik") or ""
    return {"id":f"ZLEC-{oid}","tytul":title,"status":status,"termin":deadline,"opis":z.get("opis","(brak)"),"zlecenie":oid,"login":assigned,"_kind":"order"}

def _tool_to_task(num,name,worker,idx,item):
    status = "Zrobione" if item.get("done") else _map_status(item.get("status") or "Nowe")
    return {"id":f"NARZ-{num}-{idx+1}","tytul":f"{item.get('tytul','(zadanie)')} (narz. {num} – {name})",
            "status":status,"termin":item.get("termin",""),"opis":item.get("opis",""),
            "zlecenie":"","login":worker,"_kind":"tooltask"}

# --- Widoczność ---
def _order_visible_for(z, login, rola):
    if rola=="brygadzista": return True
    for key in ("login","operator","pracownik","przydzielono","assigned_to"):
        v=z.get(key)
        if isinstance(v,str) and v.lower()==str(login).lower(): return True
        if isinstance(v,list) and str(login).lower() in [str(x).lower() for x in v]: return True
    oid=z.get("nr") or z.get("id")
    if oid and str(_ass_orders().get(str(oid),"")).lower()==str(login).lower(): return True
    return False

def _tool_visible_for(task_obj, login, rola):
    if rola=="brygadzista": return True
    if str(task_obj.get("login","")).lower()==str(login).lower(): return True
    if str(_ass_tools().get(task_obj["id"],"")).lower()==str(login).lower(): return True
    return False

# --- Odczyt zadań ---
def _read_tasks(login, rola=None):
    tasks=[]

    # lokalne zbiory zadań
    for p in (
        os.path.join("data", f"zadania_{login}.json"),
        os.path.join("data", "zadania.json"),
        os.path.join("data", "zadania_narzedzia.json"),
        os.path.join("data", "zadania_zlecenia.json"),
    ):
        if os.path.exists(p):
            try:
                arr=_load_json(p,[])
                if p.endswith("zadania.json") or "zadania_" in os.path.basename(p):
                    tasks.extend([z for z in arr if str(z.get("login"))==str(login)])
                else:
                    tasks.extend([z for z in arr if str(z.get("login"))==str(login)])
            except Exception:
                pass

    # zlecenia_<login>.json
    p=os.path.join("data",f"zlecenia_{login}.json")
    if os.path.exists(p):
        for z in _load_json(p,[]): tasks.append(_order_to_task(z))

    # zlecenia.json
    p=os.path.join("data","zlecenia.json")
    if os.path.exists(p):
        for z in _load_json(p,[]):
            if _order_visible_for(z,login,rola):
                tasks.append(_order_to_task(z))

    # katalog zlecenia/*.json
    orders_dir=os.path.join("data","zlecenia")
    if os.path.isdir(orders_dir):
        for path in glob.glob(os.path.join(orders_dir,"*.json")):
            z=_load_json(path,{})
            if isinstance(z,dict) and _order_visible_for(z,login,rola):
                tasks.append(_order_to_task(z))

    # narzedzia/*.json
    tools_dir=os.path.join("data","narzedzia")
    if os.path.isdir(tools_dir):
        for path in glob.glob(os.path.join(tools_dir,"*.json")):
            tool=_load_json(path,{})
            if not isinstance(tool,dict): continue
            num  = tool.get("numer") or os.path.splitext(os.path.basename(path))[0]
            name = tool.get("nazwa","narzędzie")
            worker = tool.get("pracownik","")
            items = tool.get("zadania",[])
            for i,it in enumerate(items):
                t=_tool_to_task(num,name,worker,i,it)
                if _tool_visible_for(t,login,rola):
                    tasks.append(t)

    # status overrides
    ovr=_status_get(login)
    for t in tasks:
        ov=ovr.get(str(t.get("id")))
        if ov: t["status"]=ov
    return tasks

# --- UI: szczegóły zadania ---
def _show_details(root, frame, login, rola, task, after_save=None):
    win=tk.Toplevel(root); win.title(f"Zadanie {task.get('id','')}")
    _apply_theme_safe(win)

    ttk.Label(win,text=f"ID: {task.get('id','')}").pack(anchor="w", padx=8, pady=(8,2))
    ttk.Label(win,text=f"Tytuł: {task.get('tytul','')}").pack(anchor="w", padx=8, pady=2)

    frm=ttk.Frame(win); frm.pack(fill="x", padx=8, pady=2)
    ttk.Label(frm,text="Opis:").pack(side="left")
    txt=tk.Text(frm,height=4,width=60); txt.pack(side="left",fill="x",expand=True)
    txt.insert("1.0", task.get("opis",""))

    status=tk.StringVar(value=task.get("status","Nowe"))
    ttk.Label(win,text="Status:").pack(anchor="w", padx=8, pady=(6,0))
    ttk.Combobox(win,textvariable=status,values=["Nowe","W toku","Pilne","Zrobione"],state="readonly").pack(anchor="w", padx=8, pady=2)

    ttk.Label(win,text=f"Termin: {task.get('termin','')}").pack(anchor="w", padx=8, pady=(2,8))

    is_order = str(task.get("id","")).startswith("ZLEC-") or task.get("_kind")=="order"
    is_tool  = str(task.get("id","")).startswith("NARZ-") or task.get("_kind")=="tooltask"

    assign=tk.StringVar(value="")
    if rola=="brygadzista" and (is_order or is_tool):
        f2=ttk.Frame(win); f2.pack(fill="x", padx=8, pady=6)
        ttk.Label(f2,text="Przypisz do (login):").pack(side="left")
        ttk.Combobox(f2,textvariable=assign,values=_login_list(),state="normal",width=24).pack(side="left", padx=6)
        if is_order:
            if not task.get("zlecenie"):
                tid=str(task.get("id",""))
                if tid.startswith("ZLEC-"): task["zlecenie"]=tid[5:]
            cur = task.get("login") or _ass_orders().get(str(task.get("zlecenie")),"")
            assign.set(cur)
        if is_tool:
            assign.set(_ass_tools().get(task.get("id"),""))

    def _save():
        _status_set(login, task.get("id",""), status.get())
        task["status"]=status.get()
        if rola=="brygadzista":
            who=assign.get().strip() or None
            if is_order:
                d=_ass_orders()
                if who: d[str(task.get("zlecenie"))]=who
                else: d.pop(str(task.get("zlecenie")),None)
                _save_json(_p_ass_orders(),d)
            if is_tool:
                d=_ass_tools()
                if who: d[task.get("id")]=who
                else: d.pop(task.get("id"),None)
                _save_json(_p_ass_tools(),d)
        if callable(after_save): after_save()
        win.destroy()

    ttk.Button(win,text="Zapisz",command=_save).pack(pady=(8,10))

# --- UI: tabela + filtry ---
def _build_table(frame, root, login, rola, tasks):
    bar=ttk.Frame(frame); bar.pack(fill="x", padx=12, pady=(8,6))
    show_orders=tk.BooleanVar(value=True)
    show_tools=tk.BooleanVar(value=True)
    only_mine=tk.BooleanVar(value=False)
    only_over=tk.BooleanVar(value=False)
    q=tk.StringVar(value="")

    ttk.Checkbutton(bar,text="Pokaż zlecenia",variable=show_orders).pack(side="left")
    ttk.Checkbutton(bar,text="Pokaż zadania z narzędzi",variable=show_tools).pack(side="left", padx=(8,0))
    ttk.Checkbutton(bar,text="Tylko przypisane do mnie",variable=only_mine).pack(side="left", padx=(8,0))
    ttk.Checkbutton(bar,text="Tylko po terminie",variable=only_over).pack(side="left", padx=(8,0))
    ttk.Label(bar,text="Szukaj:").pack(side="left", padx=(12,4))
    ent=ttk.Entry(bar,textvariable=q,width=28); ent.pack(side="left")
    ttk.Button(bar,text="Odśwież",command=lambda: reload_table()).pack(side="left", padx=8)

    container=ttk.Frame(frame); container.pack(fill="both",expand=True, padx=12, pady=(0,12))
    cols=("id","tytul","status","termin")
    tv=ttk.Treeview(container,columns=cols,show="headings",height=18)
    for c,w in zip(cols,(180,600,160,160)):
        tv.heading(c,text=c.capitalize()); tv.column(c,width=w,anchor="w")
    tv.pack(fill="both",expand=True)

    tv.tag_configure("OVERDUE", foreground="#dc2626")
    tv.tag_configure("NOWE", foreground="#60a5fa")
    tv.tag_configure("WTOKU", foreground="#f59e0b")
    tv.tag_configure("PILNE", foreground="#ef4444")
    tv.tag_configure("DONE", foreground="#22c55e")

    def tag_for(t):
        s=(t.get("status","") or "").lower()
        if _overdue(t): return "OVERDUE"
        if "nowe" in s: return "NOWE"
        if "toku" in s: return "WTOKU"
        if "pilne" in s: return "PILNE"
        if "zrobione" in s: return "DONE"
        return ""

    def _assigned_login(t):
        is_order = t.get("_kind")=="order" or str(t.get("id","")).startswith("ZLEC-")
        is_tool  = t.get("_kind")=="tooltask" or str(t.get("id","")).startswith("NARZ-")
        if is_order:
            return t.get("login") or _ass_orders().get(str(t.get("zlecenie")))
        if is_tool:
            return t.get("login") or _ass_tools().get(t.get("id"))
        return t.get("login")

    def filtered():
        out=[]
        for t in tasks:
            is_order = t.get("_kind")=="order" or str(t.get("id","")).startswith("ZLEC-")
            is_tool  = t.get("_kind")=="tooltask" or str(t.get("id","")).startswith("NARZ-")
            if is_order and not show_orders.get(): continue
            if is_tool and not show_tools.get(): continue
            if only_mine.get():
                if str(_assigned_login(t) or "").lower()!=str(login).lower(): continue
            if only_over.get() and not _overdue(t): continue
            qq=q.get().lower().strip()
            if qq and (qq not in str(t.get("id","")).lower() and qq not in str(t.get("tytul","")).lower()): continue
            out.append(t)
        return out

    def reload_table():
        tv.delete(*tv.get_children())
        for z in filtered():
            tv.insert("", "end", values=(z.get("id",""),z.get("tytul",""),z.get("status",""),z.get("termin","")), tags=(tag_for(z),))

    def on_dbl(_ev):
        sel=tv.selection()
        if not sel: return
        idx=tv.index(sel[0]); arr=filtered()
        if 0<=idx<len(arr): _show_details(root, frame, login, rola, arr[idx], reload_table)

    tv.bind("<Double-1>", on_dbl)
    ent.bind("<Return>", lambda *_: reload_table())
    for var in (show_orders,show_tools,only_mine,only_over):
        var.trace_add("write", lambda *_: reload_table())
    reload_table()

# --- Wejście panelu ---
def uruchom_panel(root, frame, login=None, rola=None):
    # wyczyść kontener
    for w in list(frame.winfo_children()):
        try: w.destroy()
        except: pass

    _apply_theme_safe(root); _apply_theme_safe(frame)

    # utwórz/załaduj plik usera
    user_data = _ensure_user_file(login or "user", rola)

    head=ttk.Frame(frame); head.pack(fill="x", padx=12, pady=10)
    ttk.Label(head,text=str(login or "-"), font=("TkDefaultFont",14,"bold")).pack(side="left", padx=(0,12))
    ttk.Label(head,text=f"Rola: {rola or user_data.get('rola','-')}").pack(side="left")

    tasks=_read_tasks(login, rola)

    # proste statystyki
    stats=ttk.Frame(frame); stats.pack(fill="x", padx=12, pady=(0,6))
    total=len(tasks); open_cnt=sum(1 for t in tasks if t.get("status") in ("Nowe","W toku","Pilne"))
    urgent=sum(1 for t in tasks if t.get("status")=="Pilne"); done=sum(1 for t in tasks if t.get("status")=="Zrobione")
    for txt in (f"Zadania: {total}", f"Otwarte: {open_cnt}", f"Pilne: {urgent}", f"Zrobione: {done}"):
        ttk.Label(stats,text=txt,relief="groove").pack(side="left", padx=4)

    _build_table(frame, root, login, rola, tasks)
    return frame

panel_profil = uruchom_panel
