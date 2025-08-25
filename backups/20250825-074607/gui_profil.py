# Plik: gui_profil.py
# Wersja pliku: 1.6.3
# Patch H2c — zasady widoczności:
# - uzytkownik: widzi tylko swoje zlecenia/narzędzia
# - brygadzista: widzi wszystko
# Dane override:
# - assign_orders.json, assign_tools.json, status_<login>.json

import os, json, glob, re
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime as _dt

try:
    from ui_theme import apply_theme
except Exception:
    def apply_theme(_): pass

# === OVERRIDES ===
_OVR_DIR = os.path.join("data","profil_overrides")
def _ensure(): os.makedirs(_OVR_DIR, exist_ok=True)

def _load(path, default):
    try:
        if os.path.exists(path):
            with open(path,"r",encoding="utf-8") as f: return json.load(f)
    except Exception: pass
    return default

def _save(path, data):
    _ensure()
    with open(path,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)

def _p_status(login): return os.path.join(_OVR_DIR,f"status_{login}.json")
def _p_ass_orders(): return os.path.join(_OVR_DIR,"assign_orders.json")
def _p_ass_tools():  return os.path.join(_OVR_DIR,"assign_tools.json")

def _status_get(login): return _load(_p_status(login),{})
def _status_set(login, task_id, status):
    d=_status_get(login); d[str(task_id)]=status; _save(_p_status(login),d)

def _ass_orders(): return _load(_p_ass_orders(),{})
def _ass_tools():  return _load(_p_ass_tools(),{})

# === HELPERS ===
def _ok_login(s): return bool(re.match(r'^[A-Za-z0-9_.-]{2,32}$', str(s)))

def _login_list():
    s=set()
    ufile=os.path.join("data","users.json")
    if os.path.exists(ufile):
        try:
            arr=json.load(open(ufile,encoding="utf-8"))
            if isinstance(arr,list):
                for el in arr:
                    if isinstance(el,str) and _ok_login(el): s.add(el)
                    elif isinstance(el,dict) and _ok_login(el.get("login","")): s.add(el["login"])
        except Exception: pass
    if os.path.isdir("avatars"):
        for p in glob.glob("avatars/*.png"):
            nm=os.path.splitext(os.path.basename(p))[0]
            if _ok_login(nm): s.add(nm)
    for pat in ("data/zadania_*.json","data/zlecenia_*.json"):
        for p in glob.glob(pat):
            nm=os.path.basename(p).split("_",1)[-1].replace(".json","")
            if _ok_login(nm): s.add(nm)
    return sorted(s)

def _map_status(s):
    s=(s or "").strip().lower()
    return {"":"Nowe","new":"Nowe","open":"Nowe","w toku":"W toku","in progress":"W toku",
            "pilne":"Pilne","urgent":"Pilne","zrobione":"Zrobione","done":"Zrobione"}.get(s, s.capitalize() if s else "Nowe")

def _parse_date(s):
    try: return _dt.strptime(s,"%Y-%m-%d").date()
    except Exception: return None

def _overdue(t):
    if str(t.get("status","")).lower()=="zrobione": return False
    d=_parse_date(t.get("termin","")); return bool(d and d<_dt.now().date())

# === CONVERTERS ===
def _order_to_task(z):
    oid = z.get("nr") or z.get("id") or "?"
    title = z.get("tytul") or z.get("temat") or z.get("nazwa") or z.get("opis_short") or z.get("opis") or f"Zlecenie {oid}"
    deadline = z.get("termin") or z.get("deadline") or z.get("data_do") or z.get("data_ukonczenia_plan") or z.get("data_plan") or ""
    status = _map_status(z.get("status"))
    assigned = z.get("login") or z.get("operator") or z.get("pracownik") or ""
    return {"id":f"ZLEC-{oid}","tytul":title,"status":status,"termin":deadline,"opis":z.get("opis","(brak)"),"zlecenie":oid,"login":assigned,"_kind":"order"}

def _tool_to_task(num,name,worker,idx,item):
    status="Zrobione" if item.get("done") else "Nowe"
    return {"id":f"NARZ-{num}-{idx+1}","tytul":f"{item.get('tytul','(zadanie)')} (narz. {num} – {name})",
            "status":status,"termin":item.get("termin",""),"opis":item.get("opis",""),
            "zlecenie":"","login":worker,"_kind":"tooltask"}

# === VISIBILITY ===
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

# === READ TASKS ===
def _read_tasks(login, rola=None):
    tasks=[]
    # TODO: dodać logikę wczytywania zadań/zleceń jak w poprzednich patchach
    # np. z zadania.json, zlecenia.json, katalogów narzędzia itp.
    # + filtrowanie przez _order_visible_for i _tool_visible_for

    # apply overrides
    ovr=_status_get(login)
    for t in tasks:
        ov=ovr.get(str(t.get("id")))
        if ov: t["status"]=ov
    return tasks

# === PANEL ===
def uruchom_panel(root, frame, login=None, rola=None):
    for w in frame.winfo_children():
        try: w.destroy()
        except: pass
    try: apply_theme(root); apply_theme(frame)
    except Exception: pass

    head=ttk.Frame(frame); head.pack(fill="x", padx=12, pady=12)
    ttk.Label(head,text=login or "-", font=("TkDefaultFont",14,"bold")).pack(side="left", padx=(0,12))
    ttk.Label(head,text=f"Rola: {rola or '-'}").pack(side="left")

    tasks=_read_tasks(login, rola)
    # TODO: tabela z filtrami + obsługa dwukliku na zadaniu, wywołanie szczegółów

    return frame

panel_profil = uruchom_panel
