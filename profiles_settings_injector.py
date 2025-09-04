# profiles_settings_injector.py
# Injects the "Profile użytkownika" tab into settings windows and
# logs TclError exceptions during discovery and attachment.
import logging
import tkinter as tk
from tkinter import ttk

DEBUG = False

logger = logging.getLogger(__name__)
if DEBUG and not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.DEBUG)


def _log_debug(msg, *args, **kwargs):
    if DEBUG:
        logger.debug(msg, *args, **kwargs)

_started = False
_SETTINGS_TITLE_KEYS = ("ustaw", "konfig", "settings")
_SETTINGS_TAB_KEYS = ("Ogólne","Motyw","Aktualizacje","Magazyn","Użytkownicy","Sieć","Baza","Backup","Logi")

def _get_title(win):
    try:
        return (win.title() or "").lower()
    except tk.TclError:
        logger.exception("Unable to get window title")
        return ""

def _iter_all_windows(root):
    yield root
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            yield w
        stack=[w]
        while stack:
            el=stack.pop()
            for ch in el.winfo_children():
                stack.append(ch)

def _find_candidate_notebooks(root):
    cands = []
    for win in list(_iter_all_windows(root)):
        stack=[win]
        while stack:
            el = stack.pop()
            if isinstance(el, ttk.Notebook):
                cands.append((win, el))
            stack.extend(el.winfo_children())
    return cands

def _nb_has_settings_like_tabs(nb):
    try:
        labels = [nb.tab(t, "text") for t in nb.tabs()]
        for k in _SETTINGS_TAB_KEYS:
            if any(isinstance(s, str) and k.lower() in s.lower() for s in labels):
                return True
    except tk.TclError:
        logger.exception("Failed to inspect notebook tabs")
    return False

def _attach_tab(nb):
    try:
        for t in nb.tabs():
            if nb.tab(t, "text") == "Profile użytkowników":
                _log_debug("[PROFILES-DBG] injector: tab already present")
                return True
    except tk.TclError:
        logger.exception("Failed to check existing tabs")

    tab = ttk.Frame(nb, style="WM.Card.TFrame")
    nb.add(tab, text="Profile użytkowników")
    _log_debug("[PROFILES-DBG] injector: tab added")

    cfg = globals().get("config", {}) if isinstance(globals().get("config", {}), dict) else {}

    def _cfg_get(key, default=None):
        if not isinstance(cfg, dict): return default
        if key in cfg: return cfg.get(key, default)
        if "." in key:
            first, rest = key.split(".", 1)
            if isinstance(cfg.get(first), dict):
                return cfg[first].get(rest, default)
        return default

    def _cfg_set(key, val):
        if not isinstance(cfg, dict): return
        if "." in key:
            first, rest = key.split(".", 1)
            if first not in cfg or not isinstance(cfg.get(first), dict):
                cfg[first] = {}
            cfg[first][rest] = val
        else:
            cfg[key] = val

    var_tab  = tk.BooleanVar(value=bool(_cfg_get("profiles.tab_enabled", True)))
    var_head = tk.BooleanVar(value=bool(_cfg_get("profiles.show_name_in_header", True)))
    _fields_default = ["login","nazwa","rola","zmiana"]
    cur_fields = _cfg_get("profiles.fields_visible", _fields_default)
    if isinstance(cur_fields, str):
        cur_fields = [x.strip() for x in cur_fields.split(",") if x.strip()]
    if not isinstance(cur_fields, (list,tuple)) or not cur_fields:
        cur_fields = list(_fields_default)
    var_fields = tk.StringVar(value=",".join(cur_fields))
    cur_edit_fields = _cfg_get("profiles.fields_editable_by_user", [])
    if isinstance(cur_edit_fields, str):
        cur_edit_fields = [x.strip() for x in cur_edit_fields.split(",") if x.strip()]
    if not isinstance(cur_edit_fields, (list, tuple)):
        cur_edit_fields = []
    var_fields_edit = tk.StringVar(value=",".join(cur_edit_fields))
    var_allow_pin = tk.BooleanVar(value=bool(_cfg_get("profiles.allow_pin_change", False)))

    row=0
    ttk.Label(tab, text="Widoczność", style="WM.H2.TLabel").grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(12,6)); row+=1
    ttk.Checkbutton(tab, text="Włącz kartę „Profil użytkownika”", variable=var_tab).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=4); row+=1
    ttk.Checkbutton(tab, text="Pokaż zalogowanego w nagłówku", variable=var_head).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=4); row+=1

    ttk.Label(tab, text="Pola w profilu", style="WM.H2.TLabel").grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(16,6)); row+=1
    ttk.Label(tab, text="Lista (po przecinku):").grid(row=row, column=0, sticky="w", padx=12, pady=4)
    ttk.Entry(tab, textvariable=var_fields, width=42).grid(row=row, column=1, sticky="w", padx=(0,6), pady=4); row+=1
    ttk.Label(tab, text="Pola edytowalne (po przecinku):").grid(row=row, column=0, sticky="w", padx=12, pady=4)
    ttk.Entry(tab, textvariable=var_fields_edit, width=42).grid(row=row, column=1, sticky="w", padx=(0,6), pady=4); row+=1
    ttk.Checkbutton(tab, text="Pozwól na zmianę PIN", variable=var_allow_pin).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=4); row+=1

    def _apply():
        _cfg_set("profiles.tab_enabled", bool(var_tab.get()))
        _cfg_set("profiles.show_name_in_header", bool(var_head.get()))
        fields = [x.strip() for x in var_fields.get().split(",") if x.strip()] or _fields_default
        _cfg_set("profiles.fields_visible", fields)
        editable = [x.strip() for x in var_fields_edit.get().split(",") if x.strip()]
        _cfg_set("profiles.fields_editable_by_user", editable)
        _cfg_set("profiles.allow_pin_change", bool(var_allow_pin.get()))
        _log_debug(
            "[PROFILES-DBG] injector: apply -> %s",
            {
                "tab_enabled": var_tab.get(),
                "show_name_in_header": var_head.get(),
                "fields": var_fields.get(),
                "editable": var_fields_edit.get(),
                "allow_pin": var_allow_pin.get(),
            },
        )
    ttk.Button(tab, text="Zastosuj", command=_apply).grid(row=row, column=0, sticky="w", padx=12, pady=(16,12))

    for c in range(2): tab.grid_columnconfigure(c, weight=0)
    return True

