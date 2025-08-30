# Plik: gui_narzedzia.py
# Wersja pliku: 1.5.29
# Zmiany 1.5.29:
# - [MAGAZYN] Integracja z magazynem: przy oznaczeniu zadania jako wykonane zużywamy materiały (consume_for_task)
# - [MAGAZYN] Dodano import logika_zadan jako LZ
#
# Zmiany 1.5.28:
# - Dodano ręczny przełącznik (checkbox) „Przenieś do SN przy zapisie” dla narzędzi NN (001–499).
#   Widoczny tylko dla NOWE; aktywny jedynie dla roli uprawnionej (wg config narzedzia.uprawnienia.zmiana_klasy).
# - Opcja co zrobić z listą zadań przy konwersji: „pozostaw”, „podmień na serwis wg typu” (domyślnie), „dodaj serwis do istniejących”.
# - Usunięto dawny auto-prompt NN→SN przy statusie „sprawne” — teraz decyzja jest wyłącznie „ptaszkiem”.
# - Zachowano: sumowanie zadań po zmianie statusu (produkcja/serwis), blokada duplikatów, fix dublowania okienek.
#
# Uwaga: Historia dopisuje wpis o zmianie trybu: [tryb] NOWE -> [tryb] STARE.

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logika_zadan as LZ  # [MAGAZYN] zużycie materiałów dla zadań

# ===================== MOTYW (użytkownika) =====================
from ui_theme import apply_theme_safe as apply_theme
from utils.gui_helpers import clear_frame
from utils import error_dialogs
import logger

# ===================== STAŁE / USTALENIA (domyślne) =====================
CONFIG_PATH  = "config.json"
STATUSY_NOWE_DEFAULT  = ["projekt", "w budowie", "próby narzędzia", "odbiór", "sprawne"]
STATUSY_STARE_DEFAULT = ["sprawne", "do ostrzenia", "w ostrzeniu", "po ostrzeniu", "w naprawie", "uszkodzone", "wycofane"]

TASK_TEMPLATES_DEFAULT = [
    "Przegląd wizualny",
    "Czyszczenie i smarowanie",
    "Pomiar luzów",
    "Wymiana elementu roboczego",
    "Test na prasie",
]
STARE_CONVERT_TEMPLATES_DEFAULT = [
    "Przegląd wizualny",
    "Czyszczenie i smarowanie",
    "Pomiar luzów",
    "Wymiana elementu roboczego",
    "Test na prasie",
]

TYPY_NARZEDZI_DEFAULT = ["Tłoczące", "Wykrawające", "Postępowe", "Giętarka"]

# Statusy NN uznawane za fazę "produkcja" (lower)
NN_PROD_STATES = {
    "projekt","w budowie","1 próba","1 proba","2 próba","2 proba","próby narzędzia","proby narzedzia","odbiór","odbior"
}

# ===================== CONFIG / DEBUG =====================
def _load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.log_akcja(f"Błąd wczytywania {CONFIG_PATH}: {e}")
        error_dialogs.show_error_dialog("Config", f"Błąd wczytywania {CONFIG_PATH}: {e}")
        return {}

def _save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.log_akcja(f"Błąd zapisu {CONFIG_PATH}: {e}")
        error_dialogs.show_error_dialog("Config", f"Błąd zapisu {CONFIG_PATH}: {e}")

_CFG_CACHE = _load_config()
DEBUG = bool(os.environ.get("WM_DEBUG") or _CFG_CACHE.get("tryb_testowy"))

def _dbg(*args):
    if DEBUG:
        try:
            print("[narzedzia]", *args, flush=True)
        except Exception:
            pass

def _maybe_seed_config_templates():
    try:
        cfg = _load_config()
        changed = False
        if "szablony_zadan_narzedzia" not in cfg:
            cfg["szablony_zadan_narzedzia"] = TASK_TEMPLATES_DEFAULT[:]; changed = True
        if "szablony_zadan_narzedzia_stare" not in cfg:
            cfg["szablony_zadan_narzedzia_stare"] = STARE_CONVERT_TEMPLATES_DEFAULT[:]; changed = True
        if "typy_narzedzi" not in cfg:
            cfg["typy_narzedzi"] = TYPY_NARZEDZI_DEFAULT[:]; changed = True
        if changed:
            _save_config(cfg)
            _dbg("Dosiano brakujące klucze (szablony/typy) w config.json")
    except Exception as e:
        _dbg("Błąd seedowania config:", e)

def _clean_list(lst):
    out, seen = [], set()
    if isinstance(lst, list):
        for x in lst:
            s = str(x).strip()
            sl = s.lower()
            if s and sl not in seen:
                seen.add(sl); out.append(s)
    return out

def _task_templates_from_config():
    try:
        cfg = _load_config()
        lst = _clean_list(cfg.get("szablony_zadan_narzedzia"))
        return lst or TASK_TEMPLATES_DEFAULT
    except Exception:
        return TASK_TEMPLATES_DEFAULT

