# Plik: gui_ustawienia.py
# Wersja pliku: 1.3.0
# Patch C: dodano zakładkę Alerty – podsumowanie zadań pracowników
# ⏹ KONIEC KODU

import os, json
import tkinter as tk
from tkinter import ttk

from ui_theme import apply_theme_safe as apply_theme

def _read_all_tasks():
    tasks_by_user = {}
    folder = "data"
    if not os.path.exists(folder): return tasks_by_user
    for fn in os.listdir(folder):
        if fn.startswith("zadania_") and fn.endswith(".json"):
            login = fn.replace("zadania_","").replace(".json","")
            try:
                with open(os.path.join(folder,fn),encoding="utf-8") as f: tasks=json.load(f)
                tasks_by_user[login]=tasks
            except: pass
    return tasks_by_user

def panel_ustawien(root, frame, login=None, rola=None):
    for w in frame.winfo_children():
        try: w.destroy()
        except: pass
    apply_theme(frame)
    nb = ttk.Notebook(frame); nb.pack(fill="both", expand=True)

    # Tab system (placeholder)
    sysf = ttk.Frame(nb); nb.add(sysf, text="System")
    ttk.Label(sysf, text="Ustawienia systemowe...").pack()

    # Alerty – tylko dla brygadzisty
    if rola=="brygadzista":
        af = ttk.Frame(nb); nb.add(af, text="Alerty")
        tasks_by_user = _read_all_tasks()
        tv = ttk.Treeview(af, columns=("login","otwarte","pilne","zrobione"), show="headings")
        for c in ("login","otwarte","pilne","zrobione"):
            tv.heading(c, text=c.capitalize()); tv.column(c,width=120)
        tv.pack(fill="both", expand=True)

        for u,ts in tasks_by_user.items():
            otwarte = sum(1 for t in ts if str(t.get("status")) in ("Nowe","W toku","Pilne"))
            pilne = sum(1 for t in ts if str(t.get("status"))=="Pilne")
            zrobione = sum(1 for t in ts if str(t.get("status"))=="Zrobione")
            tv.insert("", "end", values=(u,otwarte,pilne,zrobione))

        tv.tag_configure("pilne", foreground="red")
        for item in tv.get_children():
            vals = tv.item(item,"values")
            if int(vals[2])>0: tv.item(item,tags=("pilne",))
