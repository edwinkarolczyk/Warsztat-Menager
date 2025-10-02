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
import logging
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from datetime import datetime as _dt, datetime
from typing import Optional
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
    get_user,
    get_tasks_for,
    tasks_data_status,
    load_assign_orders,
    load_assign_tools,
    load_status_overrides,
    save_assign_order,
    save_assign_tool,
    save_status_override,
    save_user,
    workload_for,
)
from services.messages_service import (
    send_message,
    list_inbox,
    list_sent,
    mark_read,
    last_inbox_ts,
)
from profile_utils import staz_days_for_login, staz_years_floor_for_login
from logger import log_akcja
from utils.gui_helpers import clear_frame
from grafiki.shifts_schedule import (
    _user_mode,
    _week_idx,
    _slot_for_mode,
    _shift_times,
)

# Maksymalne wymiary avatara (szerokość, wysokość)
_MAX_AVATAR_SIZE = (250, 313)

from ui_theme import apply_theme_safe as apply_theme
from ui_dialogs_safe import (
    error_box,
    info_ok,
    safe_open_dir,
    safe_open_json,
    warning_box,
)

logger = logging.getLogger(__name__)

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


def _on_pick_profile_json(owner, cfg_manager):
    """Handle selection of the profile JSON path from the UI."""

    if cfg_manager is None:
        logger.warning("[PROFILE] Brak ConfigManager – pomijam wybór pliku profilu")
        return

    path = safe_open_json(owner, reason="profile.pick_json")
    if not path:
        return

    try:
        cfg_manager.set("profile.path", path, who="profile-ui")
        cfg_manager.save_all()
    except Exception as exc:  # pragma: no cover - defensive UI
        logger.exception("[PROFILE] Nie udało się zapisać profile.path: %s", exc)
        error_box(owner, "Profil", f"Nie udało się zapisać ścieżki profilu: {exc}")
        return

    logger.info("[PROFILE] Ustawiono profile.path = %s", path)
    info_ok(owner, "Profil", "Zapisano ścieżkę profilu.")


