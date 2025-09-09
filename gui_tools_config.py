import json
import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List

from utils.path_utils import cfg_path
import logika_zadan as LZ

try:
    from tools import collections_paths  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    collections_paths = None  # type: ignore

DEFAULT_PATH = cfg_path(os.path.join("data", "zadania_narzedzia.json"))
COLLECTIONS = ["NN", "ST"]


def _paths_for(collection: str) -> List[str]:
    """Resolve JSON paths for *collection*.

    If ``tools.collections_paths`` is defined it may be either a mapping or a
    callable returning a path or iterable of paths. When absent, a single file
    with both collections is used.
    """

    if collections_paths:
        paths: Any
        if callable(collections_paths):  # pragma: no branch - runtime choice
            paths = collections_paths(collection)  # type: ignore[call-arg]
        else:
            paths = collections_paths.get(collection)  # type: ignore[union-attr]
        if paths:
            if isinstance(paths, (list, tuple, set)):
                return [os.path.abspath(p) for p in paths]
            return [os.path.abspath(paths)]
    return [DEFAULT_PATH]


def _atomic_write(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def validate_structure(data: Dict[str, Any]) -> None:
    types = data.get("types") or []
    if len(types) > 8:
        raise ValueError("Za dużo typów (max 8)")
    seen_types: set[str] = set()
    for typ in types:
        tid = typ.get("id")
        if not tid or tid in seen_types:
            raise ValueError("Duplikat ID typu")
        seen_types.add(tid)
        statuses = typ.get("statuses") or []
        if len(statuses) > 8:
            raise ValueError(f"Za dużo statusów dla typu {tid}")
        seen_statuses: set[str] = set()
        for st in statuses:
            sid = st.get("id")
            if not sid or sid in seen_statuses:
                raise ValueError("Duplikat ID statusu")
            seen_statuses.add(sid)
            tasks = st.get("tasks") or []
            if len(tasks) > 8:
                raise ValueError(f"Za dużo zadań dla statusu {sid}")
            st.setdefault("auto_check_on_entry", False)


def load_collection(collection: str) -> Dict[str, Any]:
    path_list = _paths_for(collection)
    if collections_paths:
        path = path_list[0]
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            data = {"types": []}
        validate_structure(data)
        return data
    # variant A – single file containing both collections
    try:
        with open(DEFAULT_PATH, "r", encoding="utf-8") as fh:
            full = json.load(fh)
    except FileNotFoundError:
        full = {}
    data = full.get(collection, {"types": []})
    validate_structure(data)
    return data


def save_collection(collection: str, data: Dict[str, Any]) -> None:
    validate_structure(data)
    if collections_paths:
        for path in _paths_for(collection):
            _atomic_write(path, data)
    else:
        try:
            with open(DEFAULT_PATH, "r", encoding="utf-8") as fh:
                full = json.load(fh)
        except FileNotFoundError:
            full = {}
        full[collection] = data
        _atomic_write(DEFAULT_PATH, full)
    LZ._TOOL_TASKS_CACHE = None

class ToolsConfigWindow:
    """Simple editor window for tool task collections."""

    def __init__(self, master: tk.Misc) -> None:
        self.master = tk.Toplevel(master)
        self.master.title("Ustawienia narzędzi")
        self.collection = tk.StringVar(value=COLLECTIONS[0])
        top = ttk.Frame(self.master)
        top.pack(fill="x", padx=10, pady=5)
        ttk.Label(top, text="Kolekcja:").pack(side="left")
        cb = ttk.Combobox(
            top, values=COLLECTIONS, textvariable=self.collection, state="readonly"
        )
        cb.pack(side="left", padx=5)
        cb.bind("<<ComboboxSelected>>", lambda e: self._load())
        main = ttk.Frame(self.master)
        main.pack(fill="both", expand=True, padx=10, pady=5)
        self.list_types = tk.Listbox(main)
        self.list_statuses = tk.Listbox(main)
        self.list_tasks = tk.Listbox(main)
        self.list_types.grid(row=0, column=0, sticky="nsew")
        self.list_statuses.grid(row=0, column=1, sticky="nsew")
        self.list_tasks.grid(row=0, column=2, sticky="nsew")
        for i in range(3):
            main.columnconfigure(i, weight=1)
        main.rowconfigure(0, weight=1)
        btns = ttk.Frame(self.master)
        btns.pack(fill="x", padx=10, pady=5)
        ttk.Button(btns, text="Zapisz", command=self._save).pack(side="right")
        ttk.Button(btns, text="Zamknij", command=self.master.destroy).pack(
            side="right", padx=5
        )
        self.data: Dict[str, Any] = {"types": []}
        self._load()

    def _load(self) -> None:
        self.data = load_collection(self.collection.get())
        self.list_types.delete(0, tk.END)
        for t in self.data.get("types", []):
            self.list_types.insert(tk.END, t.get("name", t.get("id")))
        self.list_statuses.delete(0, tk.END)
        self.list_tasks.delete(0, tk.END)

    def _save(self) -> None:
        try:
            save_collection(self.collection.get(), self.data)
            messagebox.showinfo("Zapis", "Zapisano konfigurację.")
        except ValueError as e:
            messagebox.showerror("Błąd", str(e))


def open_tools_config(master: tk.Misc) -> None:
    ToolsConfigWindow(master)


__all__ = [
    "open_tools_config",
    "load_collection",
    "save_collection",
    "validate_structure",
]
