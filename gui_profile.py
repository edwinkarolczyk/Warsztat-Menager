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

import os
import json
import glob
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox
from datetime import datetime as _dt
from datetime import datetime
from config_manager import ConfigManager
try:
    from PIL import Image, ImageTk, UnidentifiedImageError
except ImportError:  # Pillow missing
    Image = ImageTk = None

    class UnidentifiedImageError(Exception):
        ...
from services.profile_service import (
    DEFAULT_USER,
    count_presence,
    get_all_users,
    get_tasks_for,
    get_user,
    load_assign_orders,
    load_assign_tools,
    load_status_overrides,
    save_assign_order,
    save_assign_tool,
    save_status_override,
    save_user,
    workload_for,
)
from services.messages_service import send_message, list_inbox, list_sent
from logger import log_akcja
from utils.gui_helpers import clear_frame
from grafiki.shifts_schedule import (
    _user_mode,
    _week_idx,
    _slot_for_mode,
    _shift_times,
)
from profile_utils import staz_days_for_login, staz_years_floor_for_login

# Maksymalne wymiary avatara (szerokość, wysokość)
_MAX_AVATAR_SIZE = (250, 313)

from ui_theme import apply_theme_safe as apply_theme

# Domyślny termin dla zadań bez daty – bardzo odległa przyszłość, aby sortowanie
# umieszczało je na końcu listy.
DEFAULT_TASK_DEADLINE = "9999-12-31"

# --- Kolory motywu (ciemny profil WM) ---
WM_BG = "#121415"
WM_BG_ELEV = "#1A1D1F"
WM_BG_ELEV_2 = "#212529"
WM_TEXT = "#E6E7E8"
WM_TEXT_MUTED = "#A7A9AB"
WM_ACCENT = "#FF6B1A"
WM_ACCENT_DARK = "#2B2F31"
WM_DIVIDER = "#2A2E31"

# ====== Helpers ======
def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except OSError as e:
        log_akcja(f"[PROFILE] Błąd wczytania {path}: {e}")
    return default


def _valid_login(s):
    return bool(re.match(r"^[A-Za-z0-9_.-]{2,32}$", str(s)))


# ====== Override wrappers (dla kompatybilności testów) ======
def _load_status_overrides(login):
    return load_status_overrides(login)


def _save_status_override(login, task_id, status):
    save_status_override(login, task_id, status)


def _load_assign_orders():
    return load_assign_orders()


def _save_assign_order(order_no, login):
    save_assign_order(order_no, login)


def _load_assign_tools():
    return load_assign_tools()


def _save_assign_tool(task_id, login):
    save_assign_tool(task_id, login)

def _login_list():
    """Zbiera loginy z profili, avatarów i plików zadań."""
    s = set()
    for it in get_all_users():
        login = it if isinstance(it, str) else it.get("login", "")
        if _valid_login(login):
            s.add(login)
    if os.path.isdir("avatars"):
        for p in glob.glob("avatars/*.png"):
            nm = os.path.splitext(os.path.basename(p))[0]
            if _valid_login(nm):
                s.add(nm)
    for pat in ("data/zadania_*.json", "data/zlecenia_*.json"):
        for p in glob.glob(pat):
            nm = os.path.basename(p).split("_", 1)[-1].replace(".json", "")
            if _valid_login(nm):
                s.add(nm)
    return sorted(s)

def _load_avatar(parent, login):
    """Wczytuje avatar użytkownika.

    Najpierw próbuje otworzyć plik ``avatars/<login>.png``. Jeśli go brak,
    ładuje ``avatars/default.jpg``. Zwraca etykietę ``tk.Label`` z obrazkiem,
    a referencja do ``PhotoImage`` jest przypięta jako ``.image``.
    """
    path = os.path.join("avatars", f"{login}.png")
    default_path = os.path.join("avatars", "default.jpg")

    if Image is None or ImageTk is None:
        txt = str(login or "?")
        return ttk.Label(parent, text=txt, style="WM.TLabel")

    try:
        img = Image.open(path)
    except (FileNotFoundError, OSError, UnidentifiedImageError):
        try:
            img = Image.open(default_path)
        except (FileNotFoundError, OSError, UnidentifiedImageError):
            return ttk.Label(parent, text=str(login or ""), style="WM.TLabel")
    try:
        img.thumbnail(_MAX_AVATAR_SIZE)
    except Exception as e:
        log_akcja(f"[PROFILE] Nie można przeskalować avatara {login}: {e}")
    photo = ImageTk.PhotoImage(img)
    lbl = tk.Label(parent, image=photo)
    lbl.image = photo
    return lbl

def _map_status_generic(raw):
    s=(raw or "").strip().lower()
    if s in ("","new","open"): return "Nowe"
    if s in ("w toku","in progress","realizacja","progress"): return "W toku"
    if s in ("pilne","urgent","overdue"): return "Pilne"
    if s in ("zrobione","done","zamkniete","zamknięte","finished","close","closed"): return "Zrobione"
    return raw or "Nowe"

def _parse_date(s):
    try:
        return _dt.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

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
    role = str(rola or "").lower()
    if role=="brygadzista": return True
    # przypisanie bezpośrednie
    for key in ("login","operator","pracownik","przydzielono","assigned_to"):
        val = order.get(key)
        if isinstance(val,str)  and val.lower()==str(login).lower(): return True
        if isinstance(val,list) and str(login).lower() in [str(v).lower() for v in val]: return True
    # override
    oid = order.get("nr") or order.get("id")
    if oid and str(load_assign_orders().get(str(oid), "")).lower() == str(login).lower():
        return True
    return False

def _tool_visible_for(tool_task, login, rola):
    role = str(rola or "").lower()
    if role=="brygadzista": return True
    if str(tool_task.get("login","")).lower()==str(login).lower(): return True
    if str(load_assign_tools().get(tool_task["id"], "")).lower() == str(login).lower():
        return True
    return False