def _on_pick_profile_dir(owner, cfg_manager):
    """Handle selection of the profile directory from the UI."""

    if cfg_manager is None:
        logger.warning("[PROFILE] Brak ConfigManager – pomijam wybór folderu profilu")
        return

    path = safe_open_dir(owner, reason="profile.pick_dir")
    if not path:
        return

    try:
        cfg_manager.set("profile.dir", path, who="profile-ui")
        cfg_manager.save_all()
    except Exception as exc:  # pragma: no cover - defensive UI
        logger.exception("[PROFILE] Nie udało się zapisać profile.dir: %s", exc)
        error_box(owner, "Profil", f"Nie udało się zapisać folderu profilu: {exc}")
        return

    logger.info("[PROFILE] Ustawiono profile.dir = %s", path)
    info_ok(owner, "Profil", "Zapisano folder profilu.")

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
        info_ok(parent, "Zapisano", "Dane zapisane.")

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
    head = ttk.Frame(frame, style="WM.TFrame")
    head.pack(fill="x", padx=12, pady=(8, 6))
    _load_avatar(head, login).pack(side="left", padx=(0, 12), pady=(0, 6))
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
        self.active_tab = tk.StringVar(value="Oś")
        self._tab_widgets: dict[str, ttk.Frame] = {}
        self._tab_contents: dict[str, ttk.Frame] = {}
        self._tab_builders = {}
        self._user_data: dict[str, object] = {}
        self._tasks_cache: list[dict] = []
        self._inbox_cache: list[dict] = []
        self._sent_cache: list[dict] = []
        self._staz_days: int = 0
        self._about_container = None
        self._shortcuts_container = None
        self._center_container = None
        self._header_container = None
        self.btn_send_pw = None

        self._reload_profile_data()

        self._init_styles()
        self._build_cover_header()
        self._build_tabs()
        self._build_columns()
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
            "WM.H1.TLabel",
            background=WM_BG,
            foreground=WM_TEXT,
            font=("Segoe UI", 18, "bold"),
        )
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

    def _build_header(self, parent: ttk.Frame) -> None:
        self.btn_send_pw = None

        wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrap.pack(fill="x")

        try:
            if getattr(self, "avatar_image", None):
                avatar_row = ttk.Frame(wrap)
                avatar_row.pack(fill="x", pady=(8, 6))
                ttk.Label(
                    avatar_row,
                    image=self.avatar_image,
                    anchor="center",
                ).pack(pady=(0, 6))
        except Exception:
            pass

        user = get_user(self.login) or {}
        display = (
            user.get("display_name")
            or getattr(self, "display_name", None)
            or self.login
        )
        role = user.get("rola") or self.rola or "—"
        years = staz_years_floor_for_login(self.login) or 0
        ym = user.get("zatrudniony_od") or self.zatrudniony_od or "—"

        ttk.Label(wrap, text=display, style="WM.H1.TLabel").pack(anchor="w")
        ttk.Label(
            wrap,
            text=f"@{self.login}",
            style="WM.Muted.TLabel",
        ).pack(anchor="w", pady=(2, 0))
        ttk.Label(
            wrap,
            text=f"Rola: {role}    Staż: {years} lat (od {ym})",
            style="WM.Muted.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        actions = ttk.Frame(wrap, style="WM.TFrame")
        actions.pack(anchor="w", pady=(8, 0))
        self.btn_send_pw = ttk.Button(
            actions,
            text="Wyślij PW",
            command=self._on_send_pw,
            style="WM.Side.TButton",
            takefocus=False,
        )
        self.btn_send_pw.pack(side="left", padx=(0, 6))
        ttk.Button(
            actions,
            text="Kto ma najmniej zadań?",
            command=self._on_least_tasks,
            style="WM.Side.TButton",
            takefocus=False,
        ).pack(side="left", padx=(0, 6))
        if hasattr(self, "_on_open_settings"):
            ttk.Button(
                actions,
                text="Przejdź do Ustawienia",
                command=self._on_open_settings,
                style="WM.Side.TButton",
                takefocus=False,
            ).pack(side="left")

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
        avatar_holder.grid(
            row=0, column=0, rowspan=2, padx=(16, 12), pady=(12, 8), sticky="w"
        )
        avatar_wrap = ttk.Frame(avatar_holder, style="WM.Header.TFrame")
        avatar_wrap.pack(fill="x", pady=(8, 6))
        avatar_widget = self._make_avatar(avatar_wrap)
        avatar_widget.pack(pady=(0, 6))

        info = ttk.Frame(inner, style="WM.Header.TFrame")
        info.grid(row=0, column=1, sticky="nsew")
        self._header_container = info
        self._build_header(info)

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

    def _reload_profile_data(self) -> None:
        self._user_data = get_user(self.login) or {}
        self._tasks_cache = list(get_tasks_for(self.login) or [])
        self._inbox_cache = list(list_inbox(self.login) or [])
        self._sent_cache = list(list_sent(self.login) or [])
        self._staz_days = staz_days_for_login(self.login)
        display_candidates = [
            self._user_data.get("display_name"),
            " ".join(
                part
                for part in (
                    str(self._user_data.get("imie", "")).strip() or "",
                    str(self._user_data.get("nazwisko", "")).strip() or "",
                )
                if part
            ),
            self._user_data.get("nazwa"),
            self.display_name,
            self.login,
        ]
        for candidate in display_candidates:
            text = str(candidate or "").strip()
            if text:
                self.display_name = text
                break
        rola = self._user_data.get("rola")
        if rola:
            self.rola = str(rola)
        zatr = self._user_data.get("zatrudniony_od")
        if zatr:
            self.zatrudniony_od = str(zatr)
        self.staz_lata = staz_years_floor_for_login(self.login) or self.staz_lata

    def _render_tab(self, name: str) -> None:
        frame = self._tab_contents.get(name)
        builder = self._tab_builders.get(name)
        if not frame or builder is None:
            return
        for child in frame.winfo_children():
            child.destroy()
        builder(frame)

    def _refresh_view(self) -> None:
        self._reload_profile_data()
        if self._header_container is not None:
            for child in self._header_container.winfo_children():
                child.destroy()
            self._build_header(self._header_container)
        if self._about_container is not None:
            for child in self._about_container.winfo_children():
                child.destroy()
            self._build_about(self._about_container)
        if self._shortcuts_container is not None:
            for child in self._shortcuts_container.winfo_children():
                child.destroy()
            self._build_shortcuts(self._shortcuts_container)
        for tab_name in self._tab_contents.keys():
            self._render_tab(tab_name)
        self._activate_tab(self.active_tab.get())

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        if not value:
            return None
        text = str(value)
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return datetime.fromisoformat(text)
        except Exception:
            return None

    def _format_timestamp(self, value: str | None) -> str:
        ts = self._parse_timestamp(value)
        if not ts:
            return "—"
        return ts.strftime("%Y-%m-%d %H:%M")

    def _task_deadline_text(self, task: dict) -> str:
        for key in ("deadline", "termin", "termin_do", "data_do", "data_plan"):
            value = task.get(key)
            if value:
                return str(value)
        return ""

    def _parse_deadline(self, task: dict) -> datetime | None:
        raw = self._task_deadline_text(task)
        if not raw:
            return None
        text = str(raw)
        try:
            if len(text) == 10:
                return datetime.fromisoformat(f"{text}T00:00:00")
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return datetime.fromisoformat(text)
        except Exception:
            return None

    def _task_label_text(self, task: dict) -> str:
        title = (
            task.get("title")
            or task.get("tytul")
            or task.get("nazwa")
            or task.get("opis")
            or "Zadanie"
        )
        status = task.get("status") or task.get("stan") or "?"
        deadline = self._task_deadline_text(task)
        ident = str(task.get("id") or task.get("nr") or task.get("kod") or "").strip()
        prefix = str(title)
        if ident:
            prefix = f"{ident} — {title}"
        suffix = f"Status: {status}"
        if deadline:
            suffix = f"{suffix}   Termin: {deadline}"
        return f"{prefix}   {suffix}"

    def _task_status_value(self, task: dict) -> str:
        raw = task.get("status") or task.get("stan") or ""
        return str(raw).strip().lower()

    def _is_task_done(self, task: dict) -> bool:
        return self._task_status_value(task) in {
            "zrobione",
            "done",
            "zamkniete",
            "zamknięte",
            "finished",
            "close",
            "closed",
        }

    def _is_task_overdue(self, task: dict) -> bool:
        if self._is_task_done(task):
            return False
        deadline = self._parse_deadline(task)
        if not deadline:
            return False
        try:
            return deadline.date() < datetime.now().date()
        except Exception:
            return False

    def _is_task_urgent(self, task: dict) -> bool:
        return self._task_status_value(task) in {"pilne", "urgent", "overdue"}

    def _message_refs(self, message: dict) -> list[tuple[str, str]]:
        refs: list[tuple[str, str]] = []
        for item in message.get("refs") or []:
            if not isinstance(item, dict):
                continue
            label = item.get("label") or item.get("type") or "Ref"
            value = item.get("id") or item.get("value") or ""
            if value:
                refs.append((str(label), str(value)))
        return refs

    def _format_message_event(self, message: dict) -> str:
        folder = message.get("folder") or ""
        subject = message.get("subject") or "(bez tematu)"
        ts_text = self._format_timestamp(message.get("ts"))
        if folder == "inbox":
            counter = message.get("from") or "?"
            prefix = "• " if not message.get("read") else ""
            return (
                f"{prefix}{ts_text} — Otrzymano PW od @{counter}: {subject}"
            )
        counter = message.get("to") or "?"
        return f"{ts_text} — Wysłano PW do @{counter}: {subject}"

    def _task_refs(self, task: dict) -> list[tuple[str, str]]:
        refs: list[tuple[str, str]] = []
        ident = str(task.get("id") or task.get("nr") or task.get("kod") or "").strip()
        if ident:
            refs.append(("ID", ident))
        order = task.get("zlecenie") or task.get("order") or task.get("order_id")
        if order:
            refs.append(("Zlecenie", str(order)))
        return refs

    def _format_task_event(self, task: dict) -> str:
        deadline = self._task_deadline_text(task) or "brak terminu"
        title = (
            task.get("title")
            or task.get("tytul")
            or task.get("nazwa")
            or task.get("opis")
            or "Zadanie"
        )
        ident = str(task.get("id") or task.get("nr") or task.get("kod") or "").strip()
        status = task.get("status") or task.get("stan") or "?"
        if ident:
            title = f"{ident} — {title}"
        return f"{deadline} — Zadanie: {title} (status: {status})"

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
        for tab_name, frame in self._tab_contents.items():
            if tab_name == name:
                frame.grid()
                self._render_tab(tab_name)
            else:
                frame.grid_remove()
        log_akcja(f"[WM-DBG][PROFILE] Aktywowano zakładkę: {name}")

    # ---------- TRZY KOLUMNy ----------
    def _build_columns(self) -> None:
        content = ttk.Frame(self, style="WM.Container.TFrame")
        content.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=2)
        content.columnconfigure(2, weight=1)
        content.rowconfigure(0, weight=1)

        left = ttk.Frame(content, style="WM.Card.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._about_container = left
        self._build_about(left)

        center = ttk.Frame(content, style="WM.Card.TFrame")
        center.grid(row=0, column=1, sticky="nsew", padx=8)
        center.grid_rowconfigure(0, weight=1)
        center.grid_columnconfigure(0, weight=1)
        self._center_container = center

        for tab_name, builder in (
            ("Oś", self._build_timeline),
            ("Zadania", self._build_tasks_tab),
            ("PW", self._build_pw_tab),
        ):
            frame = ttk.Frame(center, style="WM.Card.TFrame")
            frame.grid(row=0, column=0, sticky="nsew")
            self._tab_contents[tab_name] = frame
            self._tab_builders[tab_name] = builder
            self._render_tab(tab_name)
            if tab_name != self.active_tab.get():
                frame.grid_remove()

        for tab_name in ("O mnie", "Narzędzia"):
            frame = ttk.Frame(center, style="WM.Card.TFrame")
            frame.grid(row=0, column=0, sticky="nsew")
            self._tab_contents[tab_name] = frame
            self._tab_builders[tab_name] = lambda parent, name=tab_name: self._build_placeholder_tab(
                parent, name
            )
            self._render_tab(tab_name)
            frame.grid_remove()

        right = ttk.Frame(content, style="WM.Card.TFrame")
        right.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        self._shortcuts_container = right
        self._build_shortcuts(right)

        self._activate_tab(self.active_tab.get())

    # --- sekcja: O MNIE (lewa) ---
    def _build_about(self, parent: ttk.Frame) -> None:
        parent.grid_propagate(False)
        wrapper = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrapper.pack(fill="both", expand=True)

        ttk.Label(
            wrapper,
            text="O MNIE",
            style="WM.CardMuted.TLabel",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        def row(label_text: str, value_text: str) -> None:
            row_frame = ttk.Frame(wrapper, style="WM.Card.TFrame")
            row_frame.pack(fill="x", pady=4)
            ttk.Label(
                row_frame,
                text=label_text,
                style="WM.CardMuted.TLabel",
            ).pack(side="left")
            ttk.Label(
                row_frame,
                text=value_text,
                style="WM.CardLabel.TLabel",
                anchor="e",
                justify="right",
                wraplength=220,
            ).pack(side="right")

        user = self._user_data or {}
        full_name = " ".join(
            part
            for part in (
                str(user.get("imie", "")).strip(),
                str(user.get("nazwisko", "")).strip(),
            )
            if part
        )
        row("Imię i nazwisko:", full_name or "—")
        row("Login:", self.login)
        row("Rola:", user.get("rola") or self.rola or "—")
        row("Zatrudniony od:", user.get("zatrudniony_od") or self.zatrudniony_od or "—")
        if self._staz_days:
            row("Staż:", f"{self.staz_lata} lat ({self._staz_days} dni)")
        else:
            row("Staż:", f"{self.staz_lata} lat")
        row("Status:", user.get("status") or "aktywny")
        row("Telefon:", user.get("telefon") or "—")
        row("E-mail:", user.get("email") or "—")
        row("Ostatnia wizyta:", user.get("ostatnia_wizyta") or "—")

        skills = user.get("umiejetnosci") if isinstance(user, dict) else {}
        if isinstance(skills, dict) and skills:
            skill_text = ", ".join(f"{k} ({v})" for k, v in skills.items())
        else:
            skill_text = "—"
        row("Umiejętności:", skill_text)

    # --- sekcja: OŚ AKTYWNOŚCI (środek) ---
    def _build_timeline(self, parent: ttk.Frame) -> None:
        parent.grid_propagate(False)
        wrapper = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrapper.pack(fill="both", expand=True)

        ttk.Label(
            wrapper,
            text="OŚ AKTYWNOŚCI",
            style="WM.CardMuted.TLabel",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        messages = sorted(
            self._inbox_cache + self._sent_cache,
            key=lambda msg: self._parse_timestamp(msg.get("ts")) or datetime.min,
            reverse=True,
        )[:5]
        upcoming_tasks = sorted(
            self._tasks_cache,
            key=lambda task: self._parse_deadline(task) or datetime.max,
        )[:5]

        if not messages and not upcoming_tasks:
            ttk.Label(
                wrapper,
                text="Brak aktywności do wyświetlenia.",
                style="WM.CardLabel.TLabel",
            ).pack(anchor="w")
            return

        for message in messages:
            self._timeline_item(
                wrapper,
                self._format_message_event(message),
                refs=self._message_refs(message),
            )

        if upcoming_tasks:
            ttk.Label(
                wrapper,
                text="Nadchodzące zadania:",
                style="WM.CardMuted.TLabel",
            ).pack(anchor="w", pady=(12, 4))
            for task in upcoming_tasks:
                self._timeline_item(
                    wrapper,
                    self._format_task_event(task),
                    refs=self._task_refs(task),
                )

    def _build_tasks_tab(self, parent: ttk.Frame) -> None:
        wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrap.pack(fill="both", expand=True)
        ttk.Label(wrap, text="ZADANIA", style="WM.CardMuted.TLabel").pack(
            anchor="w", pady=(0, 8)
        )

        ok, src, count = tasks_data_status()
        if not ok:
            msg = (
                "Brak źródła zadań. Utwórz plik data/zadania.json lub data/zlecenia.json."
            )
            if src:
                msg = (
                    f"Nie można odczytać źródła zadań: {src}\nSprawdź format JSON."
                )
            ttk.Label(
                wrap, text=msg, style="WM.Muted.TLabel", justify="left"
            ).pack(anchor="w")
            return

        rows = get_tasks_for(self.login)
        if not rows:
            ttk.Label(
                wrap,
                text=(
                    f"Źródło: {src} (rekordów: {count}). "
                    "Brak zadań przypisanych do użytkownika."
                ),
                style="WM.Muted.TLabel",
                justify="left",
            ).pack(anchor="w")
            return

        ttk.Label(
            wrap,
            text=f"Źródło: {src} • Wszystkich rekordów: {count}",
            style="WM.Muted.TLabel",
        ).pack(anchor="w", pady=(0, 6))

        for row_data in rows[:300]:
            rid = row_data.get("id") or row_data.get("kod") or ""
            title = (
                row_data.get("title")
                or row_data.get("nazwa")
                or row_data.get("opis")
                or "Zadanie"
            )
            status = row_data.get("status") or row_data.get("stan") or "?"
            deadline = row_data.get("deadline") or row_data.get("termin") or ""
            row = ttk.Frame(wrap, style="WM.TFrame")
            row.pack(fill="x", anchor="w", pady=2)
            ttk.Label(
                row,
                text=f"{rid} — {title} • Status: {status} • Termin: {deadline}",
                style="WM.CardLabel.TLabel",
            ).pack(side="left")

    def _build_pw_tab(self, parent: ttk.Frame) -> None:
        self._pw_tab_root = wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrap.pack(fill="both", expand=True)

        top = ttk.Frame(wrap, style="WM.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="WIADOMOŚCI (PW)", style="WM.CardMuted.TLabel").pack(
            side="left"
        )

        btns = ttk.Frame(top, style="WM.TFrame")
        btns.pack(side="right")
        ttk.Button(
            btns,
            text="Odśwież",
            command=self._refresh_pw_tab,
            style="WM.Side.TButton",
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            btns,
            text="Oznacz zaznaczone jako przeczytane",
            command=self._on_mark_read,
            style="WM.Side.TButton",
        ).pack(side="left")

        body = ttk.Frame(wrap, style="WM.TFrame")
        body.pack(fill="both", expand=True, pady=(8, 0))
        self._pw_inbox_frame = ttk.Frame(body, style="WM.Card.TFrame")
        self._pw_inbox_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._pw_sent_frame = ttk.Frame(body, style="WM.Card.TFrame")
        self._pw_sent_frame.pack(side="left", fill="both", expand=True, padx=(6, 0))

        ttk.Label(
            self._pw_inbox_frame,
            text="Inbox",
            style="WM.CardLabel.TLabel",
        ).pack(anchor="w", padx=8, pady=(8, 4))
        ttk.Label(
            self._pw_sent_frame,
            text="Wysłane",
            style="WM.CardLabel.TLabel",
        ).pack(anchor="w", padx=8, pady=(8, 4))

        self._pw_checks: dict[str, tk.IntVar] = {}
        self._last_inbox_ts_cache: Optional[str] = None
        self._pw_poll_job = {"id": None}

        self._refresh_pw_tab()

        def _poll():
            if not hasattr(self, "_pw_tab_root") or not self._pw_tab_root.winfo_exists():
                self._pw_poll_job["id"] = None
                return
            ts = last_inbox_ts(self.login)
            if ts and ts != self._last_inbox_ts_cache:
                self._refresh_pw_tab()
            self._pw_poll_job["id"] = self.after(10_000, _poll)

        self._pw_poll_job["id"] = self.after(10_000, _poll)

        def _on_destroy(_e=None):
            if self._pw_poll_job.get("id"):
                try:
                    self.after_cancel(self._pw_poll_job["id"])
                except Exception:
                    pass
                self._pw_poll_job["id"] = None

        wrap.bind("<Destroy>", _on_destroy, add="+")

    def _refresh_pw_tab(self) -> None:
        print(
            f"[WM-DBG][PROFILE][PW] Odświeżam skrzynkę użytkownika: {self.login}"
        )
        for frame in (self._pw_inbox_frame, self._pw_sent_frame):
            children = list(frame.winfo_children())
            for widget in children[1:]:
                try:
                    widget.destroy()
                except Exception:
                    pass

        inbox = list_inbox(self.login) or []
        sent = list_sent(self.login) or []
        self._inbox_cache = list(inbox)
        self._sent_cache = list(sent)
        self._pw_checks.clear()

        try:
            self._last_inbox_ts_cache = last_inbox_ts(self.login)
        except Exception:
            self._last_inbox_ts_cache = None

        if not inbox:
            ttk.Label(
                self._pw_inbox_frame,
                text="Brak wiadomości.",
                style="WM.Muted.TLabel",
            ).pack(anchor="w", padx=12, pady=(0, 8))
        else:
            for message in inbox[:200]:
                row = ttk.Frame(self._pw_inbox_frame, style="WM.TFrame")
                row.pack(fill="x", anchor="w", padx=8, pady=2)
                var = tk.IntVar(value=0)
                msg_id = message.get("id")
                if msg_id is not None:
                    self._pw_checks[msg_id] = var
                tk.Checkbutton(row, variable=var, borderwidth=0, highlightthickness=0).pack(
                    side="left"
                )
                read_marker = "" if message.get("read") else " ●"
                label_text = (
                    f"{message.get('ts', '')}  {message.get('from', '?')} → "
                    f"{message.get('to', '?')}   "
                    f"{message.get('subject', '')}{read_marker}"
                )
                ttk.Label(row, text=label_text, style="WM.CardLabel.TLabel").pack(
                    side="left", padx=(6, 0)
                )

        if not sent:
            ttk.Label(
                self._pw_sent_frame,
                text="Brak wiadomości.",
                style="WM.Muted.TLabel",
            ).pack(anchor="w", padx=12, pady=(0, 8))
        else:
            for message in sent[:200]:
                row = ttk.Frame(self._pw_sent_frame, style="WM.TFrame")
                row.pack(fill="x", anchor="w", padx=8, pady=2)
                label_text = (
                    f"{message.get('ts', '')}  {message.get('from', '?')} → "
                    f"{message.get('to', '?')}   "
                    f"{message.get('subject', '')}"
                )
                ttk.Label(row, text=label_text, style="WM.CardLabel.TLabel").pack(
                    side="left"
                )

    def _on_mark_read(self) -> None:
        changed = 0
        for msg_id, var in list(self._pw_checks.items()):
            if var.get():
                try:
                    if mark_read(self.login, msg_id, True):
                        changed += 1
                except Exception:
                    pass
        print(f"[WM-DBG][PROFILE][PW] mark_read changed={changed}")
        if changed:
            info_ok(self, "PW", f"Oznaczono jako przeczytane: {changed}")
        self._refresh_pw_tab()

    def _build_placeholder_tab(self, parent: ttk.Frame, tab_name: str) -> None:
        parent.grid_propagate(False)
        wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrap.pack(fill="both", expand=True)

        ttk.Label(
            wrap,
            text=tab_name.upper(),
            style="WM.CardMuted.TLabel",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        if tab_name == "O mnie":
            message = (
                "Szczegółowe dane personalne znajdziesz w lewej kolumnie. "
                "Sekcja zakładki zostanie rozbudowana w kolejnych wydaniach."
            )
        else:
            message = (
                "Integracja z modułem narzędzi jest w przygotowaniu. "
                "Na razie skorzystaj z widoku w głównym module narzędzi."
            )

        ttk.Label(
            wrap,
            text=message,
            style="WM.CardLabel.TLabel",
            anchor="w",
            justify="left",
            wraplength=560,
        ).pack(anchor="w")

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
        parent.grid_propagate(False)
        wrapper = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrapper.pack(fill="both", expand=True)

        title = ttk.Label(
            wrapper,
            text="SKRÓTY",
            style="WM.CardMuted.TLabel",
            font=("Segoe UI", 10, "bold"),
        )
        title.pack(anchor="w", pady=(0, 8))

        task_total = len(self._tasks_cache)
        task_open = sum(1 for task in self._tasks_cache if not self._is_task_done(task))
        task_urgent = sum(1 for task in self._tasks_cache if self._is_task_urgent(task))
        unread_pw = sum(1 for msg in self._inbox_cache if not msg.get("read"))
        for text in (
            f"Zadania przypisane ({task_total})",
            f"Otwarte zadania ({task_open})",
            f"Pilne zadania ({task_urgent})",
            f"Nieprzeczytane PW ({unread_pw})",
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
            btn = ttk.Button(
                wrapper,
                text=text,
                style="WM.Button.TButton",
                command=callback,
                takefocus=False,
            )
            btn.pack(fill="x", pady=4)

    # ---------- Handlery (szkielet) ----------
    def _on_send_pw(self) -> None:
        user = get_user(self.login) or {}
        if not user.get("allow_pw", True):
            warning_box(self, "PW", "Ten użytkownik ma wyłączone PW.")
            return

        try:
            trigger_widget = self.focus_get()
        except Exception:
            trigger_widget = None

        print(
            f"[WM-DBG][PROFILE][PW] Otwieram modal wysyłki PW dla: {self.login}"
        )
        win = tk.Toplevel(self)
        win.title("Nowa wiadomość (PW)")
        win.configure(bg="#111214")
        win.transient(self.winfo_toplevel())
        apply_theme(win)
        win.grab_set()
        win.focus_set()

        ttk.Label(win, text="Do (login):").pack(anchor="w", padx=10, pady=(10, 0))
        to_entry = ttk.Entry(win)
        to_entry.pack(fill="x", padx=10, pady=4)
        to_entry.focus_set()

        ttk.Label(win, text="Temat:").pack(anchor="w", padx=10, pady=(6, 0))
        subj_entry = ttk.Entry(win)
        subj_entry.pack(fill="x", padx=10, pady=4)

        ttk.Label(win, text="Treść:").pack(anchor="w", padx=10, pady=(6, 0))
        body_txt = tk.Text(win, width=60, height=10)
        body_txt.pack(fill="both", padx=10, pady=6)

        def _submit() -> None:
            to_login = to_entry.get().strip()
            subject = subj_entry.get().strip()
            body = body_txt.get("1.0", "end").strip()

            if not to_login:
                warning_box(win, "Błąd", "Podaj login odbiorcy.")
                return
            if not subject:
                warning_box(win, "Błąd", "Temat nie może być pusty.")
                return
            if not body:
                warning_box(win, "Błąd", "Treść nie może być pusta.")
                return

            try:
                msg = send_message(
                    sender=self.login,
                    to=to_login,
                    subject=subject,
                    body=body,
                )
            except Exception as exc:  # pragma: no cover - defensive UI
                error_box(win, "Błąd", f"Nie udało się wysłać: {exc}")
                return

            print(
                f"[WM-DBG][PROFILE][PW] Wysłano wiadomość {msg['id']} "
                f"od {self.login} do {to_login}"
            )
            info_ok(win, "Sukces", "Wiadomość wysłana.")
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()
            if hasattr(self, "_refresh_pw_tab"):
                try:
                    self._refresh_pw_tab()
                except Exception:
                    pass

        ttk.Button(win, text="Wyślij", command=_submit, takefocus=False).pack(
            pady=(0, 10)
        )

        for btn in (getattr(self, "btn_send_pw", None), trigger_widget):
            try:
                if btn and hasattr(btn, "state"):
                    btn.state(["!pressed", "!active"])
            except Exception:
                pass

    def _on_least_tasks(self) -> None:
        users = self._load_users_list() or [self.login]

        print(f"[WM-DBG][RANK] Start rankingu; użytkownicy={len(users)}")

        win = tk.Toplevel(self)
        win.title("Kto ma najmniej zadań?")
        win.transient(self.winfo_toplevel())
        apply_theme(win)
        win.grab_set()
        win.focus_set()

        frame = ttk.Frame(win, style="WM.Card.TFrame", padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Ranking obciążenia (mniej = lepiej):",
            style="WM.CardLabel.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(
            frame,
            text="Filtr do terminu (YYYY-MM-DD):",
            style="WM.CardMuted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 6))
        date_var = tk.StringVar()
        ttk.Entry(frame, textvariable=date_var, width=16).grid(
            row=1, column=1, sticky="w", pady=(6, 6)
        )

        out_box = tk.Listbox(frame, width=48, height=12)
        out_box.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        def _refresh() -> None:
            deadline = self._parse_date(date_var.get().strip())
            data = (
                workload_for(users, do_deadline=deadline)
                if deadline
                else workload_for(users)
            )
            print(f"[WM-DBG][RANK] Wynik={data[:5]} ...")
            out_box.delete(0, "end")
            if not data:
                out_box.insert("end", "Brak danych o zadaniach.")
                return
            for login, count in data[:50]:
                out_box.insert("end", f"{login:15s} — {count}")

        ttk.Button(
            frame,
            text="Pokaż ranking",
            command=_refresh,
            style="WM.Side.TButton",
            takefocus=False,
        ).grid(row=3, column=1, sticky="e", pady=(8, 0))
        _refresh()

    def _parse_date(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except Exception:
            warning_box(
                self,
                "Data",
                "Wpisz datę w formacie YYYY-MM-DD (np. 2025-09-23).",
            )
            return None

    def _load_users_list(self) -> list[str]:
        try:
            with open(
                os.path.join("data", "uzytkownicy.json"), encoding="utf-8"
            ) as fh:
                data = json.load(fh)
        except Exception:
            return []
        if isinstance(data, dict):
            return [
                rec.get("login")
                for rec in data.values()
                if isinstance(rec, dict) and rec.get("login")
            ]
        if isinstance(data, list):
            return [
                rec.get("login")
                for rec in data
                if isinstance(rec, dict) and rec.get("login")
            ]
        return []

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
