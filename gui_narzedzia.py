# Plik: gui_narzedzia.py
# Wersja pliku: 1.5.30
# Zmiany 1.5.30:
# - [MAGAZYN] Zwrot materiałów przy cofnięciu oznaczenia zadania jako wykonane
#
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
import shutil
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
from contextlib import contextmanager
import logika_zadan as LZ  # [MAGAZYN] zużycie materiałów dla zadań
import logika_magazyn as LM  # [MAGAZYN] zwrot materiałów
from utils.path_utils import cfg_path
import ui_hover
import zadania_assign_io
import profile_utils
from config_manager import ConfigManager
from tools_config_loader import (
    load_config,
    get_status_names_for_type,
    get_tasks_for_status,
    get_types,
)

# ===================== MOTYW (użytkownika) =====================
from ui_theme import apply_theme_safe as apply_theme
from utils.gui_helpers import clear_frame
from utils import error_dialogs
import logger
import logging

LOG = logging.getLogger(__name__)

# ===================== STAŁE / USTALENIA (domyślne) =====================
CONFIG_PATH = cfg_path("config.json")
STATUSY_NOWE_DEFAULT  = ["projekt", "w budowie", "próby narzędzia", "odbiór", "sprawne"]
STATUSY_STARE_DEFAULT = ["sprawne", "do ostrzenia", "w ostrzeniu", "po ostrzeniu", "w naprawie", "uszkodzone", "wycofane"]

_CFG_CACHE: dict | None = None
CONFIG_MTIME: float | None = None

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