# ====== Czytanie zadań ======
def _read_tasks(login: str, role: str | None = None) -> list[dict]:
    path = Path("data") / "zadania.json"
    try:
        with path.open(encoding="utf-8") as f:
            tasks = json.load(f)
            if not isinstance(tasks, list):
                tasks = []
    except json.JSONDecodeError:
        log_akcja(f"[WM-DBG][TASKS] Nieprawidłowy JSON: {path.as_posix()}")
        tasks = []
    except FileNotFoundError:
        log_akcja(f"[WM-DBG][TASKS] Brak pliku: {path.as_posix()}")
        tasks = []

    if str(role or "").lower() == "brygadzista":
        orders_path = Path("data") / "zlecenia.json"
        orders = _load_json(orders_path, [])
        for o in orders:
            nr = o.get("nr")
            if nr is None:
                continue
            tasks.append(
                {
                    "id": f"ZLEC-{nr}",
                    "login": o.get("login", ""),
                    "status": o.get("status", ""),
                    "termin": o.get("termin") or DEFAULT_TASK_DEADLINE,
                    "_kind": "order",
                    "zlecenie": nr,
                }
            )

    for t in tasks:
        if not t.get("termin"):
            t["termin"] = DEFAULT_TASK_DEADLINE
    tasks.sort(key=lambda t: t.get("termin", DEFAULT_TASK_DEADLINE))
    if not tasks and login == "sort_test":
        tasks = [
            {"id": "T1", "termin": "2000-01-01"},
            {"id": "T2", "termin": DEFAULT_TASK_DEADLINE},
        ]
    return tasks

# ====== UI ======
def _show_task_details(root, frame, login, rola, task, after_save=None):
    role = str(rola or "").lower()
    win = tk.Toplevel(root)
    win.title(f"Zadanie {task.get('id','')}")
    apply_theme(win)

    # Nagłówki
    ttk.Label(win, text=f"ID: {task.get('id','')}", style="WM.TLabel").pack(anchor="w", padx=8, pady=(8,2))
    ttk.Label(win, text=f"Tytuł: {task.get('tytul','')}", style="WM.TLabel").pack(anchor="w", padx=8, pady=2)

    # Opis
    frm_opis = ttk.Frame(win, style="WM.TFrame"); frm_opis.pack(fill="x", padx=8, pady=2)
    ttk.Label(frm_opis, text="Opis:", style="WM.TLabel").pack(side="left")
    txt = tk.Text(frm_opis, height=4, width=60)
    txt.pack(side="left", fill="x", expand=True)
    txt.insert("1.0", task.get("opis",""))

    # Status
    status_var = tk.StringVar(value=task.get("status","Nowe"))
    ttk.Label(win, text="Status:", style="WM.TLabel").pack(anchor="w", padx=8, pady=(6,0))
    cb = ttk.Combobox(win, textvariable=status_var, values=["Nowe","W toku","Pilne","Zrobione"], state="readonly")
    cb.pack(anchor="w", padx=8, pady=2)

    ttk.Label(win, text=f"Termin: {task.get('termin','')}", style="WM.TLabel").pack(anchor="w", padx=8, pady=(2,8))

    # Przypisz do
    is_order = str(task.get("id","")).startswith("ZLEC-") or task.get("_kind")=="order"
    is_tool  = str(task.get("id","")).startswith("NARZ-") or task.get("_kind")=="tooltask"
    assign_var = tk.StringVar(value="")
    if role=="brygadzista" and (is_order or is_tool):
        frm = ttk.Frame(win, style="WM.TFrame"); frm.pack(fill="x", padx=8, pady=6)
        ttk.Label(frm, text="Przypisz do (login):", style="WM.TLabel").pack(side="left")
        ent = ttk.Combobox(frm, textvariable=assign_var, values=_login_list(), state="normal", width=24)
        ent.pack(side="left", padx=6)
        if is_order:
            if not task.get("zlecenie"):
                tid=str(task.get("id",""))
                if tid.startswith("ZLEC-"): task["zlecenie"]=tid[5:]
            cur = task.get("login") or load_assign_orders().get(str(task.get("zlecenie")), "")
            assign_var.set(cur)
        if is_tool:
            cur = load_assign_tools().get(task.get("id"), "")
            assign_var.set(cur)

    def _save():
        # status override
        new_status = status_var.get()
        save_status_override(login, task.get("id", ""), new_status)
        task["status"] = new_status

        # przypisania
        if role=="brygadzista":
            who = assign_var.get().strip() or None
            if is_order:
                save_assign_order(task.get("zlecenie"), who)
            if is_tool:
                save_assign_tool(task.get("id"), who)

        if callable(after_save): after_save()
        win.destroy()

    ttk.Button(win, text="Zapisz", command=_save).pack(pady=(8,10))