def _stare_convert_templates_from_config():
    try:
        cfg = _load_config()
        lst = _clean_list(cfg.get("szablony_zadan_narzedzia_stare"))
        return lst or STARE_CONVERT_TEMPLATES_DEFAULT
    except Exception:
        return STARE_CONVERT_TEMPLATES_DEFAULT

def _types_from_config():
    try:
        cfg = _load_config()
        lst = _clean_list(cfg.get("typy_narzedzi"))
        return lst or TYPY_NARZEDZI_DEFAULT
    except Exception:
        return TYPY_NARZEDZI_DEFAULT

def _append_type_to_config(new_type: str) -> bool:
    t = (new_type or "").strip()
    if not t:
        return False
    cfg = _load_config()
    cur = _clean_list(cfg.get("typy_narzedzi")) or []
    if t.lower() in [x.lower() for x in cur]:
        return False
    cur.append(t)
    cfg["typy_narzedzi"] = cur
    _save_config(cfg)
    _dbg("Dopisano typ do config:", t)
    return True

# ===== Uprawnienia z config =====
def _can_convert_nn_to_sn(rola: str | None) -> bool:
    """Sprawdza uprawnienie narzedzia.uprawnienia.zmiana_klasy: 'brygadzista' | 'brygadzista_serwisant'."""
    cfg = _load_config()
    setg = (((cfg.get("narzedzia") or {}).get("uprawnienia") or {}).get("zmiana_klasy") or "brygadzista").strip().lower()
    if setg == "brygadzista_serwisant":
        allowed = {"brygadzista", "serwisant"}
    else:
        allowed = {"brygadzista"}
    # zawsze przepuść „admin” jeśli używacie takiej roli
    if (rola or "").lower() in {"admin"}:
        return True
    return (rola or "").lower() in allowed

# ===== Zadania per typ (wg specy) =====
def _tasks_for_type(typ: str, phase: str):
    """
    phase: 'produkcja' | 'serwis'
    Czyta z config['narzedzia']['typy'][typ][phase], z fallbackiem na płaskie listy.
    """
    cfg = _load_config()
    try:
        narz = cfg.get("narzedzia", {})
        typy = narz.get("typy", {})
        entry = typy.get(typ)
        if not entry:
            for k in typy.keys():
                if str(k).strip().lower() == str(typ).strip().lower():
                    entry = typy[k]; break
        if entry:
            out = _clean_list(entry.get(phase))
            if out:
                return out
    except Exception as e:
        _dbg("Błąd odczytu narzedzia.typy:", e)

    if phase == "produkcja":
        return _task_templates_from_config()
    else:
        return _stare_convert_templates_from_config()

# ===================== ŚCIEŻKI DANYCH =====================
def _resolve_tools_dir():
    cfg = _load_config()
    base = (cfg.get("sciezka_danych") or "").strip()
    if base and not os.path.isabs(base):
        base = os.path.normpath(base)
    folder = os.path.join(base, "narzedzia") if base else "narzedzia"
    return folder

def _ensure_folder():
    folder = _resolve_tools_dir()
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

# ===================== STATUSY / NORMALIZACJA =====================
def _statusy_for_mode(mode):
    cfg = _load_config()
    if mode == "NOWE":
        lst = _clean_list(cfg.get("statusy_narzedzi_nowe")) or _clean_list(cfg.get("statusy_narzedzi")) or STATUSY_NOWE_DEFAULT[:]
    else:
        lst = _clean_list(cfg.get("statusy_narzedzi_stare")) or _clean_list(cfg.get("statusy_narzedzi")) or STATUSY_STARE_DEFAULT[:]
    if "sprawne" not in [x.lower() for x in lst]:
        lst = lst + ["sprawne"]
    return lst

def _normalize_status(s: str) -> str:
    sl = (s or "").strip().lower()
    if sl in ("na produkcji", "działające", "dzialajace"):
        return "sprawne"
    return (s or "").strip()

# ===================== I/O narzędzi =====================
def _existing_numbers():
    folder = _resolve_tools_dir()
    if not os.path.isdir(folder):
        return set()
    nums = set()
    for f in os.listdir(folder):
        if f.endswith(".json") and f[:-5].isdigit():
            nums.add(f[:-5].zfill(3))
    return nums

def _is_taken(nr3):
    return nr3.zfill(3) in _existing_numbers()

def _next_free_in_range(start, end):
    used = _existing_numbers()
    i = max(1, int(start))
    while i <= end:
        cand = f"{i:03d}"
        if cand not in used:
            return cand
        i += 1
    return None

def _legacy_parse_tasks(zadania_txt):
    out = []
    if not zadania_txt:
        return out
    for raw in [s.strip() for s in zadania_txt.replace("\n", ",").split(",") if s.strip()]:
        done = raw.startswith("[x]")
        title = raw[3:].strip() if done else raw
        out.append({"tytul": title, "done": done, "by": "", "ts_done": ""})
    return out