# Obsługa załączników do narzędzi
ALLOWED_EXTENSIONS = {".png", ".jpg", ".dxf"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


_current_login: str | None = None
_current_role: str | None = None
_assign_tree = None
_assign_row_data: dict[str, dict] = {}
_cmb_user_var: tk.StringVar | None = None
_var_filter_mine: tk.BooleanVar | None = None


def _profiles_usernames(cmb_user=None) -> list[str]:
    """Return list of all usernames from profiles.

    If ``cmb_user`` is provided, it will have its ``values`` configured with the
    retrieved usernames.  This mirrors the behaviour of the legacy variant
    which updated the combobox in-place.
    """
    try:
        default = getattr(profile_utils, "_DEFAULT_USERS_FILE", profile_utils.USERS_FILE)
        profile_utils.USERS_FILE = default
        users = profile_utils.read_users()
        profile_utils.USERS_FILE = default
        logins = [u.get("login", "") for u in users]
    except Exception:
        logins = []
    if cmb_user is not None:
        try:
            cmb_user.config(values=logins)
        except Exception:
            pass
    return logins


def _current_user() -> tuple[str | None, str | None]:
    """Return current login and role as tuple."""
    return _current_login, _current_role


def _selected_task() -> tuple[str | None, str]:
    """Return ``(task_id, context)`` of selected assignment."""
    if _assign_tree is None:
        return None, ""
    try:
        sel = _assign_tree.focus()
    except Exception:
        return None, ""
    if not sel:
        return None, ""
    rec = _assign_row_data.get(sel)
    if not rec:
        return None, ""
    return rec.get("task"), rec.get("context", "")


def _refresh_assignments_view() -> None:
    """Refresh assignments list using ``zadania_assign_io``."""
    if _assign_tree is None:
        return
    ctx = "narzedzia"
    data = zadania_assign_io.list_in_context(ctx)
    if _var_filter_mine is not None and _var_filter_mine.get():
        login, _ = _current_user()
        data = [d for d in data if d.get("user") == login]
    _assign_tree.delete(*_assign_tree.get_children())
    _assign_row_data.clear()
    for rec in data:
        iid = _assign_tree.insert("", "end", values=(rec.get("task"), rec.get("user")))
        _assign_row_data[iid] = rec


def _asgn_assign() -> bool:
    """Assign selected task to user from combobox."""
    login, role = _current_user()
    if role not in {"brygadzista", "admin"}:
        return False
    task_id, ctx = _selected_task()
    if not task_id:
        return False
    user = _cmb_user_var.get().strip() if _cmb_user_var else ""
    if not user:
        return False
    zadania_assign_io.assign(task_id, user, ctx or "narzedzia")
    _refresh_assignments_view()
    return True

# ===================== CONFIG / DEBUG =====================
def _load_config():
    global _CFG_CACHE, CONFIG_MTIME
    if not os.path.exists(CONFIG_PATH):
        _CFG_CACHE = {}
        CONFIG_MTIME = None
        return {}
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        if _CFG_CACHE is not None and CONFIG_MTIME == mtime:
            return _CFG_CACHE
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            content = "\n".join(
                line for line in f if not line.lstrip().startswith("#")
            )
            _CFG_CACHE = json.loads(content) if content.strip() else {}
        CONFIG_MTIME = mtime
        return _CFG_CACHE
    except (OSError, json.JSONDecodeError) as e:
        logger.log_akcja(f"Błąd wczytywania {CONFIG_PATH}: {e}")
        error_dialogs.show_error_dialog("Config", f"Błąd wczytywania {CONFIG_PATH}: {e}")
        return _CFG_CACHE or {}

def _save_config(cfg: dict) -> bool:
    global _CFG_CACHE, CONFIG_MTIME
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        _CFG_CACHE = cfg
        try:
            CONFIG_MTIME = os.path.getmtime(CONFIG_PATH)
        except (OSError, AttributeError):
            CONFIG_MTIME = None
        return True
    except (OSError, TypeError, ValueError) as e:
        logger.log_akcja(f"Błąd zapisu {CONFIG_PATH}: {e}")
        error_dialogs.show_error_dialog("Config", f"Błąd zapisu {CONFIG_PATH}: {e}")
        return False

DEBUG = bool(os.environ.get("WM_DEBUG") or _load_config().get("tryb_testowy"))

def _dbg(*args):
    if DEBUG:
        LOG.debug("[narzedzia] %s", " ".join(str(a) for a in args))

def _maybe_seed_config_templates():
    try:
        cfg = _load_config()
        changed = False
        if "szablony_zadan_narzedzia" not in cfg:
            cfg["szablony_zadan_narzedzia"] = TASK_TEMPLATES_DEFAULT[:]
            changed = True
        if "szablony_zadan_narzedzia_stare" not in cfg:
            cfg["szablony_zadan_narzedzia_stare"] = STARE_CONVERT_TEMPLATES_DEFAULT[:]
            changed = True
        if "typy_narzedzi" not in cfg:
            cfg["typy_narzedzi"] = TYPY_NARZEDZI_DEFAULT[:]
            changed = True
        if changed:
            _save_config(cfg)
            _dbg("Dosiano brakujące klucze (szablony/typy) w config.json")
    except (OSError, json.JSONDecodeError, TypeError) as e:
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
    except (OSError, json.JSONDecodeError, TypeError):
        return TASK_TEMPLATES_DEFAULT

def _stare_convert_templates_from_config():
    try:
        cfg = _load_config()
        lst = _clean_list(cfg.get("szablony_zadan_narzedzia_stare"))
        return lst or STARE_CONVERT_TEMPLATES_DEFAULT
    except (OSError, json.JSONDecodeError, TypeError):
        return STARE_CONVERT_TEMPLATES_DEFAULT

def _types_from_config():
    try:
        cfg_mgr = ConfigManager()
        default_collection = cfg_mgr.get("tools.default_collection", "NN") or "NN"
    except Exception:
        default_collection = "NN"
    names = _type_names_for_collection(str(default_collection).strip() or "NN")
    if names:
        return names
    try:
        cfg = _load_config()
        lst = _clean_list(cfg.get("typy_narzedzi"))
        return lst or TYPY_NARZEDZI_DEFAULT
    except (OSError, json.JSONDecodeError, TypeError):
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


_TOOLS_DEFINITIONS_CACHE: dict[str, dict] = {}


def _definitions_path_for_collection(collection_id: str) -> str:
    """Resolve definitions path for given *collection_id*."""

    candidate: str | None = None
    try:
        cfg_mgr = ConfigManager()
        paths_cfg = cfg_mgr.get("tools.collections_paths", {}) or {}
        if isinstance(paths_cfg, dict):
            for key in (collection_id, collection_id.upper(), collection_id.lower()):
                value = paths_cfg.get(key)
                if value:
                    candidate = str(value)
                    break
        if not candidate:
            candidate = cfg_mgr.get("tools.definitions_path", None)
    except Exception:
        candidate = None

    fallback = getattr(LZ, "TOOL_TASKS_PATH", "data/zadania_narzedzia.json")
    candidate = str(candidate or fallback or "data/zadania_narzedzia.json").strip()
    if not candidate:
        candidate = "data/zadania_narzedzia.json"
    return cfg_path(candidate)


def _invalidate_tools_definitions_cache() -> None:
    """Clear cached tool definitions paths."""

    _TOOLS_DEFINITIONS_CACHE.clear()


def _load_tools_definitions(collection_id: str, *, force: bool = False) -> dict:
    """Load tools definitions for *collection_id* with caching."""

    path = _definitions_path_for_collection(collection_id)
    cache_key = f"{collection_id}|{path}"
    if force or cache_key not in _TOOLS_DEFINITIONS_CACHE:
        _TOOLS_DEFINITIONS_CACHE[cache_key] = load_config(path) or {}
    return _TOOLS_DEFINITIONS_CACHE[cache_key]


def _type_names_for_collection(collection_id: str, *, force: bool = False) -> list[str]:
    """Return distinct type names available for *collection_id*."""

    if not collection_id:
        return []
    cfg_data = _load_tools_definitions(collection_id, force=force)
    items = get_types(cfg_data, collection_id)
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        name = str(item.get("name") or item.get("id") or "").strip()
        if not name:
            continue
        lower = name.lower()
        if lower in seen:
            continue
        seen.add(lower)
        result.append(name)
    return result


def _status_names_for_type(
    collection_id: str,
    type_name: str,
    *,
    force: bool = False,
) -> list[str]:
    """Return statuses defined for ``type_name`` in *collection_id*."""

    if not collection_id or not type_name:
        return []
    cfg_data = _load_tools_definitions(collection_id, force=force)
    statuses = get_status_names_for_type(cfg_data, collection_id, type_name)
    return [
        str(name).strip()
        for name in statuses
        if str(name or "").strip()
    ]


def _task_names_for_status(
    collection_id: str,
    type_name: str,
    status_name: str,
    *,
    force: bool = False,
) -> list[str]:
    """Return tasks defined for ``status_name`` of ``type_name``."""

    if not (collection_id and type_name and status_name):
        return []
    cfg_data = _load_tools_definitions(collection_id, force=force)
    tasks = get_tasks_for_status(cfg_data, collection_id, type_name, status_name)
    return [
        str(task).strip()
        for task in tasks
        if str(task or "").strip()
    ]


def _is_allowed_file(path: str) -> bool:
    """Verify selected file extension and size."""
    ext = os.path.splitext(str(path))[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    try:
        return os.path.getsize(path) <= MAX_FILE_SIZE
    except OSError:
        return False


def _delete_task_files(task: dict) -> None:
    """Remove media and thumbnail files referenced by *task*."""
    for key in ("media", "miniatura"):
        p = task.get(key)
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _remove_task(tasks: list, index: int) -> None:
    """Remove task at *index* and delete associated files."""
    try:
        task = tasks[index]
    except IndexError:
        return
    _delete_task_files(task)
    del tasks[index]

# ===== Zadania – pomocnicze funkcje =====


def _task_to_display(task):
    """Return listbox display text for *task*.

    Accepts both legacy string format ``"[ ] text"`` and dictionary
    representation with keys like ``text`` and ``done``.  The returned
    string always contains a prefix ``[x]`` or ``[ ]``.
    """

    if isinstance(task, str):
        return task
    text = task.get("text") or task.get("tytul") or ""
    prefix = "[x]" if task.get("done") else "[ ]"
    return f"{prefix} {text}".strip()


def _update_global_tasks(state, comment, ts):
    """Mark all tasks on *state* as done and refresh the listbox.

    ``state`` is expected to provide ``global_tasks`` and ``tasks_listbox``
    attributes. Tasks may be strings or dictionaries.  They are updated
    in-place to dictionary form and the listbox is repopulated using
    :func:`_task_to_display`.
    """

    tasks = []
    for item in getattr(state, "global_tasks", []):
        if isinstance(item, str):
            text = item[3:].strip() if item.startswith("[") else item.strip()
            task = {"text": text}
        elif isinstance(item, dict):
            task = dict(item)
            if "text" not in task:
                task["text"] = task.get("tytul") or task.get("title") or ""
        else:
            continue
        task["done"] = True
        task["status"] = "Zrobione"
        task["done_at"] = ts
        task["comment"] = comment
        tasks.append(task)

    state.global_tasks[:] = tasks

    lb = getattr(state, "tasks_listbox", None)
    if lb is not None:
        try:
            lb.delete(0, "end")
            for t in state.global_tasks:
                lb.insert("end", _task_to_display(t))
        except Exception:
            pass


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
                    entry = typy[k]
                    break
        if entry:
            out = _clean_list(entry.get(phase))
            if out:
                return out
    except (AttributeError, KeyError, TypeError) as e:
        _dbg("Błąd odczytu narzedzia.typy:", e)

    if phase == "produkcja":
        return _task_templates_from_config()
    else:
        return _stare_convert_templates_from_config()

# ===== Szablony z pliku zadania_narzedzia.json =====
class _TaskTemplateUI:
    """Helper object building comboboxes for collection/type/status and tasks."""

    def __init__(self, parent):
        self.parent = parent
        self._state = {"collection": "", "type": "", "status": ""}
        self._types: list[dict] = []
        self._statuses: list[dict] = []
        self._ui_updating = False
        self.tasks_state: list[dict] = []

        self.var_collection = tk.StringVar()
        self.var_type = tk.StringVar()
        self.var_status = tk.StringVar()

        Combobox = getattr(ttk, "Combobox", getattr(ttk, "Entry", lambda *a, **k: None))
        self.cb_collection = Combobox(parent, textvariable=self.var_collection, state="readonly", values=[])
        self.cb_type = Combobox(parent, textvariable=self.var_type, state="readonly", values=[])
        self.cb_status = Combobox(parent, textvariable=self.var_status, state="readonly", values=[])
        self.lst = tk.Listbox(parent, height=8)

        self.cb_collection.bind("<<ComboboxSelected>>", self._on_collection_selected)
        self.cb_type.bind("<<ComboboxSelected>>", self._on_type_selected)
        self.cb_status.bind("<<ComboboxSelected>>", self._on_status_selected)

        self.cb_collection.pack()
        self.cb_type.pack()
        self.cb_status.pack()
        self.lst.pack(fill="both", expand=True)

        self._render_collections_initial()

    # ===================== helpers =====================
    @contextmanager
    def _suspend_ui(self):
        prev = self._ui_updating
        self._ui_updating = True
        try:
            yield
        finally:
            self._ui_updating = prev

    def _log(self, *msg):  # pragma: no cover - debug helper
        try:
            print("[WM-DBG][NARZ]", *msg)
        except Exception:
            pass

    @staticmethod
    def _lookup_id_by_name(name: str, items: list[dict]) -> str:
        for it in items:
            if it.get("name") == name:
                return it.get("id", "")
        return ""

    def _get_collections(self):
        return LZ.get_collections()

    def _get_types(self, collection_id):
        return LZ.get_tool_types(collection=collection_id)

    def _get_statuses(self, type_id, collection_id):
        return LZ.get_statuses(type_id, collection=collection_id)

    def _get_tasks(self, type_id, status_id, collection_id):
        return LZ.get_tasks(type_id, status_id, collection=collection_id)

    def _set_info(self, msg: str) -> None:
        try:
            self.parent.statusbar.config(text=msg)  # type: ignore[attr-defined]
        except Exception:
            print(f"[WM-DBG][NARZ] {msg}")

    # ===================== renderers =====================
    def _render_collections_initial(self):
        try:
            collections = self._get_collections()
        except Exception as e:
            self._log("collections", e)
            collections = []
        with self._suspend_ui():
            names = [c.get("name", "") for c in collections]
            self.cb_collection.config(values=names)
            cid = self._state.get("collection") or LZ.get_default_collection()
            sel_name = next((c.get("name") for c in collections if c.get("id") == cid), "")
            if not sel_name and names:
                sel_name = names[0]
                cid = self._lookup_id_by_name(sel_name, collections)
            else:
                if not names:
                    cid = ""
            self.var_collection.set(sel_name)
            self._state["collection"] = cid or ""
        self._render_types()

    def _render_types(self):
        cid = self._state.get("collection")
        try:
            types = self._get_types(cid) if cid else []
        except Exception as e:
            self._log("types", e)
            types = []
        if types:
            self._set_info("")
        else:
            self._set_info("Brak typów w wybranej kolekcji.")
        with self._suspend_ui():
            self._types = types
            names = [t.get("name", "") for t in types]
            self.cb_type.config(values=names)
            tid = self._state.get("type")
            sel_name = next((t.get("name") for t in types if t.get("id") == tid), "")
            if not sel_name and names:
                sel_name = names[0]
                tid = self._lookup_id_by_name(sel_name, types)
            else:
                if not names:
                    tid = ""
            self.var_type.set(sel_name)
            self._state["type"] = tid or ""
        self._render_statuses()

    def _render_statuses(self):
        cid = self._state.get("collection")
        tid = self._state.get("type")
        try:
            statuses = self._get_statuses(tid, cid) if tid else []
        except Exception as e:
            self._log("statuses", e)
            statuses = []
        if statuses:
            self._set_info("")
        else:
            self._set_info("Brak statusów dla wybranego typu.")
        with self._suspend_ui():
            self._statuses = statuses
            names = [s.get("name", "") for s in statuses]
            self.cb_status.config(values=names)
            sid = self._state.get("status")
            sel_name = next((s.get("name") for s in statuses if s.get("id") == sid), "")
            if not sel_name and names:
                sel_name = names[0]
                sid = self._lookup_id_by_name(sel_name, statuses)
            else:
                if not names:
                    sid = ""
            self.var_status.set(sel_name)
            self._state["status"] = sid or ""
        self._render_tasks()

    def _render_tasks(self):
        cid = self._state.get("collection")
        tid = self._state.get("type")
        sid = self._state.get("status")
        try:
            tasks = self._get_tasks(tid, sid, cid) if (cid and tid and sid) else []
        except Exception as e:
            self._log("tasks", e)
            tasks = []
        with self._suspend_ui():
            self.lst.delete(0, tk.END)
            self.tasks_state.clear()
            if tasks:
                for t in tasks:
                    self.tasks_state.append({"text": t, "done": False})
                if LZ.should_autocheck(sid, cid):
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    user = getattr(self.parent, "login", None) or getattr(self.parent, "user", None)
                    for task in self.tasks_state:
                        task["done"] = True
                        task["done_at"] = ts
                        if user:
                            task["user"] = user
                for t in self.tasks_state:
                    prefix = "[x]" if t.get("done") else "[ ]"
                    self.lst.insert(tk.END, f"{prefix} {t['text']}")
                self._set_info("")
            else:
                self._set_info("Brak zadań dla wybranego statusu.")
                self.lst.insert(tk.END, "-- brak zadań --")
                try:
                    self.lst.itemconfig(0, state="disabled")
                except Exception:
                    pass

    # ===================== event handlers =====================
    def _on_collection_selected(self, _=None):
        if self._ui_updating:
            return
        name = self.var_collection.get()
        self._state["collection"] = self._lookup_id_by_name(name, self._get_collections())
        self._state["type"] = ""
        self._state["status"] = ""
        self._render_types()

    def _on_type_selected(self, _=None):
        if self._ui_updating:
            return
        name = self.var_type.get()
        self._state["type"] = self._lookup_id_by_name(name, self._types)
        self._state["status"] = ""
        self._render_statuses()

    def _on_status_selected(self, _=None):
        if self._ui_updating:
            return
        name = self.var_status.get()
        self._state["status"] = self._lookup_id_by_name(name, self._statuses)
        self._render_tasks()

    def _reload_from_lz(self) -> None:
        try:
            self._render_collections_initial()
        except Exception as e:  # pragma: no cover
            self._log("_reload_from_lz", e)
            self._set_info("Błąd odświeżania danych")

    def _odswiez_zadania(self) -> None:
        try:
            LZ.invalidate_cache()
            self._render_types()
            print("[WM-DBG][NARZ] Odświeżono zadania (invalidate_cache).")
        except Exception as e:  # pragma: no cover
            self._log("Odświeżanie zadań:", e)
            self._set_info("Błąd odświeżania zadań")


def build_task_template(parent):
    """Build simple comboboxes for collection/type/status and a tasks list."""

    LZ.invalidate_cache()
    ui = _TaskTemplateUI(parent)
    return {
        "cb_collection": ui.cb_collection,
        "cb_type": ui.cb_type,
        "cb_status": ui.cb_status,
        "listbox": ui.lst,
        "on_collection_change": ui._on_collection_selected,
        "on_type_change": ui._on_type_selected,
        "on_status_change": ui._on_status_selected,
        "on_collection_selected": ui._on_collection_selected,
        "on_type_selected": ui._on_type_selected,
        "on_status_selected": ui._on_status_selected,
        "tasks_state": ui.tasks_state,
        "odswiez_zadania": ui._odswiez_zadania,
        "reload_from_lz": ui._reload_from_lz,
        "set_info": ui._set_info,
    }

# ===================== ŚCIEŻKI DANYCH =====================
def _resolve_tools_dir():
    cfg = _load_config()
    if (cfg.get("paths") or {}).get("narzedzia"):
        LOG.debug("[WM-DBG][TOOLS] paths.narzedzia deprecated")
    base = (cfg.get("sciezka_danych") or "").strip()
    if base and not os.path.isabs(base):
        base = os.path.normpath(base)
    folder = os.path.join(base, "narzedzia") if base else "narzedzia"
    return folder

def _ensure_folder():
    folder = _resolve_tools_dir()
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)


def _generate_dxf_preview(dxf_path: str) -> str | None:
    """Spróbuj wygenerować miniaturę PNG dla pliku DXF.

    Zwraca ścieżkę do wygenerowanego pliku lub None w przypadku błędu.
    """
    try:  # pragma: no cover - zależne od opcjonalnych bibliotek
        import ezdxf
        from ezdxf.addons.drawing import matplotlib as ezdxf_matplotlib
        import matplotlib.pyplot as plt

        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        fig = ezdxf_matplotlib.draw(msp)
        png_path = os.path.splitext(dxf_path)[0] + "_dxf.png"
        fig.savefig(png_path)
        plt.close(fig)
        try:
            from PIL import Image

            with Image.open(png_path) as img:
                img.thumbnail((600, 800))
                img.save(png_path)
        except OSError:  # pragma: no cover - Pillow best effort
            pass
        return png_path
    except (OSError, ImportError, ValueError, RuntimeError) as e:  # pragma: no cover - best effort
        _dbg("Błąd generowania miniatury DXF:", e)
        return None

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
            data = json.load(f)
        data.setdefault("obraz", "")
        data.setdefault("dxf", "")
        data.setdefault("dxf_png", "")
        return data
    except (OSError, json.JSONDecodeError) as e:
        _dbg("Błąd odczytu narzędzia", p, e)
        return None

def _save_tool(data):
    _ensure_folder()
    obj = dict(data)
    obj["numer"] = str(obj.get("numer", "")).zfill(3)
    obj.setdefault("obraz", "")
    obj.setdefault("dxf", "")
    obj.setdefault("dxf_png", "")
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
                "obraz": d.get("obraz", ""),
                "dxf": d.get("dxf", ""),
                "dxf_png": d.get("dxf_png", ""),
            })
        except (OSError, json.JSONDecodeError, TypeError) as e:
            _dbg("Błąd wczytania pliku:", path, e)
    return items