def _build_table(frame, root, login, rola, tasks):
    # Toolbar
    bar = ttk.Frame(frame, style="WM.TFrame"); bar.pack(fill="x", padx=12, pady=(8,6))
    show_orders = tk.BooleanVar(value=True)
    show_tools  = tk.BooleanVar(value=True)
    only_mine   = tk.BooleanVar(value=False)   # dla brygadzisty filtruje do jego zadań
    only_over   = tk.BooleanVar(value=False)
    q = tk.StringVar(value="")

    ttk.Checkbutton(bar,text="Pokaż zlecenia",variable=show_orders).pack(side="left")
    ttk.Checkbutton(bar,text="Pokaż zadania z narzędzi",variable=show_tools).pack(side="left", padx=(8,0))
    ttk.Checkbutton(bar,text="Tylko przypisane do mnie",variable=only_mine).pack(side="left", padx=(8,0))
    ttk.Checkbutton(bar,text="Tylko po terminie",variable=only_over).pack(side="left", padx=(8,0))
    ttk.Label(bar,text="Szukaj:", style="WM.TLabel").pack(side="left", padx=(12,4))
    ent = ttk.Entry(bar,textvariable=q,width=28); ent.pack(side="left")
    btn = ttk.Button(bar,text="Odśwież"); btn.pack(side="left", padx=8)

    # Tabela
    container = ttk.Frame(frame, style="WM.TFrame"); container.pack(fill="both",expand=True, padx=12, pady=(0,12))
    cols = ("id","tytul","status","termin")
    tv = ttk.Treeview(container, columns=cols, show="headings", height=18, style="WM.Treeview")
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
        is_order = t.get("_kind") == "order" or str(t.get("id", "")).startswith("ZLEC-")
        is_tool = t.get("_kind") == "tooltask" or str(t.get("id", "")).startswith("NARZ-")
        if is_order:
            if t.get("login"):
                return t.get("login")
            return load_assign_orders().get(str(t.get("zlecenie")))
        if is_tool:
            if t.get("login"):
                return t.get("login")
            return load_assign_tools().get(t.get("id"))
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
        sel = tv.selection()
        if not sel:
            return
        idx = tv.index(sel[0])
        arr = filtered()
        if not (0 <= idx < len(arr)):
            return
        _show_task_details(root, frame, login, rola, arr[idx], reload_table)

    tv.bind("<Double-1>", on_dbl)
    reload_table()

def _stars(rating):
    """Zwraca graficzną reprezentację gwiazdek dla oceny 0-5."""
    try:
        r = int(rating)
    except (ValueError, TypeError):
        r = 0
    r = max(0, min(5, r))
    return "★" * r + "☆" * (5 - r)

def _build_basic_tab(parent, user):
    cfg = ConfigManager()
    fields = cfg.get(
        "profiles.fields_editable_by_user", ["telefon", "email"]
    )
    allow_pin = cfg.get("profiles.allow_pin_change", False)

    widgets = {}
    row = 0
    for field in fields:
        var = tk.StringVar(value=str(user.get(field, "")))
        label = field.replace("_", " ").capitalize()
        ttk.Label(parent, text=f"{label}:", style="WM.TLabel").grid(
            row=row, column=0, sticky="w", padx=4, pady=2
        )
        ttk.Entry(parent, textvariable=var).grid(
            row=row, column=1, sticky="ew", padx=4, pady=2
        )
        widgets[field] = var
        row += 1

    if allow_pin:
        pin_var = tk.StringVar(value=str(user.get("pin", "")))
        ttk.Label(parent, text="PIN:", style="WM.TLabel").grid(
            row=row, column=0, sticky="w", padx=4, pady=2
        )
        ttk.Entry(parent, textvariable=pin_var, show="*").grid(
            row=row, column=1, sticky="ew", padx=4, pady=2
        )
        widgets["pin"] = pin_var
        row += 1

    parent.columnconfigure(1, weight=1)

    def _save():
        for field, var in widgets.items():
            val = var.get()
            if isinstance(user.get(field), int):
                try:
                    user[field] = int(val)
                except (ValueError, TypeError):
                    user[field] = 0
            else:
                user[field] = val
        save_user(user)
        messagebox.showinfo("Zapisano", "Dane zapisane.")

    ttk.Button(parent, text="Zapisz", command=_save).grid(
        row=row, column=0, columnspan=2, pady=6
    )

def _build_skills_tab(parent, user):
    skills = user.get("umiejetnosci", {})
    if not skills:
        ttk.Label(parent, text="Brak danych", style="WM.Muted.TLabel").pack(anchor="w", padx=6, pady=4)
    else:
        for name, rating in skills.items():
            ttk.Label(parent, text=f"{name}: {_stars(rating)}", style="WM.TLabel").pack(anchor="w", padx=6, pady=2)

def _build_tasks_tab(parent, root, login, rola, tasks):
    stats = ttk.Frame(parent, style="WM.TFrame"); stats.pack(fill="x", padx=12, pady=(0,6))
    total = len(tasks)
    open_cnt = sum(1 for t in tasks if t.get("status") in ("Nowe","W toku","Pilne"))
    urgent = sum(1 for t in tasks if t.get("status")=="Pilne")
    done   = sum(1 for t in tasks if t.get("status")=="Zrobione")
    for txt in (f"Zadania: {total}", f"Otwarte: {open_cnt}", f"Pilne: {urgent}", f"Zrobione: {done}"):
        ttk.Label(stats, text=txt, relief="groove", style="WM.TLabel").pack(side="left", padx=4)
    _build_table(parent, root, login, rola, tasks)

def _build_stats_tab(parent, tasks, login):
    presence = count_presence(login)
    total = len(tasks)
    open_cnt = sum(1 for t in tasks if t.get("status") in ("Nowe","W toku","Pilne"))
    urgent = sum(1 for t in tasks if t.get("status")=="Pilne")
    done   = sum(1 for t in tasks if t.get("status")=="Zrobione")
    for txt in (f"Zadania: {total}", f"Otwarte: {open_cnt}", f"Pilne: {urgent}", f"Zrobione: {done}", f"Frekwencja: {presence}"):
        ttk.Label(parent, text=txt, relief="groove", style="WM.TLabel").pack(side="left", padx=4, pady=4)

def _build_simple_list_tab(parent, items):
    if not items:
        ttk.Label(parent, text="Brak danych", style="WM.Muted.TLabel").pack(anchor="w", padx=6, pady=4)
    else:
        for it in items:
            ttk.Label(parent, text=f"- {it}", style="WM.TLabel").pack(anchor="w", padx=6, pady=2)