def _candidate_score(win, nb):
    score = 0
    title = _get_title(win)
    if any(k in title for k in _SETTINGS_TITLE_KEYS): score += 2
    if _nb_has_settings_like_tabs(nb): score += 2
    if isinstance(win, tk.Toplevel): score += 1
    return score

def start(root):
    global _started
    if _started: return
    _started = True
    _log_debug("[PROFILES-DBG] injector: start")

    tries = {"n": 0}
    def tick():
        tries["n"] += 1
        cands = _find_candidate_notebooks(root)
        _log_debug(
            "[PROFILES-DBG] injector: tick %s — found %s notebooks",
            tries["n"],
            len(cands),
        )
        best = None; best_score = -1
        for win, nb in cands:
            s = _candidate_score(win, nb)
            t = _get_title(win)
            try:
                tab_texts = [nb.tab(ti, "text") for ti in nb.tabs()]
            except tk.TclError:
                logger.exception("Failed to read notebook tabs")
                tab_texts = []
            _log_debug(
                "[PROFILES-DBG] injector:  cand score=%s title='%s' tabs=%s",
                s,
                t,
                tab_texts,
            )
            if s > best_score:
                best = (win, nb); best_score = s
        if best and best_score > 0:
            _attach_tab(best[1])

        if tries["n"] < 600:  # 5 min
            root.after(500, tick)
    root.after(500, tick)

def force_attach_to_focused(root):
    _log_debug("[PROFILES-DBG] injector: force attach (focused)")
    try:
        w = root.focus_get()
    except tk.TclError:
        logger.exception("Failed to get focused widget")
        w = None
    if not w:
        return
    while True:
        try:
            parent_name = w.winfo_parent()
        except tk.TclError:
            logger.exception("Failed to get parent widget")
            break
        if not parent_name:
            break
        parent = w._nametowidget(parent_name)
        if isinstance(parent, ttk.Notebook):
            _attach_tab(parent)
            return
        w = parent
