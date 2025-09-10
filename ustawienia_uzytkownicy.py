# Plik: ustawienia_uzytkownicy.py
# Wersja pliku: 1.0.0
# Zakładka zarządzania użytkownikami wydzielona z gui_uzytkownicy.py

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

from utils.dirty_guard import DirtyGuard
from services.profile_service import (
    get_all_users as _get_all_users,
    is_logged_in as _service_is_logged_in,
    sync_presence as _service_sync_presence,
    write_users as _write_users,
)
from profile_utils import SIDEBAR_MODULES

MODULES = [key for key, _ in SIDEBAR_MODULES]

_USERS_FILE = "uzytkownicy.json"
_PRESENCE_FILE = "uzytkownicy_presence.json"


def _load_users():
    return _get_all_users(_USERS_FILE)


def _save_users(data):
    _write_users(data, _USERS_FILE)


def _sync_presence(users):
    _service_sync_presence(users, _PRESENCE_FILE)


def _is_logged_in(login):
    return _service_is_logged_in(login)


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
    widok_var = tk.StringVar()
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
    vars = {}
    text_widgets = {}
    module_vars = {}

    row = 1
    for f in fields_entry:
        vars[f] = tk.StringVar()
        ttk.Label(form, text=f).grid(row=row, column=0, sticky="e")
        ttk.Entry(form, textvariable=vars[f]).grid(row=row, column=1, sticky="ew")
        row += 1

    ttk.Label(form, text="widok_startowy").grid(row=row, column=0, sticky="e")
    ttk.Combobox(
        form,
        textvariable=widok_var,
        values=["panel", "dashboard"],
        state="readonly",
    ).grid(row=row, column=1, sticky="ew")
    row += 1

    ttk.Label(form, text="disabled_modules").grid(row=row, column=0, sticky="ne")
    mods_frame = ttk.Frame(form)
    mods_frame.grid(row=row, column=1, sticky="w")
    for mod in MODULES:
        var = tk.BooleanVar()
        module_vars[mod] = var
        ttk.Checkbutton(mods_frame, text=mod, variable=var).pack(anchor="w")
    row += 1

    for f in text_fields:
        ttk.Label(form, text=f).grid(row=row, column=0, sticky="ne")
        txt = tk.Text(form, height=3)
        txt.grid(row=row, column=1, sticky="ew")
        text_widgets[f] = txt
        row += 1

    def load_selected(_=None):
        sel = lb.curselection()
        if not sel:
            return
        idx = sel[0]
        user = users[idx]
        login_var.set(user.get("login", ""))
        for f in fields_entry:
            vars[f].set(user.get(f, ""))
        mods = {m.strip().lower() for m in user.get("disabled_modules", [])}
        for mod, var in module_vars.items():
            var.set(mod in mods)
        for f in text_fields:
            w = text_widgets[f]
            w.delete("1.0", "end")
            val = user.get(f, "")
            if f == "preferencje" and isinstance(val, dict):
                val = dict(val)
                val.pop("widok_startowy", None)
            if isinstance(val, (list, dict)):
                w.insert("1.0", json.dumps(val, ensure_ascii=False, indent=2))
            else:
                w.insert("1.0", val)
        widok_var.set(user.get("preferencje", {}).get("widok_startowy", "panel"))
        entry_login.config(state="disabled")

    def save_user():
        sel = lb.curselection()
        if sel:
            idx = sel[0]
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
        user["disabled_modules"] = [m for m, v in module_vars.items() if v.get()]
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
                    val = json.loads(text)
                    if f == "preferencje" and isinstance(val, dict):
                        val.pop("widok_startowy", None)
                        text_widgets[f].delete("1.0", "end")
                        text_widgets[f].insert(
                            "1.0", json.dumps(val, ensure_ascii=False, indent=2)
                        )
                    user[f] = val
                except Exception:
                    user[f] = text
            else:
                user[f] = defaults[f]
        prefs = user.setdefault("preferencje", {})
        prefs["widok_startowy"] = widok_var.get()
        _save_users(users)
        _sync_presence(users)
        load_selected()

    btn_save = ttk.Button(form, text="Zapisz")
    btn_save.grid(row=row, column=0, columnspan=2, pady=5)

    if str(rola).lower() == "admin":
        btns = ttk.Frame(frame)
        btns.pack(side="bottom", fill="x", pady=5)

        def new_user():
            lb.selection_clear(0, tk.END)
            login_var.set("")
            for f in fields_entry:
                vars[f].set("")
            for var in module_vars.values():
                var.set(False)
            for f in text_fields:
                text_widgets[f].delete("1.0", "end")
            widok_var.set("panel")
            entry_login.config(state="normal")

        def delete_user():
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
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

        btn_new = ttk.Button(btns, text="Nowy")
        btn_new.pack(side="left", padx=2)
        btn_del = ttk.Button(btns, text="Usuń")
        btn_del.pack(side="left", padx=2)

    notebook = parent.nametowidget(parent.winfo_parent())
    base_title = notebook.tab(parent, "text")
    guard = DirtyGuard(
        "Użytkownicy",
        on_save=lambda: (save_user(), guard.reset()),
        on_reset=lambda: (load_selected(), guard.reset()),
        on_dirty_change=lambda d: notebook.tab(
            parent, text=base_title + (" •" if d else "")
        ),
    )
    guard.watch(frame)
    for var in module_vars.values():
        var.trace_add("write", lambda *_: guard.set_dirty(True))

    frame.lb = lb
    frame.btn_save = btn_save
    frame.module_vars = module_vars

    lb.bind(
        "<<ListboxSelect>>",
        lambda e: guard.check_before(lambda: (load_selected(), guard.reset())),
    )
    btn_save.configure(command=guard.on_save)

    if str(rola).lower() == "admin":
        btn_new.configure(
            command=lambda: guard.check_before(lambda: (new_user(), guard.reset()))
        )
        btn_del.configure(
            command=lambda: guard.check_before(
                lambda: (delete_user(), guard.reset())
            )
        )

    return frame


def cofnij_przeniesienie_do_sn(numer):
    """Cofa oznaczenie narzędzia jako SN (is_old/kategoria)."""
    path = os.path.join("data", "narzedzia", f"{str(numer).zfill(3)}.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("is_old"):
            data["is_old"] = False
            data["kategoria"] = ""
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("SN", f"Cofnięto przeniesienie narzędzia {numer} do SN.")
        else:
            messagebox.showinfo("SN", f"Narzędzie {numer} nie jest oznaczone jako SN.")
    except Exception as e:
        messagebox.showwarning("SN", f"Błąd podczas cofania: {e}")


__all__ = ["make_tab", "cofnij_przeniesienie_do_sn"]

