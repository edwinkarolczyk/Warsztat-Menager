# Plik: gui_profil.py
# Wersja pliku: 1.5.1 (hotfix H1)
# Zmiana: pole „Przypisz do (login)” pojawia się także,
# gdy wpis NIE ma _kind=='order', ale ID zaczyna się od 'ZLEC-'.
# Dodatkowo wyciągam numer zlecenia z ID, jeśli brak 'zlecenie' w rekordzie.

import os, json, glob
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime as _dt

# --- małe, samodzielne helpery z poprzednich wersji ---
_OVR_DIR = os.path.join("data", "profil_overrides")
def _ensure_ovr_dir():
    try: os.makedirs(_OVR_DIR, exist_ok=True)
    except Exception: pass

def _load_assign_map():
    _ensure_ovr_dir()
    p = os.path.join(_OVR_DIR, "assign_orders.json")
    if os.path.exists(p):
        try:
            with open(p,"r",encoding="utf-8") as f: return json.load(f)
        except Exception: return {}
    return {}

def _save_assign(order_id, login):
    _ensure_ovr_dir()
    p = os.path.join(_OVR_DIR, "assign_orders.json")
    data = _load_assign_map()
    if login:
        data[str(order_id)] = str(login)
    else:
        data.pop(str(order_id), None)
    with open(p,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)

def _save_status_override(login, task_id, status):
    _ensure_ovr_dir()
    p = os.path.join(_OVR_DIR, f"status_{login}.json")
    try:
        data = {}
        if os.path.exists(p):
            with open(p,"r",encoding="utf-8") as f: data = json.load(f)
    except Exception:
        data = {}
    data[str(task_id)] = status
    with open(p,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)

def _load_user_logins_simple():
    s=set()
    if os.path.isdir("avatars"):
        for p in glob.glob("avatars/*.png"):
            s.add(os.path.splitext(os.path.basename(p))[0])
    for pat in ("data/zadania_*.json","data/zlecenia_*.json"):
        for p in glob.glob(pat):
            s.add(os.path.basename(p).split("_",1)[-1].replace(".json",""))
    return sorted(s)

# --- Jedyna publiczna funkcja: pokaz okno szczegółów z hotfixem ---
def show_task_details_hotfix(root, frame, login, rola, task, after_save=None):
    win = tk.Toplevel(root); win.title(f"Zadanie {task.get('id','')} – szczegóły (H1)")

    ttk.Label(win, text=f"ID: {task.get('id','')}").pack(anchor="w", padx=8, pady=2)
    ttk.Label(win, text=f"Tytuł: {task.get('tytul','')}").pack(anchor="w", padx=8, pady=2)
    ttk.Label(win, text=f"Opis: {task.get('opis','(brak)')}").pack(anchor="w", padx=8, pady=2)

    status_var = tk.StringVar(value=task.get("status",""))
    ttk.Label(win, text="Status:").pack(anchor="w", padx=8, pady=(6,0))
    cb = ttk.Combobox(win, textvariable=status_var, values=["Nowe","W toku","Pilne","Zrobione"], state="readonly")
    cb.pack(anchor="w", padx=8, pady=2)

    ttk.Label(win, text=f"Termin: {task.get('termin','')}").pack(anchor="w", padx=8, pady=2)

    # warunek pokazania „Przypisz do” poszerzony:
    is_order_like = str(task.get("id","")).startswith("ZLEC-") or task.get("_kind")=="order"
    assign_var = tk.StringVar(value="")
    if is_order_like and rola=="brygadzista":
        # ustal numer zlecenia
        znum = task.get("zlecenie")
        if not znum and str(task.get("id","")).startswith("ZLEC-"):
            znum = str(task.get("id"))[5:]
            task["zlecenie"] = znum  # dla spójności
        frm = ttk.Frame(win); frm.pack(fill="x", padx=8, pady=6)
        ttk.Label(frm, text="Przypisz do (login):").pack(side="left")
        ent = ttk.Combobox(frm, textvariable=assign_var, values=_load_user_logins_simple(), state="normal")
        ent.pack(side="left", padx=6)

        cur = task.get("login") or _load_assign_map().get(str(znum),"") or ""
        assign_var.set(cur)

    def _save_and_close():
        _save_status_override(login, task.get("id",""), status_var.get())
        if is_order_like and rola=="brygadzista":
            new_owner = assign_var.get().strip()
            _save_assign(task.get("zlecenie"), new_owner if new_owner else None)
        if callable(after_save):
            after_save()
        win.destroy()

    ttk.Button(win, text="Zapisz", command=_save_and_close).pack(pady=6)

# Instrukcja integracji:
# 1) w gui_profil.py zamień wywołanie _show_task_details(...) na show_task_details_hotfix(...).
#    Parametry te same + opcjonalne after_save=reloader.
