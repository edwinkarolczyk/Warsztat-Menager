# Plik: ustawienia_uzytkownicy.py
# Wersja pliku: 1.0.0
# Zakładka zarządzania użytkownikami wydzielona z gui_uzytkownicy.py

import json
import tkinter as tk
from tkinter import ttk, messagebox

_USERS_FILE = "uzytkownicy.json"
_PRESENCE_FILE = "uzytkownicy_presence.json"


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


def _sync_presence(users):
    try:
        with open(_PRESENCE_FILE, encoding="utf-8") as f:
            presence_data = json.load(f)
        if not isinstance(presence_data, list):
            presence_data = []
    except Exception:
        presence_data = []

    presence_map = {p.get("login"): p for p in presence_data if isinstance(p, dict)}
    current = set()
    for u in users:
        login = u.get("login")
        if not login:
            continue
        current.add(login)
        rec = presence_map.get(login)
        if rec:
            rec["rola"] = u.get("rola", "")
            rec["zmiana_plan"] = u.get("zmiana_plan", "")
            rec["imie"] = u.get("imie", "")
            rec["nazwisko"] = u.get("nazwisko", "")
        else:
            presence_map[login] = {
                "login": login,
                "rola": u.get("rola", ""),
                "zmiana_plan": u.get("zmiana_plan", ""),
                "status": "",
                "imie": u.get("imie", ""),
                "nazwisko": u.get("nazwisko", ""),
            }
    for login in list(presence_map.keys()):
        if login not in current:
            presence_map.pop(login, None)
    try:
        with open(_PRESENCE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(presence_map.values()), f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _is_logged_in(login):
    if not login:
        return False
    try:
        import presence

        recs, _ = presence.read_presence()
        for r in recs:
            if r.get("login") == login and r.get("online"):
                return True
    except Exception:
        pass
    return False


def make_tab(parent, rola):
    """Zwraca ramkę zarządzania użytkownikami."""

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

    fields_entry = [
        "rola",
        "zmiana_plan",
        "status",
        "stanowisko",
        "pin",
        "imie",
        "nazwisko",
        "staz",
    ]
    text_fields = [
        "umiejetnosci",
        "kursy",
        "ostrzezenia",
        "nagrody",
        "historia_maszyn",
        "awarie",
        "sugestie",
        "preferencje",
        "opis",
    ]
    fields = fields_entry + text_fields

    vars = {}
    text_widgets = {}

    row = 1
    for f in fields_entry:
        vars[f] = tk.StringVar()
        ttk.Label(form, text=f).grid(row=row, column=0, sticky="e")
        ttk.Entry(form, textvariable=vars[f]).grid(row=row, column=1, sticky="ew")
        row += 1

    for f in text_fields:
        ttk.Label(form, text=f).grid(row=row, column=0, sticky="ne")
        txt = tk.Text(form, height=3)
        txt.grid(row=row, column=1, sticky="ew")
        text_widgets[f] = txt
        row += 1

    def load_selected(_=None):
        if not lb.curselection():
            return
        idx = lb.curselection()[0]
        user = users[idx]
        login_var.set(user.get("login", ""))
        for f in fields_entry:
            vars[f].set(user.get(f, ""))
        for f in text_fields:
            w = text_widgets[f]
            w.delete("1.0", "end")
            val = user.get(f, "")
            if isinstance(val, (list, dict)):
                w.insert("1.0", json.dumps(val, ensure_ascii=False, indent=2))
            else:
                w.insert("1.0", val)
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
            lb.selection_set(lb.size() - 1)
        for f in fields_entry:
            user[f] = vars[f].get()
        defaults = {
            "umiejetnosci": {},
            "kursy": [],
            "ostrzezenia": [],
            "nagrody": [],
            "historia_maszyn": [],
            "awarie": [],
            "sugestie": [],
            "preferencje": {},
            "opis": "",
        }
        for f in text_fields:
            text = text_widgets[f].get("1.0", "end").strip()
            if text:
                try:
                    user[f] = json.loads(text)
                except Exception:
                    user[f] = text
            else:
                user[f] = defaults[f]
        _save_users(users)
        _sync_presence(users)
        load_selected()

    ttk.Button(form, text="Zapisz", command=save_user).grid(
        row=len(fields) + 1, column=0, columnspan=2, pady=5
    )

    if str(rola).lower() == "admin":
        btns = ttk.Frame(frame)
        btns.pack(side="bottom", fill="x", pady=5)

        def new_user():
            lb.selection_clear(0, tk.END)
            login_var.set("")
            for f in fields_entry:
                vars[f].set("")
            for f in text_fields:
                text_widgets[f].delete("1.0", "end")
            entry_login.config(state="normal")

        def delete_user():
            if not lb.curselection():
                return
            idx = lb.curselection()[0]
            login = users[idx].get("login", "")
            if _is_logged_in(login):
                if not messagebox.askyesno(
                    "Usuń konto", f"Użytkownik '{login}' jest zalogowany. Kontynuować?"
                ):
                    return
            lb.delete(idx)
            users.pop(idx)
            _save_users(users)
            _sync_presence(users)
            new_user()

        ttk.Button(btns, text="Nowy", command=new_user).pack(side="left", padx=2)
        ttk.Button(btns, text="Usuń", command=delete_user).pack(side="left", padx=2)

    return frame


__all__ = ["make_tab"]