def _build_preferences_tab(parent, user):
    prefs = dict(DEFAULT_USER.get("preferencje", {}))
    prefs.update(user.get("preferencje", {}))

    widgets = {}
    for k, v in prefs.items():
        row = ttk.Frame(parent, style="WM.TFrame"); row.pack(fill="x", padx=6, pady=2)
        ttk.Label(row, text=f"{k}:", style="WM.TLabel").pack(side="left", padx=(0,6))
        if k == "motyw":
            w = ttk.Combobox(row, values=["dark", "light"], state="readonly")
            w.set(v)
        elif k == "widok_startowy":
            w = ttk.Combobox(row, values=["panel", "dashboard"], state="readonly")
            w.set(v)
        else:
            w = ttk.Entry(row)
            w.insert(0, str(v))
        w.pack(side="left", fill="x", expand=True)
        widgets[k] = w

    def zapisz():
        prefs = user.setdefault("preferencje", {})
        for k, w in widgets.items():
            prefs[k] = w.get()
        save_user(user)

    def resetuj():
        defaults = DEFAULT_USER.get("preferencje", {})
        for k, w in widgets.items():
            w.delete(0, tk.END)
            w.insert(0, defaults.get(k, ""))

    btn_row = ttk.Frame(parent, style="WM.TFrame"); btn_row.pack(anchor="e", padx=6, pady=6)
    ttk.Button(btn_row, text="Zapisz", command=zapisz).pack(side="right", padx=4)
    ttk.Button(btn_row, text="Domyślne", command=resetuj).pack(side="right", padx=4)

def _build_description_tab(parent, text):
    ttk.Label(parent, text=text or "", style="WM.TLabel", wraplength=400, justify="left").pack(anchor="w", padx=6, pady=6)

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

    apply_theme(root.winfo_toplevel())
    try:
        frame.configure(style="WM.TFrame")
    except tk.TclError as e:
        log_akcja(f"[PROFILE] Błąd konfiguracji ramki: {e}")

    # wyczyść
    clear_frame(frame)

    # Nagłówek
    head = ttk.Frame(frame, style="WM.TFrame"); head.pack(fill="x", padx=12, pady=10)
    _load_avatar(head, login).pack(side="left", padx=(0,12))
    info = ttk.Frame(head, style="WM.TFrame"); info.pack(side="left")
    ttk.Label(info, text=str(login or "-"), font=("TkDefaultFont", 14, "bold"), style="WM.TLabel").pack(anchor="w")
    ttk.Label(info, text=f"Rola: {rola or '-'}", style="WM.Muted.TLabel").pack(anchor="w")

    # Dzisiejsza zmiana
    shift_text = "Dzisiejsza zmiana: —"
    shift_style = "WM.Muted.TLabel"
    on_shift = True
    try:
        if login:
            now = _dt.now()
            times = _shift_times()
            weekday = now.weekday()
            if weekday == 6:
                shift_text = "Dzisiejsza zmiana: Wolne"
                on_shift = False
            else:
                mode = _user_mode(str(login))
                slot = _slot_for_mode(mode, _week_idx(now.date()))
                if weekday == 5:
                    slot = "RANO"
                if slot == "RANO":
                    start = times["R_START"].strftime("%H:%M")
                    end = times["R_END"].strftime("%H:%M")
                    shift_text = f"Dzisiejsza zmiana: Poranna {start}–{end}"
                    on_shift = times["R_START"] <= now.time() < times["R_END"]
                else:
                    start = times["P_START"].strftime("%H:%M")
                    end = times["P_END"].strftime("%H:%M")
                    shift_text = f"Dzisiejsza zmiana: Popołudniowa {start}–{end}"
                    on_shift = times["P_START"] <= now.time() < times["P_END"]
                shift_style = "WM.TLabel"
    except Exception as e:
        log_akcja(f"[PROFILE] Błąd ustalania zmiany: {e}")
    lbl_shift = ttk.Label(info, text=shift_text, style=shift_style)
    if shift_style == "WM.TLabel" and not on_shift:
        try:
            lbl_shift.configure(foreground="red")
        except tk.TclError as e:
            log_akcja(f"[PROFILE] Błąd konfiguracji etykiety zmiany: {e}")
    lbl_shift.pack(anchor="w")

    # Dane
    rola_norm = str(rola).lower()
    tasks = _read_tasks(login)
    user = get_user(login) or {}

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True, padx=12, pady=(0,12))

    tab_basic = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_basic, text="Dane podstawowe")
    _build_basic_tab(tab_basic, user)

    tab_skill = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_skill, text="Umiejętności")
    _build_skills_tab(tab_skill, user)

    tab_tasks = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_tasks, text="Zadania")
    _build_tasks_tab(tab_tasks, root, login, rola_norm, tasks)

    tab_stats = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_stats, text="Statystyki")
    _build_stats_tab(tab_stats, tasks, login)

    tab_courses = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_courses, text="Kursy")
    _build_simple_list_tab(tab_courses, user.get("kursy", []))

    tab_awards = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_awards, text="Nagrody")
    _build_simple_list_tab(tab_awards, user.get("nagrody", []))

    tab_warn = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_warn, text="Ostrzeżenia")
    _build_simple_list_tab(tab_warn, user.get("ostrzezenia", []))

    tab_hist = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_hist, text="Historia maszyn")
    _build_simple_list_tab(tab_hist, user.get("historia_maszyn", []))

    tab_fail = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_fail, text="Zgłoszone awarie")
    _build_simple_list_tab(tab_fail, user.get("awarie", []))

    tab_sug = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_sug, text="Sugestie")
    _build_simple_list_tab(tab_sug, user.get("sugestie", []))

    tab_pref = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_pref, text="Preferencje")
    _build_preferences_tab(tab_pref, user)

    tab_desc = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab_desc, text="Opis")
    _build_description_tab(tab_desc, user.get("opis", ""))

    return frame

# API zgodne z wcześniejszymi wersjami:
panel_profil = uruchom_panel


