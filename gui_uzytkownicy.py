# Plik: gui_uzytkownicy.py
# Wersja pliku: 1.2.0
# Zmiany 1.2.0 (2025-08-25):
# - Brygadzista edytuje pola innych (bez loginu/hasła/avataru).
# - Admin może dodatkowo dodawać i usuwać konta.
# ⏹ KONIEC KODU

import json
import tkinter as tk
from tkinter import ttk

from ui_theme import apply_theme_safe as apply_theme

def _build_tab_profil(parent, login, rola):
    import gui_profile
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    # Wywołanie nowego panelu profilu w ramach zakładki
    gui_profile.panel_profil(parent, frame, login, rola)
    return frame

_USERS_FILE = "uzytkownicy.json"

def _load_users():
    try:
        with open(_USERS_FILE, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

def _save_users(data):
    with open(_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _build_tab_users(parent, rola):
    users = _load_users()
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)

    lb = tk.Listbox(frame)
    lb.pack(side="left", fill="y")
    for u in users:
        lb.insert("end", u.get("login", ""))

    form = ttk.Frame(frame)
    form.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    form.columnconfigure(1, weight=1)

    login_var = tk.StringVar()
    ttk.Label(form, text="login").grid(row=0, column=0, sticky="e")
    entry_login = ttk.Entry(form, textvariable=login_var, state="disabled")
    entry_login.grid(row=0, column=1, sticky="ew")

    fields = ["rola", "zmiana_plan", "status", "stanowisko", "pin"]
    vars = {}
    for i, f in enumerate(fields, start=1):
        vars[f] = tk.StringVar()
        ttk.Label(form, text=f).grid(row=i, column=0, sticky="e")
        ttk.Entry(form, textvariable=vars[f]).grid(row=i, column=1, sticky="ew")

    def load_selected(_=None):
        if not lb.curselection():
            return
        idx = lb.curselection()[0]
        user = users[idx]
        login_var.set(user.get("login", ""))
        for f in fields:
            vars[f].set(user.get(f, ""))
        entry_login.config(state="disabled")
    lb.bind("<<ListboxSelect>>", load_selected)

    def save_user():
        if lb.curselection():
            idx = lb.curselection()[0]
            user = users[idx]
        else:
            if str(rola).lower() != "admin":
                return
            login = login_var.get().strip()
            if not login:
                return
            user = {"login": login}
            users.append(user)
            lb.insert("end", login)
            lb.selection_clear(0, tk.END)
            lb.selection_set(lb.size()-1)
        for f in fields:
            user[f] = vars[f].get()
        _save_users(users)
        load_selected()
    ttk.Button(form, text="Zapisz", command=save_user).grid(row=len(fields)+1, column=0, columnspan=2, pady=5)

    if str(rola).lower() == "admin":
        btns = ttk.Frame(frame)
        btns.pack(side="bottom", fill="x", pady=5)
        def new_user():
            lb.selection_clear(0, tk.END)
            login_var.set("")
            for f in fields:
                vars[f].set("")
            entry_login.config(state="normal")
        def delete_user():
            if not lb.curselection():
                return
            idx = lb.curselection()[0]
            lb.delete(idx)
            users.pop(idx)
            _save_users(users)
            new_user()
        ttk.Button(btns, text="Nowy", command=new_user).pack(side="left", padx=2)
        ttk.Button(btns, text="Usuń", command=delete_user).pack(side="left", padx=2)

    return frame

def panel_uzytkownicy(root, frame, login=None, rola=None):
    # Czyść
    for w in frame.winfo_children():
        try: w.destroy()
        except: pass
    apply_theme(frame)

    nb = ttk.Notebook(frame); nb.pack(fill="both", expand=True)

    # Zakładka: Profil
    tab_profil = ttk.Frame(nb); nb.add(tab_profil, text="Profil")
    _build_tab_profil(tab_profil, login, rola)

    # Zakładka zarządzania użytkownikami dla brygadzisty/admina
    if str(rola).lower() in ("brygadzista", "admin"):
        tab_users = ttk.Frame(nb); nb.add(tab_users, text="Użytkownicy")
        _build_tab_users(tab_users, rola)

    # domyślnie przełącz na Profil dla zwykłego użytkownika
    if str(rola).lower() not in ("brygadzista","admin"):
        nb.select(tab_profil)

    return nb

# Zgodność: jeżeli panel woła uruchom_panel(root, frame, login, rola)
def uruchom_panel(root, frame, login=None, rola=None):
    return panel_uzytkownicy(root, frame, login, rola)