def _iter_legacy_json_items():
    cfg = _load_config()
    p_cfg_flat = (cfg.get("paths") or {}).get("narzedzia")
    if p_cfg_flat:
        LOG.debug("[WM-DBG][TOOLS] paths.narzedzia deprecated")
    base = (cfg.get("sciezka_danych") or "").strip()
    p_in_base = os.path.join(base, "narzedzia.json") if base else None
    p_cwd = "narzedzia.json"
    cands = []

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
    except (OSError, json.JSONDecodeError) as e:
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
                "obraz": d.get("obraz", ""),
                "dxf": d.get("dxf", ""),
                "dxf_png": d.get("dxf_png", ""),
            })
        except (KeyError, TypeError) as e:
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
    except (TypeError, ValueError):
        p = 0
    p = max(0, min(100, p))
    filled = p // 10
    empty = 10 - filled
    return ("■" * filled) + ("□" * empty) + f"  {p}%"

def _band_tag(percent):
    try:
        p = int(percent)
    except (TypeError, ValueError):
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
    global _current_login, _current_role, _assign_tree, _assign_row_data, _cmb_user_var, _var_filter_mine
    _current_login = login
    _current_role = rola
    _load_config()
    _maybe_seed_config_templates()
    apply_theme(root)
    clear_frame(frame)

    header = ttk.Frame(frame, style="WM.TFrame")
    header.pack(fill="x", padx=10, pady=(10, 0))
    ttk.Label(header, text="🔧 Narzędzia", style="WM.H1.TLabel").pack(side="left")

    search_var = tk.StringVar()
    ttk.Entry(header, textvariable=search_var, width=36, style="WM.Search.TEntry").pack(side="right", padx=(8, 0))

    def _set_info(msg: str) -> None:
        try:
            frame.statusbar.config(text=msg)  # type: ignore[attr-defined]
        except Exception:
            print(f"[WM-DBG][NARZ] {msg}")

    def _odswiez_zadania():
        try:
            LZ.invalidate_cache()
            fn = (
                locals().get("_reload_from_lz")
                or locals().get("_on_collection_selected")
                or getattr(frame, "reload_from_lz", None)
                or getattr(frame, "on_collection_selected", None)
            )
            if callable(fn):
                fn()
            print("[WM-DBG][NARZ] Odświeżono zadania (invalidate_cache).")
        except Exception as e:  # pragma: no cover - safeguard
            print(f"[WM-DBG][NARZ][ERROR] Odświeżanie zadań: {e!r}")
            _set_info("Błąd odświeżania zadań")

    btn_add = ttk.Button(header, text="Dodaj", style="WM.Side.TButton")
    btn_add.pack(side="right", padx=(0, 8))

    btn_odswiez = ttk.Button(
        header,
        text="Odśwież zadania",
        command=_odswiez_zadania,
        style="WM.Side.TButton",
    )
    btn_odswiez.pack(side="right", padx=4)

    cmb_user_var = tk.StringVar()
    Combobox = getattr(ttk, "Combobox", getattr(ttk, "Entry", lambda *a, **k: None))
    cmb_user = Combobox(
        header,
        textvariable=cmb_user_var,
        state="readonly",
        values=_profiles_usernames(),
        width=16,
    )
    cmb_user.pack(side="left", padx=(8, 0))
    btn_asgn = ttk.Button(header, text="Przypisz", command=_asgn_assign, style="WM.Side.TButton")
    btn_asgn.pack(side="left", padx=4)
    BooleanVar = getattr(tk, "BooleanVar", tk.StringVar)
    var_filter_mine = BooleanVar(value=False)
    Checkbutton = getattr(ttk, "Checkbutton", ttk.Button)
    Checkbutton(
        header, text="Moje", variable=var_filter_mine, command=_refresh_assignments_view
    ).pack(side="left", padx=4)

    _cmb_user_var = cmb_user_var
    _var_filter_mine = var_filter_mine
    frame.cmb_user = cmb_user
    frame.var_filter_mine = var_filter_mine
    frame.btn_asgn = btn_asgn

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

    assign_wrap = ttk.Frame(frame, style="WM.Card.TFrame")
    assign_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    assign_cols = ("task", "user")
    assign_headers = {"task": "Zadanie", "user": "Użytkownik"}
    assign_widths = {"task": 240, "user": 160}
    assign_tree = ttk.Treeview(assign_wrap, columns=assign_cols, show="headings", style="WM.Treeview")
    for c in assign_cols:
        assign_tree.heading(c, text=assign_headers[c])
        assign_tree.column(c, width=assign_widths[c], anchor="w")
    assign_tree.pack(fill="both", expand=True)
    _assign_tree = assign_tree
    _assign_row_data = {}
    _refresh_assignments_view()
    frame.assign_tree = assign_tree

    def refresh_list(*_):
        tree.delete(*tree.get_children()); row_data.clear()
        q = (search_var.get() or "").strip().lower()
        data = _load_all_tools()
        for tool in data:
            blob = ("%s %s %s %s %s %s %s %s" % (
                tool["nr"], tool["nazwa"], tool["typ"], tool["status"], tool["data"], tool["postep"], tool.get("tryb", ""), tool.get("opis", "")
            )).lower()
            if q and q not in blob:
                continue
            tag = _band_tag(tool["postep"])
            bar = _bar_text(tool["postep"])
            iid = tree.insert(
                "",
                "end",
                values=(tool["nr"], tool["nazwa"], tool["typ"], tool["status"], tool["data"], bar),
                tags=(tag,),
            )
            row_data[iid] = tool
            base_dir = Path(_resolve_tools_dir())
            paths = []
            rel = tool.get("dxf_png")
            if rel:
                p = base_dir / rel
                if p.exists():
                    paths.append(str(p))
            if not paths:
                rel = tool.get("obraz")
                if rel:
                    p = base_dir / rel
                    if p.exists():
                        paths.append(str(p))
            if paths:
                ui_hover.bind_treeview_row_hover(tree, iid, paths)
        if not data:
            _dbg("Lista narzędzi pusta – filtr:", q or "(brak)")

    _defs_watch_state: dict[str, object] = {"path": None, "mtime": None}

    def _resolve_definitions_path() -> str | None:
        candidate: str | None = None
        try:
            cfg_mgr = ConfigManager()
            candidate = cfg_mgr.get("tools.definitions_path", None)
        except Exception:
            candidate = None
        if not candidate:
            candidate = getattr(LZ, "TOOL_TASKS_PATH", os.path.join("data", "zadania_narzedzia.json"))
        candidate = str(candidate or "").strip()
        if not candidate:
            return None
        if not os.path.isabs(candidate):
            try:
                candidate = cfg_path(candidate)
            except Exception:
                candidate = os.path.join("data", "zadania_narzedzia.json")
        return candidate

    def _definitions_mtime(path: str | None) -> float | None:
        if not path:
            return None
        try:
            return os.path.getmtime(path)
        except OSError:
            return None

    def _reload_definitions_from_disk(path: str | None) -> None:
        if not path:
            return
        try:
            LZ.invalidate_cache()
        except Exception as exc:
            print("[ERROR][NARZ] błąd przeładowania definicji:", exc)
        _invalidate_tools_definitions_cache()
        try:
            refresh_list()
        except Exception as exc:
            print("[ERROR][NARZ] błąd odświeżenia widoku:", exc)
        else:
            print(
                f"[WM-DBG][NARZ] Definicje narzędzi przeładowane po zapisie w ustawieniach ({path})."
            )

    def _maybe_reload_definitions(_event=None, *, force: bool = False) -> bool:
        path = _resolve_definitions_path()
        mtime = _definitions_mtime(path)
        prev_path = _defs_watch_state.get("path")
        prev_mtime = _defs_watch_state.get("mtime")
        _defs_watch_state["path"] = path
        _defs_watch_state["mtime"] = mtime
        if not path:
            return False
        if not force and prev_path == path and prev_mtime == mtime:
            return False
        print(f"[WM-DBG][NARZ] Wykryto zmianę definicji ({path}) → przeładowuję.")
        _reload_definitions_from_disk(path)
        return True

    _defs_watch_state["path"] = _resolve_definitions_path()
    _defs_watch_state["mtime"] = _definitions_mtime(_defs_watch_state["path"])

    def _on_focus_back(_event=None):
        _maybe_reload_definitions()

    widgets_to_bind = {root, frame, getattr(frame, "master", None)}
    try:
        widgets_to_bind.add(frame.winfo_toplevel())
    except Exception:
        pass
    for widget in widgets_to_bind:
        if widget is None:
            continue
        try:
            widget.bind("<FocusIn>", _on_focus_back, add="+")
        except Exception:
            pass

    def _on_cfg_updated(_event=None):
        _maybe_seed_config_templates()
        changed = _maybe_reload_definitions(force=True)
        if not changed:
            refresh_list()

    root.bind("<<ConfigUpdated>>", _on_cfg_updated)

    # ===================== POPUP WYBORU TRYBU =====================
    def choose_mode_and_add():
        dlg = tk.Toplevel(root)
        dlg.title("Dodaj narzędzie – wybierz tryb")
        apply_theme(dlg)
        frm = ttk.Frame(dlg, padding=10, style="WM.Card.TFrame")
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Jakie narzędzie chcesz dodać?", style="WM.Card.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,6))
        var = tk.StringVar(value="NOWE")
        ttk.Radiobutton(frm, text="Nowe (001–499)", variable=var, value="NOWE").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(frm, text="Stare/produkcyjne (500–1000)", variable=var, value="STARE").grid(row=2, column=0, sticky="w")
        btns = ttk.Frame(frm, style="WM.TFrame")
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8,0))

        def _next(_event=None):
            dlg.destroy()
            open_tool_dialog(None, var.get())

        ttk.Button(btns, text="Anuluj", command=dlg.destroy, style="WM.Side.TButton").pack(side="right", padx=(0,8))
        ttk.Button(btns, text="Dalej", command=_next, style="WM.Side.TButton").pack(side="right")
        dlg.bind("<Return>", _next)

    # ===================== DIALOG DODAWANIA / EDYCJI =====================
    def open_tool_dialog(tool, mode=None):
        editing = tool is not None
        if editing:
            try:
                tool_mode = tool.get("tryb") or ("NOWE" if int(str(tool.get("nr","000"))) < 500 else "STARE")
            except (TypeError, ValueError):
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
            "obraz": "",
            "dxf": "",
            "dxf_png": "",
        }

        nr_auto = start.get("nr")
        if nr_auto:
            nr_auto = str(nr_auto).zfill(3)
        else:
            nr_auto = _next_free_in_range(range_lo, range_hi)
        if not nr_auto:
            nr_auto = ""

        dlg = tk.Toplevel(root)
        dlg.title(("Edytuj" if editing else "Dodaj") + " – " + tool_mode)
        apply_theme(dlg)
        nb = ttk.Notebook(dlg, style="TNotebook")
        nb.pack(fill="both", expand=True)

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
        var_img = tk.StringVar(value=start.get("obraz", ""))
        var_dxf = tk.StringVar(value=start.get("dxf", ""))
        var_dxf_png = tk.StringVar(value=start.get("dxf_png", ""))

        # ostatnio obsłużony status (do gardy)
        last_applied_status = [ (start.get("status") or "").strip() ]
        # status poprzedni (do historii/przyszłych reguł)
        last_status = [ (start.get("status") or "").strip() ]

        def _active_collection() -> str:
            fallback = "SN" if tool_mode == "STARE" else "NN"
            try:
                cfg_mgr = ConfigManager()
                if tool_mode == "STARE":
                    enabled = cfg_mgr.get("tools.collections_enabled", []) or []
                    for candidate in ("SN", "ST"):
                        if candidate in enabled:
                            fallback = candidate
                            break
                    paths_cfg = cfg_mgr.get("tools.collections_paths", {}) or {}
                    if isinstance(paths_cfg, dict):
                        for candidate in ("SN", "ST"):
                            if candidate in paths_cfg:
                                fallback = candidate
                                break
                else:
                    fallback = cfg_mgr.get("tools.default_collection", fallback) or fallback
            except Exception:
                pass
            result = str(fallback or ("SN" if tool_mode == "STARE" else "NN")).strip()
            return result.upper() if result else ("SN" if tool_mode == "STARE" else "NN")

        r = 2
        def row(lbl, widget):
            nonlocal r
            ttk.Label(frm, text=lbl, style="WM.Card.TLabel").grid(row=r, column=0, sticky="w")
            widget.grid(row=r, column=1, sticky="ew", pady=2)
            r += 1

        row("Numer (3 cyfry)", ttk.Entry(frm, textvariable=var_nr, style="WM.Search.TEntry"))
        row("Nazwa",           ttk.Entry(frm, textvariable=var_nm, style="WM.Search.TEntry"))

        # === Typ (Combobox z definicji) ===
        typ_frame = ttk.Frame(frm, style="WM.TFrame")
        var_typ = tk.StringVar(value=start.get("typ", ""))
        collection_for_types = _active_collection()
        type_names = _type_names_for_collection(collection_for_types, force=True)
        start_typ = (start.get("typ", "") or "").strip()
        if start_typ and start_typ not in type_names:
            type_names = [start_typ] + [name for name in type_names if name != start_typ]
        print(
            "[WM-DBG][NARZ] Typy z definicji: "
            f"coll={collection_for_types} → {len(type_names)} pozycji"
        )
        cb_ty = ttk.Combobox(
            typ_frame,
            textvariable=var_typ,
            values=type_names,
            state="readonly",
            width=28,
        )
        if start_typ:
            cb_ty.set(start_typ)
        elif type_names:
            try:
                cb_ty.set(type_names[0])
            except tk.TclError:
                var_typ.set(type_names[0])
        cb_ty.pack(side="left", fill="x", expand=True)
        row("Typ", typ_frame)

        status_frame = ttk.Frame(frm, style="WM.TFrame")
        cb_status = ttk.Combobox(
            status_frame,
            textvariable=var_st,
            values=statusy,
            state="readonly",
        )
        cb_status.pack(side="left", fill="x", expand=True)
        btn_status_reload = ttk.Button(
            status_frame,
            text="↻",
            width=3,
            style="WM.Side.TButton",
        )
        btn_status_reload.pack(side="left", padx=(6, 0))
        row("Status", status_frame)

        status_fallback = list(statusy)

        def _status_values_list() -> list[str]:
            try:
                raw_values = cb_status.cget("values")
            except Exception:
                return []
            if isinstance(raw_values, (list, tuple)):
                return [str(v) for v in raw_values]
            try:
                split = cb_status.tk.splitlist(raw_values)
            except Exception:
                return [str(raw_values)] if raw_values else []
            return [str(v) for v in split]

        def _reload_statuses_from_definitions(*, via_button: bool = False, force: bool = False) -> None:
            type_name = (var_typ.get() or "").strip()
            if not type_name:
                cb_status.config(values=status_fallback)
                if status_fallback:
                    var_st.set(status_fallback[0])
                return
            collection_id = _active_collection()
            names = _status_names_for_type(collection_id, type_name, force=force)
            print(
                "[WM-DBG][NARZ] Statusy z definicji: "
                f"coll={collection_id} typ={type_name} → {len(names)} pozycji"
            )
            if not names:
                cb_status.config(values=status_fallback)
                if via_button and type_name:
                    messagebox.showinfo(
                        "Brak statusów",
                        f"Nie znaleziono statusów dla typu '{type_name}' w kolekcji {collection_id}.",
                    )
                current = (var_st.get() or "").strip()
                if status_fallback:
                    fallback_lower = {s.lower() for s in status_fallback if s}
                    if current.lower() not in fallback_lower:
                        var_st.set(status_fallback[0])
                else:
                    var_st.set("")
                return
            cb_status.config(values=names)
            current = (var_st.get() or "").strip()
            names_lower = {n.lower() for n in names}
            if current.lower() not in names_lower:
                var_st.set(names[0])

        def _reload_statuses_and_refresh(*, via_button: bool = False, force: bool = False) -> None:
            _reload_statuses_from_definitions(via_button=via_button, force=force)
            try:
                _refresh_task_presets()
            except Exception:
                pass

        btn_status_reload.configure(
            command=lambda: _reload_statuses_and_refresh(via_button=True, force=True)
        )

        cb_ty.bind("<<ComboboxSelected>>", lambda *_: _reload_statuses_and_refresh())
        try:
            var_typ.trace_add("write", lambda *_: _reload_statuses_and_refresh())
        except AttributeError:
            pass

        _reload_statuses_and_refresh()

        row("Opis",   ttk.Entry(frm, textvariable=var_op, style="WM.Search.TEntry"))
        row("Pracownik", ttk.Entry(frm, textvariable=var_pr, style="WM.Search.TEntry"))

        def _media_dir():
            path = os.path.join(_resolve_tools_dir(), "media")
            os.makedirs(path, exist_ok=True)
            return path

        img_frame = ttk.Frame(frm, style="WM.TFrame")
        btn_img = ttk.Button(img_frame, text="Wybierz...", style="WM.Side.TButton")
        btn_img.pack(side="left")
        preview_btn = ttk.Button(img_frame, text="Podgląd", style="WM.Side.TButton")
        preview_btn.pack(side="left", padx=(6, 0))
        img_lbl = ttk.Label(
            img_frame,
            text=os.path.basename(var_img.get()) if var_img.get() else "—",
            style="WM.Muted.TLabel",
        )
        img_lbl.pack(side="left", padx=6)

        dxf_frame = ttk.Frame(frm, style="WM.TFrame")
        btn_dxf = ttk.Button(dxf_frame, text="Wybierz...", style="WM.Side.TButton")
        btn_dxf.pack(side="left")
        dxf_lbl = ttk.Label(
            dxf_frame,
            text=os.path.basename(var_dxf.get()) if var_dxf.get() else "—",
            style="WM.Muted.TLabel",
        )
        dxf_lbl.pack(side="left", padx=6)

        def select_img():
            p = filedialog.askopenfilename(filetypes=[("Obrazy", "*.png *.jpg *.jpeg")])
            if not p:
                return
            numer = (var_nr.get() or "").strip().zfill(3)
            dest_dir = _media_dir()
            ext = os.path.splitext(p)[1].lower()
            dest = os.path.join(dest_dir, f"{numer}_img{ext}")
            try:
                shutil.copy2(p, dest)
                rel = os.path.relpath(dest, _resolve_tools_dir())
                var_img.set(rel)
                img_lbl.config(text=os.path.basename(dest))
            except (OSError, shutil.Error) as e:
                _dbg("Błąd kopiowania obrazu:", e)

        def select_dxf():
            p = filedialog.askopenfilename(filetypes=[("DXF", "*.dxf")])
            if not p:
                return
            numer = (var_nr.get() or "").strip().zfill(3)
            dest_dir = _media_dir()
            dest = os.path.join(dest_dir, f"{numer}.dxf")
            try:
                shutil.copy2(p, dest)
                rel = os.path.relpath(dest, _resolve_tools_dir())
                var_dxf.set(rel)
                dxf_lbl.config(text=os.path.basename(dest))
                png = _generate_dxf_preview(dest)
                if png:
                    rel_png = os.path.relpath(png, _resolve_tools_dir())
                    var_dxf_png.set(rel_png)
            except (OSError, shutil.Error) as e:
                _dbg("Błąd kopiowania DXF:", e)

        def preview_media():
            path = (var_img.get() or "").strip()
            dxf_png = (var_dxf_png.get() or "").strip()
            dxf = (var_dxf.get() or "").strip()
            base = _resolve_tools_dir()
            for rel in (path, dxf_png, dxf):
                if rel:
                    full = os.path.join(base, rel)
                    if os.path.exists(full):
                        try:
                            if os.name == "nt":
                                os.startfile(full)  # type: ignore[attr-defined]
                            elif sys.platform == "darwin":
                                subprocess.run(["open", full], check=False)
                            else:
                                subprocess.run(["xdg-open", full], check=False)
                        except (OSError, subprocess.SubprocessError) as e:
                            messagebox.showwarning("Podgląd", f"Nie udało się otworzyć pliku: {e}")
                        return
            messagebox.showinfo("Podgląd", "Brak pliku do podglądu.")

        btn_img.config(command=select_img)
        btn_dxf.config(command=select_dxf)
        preview_btn.config(command=preview_media)
        preview_btn.bind("<Return>", lambda e: preview_media())

        row("Obraz", img_frame)
        row("Plik DXF", dxf_frame)

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
                except tk.TclError:
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
                "ts_done": t.get("ts_done","")
            })

        def _has_title(title: str) -> bool:
            tl = (title or "").strip().lower()
            return any((t.get("tytul","").strip().lower() == tl) for t in tasks)

        def _add_default_tasks_for_status(status_name: str) -> None:
            status_clean = (status_name or "").strip()
            type_clean = (var_typ.get() or "").strip()
            if not status_clean or not type_clean:
                return
            collection_id = _active_collection()
            defaults = _task_names_for_status(collection_id, type_clean, status_clean)
            print(
                "[WM-DBG][NARZ] Zadania z definicji: "
                f"coll={collection_id} typ={type_clean} "
                f"status={status_clean} → {len(defaults)} zadań"
            )
            added = False
            for title in defaults:
                if _has_title(title):
                    continue
                tasks.append({"tytul": title, "done": False, "by": "", "ts_done": ""})
                added = True
            if added:
                repaint_tasks()

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
            try:
                _refresh_task_presets()
            except Exception:
                pass
            new_st = (var_st.get() or "").strip()
            # garda: jeśli to samo co ostatnio obsłużone, nic nie rób
            if new_st == (last_applied_status[0] or ""):
                return
            phase = _phase_for_status(tool_mode, new_st)
            if phase:
                _apply_template_for_phase(phase)
            _add_default_tasks_for_status(new_st)
            if tool_mode == "NOWE" and new_st.lower() == "odbiór zakończony".lower():
                if messagebox.askyesno("Przenieść", "Przenieść do SN?"):
                    convert_var.set(True)
                    convert_tasks_var.set("keep")
                    try:
                        cb_conv.current(0)
                    except tk.TclError:
                        pass
                    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                    for t in tasks:
                        if not t.get("done"):
                            t["done"] = True
                            t["by"] = login or "system"
                            t["ts_done"] = now_ts
                    repaint_tasks()
                    hist_items.append({"ts": now_ts, "by": (login or "system"), "z": "[zadania]", "na": "auto ✔ przy przeniesieniu do SN"})
                    hist_view.insert("", 0, values=(now_ts, login or "system", "[zadania]", "auto ✔ przy przeniesieniu do SN"))
            status_values = [s for s in _status_values_list() if s]
            final_status = status_values[-1] if status_values else ""
            if final_status and new_st.lower() == final_status.lower():
                now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                marked_any = False
                for item in tasks:
                    if not item.get("done"):
                        item["done"] = True
                        item["by"] = login or "system"
                        item["ts_done"] = now_ts
                        marked_any = True
                if marked_any:
                    repaint_tasks()
                    hist_items.append({
                        "ts": now_ts,
                        "by": (login or "system"),
                        "z": "[zadania]",
                        "na": "auto ✔ przy statusie końcowym",
                    })
                    hist_view.insert(
                        "",
                        0,
                        values=(
                            now_ts,
                            login or "system",
                            "[zadania]",
                            "auto ✔ przy statusie końcowym",
                        ),
                    )
                else:
                    try:
                        comment = simpledialog.askstring(
                            "Brak odhaczeń",
                            "Nie odhaczono żadnych zadań dla ostatniego statusu.\n"
                            "Podaj komentarz (dlaczego):",
                            parent=dlg,
                        )
                    except Exception:
                        comment = ""
                    msg = f"Ostatni status '{new_st}': brak zadań do odhaczenia."
                    if comment:
                        msg += f" Komentarz: {comment}"
                    hist_items.append(
                        {
                            "ts": now_ts,
                            "by": (login or "system"),
                            "z": "[zadania]",
                            "na": msg,
                        }
                    )
                    hist_view.insert(
                        "",
                        0,
                        values=(now_ts, login or "system", "[zadania]", msg),
                    )
            last_status[0] = new_st
            last_applied_status[0] = new_st

        cb_status.bind("<<ComboboxSelected>>", _on_status_change)
        # (bez '<FocusOut>' – żeby nie dublować)

        # Pasek narzędzi do zadań (manualnie też można)
        tools_bar = ttk.Frame(frm, style="WM.TFrame"); tools_bar.grid(row=r+1, column=0, columnspan=2, sticky="ew", pady=(6,0))
        legacy_task_presets = list(_task_templates_from_config())
        tmpl_var = tk.StringVar()
        tmpl_box = ttk.Combobox(
            tools_bar,
            textvariable=tmpl_var,
            values=legacy_task_presets,
            state="readonly",
            width=36,
        )
        tmpl_box.pack(side="left")

        def _refresh_task_presets() -> None:
            type_name = (var_typ.get() or "").strip()
            status_name = (var_st.get() or "").strip()
            collection_id = _active_collection()
            try:
                tasks_from_defs = _task_names_for_status(collection_id, type_name, status_name)
            except Exception:
                tasks_from_defs = []
            if tasks_from_defs:
                tmpl_box.config(values=tasks_from_defs)
                current = (tmpl_var.get() or "").strip()
                if current not in tasks_from_defs:
                    tmpl_var.set(tasks_from_defs[0])
                print(
                    "[WM-DBG][TOOLS_UI] presets set from defs "
                    f"coll={collection_id} type='{type_name}' status='{status_name}' "
                    f"count={len(tasks_from_defs)}"
                )
                return
            alt_status: str | None = None
            if type_name and status_name and collection_id:
                try:
                    for candidate in _status_names_for_type(collection_id, type_name):
                        cand_clean = (candidate or "").strip()
                        if not cand_clean or cand_clean == status_name:
                            continue
                        cand_tasks = _task_names_for_status(
                            collection_id, type_name, cand_clean
                        )
                        if cand_tasks:
                            alt_status = cand_clean
                            break
                except Exception:
                    alt_status = None
            if alt_status:
                try:
                    ask_switch = messagebox.askyesno(
                        "Brak zadań dla statusu",
                        (
                            f"Dla statusu „{status_name}” nie ma zdefiniowanych zadań.\n"
                            f"Czy przełączyć na najbliższy status z zadaniami: „{alt_status}”?"
                        ),
                    )
                except Exception:
                    ask_switch = False
                if ask_switch:
                    try:
                        cb_status.set(alt_status)
                    except Exception:
                        pass
                    var_st.set(alt_status)
                    status_name = alt_status
                    try:
                        tasks_from_defs = _task_names_for_status(
                            collection_id, type_name, alt_status
                        )
                    except Exception:
                        tasks_from_defs = []
                    if tasks_from_defs:
                        tmpl_box.config(values=tasks_from_defs)
                        current = (tmpl_var.get() or "").strip()
                        if current not in tasks_from_defs:
                            tmpl_var.set(tasks_from_defs[0])
                        print(
                            f"[WM-DBG][TOOLS_UI] status auto-switched to '{alt_status}' "
                            f"(tasks={len(tasks_from_defs)})"
                        )
                        return
            tmpl_box.config(values=legacy_task_presets)
            current = (tmpl_var.get() or "").strip()
            if legacy_task_presets and current not in legacy_task_presets:
                tmpl_var.set(legacy_task_presets[0])
            print(
                "[WM-DBG][TOOLS_UI] no task defs for "
                f"type='{type_name}' status='{status_name}' — user kept status"
            )

        _refresh_task_presets()

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
            if i < 0:
                return
            _remove_task(tasks, i)
            repaint_tasks()
        def _toggle_done():
            i = _sel_idx()
            if i < 0:
                return
            t = tasks[i]
            t["done"] = not t["done"]
            if t["done"]:
                t["by"] = login or "nieznany"
                t["ts_done"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                # [MAGAZYN] zużycie materiałów powiązanych z zadaniem / BOM
                try:
                    zuzyte = LZ.consume_for_task(
                        tool_id=str(nr_auto), task=t, uzytkownik=login or "system"
                    )
                    if zuzyte:
                        t["zuzyte_materialy"] = (t.get("zuzyte_materialy") or []) + list(
                            zuzyte
                        )
                except (KeyError, ValueError, RuntimeError) as _e:
                    t["done"] = False
                    t["by"] = ""
                    t["ts_done"] = ""
                    messagebox.showerror("Magazyn", f"Błąd zużycia: {_e}")
            else:
                try:
                    zuzyte = t.get("zuzyte_materialy")
                    if zuzyte:
                        for poz in zuzyte:
                            LM.zwrot(
                                poz["id"],
                                float(poz["ilosc"]),
                                uzytkownik=login or "system",
                            )
                        t["zuzyte_materialy"] = []
                except (KeyError, ValueError, RuntimeError) as _e:
                    t["done"] = True
                    messagebox.showerror("Magazyn", f"Błąd zwrotu: {_e}")
                    return
                t["by"] = ""
                t["ts_done"] = ""
            repaint_tasks()
        ttk.Button(tools_bar, text="Usuń zaznaczone", style="WM.Side.TButton",
                   command=_del_sel).pack(side="left", padx=(6,0))
        ttk.Button(tools_bar, text="Oznacz/Cofnij ✔", style="WM.Side.TButton",
                   command=_toggle_done).pack(side="left", padx=(6,0))

        def _update_global_tasks(comment, ts):
            self_ref = locals().get("self")
            if self_ref is not None and getattr(self_ref, "global_tasks", None) is None:
                self_ref.global_tasks = []
            path = os.path.join("data", "zadania_narzedzia.json")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                data = []
            if self_ref is not None:
                self_ref.global_tasks = data
            changed = False
            for item in data:
                if item.get("status") != "Zrobione":
                    item["status"] = "Zrobione"
                    item["by"] = login or "nieznany"
                    item["ts_done"] = ts
                    if comment:
                        item["komentarz"] = comment
                    changed = True
            if changed:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

        def _mark_all_done():
            self_ref = locals().get("self")
            if self_ref is not None and getattr(self_ref, "global_tasks", None) is None:
                self_ref.global_tasks = []
            comment = simpledialog.askstring(
                "Komentarz",
                "Komentarz do wykonania wszystkich zadań:",
                parent=dlg,
            )
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            for t in tasks:
                if not t.get("done"):
                    t["done"] = True
                    t["by"] = login or "nieznany"
                    t["ts_done"] = ts
                    if comment:
                        t["komentarz"] = comment
            if self_ref is None or not hasattr(self_ref, "tasks_listbox"):
                print("[WM-DBG][TASKS] listbox missing, skip refresh")
                return
            repaint_tasks()
            _update_global_tasks(comment, ts)
            print("[WM-DBG][TASKS] marked all done")

        ttk.Button(
            tools_bar,
            text="Zaznacz wszystkie jako wykonane",
            style="WM.Side.TButton",
            command=_mark_all_done,
        ).pack(side="left", padx=(6,0))

        # --- PRZYCISKI ZAPISU ---
        btns = ttk.Frame(dlg, padding=8, style="WM.TFrame"); btns.pack(fill="x")

        def _suggest_after(n, mode_local):
            if mode_local == "NOWE":
                nxt = _next_free_in_range(max(1, n+1), 499)
            else:
                nxt = _next_free_in_range(max(500, n+1), 1000)
            return nxt or "—"

        def save(_event=None):
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
            status_values = [s for s in _status_values_list() if s]
            allowed_lower = {x.lower() for x in allowed}
            allowed_lower.update(s.lower() for s in status_values)
            if (st_new.lower() not in allowed_lower) and (raw_status.lower() not in allowed_lower):
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
            historia = list(hist_items)
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
                "obraz": (var_img.get() or "").strip(),
                "dxf": (var_dxf.get() or "").strip(),
                "dxf_png": (var_dxf_png.get() or "").strip(),
            }
            if tool_mode_local == "STARE":
                data_obj["is_old"] = True
                data_obj["kategoria"] = "SN"

            _save_tool(data_obj)
            dlg.destroy()
            refresh_list()

        ttk.Button(btns, text="Zapisz", command=save, style="WM.Side.TButton").pack(side="right")
        ttk.Button(btns, text="Anuluj", command=dlg.destroy, style="WM.Side.TButton").pack(side="right", padx=(0,8))
        dlg.bind("<Return>", save)

    # ===================== BINDY / START =====================
    def on_double(_=None):
        sel = tree.focus()
        if not sel: return
        open_tool_dialog(row_data.get(sel))

    _dbg("Init panel_narzedzia – start listy")
    btn_add.configure(command=choose_mode_and_add)
    tree.bind("<Double-1>", on_double)
    tree.bind("<Return>", on_double)
    search_var.trace_add("write", refresh_list)
    refresh_list()

__all__ = [
    "panel_narzedzia",
    "_profiles_usernames",
    "_current_user",
    "_selected_task",
    "_asgn_assign",
    "_refresh_assignments_view",
]
# Koniec pliku