def _read_tool(numer_3):
    folder = _resolve_tools_dir()
    p = os.path.join(folder, f"{numer_3}.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _dbg("Błąd odczytu narzędzia", p, e)
        return None

def _save_tool(data):
    _ensure_folder()
    obj = dict(data)
    obj["numer"] = str(obj.get("numer", "")).zfill(3)
    folder = _resolve_tools_dir()
    path = os.path.join(folder, f"{obj['numer']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    _dbg("Zapisano narzędzie:", path)

def _iter_folder_items():
    items = []
    folder = _resolve_tools_dir()
    if not os.path.isdir(folder):
        _dbg("Folder narzędzi nie istnieje:", folder)
        return items
    files = [fn for fn in os.listdir(folder) if fn.endswith(".json")]
    if not files:
        _dbg("Brak plików w folderze narzędzi:", folder)
        return items
    for fname in files:
        path = os.path.join(folder, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            tasks = d.get("zadania", [])
            if isinstance(tasks, str):
                tasks = _legacy_parse_tasks(tasks)
            total = len(tasks)
            done = sum(1 for t in tasks if t.get("done"))
            postep = int(done * 100 / total) if total else 0
            items.append({
                "nr": str(d.get("numer", fname[:-5])).zfill(3),
                "nazwa": d.get("nazwa", ""),
                "typ": d.get("typ", ""),
                "status": d.get("status", ""),
                "data": d.get("data_dodania", ""),
                "zadania": tasks,
                "postep": postep,
                "tryb": d.get("tryb", ""),
                "interwencje": d.get("interwencje", []),
                "historia": d.get("historia", []),
                "opis": d.get("opis", ""),
                "pracownik": d.get("pracownik", ""),
            })
        except Exception as e:
            _dbg("Błąd wczytania pliku:", path, e)
    return items

def _iter_legacy_json_items():
    cfg = _load_config()
    cands = []
    p_cfg_flat = cfg.get("paths.narzedzia")
    base = (cfg.get("sciezka_danych") or "").strip()
    p_in_base = os.path.join(base, "narzedzia.json") if base else None
    p_cwd = "narzedzia.json"

    for p in [p_cfg_flat, p_in_base, p_cwd]:
        if p and os.path.isfile(p):
            cands.append(p)

    items = []
    if not cands:
        _dbg("Legacy narzedzia.json – brak kandydata do odczytu")
        return items

    picked = cands[0]
    _dbg("Wczytuję LEGACY z pliku:", picked)

    try:
        with open(picked, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        _dbg("Błąd odczytu legacy:", picked, e)
        return items

    if isinstance(data, list):
        src_list = data
    elif isinstance(data, dict) and isinstance(data.get("narzedzia"), list):
        src_list = data["narzedzia"]
    elif isinstance(data, dict):
        src_list = []
        for k, v in data.items():
            if isinstance(v, dict):
                v2 = dict(v)
                v2.setdefault("numer", k)
                src_list.append(v2)
    else:
        _dbg("Legacy plik ma nieobsługiwany format")
        return items

    for d in src_list:
        try:
            tasks = d.get("zadania", [])
            if isinstance(tasks, str):
                tasks = _legacy_parse_tasks(tasks)
            total = len(tasks)
            done = sum(1 for t in tasks if t.get("done"))
            postep = int(done * 100 / total) if total else 0
            items.append({
                "nr": str(d.get("numer", "") or d.get("nr","")).zfill(3) if (d.get("numer") or d.get("nr")) else "",
                "nazwa": d.get("nazwa", ""),
                "typ": d.get("typ", ""),
                "status": d.get("status", ""),
                "data": d.get("data_dodania", d.get("data","")),
                "zadania": tasks,
                "postep": postep,
                "tryb": d.get("tryb", ""),
                "interwencje": d.get("interwencje", []),
                "historia": d.get("historia", []),
                "opis": d.get("opis", ""),
                "pracownik": d.get("pracownik", ""),
            })
        except Exception as e:
            _dbg("Błąd parsowania pozycji legacy:", e)
    return items

def _load_all_tools():
    _dbg("CWD:", os.getcwd())
    tools_dir = _resolve_tools_dir()
    _dbg("tools_dir:", tools_dir)

    items = _iter_folder_items()
    if items:
        _dbg("Załadowano z folderu:", len(items), "szt.")
        items.sort(key=lambda x: x["nr"])
        return items

    legacy = _iter_legacy_json_items()
    if legacy:
        _dbg("Załadowano LEGACY z narzedzia.json:", len(legacy), "szt.")
        legacy.sort(key=lambda x: x["nr"])
        return legacy

    _dbg("Brak narzędzi do wyświetlenia (folder i legacy puste).")
    return []

# ===================== POSTĘP =====================
def _bar_text(percent):
    try:
        p = int(percent)
    except Exception:
        p = 0
    p = max(0, min(100, p))
    filled = p // 10
    empty = 10 - filled
    return ("■" * filled) + ("□" * empty) + f"  {p}%"

def _band_tag(percent):
    try:
        p = int(percent)
    except Exception:
        p = 0
    p = max(0, min(100, p))
    if p == 0: return "p0"
    if p <= 25: return "p25"
    if p <= 75: return "p75"
    return "p100"

# ===================== POMOCNICZE – faza pracy dla statusu =====================
def _phase_for_status(tool_mode: str, status_text: str) -> str | None:
    stl = (status_text or "").strip().lower()
    if tool_mode == "NOWE" and stl in NN_PROD_STATES:
        return "produkcja"
    if stl == "w serwisie":
        return "serwis"
    return None

# ===================== UI GŁÓWNY =====================
def panel_narzedzia(root, frame, login=None, rola=None):
    _maybe_seed_config_templates()
    apply_theme(root)
    clear_frame(frame)

    header = ttk.Frame(frame, style="WM.TFrame")
    header.pack(fill="x", padx=10, pady=(10, 0))
    ttk.Label(header, text="🔧 Narzędzia", style="WM.H1.TLabel").pack(side="left")

    search_var = tk.StringVar()
    ttk.Entry(header, textvariable=search_var, width=36, style="WM.Search.TEntry").pack(side="right", padx=(8, 0))

    btn_add = ttk.Button(header, text="Dodaj", style="WM.Side.TButton")
    btn_add.pack(side="right", padx=(0, 8))

    wrap = ttk.Frame(frame, style="WM.Card.TFrame")
    wrap.pack(fill="both", expand=True, padx=10, pady=10)

    columns = ("nr", "nazwa", "typ", "status", "data", "postep")
    headers = {"nr":"Nr","nazwa":"Nazwa","typ":"Typ","status":"Status aktualny","data":"Data","postep":"Postęp (10 kratek)"}
    widths  = {"nr":80,"nazwa":240,"typ":170,"status":160,"data":150,"postep":220}

    tree = ttk.Treeview(wrap, columns=columns, show="headings", style="WM.Treeview")
    for c in columns:
        tree.heading(c, text=headers[c])
        tree.column(c, width=widths[c], anchor="w")
    tree.pack(fill="both", expand=True)

    tree.tag_configure("p0",   foreground="#9aa0a6")
    tree.tag_configure("p25",  foreground="#d93025")
    tree.tag_configure("p75",  foreground="#f9ab00")
    tree.tag_configure("p100", foreground="#188038")

    row_data = {}

    def refresh_list(*_):
        tree.delete(*tree.get_children()); row_data.clear()
        q = (search_var.get() or "").strip().lower()
        data = _load_all_tools()
        for t in data:
            blob = ("%s %s %s %s %s %s %s %s" % (
                t["nr"], t["nazwa"], t["typ"], t["status"], t["data"], t["postep"], t.get("tryb",""), t.get("opis","")
            )).lower()
            if q and q not in blob:
                continue
            tag = _band_tag(t["postep"])
            bar = _bar_text(t["postep"])
            iid = tree.insert("", "end", values=(t["nr"], t["nazwa"], t["typ"], t["status"], t["data"], bar), tags=(tag,))
            row_data[iid] = t
        if not data:
            _dbg("Lista narzędzi pusta – filtr:", q or "(brak)")

    # ===================== POPUP WYBORU TRYBU =====================
    def choose_mode_and_add():
        dlg = tk.Toplevel(root); dlg.title("Dodaj narzędzie – wybierz tryb")
        apply_theme(dlg)
        dlg.bind("<Return>", lambda e: None)
        frm = ttk.Frame(dlg, padding=10, style="WM.Card.TFrame"); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Jakie narzędzie chcesz dodać?", style="WM.Card.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,6))
        var = tk.StringVar(value="NOWE")
        ttk.Radiobutton(frm, text="Nowe (001–499)", variable=var, value="NOWE").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(frm, text="Stare/produkcyjne (500–1000)", variable=var, value="STARE").grid(row=2, column=0, sticky="w")
        btns = ttk.Frame(frm, style="WM.TFrame"); btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8,0))
        ttk.Button(btns, text="Anuluj", command=dlg.destroy, style="WM.Side.TButton").pack(side="right", padx=(0,8))
        ttk.Button(btns, text="Dalej", command=lambda: (dlg.destroy(), open_tool_dialog(None, var.get())), style="WM.Side.TButton").pack(side="right")

    # ===================== DIALOG DODAWANIA / EDYCJI =====================
    def open_tool_dialog(tool, mode=None):
        editing = tool is not None
        if editing:
            try:
                tool_mode = tool.get("tryb") or ("NOWE" if int(str(tool.get("nr","000"))) < 500 else "STARE")
            except Exception:
                tool_mode = "NOWE"
        else:
            tool_mode = mode or "NOWE"

        if tool_mode == "NOWE":
            range_lo, range_hi = 1, 499
            statusy = _statusy_for_mode("NOWE")
        else:
            range_lo, range_hi = 500, 1000
            statusy = _statusy_for_mode("STARE")

        start = tool or {
            "nr": None,
            "nazwa": "",
            "typ": "",
            "status": statusy[0] if statusy else "",
            "opis": "",
            "pracownik": login or "",
            "zadania": [],
            "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "tryb": tool_mode,
            "interwencje": [],
            "historia": [],
            "kategoria": "",
            "is_old": False,
        }

        nr_auto = start.get("nr")
        if nr_auto:
            nr_auto = str(nr_auto).zfill(3)
        else:
            nr_auto = _next_free_in_range(range_lo, range_hi)
        if not nr_auto:
            nr_auto = ""

        dlg = tk.Toplevel(root); dlg.title(("Edytuj" if editing else "Dodaj") + " – " + tool_mode)
        apply_theme(dlg)
        dlg.bind("<Return>", lambda e: None)
        nb = ttk.Notebook(dlg, style="TNotebook"); nb.pack(fill="both", expand=True)

        # --- OGÓLNE ---
        frm = ttk.Frame(nb, padding=10, style="WM.Card.TFrame"); nb.add(frm, text="Ogólne")

        # ===== HISTORIA (kompakt, toggle) =====
        hist_frame = ttk.Frame(frm, style="WM.TFrame")
        hist_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0,6))
        ttk.Label(hist_frame, text="Historia (najnowsze na górze)", style="WM.Card.TLabel").pack(side="left")
        hist_shown = [True]
        btn_toggle = ttk.Button(hist_frame, text="Schowaj", style="WM.Side.TButton")
        btn_toggle.pack(side="right")

        hist_cols = ("ts","by","z","na")
        hist_view = ttk.Treeview(frm, columns=hist_cols, show="headings", height=4, style="WM.Treeview")
        for c, txt, w in (("ts","Kiedy",160),("by","Kto",120),("z","Z",140),("na","Na",140)):
            hist_view.heading(c, text=txt); hist_view.column(c, width=w, anchor="w")
        hist_view.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0,10))

        hist_items = list((tool.get("historia") if editing else []) or [])
        def repaint_hist():
            hist_view.delete(*hist_view.get_children())
            for h in reversed(hist_items[-50:]):
                ts = h.get("ts",""); by = h.get("by",""); z = h.get("z",""); na = h.get("na","")
                hist_view.insert("", "end", values=(ts, by, z, na))
        repaint_hist()

        def toggle_hist():
            if hist_shown[0]:
                hist_view.grid_remove(); btn_toggle.config(text="Pokaż")
            else:
                hist_view.grid(); btn_toggle.config(text="Schowaj")
            hist_shown[0] = not hist_shown[0]
        btn_toggle.configure(command=toggle_hist)

        # ===== POLA OGÓLNE =====
        var_nr = tk.StringVar(value=str(nr_auto))
        var_nm = tk.StringVar(value=start.get("nazwa",""))
        var_st = tk.StringVar(value=start.get("status", statusy[0] if statusy else ""))
        var_op = tk.StringVar(value=start.get("opis",""))
        var_pr = tk.StringVar(value=start.get("pracownik", login or ""))

        # ostatnio obsłużony status (do gardy)
        last_applied_status = [ (start.get("status") or "").strip() ]
        # status poprzedni (do historii/przyszłych reguł)
        last_status = [ (start.get("status") or "").strip() ]
        move_to_sn = [False]

        r = 2
        def row(lbl, widget):
            nonlocal r
            ttk.Label(frm, text=lbl, style="WM.Card.TLabel").grid(row=r, column=0, sticky="w")
            widget.grid(row=r, column=1, sticky="ew", pady=2)
            r += 1

        row("Numer (3 cyfry)", ttk.Entry(frm, textvariable=var_nr, style="WM.Search.TEntry"))
        row("Nazwa",           ttk.Entry(frm, textvariable=var_nm, style="WM.Search.TEntry"))

        # === Typ (Combobox + ➕ do listy) ===
        typy_list = _types_from_config()
        typ_frame = ttk.Frame(frm, style="WM.TFrame")
        cb_ty = ttk.Combobox(typ_frame, values=typy_list, state="normal", width=28)
        start_typ = start.get("typ","")
        if start_typ:
            cb_ty.set(start_typ)
        cb_ty.pack(side="left")
        def _add_type():
            try:
                val = (cb_ty.get() or "").strip()
                if not val:
                    messagebox.showinfo("Typ", "Podaj nazwę typu."); return
                if _append_type_to_config(val):
                    messagebox.showinfo("Typ", f"Dodano '{val}' do listy typów.")
                    cb_ty.config(values=_types_from_config())
                else:
                    messagebox.showinfo("Typ", f"'{val}' już jest na liście.")
            except Exception as e:
                messagebox.showwarning("Typ", f"Nie udało się dopisać typu: {e}")
        ttk.Button(typ_frame, text="➕ do listy", style="WM.Side.TButton", command=_add_type).pack(side="left", padx=6)
        row("Typ", typ_frame)

        cb_status = ttk.Combobox(frm, textvariable=var_st, values=statusy, state="readonly")
        row("Status", cb_status)
        row("Opis",   ttk.Entry(frm, textvariable=var_op, style="WM.Search.TEntry"))
        row("Pracownik", ttk.Entry(frm, textvariable=var_pr, style="WM.Search.TEntry"))

        # ===== Konwersja NN→SN (tylko dla NOWE) =====
        convert_var = tk.BooleanVar(value=False)
        convert_tasks_var = tk.StringVar(value="replace")  # 'keep' | 'replace' | 'sum'
        conv_frame = ttk.Frame(frm, style="WM.TFrame")
        chk = ttk.Checkbutton(conv_frame, text="Przenieś do SN przy zapisie", variable=convert_var)
        chk.pack(side="left")
        ttk.Label(conv_frame, text="  Zadania po konwersji:", style="WM.Muted.TLabel").pack(side="left", padx=(8,4))
        cb_conv = ttk.Combobox(conv_frame, values=["pozostaw", "podmień na serwis wg typu", "dodaj serwis do istniejących"], state="readonly", width=28)
        cb_conv.current(1)  # domyślnie "podmień"
        def _sync_conv_mode(*_):
            lab = (cb_conv.get() or "").strip().lower()
            if lab.startswith("pozostaw"):
                convert_tasks_var.set("keep")
            elif lab.startswith("dodaj"):
                convert_tasks_var.set("sum")
            else:
                convert_tasks_var.set("replace")
        cb_conv.bind("<<ComboboxSelected>>", _sync_conv_mode)
        cb_conv.pack(side="left", padx=(0,0))

        # uprawnienia i widoczność
        if tool_mode == "NOWE":
            allowed = _can_convert_nn_to_sn(rola)
            chk.state(["!alternate"])
            if not allowed:
                try:
                    chk.state(["disabled"])
                    cb_conv.state(["disabled"])
                except Exception:
                    pass
                ttk.Label(conv_frame, text=" (wymaga roli brygadzisty)", style="WM.Muted.TLabel").pack(side="left", padx=(6,0))
            row("Konwersja NN→SN", conv_frame)

        # ===== Zadania (lista) =====
        ttk.Label(frm, text="Zadania narzędzia", style="WM.Card.TLabel").grid(row=r, column=0, sticky="w", pady=(8,2)); r += 1
        tasks_frame = ttk.Frame(frm, style="WM.Card.TFrame"); tasks_frame.grid(row=r, column=0, columnspan=2, sticky="nsew")
        frm.rowconfigure(r, weight=1); frm.columnconfigure(1, weight=1)

        task_cols = ("tytul","done","by","ts")
        tv = ttk.Treeview(tasks_frame, columns=task_cols, show="headings", height=7, style="WM.Treeview")
        for c, txt, w in (("tytul","Tytuł",320),("done","Status",90),("by","Wykonał",120),("ts","Kiedy",160)):
            tv.heading(c, text=txt); tv.column(c, width=w, anchor="w")
        tv.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(tasks_frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y")

        tasks = []
        for t in start.get("zadania", []):
            tasks.append({
                "tytul": t.get("tytul",""),
                "done": bool(t.get("done")),
                "by": t.get("by",""),
                "ts_done": t.get("ts_done",""),
                "komentarz": t.get("komentarz", "")
            })

        def _has_title(title: str) -> bool:
            tl = (title or "").strip().lower()
            return any((t.get("tytul","").strip().lower() == tl) for t in tasks)

        def repaint_tasks():
            tv.delete(*tv.get_children())
            for t in tasks:
                tv.insert("", "end", values=(t["tytul"], ("✔" if t["done"] else "—"), t["by"], t["ts_done"]))
        repaint_tasks()

        # ---- OPERACJE NA LISTACH ZADAŃ (faza) ----
        def _apply_template_for_phase(phase: str):
            typ_val = (cb_ty.get() or "").strip()
            if not typ_val:
                messagebox.showinfo("Zadania", "Najpierw wybierz 'Typ' narzędzia.")
                return
            tpl = _tasks_for_type(typ_val, phase)
            if not tpl:
                messagebox.showinfo("Zadania", f"Brak zdefiniowanych zadań dla typu „{typ_val}” ({phase}).")
                return
            missing = [t for t in tpl if not _has_title(t)]
            if not missing:
                return
            for m in missing:
                tasks.append({"tytul": m, "done": False, "by": "", "ts_done": ""})
            repaint_tasks()

        # ---- REAKCJA NA ZMIANĘ STATUSU ----
        def _on_status_change(_=None):
            new_st = (var_st.get() or "").strip()
            # garda: jeśli to samo co ostatnio obsłużone, nic nie rób
            if new_st == (last_applied_status[0] or ""):
                return
            phase = _phase_for_status(tool_mode, new_st)
            if phase:
                _apply_template_for_phase(phase)
            if new_st.lower() == "odbiór zakończony":
                if messagebox.askyesno("Przenieść do SN?", "Przenieść do SN?"):
                    move_to_sn[0] = True
                    for t in tasks:
                        if not t.get("done"):
                            _mark_done(t, "system")
                            t["komentarz"] = "Oznaczono przy przeniesieniu do SN"
                    repaint_tasks()
            last_status[0] = new_st
            last_applied_status[0] = new_st

        cb_status.bind("<<ComboboxSelected>>", _on_status_change)
        # (bez '<FocusOut>' – żeby nie dublować)

        # Pasek narzędzi do zadań (manualnie też można)
        tools_bar = ttk.Frame(frm, style="WM.TFrame"); tools_bar.grid(row=r+1, column=0, columnspan=2, sticky="ew", pady=(6,0))
        tmpl_var = tk.StringVar()
        tmpl_box = ttk.Combobox(tools_bar, textvariable=tmpl_var, values=_task_templates_from_config(), state="readonly", width=36)
        tmpl_box.pack(side="left")

        def _add_from_template(sel):
            s = (sel or "").strip()
            if not s: return
            if _has_title(s):
                messagebox.showinfo("Zadania", "Takie zadanie już istnieje."); return
            tasks.append({"tytul": s, "done": False, "by": "", "ts_done": ""})
            repaint_tasks()

        ttk.Button(tools_bar, text="Dodaj z listy", style="WM.Side.TButton",
                   command=lambda: (_add_from_template(tmpl_var.get()))).pack(side="left", padx=(6,0))
        ttk.Button(tools_bar, text="Dodaj z typu (dla bieżącej fazy)", style="WM.Side.TButton",
                   command=lambda: (_apply_template_for_phase(_phase_for_status(tool_mode, var_st.get()) or ("produkcja" if tool_mode=="NOWE" else "serwis")))).pack(side="left", padx=(6,0))

        new_var = tk.StringVar()
        ttk.Entry(tools_bar, textvariable=new_var, width=28, style="WM.Search.TEntry").pack(side="left", padx=(12,6))
        def _add_task(var):
            t = (var.get() or "").strip()
            if not t: return
            if _has_title(t):
                messagebox.showinfo("Zadania", "Takie zadanie już istnieje."); return
            tasks.append({"tytul": t, "done": False, "by": "", "ts_done": ""})
            var.set(""); repaint_tasks()
        ttk.Button(tools_bar, text="Dodaj własne", style="WM.Side.TButton",
                   command=lambda: _add_task(new_var)).pack(side="left")
        def _sel_idx():
            iid = tv.focus()
            if not iid: return -1
            vals = tv.item(iid, "values")
            if not vals: return -1
            title = vals[0]
            for i, t in enumerate(tasks):
                if t["tytul"] == title: return i
            return -1
        def _del_sel():
            i = _sel_idx()
            if i < 0: return
            tasks.pop(i); repaint_tasks()
        def _mark_done(t, by_fallback="nieznany"):
            t["done"] = True
            t["by"] = login or by_fallback
            t["ts_done"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            # [MAGAZYN] zużycie materiałów powiązanych z zadaniem / BOM
            try:
                zuzyte = LZ.consume_for_task(tool_id=str(nr_auto), task=t, uzytkownik=login or "system")
                if zuzyte:
                    t["zuzyte_materialy"] = (t.get("zuzyte_materialy") or []) + list(zuzyte)
            except Exception as _e:
                try:
                    _dbg("[MAGAZYN] błąd zużycia", _e)
                except Exception:
                    pass

        def _unmark_done(t):
            t["done"] = False
            t["by"] = ""
            t["ts_done"] = ""

        def _toggle_done():
            i = _sel_idx()
            if i < 0:
                return
            t = tasks[i]
            if t.get("done"):
                _unmark_done(t)
            else:
                _mark_done(t)
            repaint_tasks()
        ttk.Button(tools_bar, text="Usuń zaznaczone", style="WM.Side.TButton",
                   command=_del_sel).pack(side="left", padx=(6,0))
        ttk.Button(tools_bar, text="Oznacz/Cofnij ✔", style="WM.Side.TButton",
                   command=_toggle_done).pack(side="left", padx=(6,0))

        # --- PRZYCISKI ZAPISU ---
        btns = ttk.Frame(dlg, padding=8, style="WM.TFrame"); btns.pack(fill="x")

        def _suggest_after(n, mode_local):
            if mode_local == "NOWE":
                nxt = _next_free_in_range(max(1, n+1), 499)
            else:
                nxt = _next_free_in_range(max(500, n+1), 1000)
            return nxt or "—"

        def save():
            raw = (var_nr.get() or "").strip()
            numer = (f"{int(raw):03d}") if raw.isdigit() else raw.zfill(3)
            if (not numer.isdigit()) or len(numer) != 3:
                error_dialogs.show_error_dialog("Błąd", "Numer musi mieć dokładnie 3 cyfry (np. 001).")
                return
            nint = int(numer)

            if tool_mode == "NOWE" and not (1 <= nint <= 499):
                error_dialogs.show_error_dialog("Błąd", "Dla trybu NOWE numer 001–499.")
                return
            if tool_mode == "STARE" and not (500 <= nint <= 1000):
                error_dialogs.show_error_dialog("Błąd", "Dla trybu STARE numer 500–1000.")
                return

            current_nr = str(start.get("nr","")).zfill(3) if editing else None
            if _is_taken(numer) and (not editing or numer != current_nr):
                exist = _read_tool(numer) or {}
                messagebox.showwarning(
                    "Duplikat numeru",
                    "Narzędzie %s już istnieje.\nNazwa: %s\nTyp: %s\nStatus: %s\n\nWybierz inny numer (np. %s)." % (
                        numer, exist.get("nazwa","—"), exist.get("typ","—"),
                        exist.get("status","—"), _suggest_after(nint, tool_mode)
                    )
                )
                return

            nazwa = (var_nm.get() or "").strip()
            typ   = (cb_ty.get() or "").strip()
            if not nazwa or not typ:
                error_dialogs.show_error_dialog("Błąd", "Pola 'Nazwa' i 'Typ' są wymagane.")
                return

            raw_status = (var_st.get() or "").strip()
            st_new = _normalize_status(raw_status)

            allowed = _statusy_for_mode(tool_mode)
            if (st_new.lower() not in [x.lower() for x in allowed]) and (raw_status.lower() not in [x.lower() for x in allowed]):
                error_dialogs.show_error_dialog("Błąd", f"Status '{raw_status}' nie jest dozwolony.")
                return

            # KONWERSJA: tylko jeśli NN, checkbox zaznaczony i rola pozwala
            tool_mode_local = tool_mode
            now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            if tool_mode == "NOWE" and convert_var.get():
                if not _can_convert_nn_to_sn(rola):
                    error_dialogs.show_error_dialog("Uprawnienia", "Tę operację może wykonać tylko brygadzista.")
                    return
                tool_mode_local = "STARE"

                # co zrobić z zadaniami?
                mode_tasks = convert_tasks_var.get()  # keep | replace | sum
                if mode_tasks == "replace":
                    typ_val = (cb_ty.get() or "").strip()
                    serwis_tpl = _tasks_for_type(typ_val, "serwis")
                    tasks[:] = [{"tytul": t, "done": False, "by": "", "ts_done": ""} for t in _clean_list(serwis_tpl)]
                elif mode_tasks == "sum":
                    typ_val = (cb_ty.get() or "").strip()
                    serwis_tpl = _tasks_for_type(typ_val, "serwis")
                    for t in _clean_list(serwis_tpl):
                        if not _has_title(t):
                            tasks.append({"tytul": t, "done": False, "by": "", "ts_done": ""})
                # keep -> nic nie zmieniamy

            data_existing = _read_tool(numer) or {}
            historia = list(data_existing.get("historia", start.get("historia", [])))
            st_prev = data_existing.get("status", start.get("status", st_new))

            # historia: zmiana statusu
            if (st_prev or "").strip().lower() != (st_new or "").strip().lower():
                historia.append({"ts": now_ts, "by": (login or "nieznany"), "z": st_prev, "na": st_new})
            # historia: zmiana trybu NN->SN
            if tool_mode != tool_mode_local:
                historia.append({"ts": now_ts, "by": (login or "nieznany"), "z": "[tryb] NOWE", "na": "[tryb] STARE"})

            data_obj = {
                "numer": numer,
                "nazwa": nazwa,
                "typ": typ,
                "status": st_new,
                "opis": (var_op.get() or "").strip(),
                "pracownik": (var_pr.get() or "").strip(),
                "zadania": tasks,
                "data_dodania": data_existing.get("data_dodania") or start.get("data") or now_ts,
                "tryb": tool_mode_local,
                "interwencje": data_existing.get("interwencje", []),
                "historia": historia,
                "kategoria": data_existing.get("kategoria", start.get("kategoria", "")),
                "is_old": data_existing.get("is_old", start.get("is_old", False)),
            }

            if move_to_sn[0]:
                data_obj["is_old"] = True
                data_obj["kategoria"] = "SN"

            _save_tool(data_obj)
            dlg.destroy()
            refresh_list()

        ttk.Button(btns, text="Zapisz", command=save, style="WM.Side.TButton").pack(side="right")
        ttk.Button(btns, text="Anuluj", command=dlg.destroy, style="WM.Side.TButton").pack(side="right", padx=(0,8))

    # ===================== BINDY / START =====================
    def on_double(_=None):
        sel = tree.focus()
        if not sel: return
        open_tool_dialog(row_data.get(sel))

    _dbg("Init panel_narzedzia – start listy")
    btn_add.configure(command=choose_mode_and_add)
    tree.bind("<Double-1>", on_double)
    search_var.trace_add("write", refresh_list)
    refresh_list()

__all__ = ["panel_narzedzia"]
# Koniec pliku