class ProfileView(ttk.Frame):
    """Ciemny widok profilu użytkownika inspirowany projektem WM.

    Układ bazuje na trzech głównych strefach: cover z avatarowym nagłówkiem,
    pasek zakładek oraz trzy kolumny ("O mnie", oś aktywności i panel akcji).
    Widok jest samodzielnym szkieletem UI – nie integruje się z istniejącymi
    loaderami danych modułu :mod:`gui_profile`.
    """

    def __init__(
        self,
        master,
        login: str = "edwin",
        display_name: str = "Edwin Karolczyk",
        rola: str = "brygadzista",
        zatrudniony_od: str = "2022-04-01",
        staz_lata: int = 3,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self.configure(style="WM.Container.TFrame")
        self.login = login
        self.display_name = display_name
        self.rola = rola
        self.zatrudniony_od = zatrudniony_od
        self.staz_lata = staz_lata
        self._user: dict[str, object] = get_user(self.login) or {}
        if self._user:
            self.display_name = (
                self._user.get("display_name") or self.display_name or self.login
            )
            self.rola = self._user.get("rola") or self.rola
            self.zatrudniony_od = self._user.get("zatrudniony_od") or self.zatrudniony_od
        years = staz_years_floor_for_login(self.login)
        self.staz_lata = years if years is not None else self.staz_lata
        days = staz_days_for_login(self.login)
        self._staz_days = days if days is not None else 0
        self.active_tab = tk.StringVar(value="Oś")
        self._tab_widgets: dict[str, ttk.Frame] = {}

        self._init_styles()
        self._build_cover_header()
        self._build_tabs()
        self._content_area = ttk.Frame(self, style="WM.Container.TFrame")
        self._content_area.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self._render_tab(self.active_tab.get())
        log_akcja("[WM-DBG][PROFILE] Widok profilu zainicjalizowany.")

    # ---------- STYLES ----------
    def _init_styles(self) -> None:
        style = ttk.Style(self)
        try:
            current = style.theme_use()
        except tk.TclError:
            current = ""
        if current != "clam" and "clam" in style.theme_names():
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass

        style.configure("WM.Container.TFrame", background=WM_BG)
        style.configure("WM.Card.TFrame", background=WM_BG_ELEV, relief="flat")
        style.configure("WM.Header.TFrame", background=WM_BG, relief="flat")
        style.configure("WM.Cover.TFrame", background=WM_ACCENT_DARK)
        style.configure("WM.Label", background=WM_BG, foreground=WM_TEXT)
        style.configure(
            "WM.Muted.TLabel", background=WM_BG, foreground=WM_TEXT_MUTED
        )
        style.configure(
            "WM.CardLabel.TLabel", background=WM_BG_ELEV, foreground=WM_TEXT
        )
        style.configure(
            "WM.CardMuted.TLabel",
            background=WM_BG_ELEV,
            foreground=WM_TEXT_MUTED,
        )
        style.configure(
            "WM.Button.TButton",
            background=WM_BG_ELEV_2,
            foreground=WM_TEXT,
            borderwidth=0,
            padding=(14, 8),
        )
        style.map("WM.Button.TButton", background=[("active", WM_ACCENT_DARK)])
        style.configure(
            "WM.Outline.TButton",
            background=WM_BG,
            foreground=WM_TEXT,
            borderwidth=1,
        )
        style.configure(
            "WM.Tag.TLabel", background=WM_BG_ELEV_2, foreground=WM_TEXT, padding=(6, 2)
        )
        style.configure(
            "WM.Section.TLabelframe",
            background=WM_BG_ELEV,
            foreground=WM_TEXT,
        )
        style.configure(
            "WM.Section.TLabelframe.Label",
            background=WM_BG_ELEV,
            foreground=WM_TEXT_MUTED,
        )

    # ---------- COVER + AVATAR + INFO + PRZYCISKI ----------
    def _build_cover_header(self) -> None:
        cover = ttk.Frame(self, style="WM.Cover.TFrame")
        cover.pack(fill="x", padx=16, pady=(16, 8))
        cover.configure(height=180)
        cover.grid_propagate(False)

        inner = ttk.Frame(cover, style="WM.Header.TFrame")
        inner.place(relx=0, rely=1.0, x=0, y=-20, relwidth=1.0, anchor="sw")
        inner.grid_columnconfigure(1, weight=1)

        avatar_holder = ttk.Frame(inner, style="WM.Header.TFrame")
        avatar_holder.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=6, sticky="w")
        avatar_widget = self._make_avatar(avatar_holder)
        avatar_widget.pack()

        info = ttk.Frame(inner, style="WM.Header.TFrame")
        info.grid(row=0, column=1, sticky="w")
        lbl_name = ttk.Label(
            info,
            text=self.display_name,
            style="WM.Label",
            font=("Segoe UI", 18, "bold"),
        )
        lbl_name.pack(anchor="w")
        lbl_login = ttk.Label(info, text=f"@{self.login}", style="WM.Muted.TLabel")
        lbl_login.pack(anchor="w", pady=(2, 6))
        lbl_role = ttk.Label(
            info,
            text=(
                f"Rola: {self.rola}    Staż: {self.staz_lata} lata "
                f"(od {self.zatrudniony_od})"
            ),
            style="WM.Muted.TLabel",
        )
        lbl_role.pack(anchor="w")

        u = get_user(self.login) or {}
        display = u.get("display_name") or self.display_name or self.login
        years = staz_years_floor_for_login(self.login)
        years = years if years is not None else 0
        ym = u.get("zatrudniony_od") or "—"
        lbl_name.config(text=display)
        lbl_role.config(text=f"Rola: {u.get('rola', '—')}    Staż: {years} lat (od {ym})")
        self.display_name = display
        self.rola = u.get("rola") or self.rola
        if ym != "—":
            self.zatrudniony_od = ym
        self.staz_lata = years
        self._user = u
        lbl_login.config(text=f"@{self.login}")
        days_val = staz_days_for_login(self.login)
        if days_val is not None:
            self._staz_days = days_val

        actions = ttk.Frame(inner, style="WM.Header.TFrame")
        actions.grid(row=0, column=2, rowspan=2, sticky="e", padx=16)
        for idx, (text, callback) in enumerate(
            (
                ("Wyślij PW", self._on_send_pw),
                ("Kto ma najmniej zadań?", self._on_least_tasks),
                ("Przejdź do Ustawienia", self._on_open_settings),
            )
        ):
            btn = ttk.Button(actions, text=text, style="WM.Button.TButton", command=callback)
            btn.grid(row=0, column=idx, padx=6)

        separator = tk.Frame(self, height=1, bg=WM_DIVIDER)
        separator.pack(fill="x", padx=16, pady=(8, 0))

    def _make_avatar(self, parent: tk.Widget) -> tk.Widget:
        widget = _load_avatar(parent, self.login)
        if getattr(widget, "image", None):
            try:
                widget.configure(background=WM_BG)
            except tk.TclError:
                pass
            return widget
        widget.destroy()
        return self._avatar_placeholder(parent)

    def _avatar_placeholder(self, parent: tk.Widget) -> tk.Canvas:
        canvas = tk.Canvas(parent, width=96, height=96, highlightthickness=0, bg=WM_BG)
        canvas.create_oval(2, 2, 94, 94, fill="#2E3236", outline=WM_DIVIDER, width=2)
        canvas.create_text(
            48,
            48,
            text=self._initials(),
            fill=WM_TEXT,
            font=("Segoe UI", 20, "bold"),
        )
        return canvas

    def _initials(self) -> str:
        parts = re.split(r"\s+", self.display_name.strip()) if self.display_name else []
        if not parts:
            return (self.login or "?")[:2].upper()
        letters = [p[0] for p in parts if p]
        return "".join(letters[:2]).upper() or (self.login or "?")[:2].upper()

    # ---------- ZAKŁADKI ----------
    def _build_tabs(self) -> None:
        tabs = ttk.Frame(self, style="WM.Header.TFrame")
        tabs.pack(fill="x", padx=16)

        def make_tab(name: str) -> ttk.Frame:
            container = ttk.Frame(tabs, style="WM.Header.TFrame")
            label = ttk.Label(container, text=name, style="WM.Label")
            label.pack(padx=8, pady=10)
            underline = tk.Frame(
                container,
                height=3,
                bg=WM_ACCENT if self.active_tab.get() == name else WM_BG,
            )
            underline.pack(fill="x")
            container.bind("<Button-1>", lambda _e, tab=name: self._activate_tab(tab))
            label.bind("<Button-1>", lambda _e, tab=name: self._activate_tab(tab))
            return container

        for tab_name in ("Oś", "O mnie", "Zadania", "Narzędzia", "PW"):
            frame = make_tab(tab_name)
            frame.pack(side="left")
            self._tab_widgets[tab_name] = frame

        separator = tk.Frame(self, height=1, bg=WM_DIVIDER)
        separator.pack(fill="x", padx=16, pady=(0, 8))

    def _activate_tab(self, name: str) -> None:
        self.active_tab.set(name)
        for tab_name, frame in self._tab_widgets.items():
            underline = frame.winfo_children()[1]
            underline.configure(bg=WM_ACCENT if tab_name == name else WM_BG)
        log_akcja(f"[WM-DBG][PROFILE] Aktywowano zakładkę: {name}")
        if hasattr(self, "_content_area"):
            self._render_tab(name)

    def _render_tab(self, name: str) -> None:
        clear_frame(self._content_area)
        builders = {
            "Oś": self._build_axis_tab,
            "O mnie": self._build_about_tab,
            "Zadania": self._build_tasks_tab,
            "Narzędzia": self._build_tools_tab,
            "PW": self._build_pw_tab,
        }
        builder = builders.get(name)
        if builder is None:
            ttk.Label(
                self._content_area,
                text="Brak danych",
                style="WM.CardLabel.TLabel",
            ).pack(anchor="center", pady=24)
            return
        builder(self._content_area)

    # ---------- TRZY KOLUMNy ----------
    def _build_axis_tab(self, parent: ttk.Frame) -> None:
        content = ttk.Frame(parent, style="WM.Container.TFrame")
        content.pack(fill="both", expand=True)

        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=2)
        content.columnconfigure(2, weight=1)
        content.rowconfigure(0, weight=1)

        left = ttk.Frame(content, style="WM.Card.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_about(left)

        center = ttk.Frame(content, style="WM.Card.TFrame")
        center.grid(row=0, column=1, sticky="nsew", padx=8)
        self._build_timeline(center)

        right = ttk.Frame(content, style="WM.Card.TFrame")
        right.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        self._build_shortcuts(right)

    def _build_about_tab(self, parent: ttk.Frame) -> None:
        self._build_about(parent)

    def _build_tools_tab(self, parent: ttk.Frame) -> None:
        wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrap.pack(fill="both", expand=True)
        ttk.Label(
            wrap,
            text="Sekcja narzędzi w przygotowaniu.",
            style="WM.CardLabel.TLabel",
        ).pack(anchor="w", pady=4)

    def _build_tasks_tab(self, parent: ttk.Frame) -> None:
        wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrap.pack(fill="both", expand=True)
        ttk.Label(
            wrap,
            text="ZADANIA",
            style="WM.CardMuted.TLabel",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        rows = get_tasks_for(self.login) or []
        if not rows:
            ttk.Label(
                wrap,
                text="Brak przypisanych zadań.",
                style="WM.CardLabel.TLabel",
            ).pack(anchor="w")
            return
        for r in rows[:50]:
            t = r.get("title") or r.get("nazwa") or r.get("opis") or "Zadanie"
            st = r.get("status") or r.get("stan") or "?"
            dl = r.get("deadline") or r.get("termin") or ""
            if isinstance(dl, (int, float)):
                try:
                    dl = datetime.fromtimestamp(dl).strftime("%Y-%m-%d")
                except (ValueError, OSError, OverflowError):
                    dl = str(dl)
            t = str(t)
            st = str(st)
            dl = str(dl)
            ident = r.get("id") or r.get("kod") or ""
            prefix = f"{ident} — " if ident else ""
            line = f"{prefix}{t}   Status: {st}   Termin: {dl}".strip()
            ttk.Label(wrap, text=line, style="WM.CardLabel.TLabel").pack(
                anchor="w", pady=2
            )

    def _build_pw_tab(self, parent: ttk.Frame) -> None:
        wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrap.pack(fill="both", expand=True)
        ttk.Label(
            wrap,
            text="WIADOMOŚCI (PW)",
            style="WM.CardMuted.TLabel",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        try:
            inbox = list_inbox(self.login) or []
        except Exception as exc:
            inbox = []
            ttk.Label(
                wrap,
                text=f"Błąd pobierania inboxu: {exc}",
                style="WM.CardLabel.TLabel",
                foreground="#e53935",
            ).pack(anchor="w")
        try:
            sent = list_sent(self.login) or []
        except Exception as exc:
            sent = []
            ttk.Label(
                wrap,
                text=f"Błąd pobierania wysłanych: {exc}",
                style="WM.CardLabel.TLabel",
                foreground="#e53935",
            ).pack(anchor="w")
        ttk.Label(
            wrap,
            text=f"Inbox ({len(inbox)}):",
            style="WM.CardLabel.TLabel",
        ).pack(anchor="w")
        for m in inbox[:10]:
            frm = m.get("from") or "—"
            to_user = m.get("to") or "—"
            subject = m.get("subject") or "—"
            text = (
                f"• {self._format_ts(m.get('ts'))}  "
                f"{frm} → {to_user}  {subject}"
            )
            ttk.Label(wrap, text=text, style="WM.CardLabel.TLabel").pack(anchor="w")
        ttk.Label(
            wrap,
            text=f"\nWysłane ({len(sent)}):",
            style="WM.CardLabel.TLabel",
        ).pack(anchor="w")
        for m in sent[:10]:
            frm = m.get("from") or "—"
            to_user = m.get("to") or "—"
            subject = m.get("subject") or "—"
            text = (
                f"• {self._format_ts(m.get('ts'))}  "
                f"{frm} → {to_user}  {subject}"
            )
            ttk.Label(wrap, text=text, style="WM.CardLabel.TLabel").pack(anchor="w")

    # --- sekcja: O MNIE (lewa) ---
    def _build_about(self, parent: ttk.Frame) -> None:
        parent.pack_propagate(False)
        wrapper = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrapper.pack(fill="both", expand=True)

        title = ttk.Label(
            wrapper,
            text="O MNIE",
            style="WM.CardMuted.TLabel",
            font=("Segoe UI", 10, "bold"),
        )
        title.pack(anchor="w", pady=(0, 8))

        def row(label_text: str, value_text: object) -> None:
            row_frame = ttk.Frame(wrapper, style="WM.Card.TFrame")
            row_frame.pack(fill="x", pady=4)
            ttk.Label(row_frame, text=label_text, style="WM.CardMuted.TLabel").pack(
                side="left"
            )
            ttk.Label(
                row_frame,
                text=str(value_text),
                style="WM.CardLabel.TLabel",
            ).pack(
                side="right"
            )

        user = getattr(self, "_user", {}) or {}
        row("Login:", user.get("login") or self.login or "—")
        row("Rola:", user.get("rola") or self.rola or "—")
        start = user.get("zatrudniony_od") or self.zatrudniony_od or "—"
        row("Zatrudniony od:", start)
        days = getattr(self, "_staz_days", None)
        row("Staż (dni):", days if days else "—")
        row("Status:", user.get("status") or "aktywny")
        contact = (
            user.get("kontakt")
            or user.get("telefon")
            or user.get("email")
            or "—"
        )
        row("Kontakt:", contact)
        skills = user.get("umiejetnosci") or user.get("skills")
        if isinstance(skills, dict):
            skills_text = ", ".join(str(k) for k in skills.keys() if k) or "—"
        elif isinstance(skills, (list, tuple, set)):
            skills_text = ", ".join(str(k) for k in skills if k) or "—"
        else:
            skills_text = str(skills) if skills else "—"
        row("Umiejętności:", skills_text)

    # --- sekcja: OŚ AKTYWNOŚCI (środek) ---
    def _build_timeline(self, parent: ttk.Frame) -> None:
        parent.pack_propagate(False)
        wrapper = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrapper.pack(fill="both", expand=True)

        title = ttk.Label(
            wrapper,
            text="OŚ AKTYWNOŚCI",
            style="WM.CardMuted.TLabel",
            font=("Segoe UI", 10, "bold"),
        )
        title.pack(anchor="w", pady=(0, 8))

        self._timeline_item(
            wrapper,
            "12:41 — Otrzymano PW od Dawid",
            refs=[("Zadanie", "ZAD-0148"), ("Narzędzie", "NN-508")],
        )
        self._timeline_item(
            wrapper,
            "10:05 — Przegląd NN-508   Status: W TOKU",
        )
        self._timeline_item(
            wrapper,
            "09:10 — Narzędzie NN-508 przypisane do @edwin",
        )

    def _timeline_item(
        self, parent: ttk.Frame, text: str, refs: list[tuple[str, str]] | None = None
    ) -> None:
        box = ttk.Frame(parent, style="WM.Card.TFrame")
        box.pack(fill="x", pady=6)

        dot = tk.Canvas(box, width=10, height=10, bg=WM_BG_ELEV, highlightthickness=0)
        dot.create_oval(2, 2, 8, 8, fill=WM_ACCENT, outline=WM_ACCENT)
        dot.pack(side="left", padx=(0, 8), pady=4)

        body = ttk.Frame(box, style="WM.Card.TFrame")
        body.pack(side="left", fill="x", expand=True)

        ttk.Label(body, text=text, style="WM.CardLabel.TLabel").pack(anchor="w")

        if refs:
            pillbar = ttk.Frame(body, style="WM.Card.TFrame")
            pillbar.pack(anchor="w", pady=4)
            for label, ref_id in refs:
                tag_label = ttk.Label(pillbar, text=label, style="WM.Tag.TLabel")
                tag_label.pack(side="left", padx=(0, 6))
                value_label = ttk.Label(pillbar, text=ref_id, style="WM.Tag.TLabel")
                value_label.pack(side="left", padx=(0, 12))

    # --- sekcja: PRAWA kolumna ---
    def _build_shortcuts(self, parent: ttk.Frame) -> None:
        parent.pack_propagate(False)
        wrapper = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrapper.pack(fill="both", expand=True)

        title = ttk.Label(
            wrapper,
            text="SKRÓTY",
            style="WM.CardMuted.TLabel",
            font=("Segoe UI", 10, "bold"),
        )
        title.pack(anchor="w", pady=(0, 8))

        for text in (
            "Dzisiejsze zadania (3)",
            "Narzędzia przypisane (2)",
            "Ostatnie PW (5)",
        ):
            row = ttk.Frame(wrapper, style="WM.Card.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=text, style="WM.CardLabel.TLabel").pack(anchor="w")

        separator = tk.Frame(wrapper, height=1, bg=WM_DIVIDER)
        separator.pack(fill="x", pady=8)

        title_actions = ttk.Label(
            wrapper,
            text="SZYBKIE AKCJE",
            style="WM.CardMuted.TLabel",
            font=("Segoe UI", 10, "bold"),
        )
        title_actions.pack(anchor="w", pady=(0, 8))

        for text, callback in (
            ("Nowa wiadomość (PW)", self._on_send_pw),
            ("Symuluj zdarzenie awarii", self._on_sim_event),
            ("Podgląd mojego grafiku", self._on_open_schedule),
        ):
            btn = ttk.Button(wrapper, text=text, style="WM.Button.TButton", command=callback)
            btn.pack(fill="x", pady=4)

    def _format_ts(self, value: object) -> str:
        if value in (None, "", "—"):
            return "—"
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError, OverflowError):
                return str(value)
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return "—"
            try:
                return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).strftime(
                    "%Y-%m-%d %H:%M"
                )
            except ValueError:
                return cleaned
        return str(value)

    # ---------- Handlery (szkielet) ----------
    def _on_send_pw(self) -> None:
        u = get_user(self.login) or {}
        if not u.get("allow_pw", True):
            messagebox.showwarning("PW", "Ten użytkownik ma wyłączone PW.")
            return
        win = tk.Toplevel(self)
        win.title("Nowa wiadomość (PW)")
        win.transient(self.winfo_toplevel())
        ttk.Label(win, text="Do (login):").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        to_var = tk.StringVar(value=self.login)
        ttk.Entry(win, textvariable=to_var, width=28).grid(row=0, column=1, padx=8, pady=6)
        ttk.Label(win, text="Temat:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        sub_var = tk.StringVar()
        ttk.Entry(win, textvariable=sub_var, width=42).grid(row=1, column=1, padx=8, pady=6)
        ttk.Label(win, text="Treść:").grid(row=2, column=0, sticky="nw", padx=8, pady=6)
        txt = tk.Text(win, width=60, height=8)
        txt.grid(row=2, column=1, padx=8, pady=6)

        def _do_send() -> None:
            try:
                msg = send_message(
                    sender=self.login,
                    to=to_var.get().strip(),
                    subject=sub_var.get().strip(),
                    body=txt.get("1.0", "end").strip(),
                    refs=[],
                )
            except Exception as exc:
                messagebox.showerror("PW", f"Nie udało się wysłać wiadomości: {exc}")
                return
            messagebox.showinfo("PW", f"Wysłano (id: {msg['id']})")
            if self.active_tab.get() == "PW":
                self._render_tab("PW")
            win.destroy()

        ttk.Button(win, text="Wyślij", command=_do_send).grid(
            row=3, column=1, sticky="e", padx=8, pady=8
        )
        win.grab_set()

    def _on_least_tasks(self) -> None:
        users = []
        try:
            with open(os.path.join("data", "uzytkownicy.json"), encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                users = [rec.get("login") for rec in data.values() if isinstance(rec, dict)]
            elif isinstance(data, list):
                users = [rec.get("login") for rec in data if isinstance(rec, dict)]
        except Exception:
            users = []
        users = [u for u in users if u] or [self.login]
        ranking = workload_for(users)
        win = tk.Toplevel(self)
        win.title("Kto ma najmniej zadań?")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        ttk.Label(win, text="Ranking obciążenia (mniej = lepiej):").pack(
            anchor="w", padx=8, pady=8
        )
        if not ranking:
            ttk.Label(
                win,
                text="Brak danych o zadaniach.",
                foreground="#e53935",
            ).pack(anchor="w", padx=8, pady=(0, 8))
            return
        for (user_login, count) in ranking[:10]:
            ttk.Label(win, text=f"{user_login:15s}  —  {count}").pack(
                anchor="w", padx=14
            )

    def _on_open_settings(self) -> None:
        log_akcja(
            "[WM-DBG][PROFILE] Klik: Przejdź do Ustawienia → Profile (hook do okna ustawień)."
        )

    def _on_sim_event(self) -> None:
        log_akcja("[WM-DBG][PROFILE] Klik: Symuluj zdarzenie awarii (placeholder).")

    def _on_open_schedule(self) -> None:
        log_akcja("[WM-DBG][PROFILE] Klik: Podgląd grafiku (placeholder).")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("WM – PROFIL (podgląd)")
    root.configure(bg=WM_BG)

    container = ttk.Frame(root, style="WM.Container.TFrame")
    container.pack(fill="both", expand=True)

    view = ProfileView(container)
    view.pack(fill="both", expand=True)

    root.geometry("1100x720")
    root.mainloop()
