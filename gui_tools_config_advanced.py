"""Zaawansowany edytor konfiguracji zadań narzędzi (kolekcje NN/SN)."""

from __future__ import annotations

import glob
import json
import os
import re
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import logika_zadan as LZ

COLLECTIONS = ("NN", "SN")
MAX_TOOL_TYPES = 8
MAX_STATUSES_PER_TYPE = 8
MAX_TASKS_PER_STATUS = 10
BACKUP_KEEP_LAST = 5


def _wm(msg: str) -> None:
    try:
        print(f"[WM-DBG][TOOLS_ADV] {msg}")
    except Exception:  # pragma: no cover - debug helper
        pass


def _require_brygadzista_auth(master: tk.Misc) -> bool:
    """Prosta walidacja roli brygadzisty (login+hasło muszą być podane)."""

    login = simpledialog.askstring(
        "Autoryzacja", "Login brygadzisty:", parent=master
    )
    if not login:
        return False
    pwd = simpledialog.askstring(
        "Autoryzacja", "Hasło brygadzisty:", parent=master, show="*"
    )
    if not pwd:
        return False
    return True


def _make_backup(path: str) -> None:
    """Zapisz kopię zapasową pliku wraz z obcięciem starych backupów."""

    if not os.path.exists(path):
        return
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_path = f"{path}.bak.{ts}.json"
    try:
        with open(path, "rb") as src, open(backup_path, "wb") as dst:
            dst.write(src.read())
        _wm(f"Backup zapisany: {backup_path}")
    except OSError as exc:  # pragma: no cover - best effort
        print(f"[WM-DBG][TOOLS_ADV] Backup nieudany: {exc}")
    try:
        backups = sorted(glob.glob(f"{path}.bak.*.json"))
        for old in backups[: max(0, len(backups) - BACKUP_KEEP_LAST)]:
            try:
                os.remove(old)
            except OSError:
                pass
    except OSError:
        pass


def _make_unique_id(label: str, existing: set[str]) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "_", label.strip())
    slug = slug.strip("_") or "ID"
    candidate = slug.upper()
    counter = 2
    while candidate in existing:
        candidate = f"{slug}_{counter}".upper()
        counter += 1
    return candidate


class ToolsConfigDialog(tk.Toplevel):
    """Okno edycji typów/statusów zadań z kolekcjami NN/SN."""

    def __init__(
        self,
        master: tk.Widget | None = None,
        *,
        path: str,
        on_save=None,
    ) -> None:
        super().__init__(master)
        self.title("Narzędzia — konfiguracja (NN/SN)")
        self.resizable(True, True)
        try:
            self.attributes("-topmost", True)
            self.lift()
            self.focus_force()
        except Exception:
            pass
        self._write_through = True
        self.path = path
        self.on_save = on_save

        self._data = self._load_or_init()
        self._ensure_shared_types_integrity()

        self._current_collection = COLLECTIONS[0]
        self._current_type_index: int | None = None
        self._current_status_index: int | None = None
        self._visible_type_indexes: list[int] = []
        self._visible_status_indexes: list[int] = []
        self._types_index_map: list[int] = self._visible_type_indexes

        self._collection_var = tk.StringVar(value=COLLECTIONS[0])
        self._search_var = tk.StringVar()

        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Label(top, text="Kolekcja:").pack(side="left")
        self._collection_cb = ttk.Combobox(
            top,
            values=COLLECTIONS,
            state="readonly",
            textvariable=self._collection_var,
            width=6,
        )
        self._collection_cb.pack(side="left", padx=(4, 12))
        self._collection_cb.bind("<<ComboboxSelected>>", self._on_collection_change)

        ttk.Label(top, text="Szukaj:").pack(side="left")
        search_entry = ttk.Entry(top, textvariable=self._search_var, width=24)
        search_entry.pack(side="left", fill="x", expand=True)
        search_entry.bind("<KeyRelease>", self._on_search)

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Typy (wspólne NN/SN)").pack(anchor="w")
        self.types_list = tk.Listbox(left, height=12, exportselection=False)
        self.types_list.pack(fill="both", expand=True, pady=(2, 4))
        self.types_list.bind("<<ListboxSelect>>", self._on_type_select)
        self.types_list.bind("<Double-Button-1>", self._on_type_edit)
        type_btns = ttk.Frame(left)
        type_btns.pack(fill="x")
        ttk.Button(type_btns, text="Dodaj typ", command=self._add_type).pack(side="left")
        ttk.Button(type_btns, text="Usuń typ", command=self._del_type).pack(
            side="left", padx=(6, 0)
        )

        mid = ttk.Frame(main)
        mid.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ttk.Label(mid, text="Statusy (dla kolekcji)").pack(anchor="w")
        status_frame = ttk.Frame(mid)
        status_frame.pack(fill="both", expand=True, pady=(2, 4))
        self.status_list = tk.Listbox(status_frame, height=12, exportselection=False)
        self.status_list.pack(side="left", fill="both", expand=True)
        self.status_list.bind("<<ListboxSelect>>", self._on_status_select)
        self.status_list.bind("<Double-Button-1>", self._on_status_edit)
        status_arrows = ttk.Frame(status_frame)
        status_arrows.pack(side="left", fill="y", padx=(4, 0), anchor="n")
        ttk.Button(
            status_arrows,
            text="▲",
            width=3,
            command=lambda: self._move_status(-1),
        ).pack(pady=(0, 4))
        ttk.Button(
            status_arrows,
            text="▼",
            width=3,
            command=lambda: self._move_status(1),
        ).pack()
        status_btns = ttk.Frame(mid)
        status_btns.pack(fill="x")
        ttk.Button(status_btns, text="Dodaj status", command=self._add_status).pack(
            side="left"
        )
        ttk.Button(status_btns, text="Usuń status", command=self._del_status).pack(
            side="left", padx=(6, 0)
        )

        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ttk.Label(right, text="Zadania (dla statusu)").pack(anchor="w")
        tasks_frame = ttk.Frame(right)
        tasks_frame.pack(fill="both", expand=True, pady=(2, 4))
        self.tasks_list = tk.Listbox(tasks_frame, height=12, exportselection=False)
        self.tasks_list.pack(side="left", fill="both", expand=True)
        self.tasks_list.bind("<Double-Button-1>", self._on_task_edit)
        task_arrows = ttk.Frame(tasks_frame)
        task_arrows.pack(side="left", fill="y", padx=(4, 0), anchor="n")
        ttk.Button(
            task_arrows,
            text="▲",
            width=3,
            command=lambda: self._move_task(-1),
        ).pack(pady=(0, 4))
        ttk.Button(
            task_arrows,
            text="▼",
            width=3,
            command=lambda: self._move_task(1),
        ).pack()
        task_btns = ttk.Frame(right)
        task_btns.pack(fill="x")
        ttk.Button(task_btns, text="Dodaj zadanie", command=self._add_task).pack(
            side="left"
        )
        ttk.Button(task_btns, text="Usuń zadanie", command=self._del_task).pack(
            side="left", padx=(6, 0)
        )

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=6, pady=6)
        ttk.Button(bottom, text="Zapisz", command=self._save).pack(side="left")
        ttk.Button(bottom, text="Anuluj", command=self.destroy).pack(
            side="left", padx=(6, 0)
        )

        self._current_collection = self._collection_var.get()
        self._refresh_types()

    # ===== model helpers ==================================================
    def _load_or_init(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            data = {"collections": {}}
        except json.JSONDecodeError as exc:
            messagebox.showerror("Błąd", f"Niepoprawny JSON: {exc}")
            data = {"collections": {}}
        collections = data.setdefault("collections", {})
        legacy = collections.pop("ST", None)
        collections.setdefault("NN", {"types": []})
        if legacy is not None and "SN" not in collections:
            collections["SN"] = legacy
        collections.setdefault("SN", {"types": []})
        for cid in COLLECTIONS:
            coll = collections.get(cid, {})
            coll.setdefault("types", [])
            for typ in coll.get("types", []):
                typ.setdefault("id", typ.get("id") or _make_unique_id("TYP", set()))
                typ.setdefault("name", typ.get("name") or typ.get("id"))
                typ.setdefault("statuses", [])
                for status in typ.get("statuses", []):
                    status.setdefault(
                        "id", status.get("id") or _make_unique_id("STATUS", set())
                    )
                    status.setdefault("name", status.get("name") or status.get("id"))
                    status.setdefault("tasks", [])
        return data

    def _ensure_shared_types_integrity(self) -> None:
        collections = self._data.setdefault("collections", {})
        nn_types = collections.setdefault("NN", {}).setdefault("types", [])
        sn_types = collections.setdefault("SN", {}).setdefault("types", [])
        sn_by_id = {t.get("id"): t for t in sn_types}
        new_sn_types: list[dict] = []
        for typ in nn_types:
            typ.setdefault("statuses", [])
            tid = typ.get("id")
            name = typ.get("name") or tid or ""
            sn_entry = sn_by_id.get(tid)
            if sn_entry is None:
                sn_entry = {"id": tid, "name": name, "statuses": []}
            else:
                sn_entry.setdefault("statuses", [])
                sn_entry["id"] = tid
                sn_entry["name"] = name
            new_sn_types.append(sn_entry)
        collections["SN"]["types"] = new_sn_types

    def _get_shared_types(self) -> list[dict]:
        return self._data["collections"]["NN"].setdefault("types", [])

    def _get_statuses_for_current(self, type_idx: int) -> list[dict]:
        coll = self._data["collections"].setdefault(self._current_collection, {})
        types = coll.setdefault("types", [])
        if 0 <= type_idx < len(types):
            return types[type_idx].setdefault("statuses", [])
        return []

    # ===== UI refresh =====================================================
    def _refresh_types(
        self,
        preferred_idx: int | None = None,
        preferred_status_idx: int | None = None,
    ) -> None:
        types = self._get_shared_types()
        query = (self._search_var.get() or "").strip().lower()
        self.types_list.delete(0, tk.END)
        self._visible_type_indexes.clear()
        for idx, typ in enumerate(types):
            label = str(typ.get("name") or typ.get("id") or "")
            if query and query not in label.lower():
                continue
            self.types_list.insert(tk.END, label)
            self._visible_type_indexes.append(idx)
        if not self._visible_type_indexes:
            self._current_type_index = None
            self._current_status_index = None
            self._refresh_statuses()
            return
        target = preferred_idx if preferred_idx is not None else self._current_type_index
        if target not in self._visible_type_indexes:
            target = self._visible_type_indexes[0]
        self._select_type_by_index(target, preferred_status_idx)

    def _refresh_statuses(self, preferred_idx: int | None = None) -> None:
        self.status_list.delete(0, tk.END)
        self._visible_status_indexes.clear()
        type_idx = self._current_type_index
        if type_idx is None:
            self._current_status_index = None
            self._refresh_tasks()
            return
        statuses = self._get_statuses_for_current(type_idx)
        query = (self._search_var.get() or "").strip().lower()
        for idx, status in enumerate(statuses):
            label = str(status.get("name") or status.get("id") or "")
            if query and query not in label.lower():
                continue
            self.status_list.insert(tk.END, label)
            self._visible_status_indexes.append(idx)
        if not self._visible_status_indexes:
            self._current_status_index = None
            self._refresh_tasks()
            return
        target = preferred_idx if preferred_idx is not None else self._current_status_index
        if target not in self._visible_status_indexes:
            target = self._visible_status_indexes[0]
        self._select_status_by_index(target)

    def _refresh_tasks(self) -> None:
        self.tasks_list.delete(0, tk.END)
        type_idx = self._current_type_index
        status_idx = self._current_status_index
        if type_idx is None or status_idx is None:
            return
        coll = self._data["collections"].setdefault(self._current_collection, {})
        types = coll.setdefault("types", [])
        if not (0 <= type_idx < len(types)):
            return
        statuses = types[type_idx].setdefault("statuses", [])
        if not (0 <= status_idx < len(statuses)):
            return
        tasks = list(statuses[status_idx].get("tasks") or [])
        for task in tasks:
            self.tasks_list.insert(tk.END, str(task))

    # ===== selections =====================================================
    def _select_type_by_index(
        self,
        data_index: int,
        preferred_status_idx: int | None = None,
    ) -> None:
        self._current_type_index = data_index
        for visible_idx, actual_idx in enumerate(self._visible_type_indexes):
            if actual_idx == data_index:
                self.types_list.selection_clear(0, tk.END)
                self.types_list.selection_set(visible_idx)
                self.types_list.activate(visible_idx)
                break
        self._refresh_statuses(preferred_status_idx)

    def _select_status_by_index(self, data_index: int) -> None:
        self._current_status_index = data_index
        for visible_idx, actual_idx in enumerate(self._visible_status_indexes):
            if actual_idx == data_index:
                self.status_list.selection_clear(0, tk.END)
                self.status_list.selection_set(visible_idx)
                self.status_list.activate(visible_idx)
                break
        self._refresh_tasks()

    def _selected_type_true_index(self) -> int | None:
        """Zwraca indeks typu w danych zgodny z aktualnym wyborem."""

        sel = self.types_list.curselection()
        if sel:
            visible_idx = sel[0]
            if 0 <= visible_idx < len(self._types_index_map):
                return self._types_index_map[visible_idx]
        return self._current_type_index

    def _selected_type_index(self) -> int | None:
        return self._selected_type_true_index()

    def _selected_status_index(self) -> int | None:
        return self._current_status_index

    # ===== event handlers =================================================
    def _on_collection_change(self, *_event) -> None:
        new_coll = self._collection_var.get()
        if new_coll == self._current_collection:
            return
        if not _require_brygadzista_auth(self):
            self._collection_var.set(self._current_collection)
            return
        self._current_collection = new_coll
        self._current_status_index = None
        self._refresh_statuses()

    def _on_search(self, *_event) -> None:
        self._refresh_types(
            preferred_idx=self._current_type_index,
            preferred_status_idx=self._current_status_index,
        )

    def _on_type_select(self, *_event) -> None:
        _wm("type_select")
        sel = self.types_list.curselection()
        if not sel:
            self._current_type_index = None
            self._current_status_index = None
            self._refresh_statuses()
            return
        visible_idx = sel[0]
        if visible_idx >= len(self._visible_type_indexes):
            return
        data_index = self._visible_type_indexes[visible_idx]
        self._select_type_by_index(data_index)

    def _on_status_select(self, *_event) -> None:
        _wm("status_select")
        sel = self.status_list.curselection()
        if not sel:
            self._current_status_index = None
            self._refresh_tasks()
            return
        visible_idx = sel[0]
        if visible_idx >= len(self._visible_status_indexes):
            return
        data_index = self._visible_status_indexes[visible_idx]
        self._select_status_by_index(data_index)

    def _on_type_edit(self, *_event) -> None:
        idx = self._selected_type_true_index()
        if idx is None:
            return
        shared_types = self._get_shared_types()
        current = shared_types[idx]
        label = current.get("name") or current.get("id") or ""
        value = simpledialog.askstring(
            "Edycja typu", "Nazwa typu:", initialvalue=str(label), parent=self
        )
        if not value:
            return
        value = value.strip()
        if not value:
            return
        if any(
            (t is not current and str(t.get("name", "")).lower() == value.lower())
            for t in shared_types
        ):
            messagebox.showinfo("Typy", "Taki typ już istnieje.")
            return
        for cid in COLLECTIONS:
            types = self._data["collections"][cid].setdefault("types", [])
            if 0 <= idx < len(types):
                types[idx]["name"] = value
        _wm(f"edited type idx={idx} name={value}")
        self._refresh_types(preferred_idx=idx)
        if self._write_through:
            self._save_now()

    def _on_status_edit(self, *_event) -> None:
        type_idx = self._selected_type_true_index()
        status_idx = self._selected_status_index()
        if type_idx is None or status_idx is None:
            return
        statuses = self._get_statuses_for_current(type_idx)
        current = statuses[status_idx]
        label = current.get("name") or current.get("id") or ""
        value = simpledialog.askstring(
            "Edycja statusu", "Nazwa statusu:", initialvalue=str(label), parent=self
        )
        if not value:
            return
        value = value.strip()
        if not value:
            return
        if any(
            (s is not current and str(s.get("name", "")).lower() == value.lower())
            for s in statuses
        ):
            messagebox.showinfo("Statusy", "Taki status już istnieje.")
            return
        current["name"] = value
        self._refresh_statuses(preferred_idx=status_idx)
        if self._write_through:
            self._save_now()

    def _on_task_edit(self, *_event) -> None:
        type_idx = self._selected_type_true_index()
        status_idx = self._selected_status_index()
        if type_idx is None or status_idx is None:
            return
        statuses = self._get_statuses_for_current(type_idx)
        status = statuses[status_idx]
        tasks = status.setdefault("tasks", [])
        sel = self.tasks_list.curselection()
        if not sel:
            return
        task_idx = sel[0]
        if not (0 <= task_idx < len(tasks)):
            return
        current = str(tasks[task_idx])
        value = simpledialog.askstring(
            "Edycja zadania", "Treść zadania:", initialvalue=current, parent=self
        )
        if not value:
            return
        value = value.strip()
        if not value:
            return
        tasks[task_idx] = value
        self._refresh_tasks()
        if self._write_through:
            self._save_now()

    # ===== reorder operations (▲/▼) =====================================
    def _move_status(self, delta: int) -> None:
        type_idx = self._selected_type_true_index()
        status_idx = self._selected_status_index()
        if type_idx is None or status_idx is None:
            return
        statuses = self._get_statuses_for_current(type_idx)
        target_idx = status_idx + delta
        if not (0 <= target_idx < len(statuses)):
            return
        statuses[status_idx], statuses[target_idx] = (
            statuses[target_idx],
            statuses[status_idx],
        )
        self._refresh_statuses(preferred_idx=target_idx)
        if self._write_through:
            self._save_now()
        _wm(
            f"moved status type_idx={type_idx} from={status_idx} to={target_idx} "
            f"coll={self._current_collection}"
        )

    def _move_task(self, delta: int) -> None:
        type_idx = self._selected_type_true_index()
        status_idx = self._selected_status_index()
        if type_idx is None or status_idx is None:
            return
        statuses = self._get_statuses_for_current(type_idx)
        if not (0 <= status_idx < len(statuses)):
            return
        tasks = statuses[status_idx].setdefault("tasks", [])
        sel = self.tasks_list.curselection()
        if not sel:
            return
        task_idx = sel[0]
        target_idx = task_idx + delta
        if not (0 <= target_idx < len(tasks)):
            return
        tasks[task_idx], tasks[target_idx] = tasks[target_idx], tasks[task_idx]
        self._refresh_tasks()
        self.tasks_list.selection_clear(0, tk.END)
        self.tasks_list.selection_set(target_idx)
        self.tasks_list.activate(target_idx)
        self.tasks_list.see(target_idx)
        if self._write_through:
            self._save_now()
        _wm(
            "moved task type_idx=%s status_idx=%s from=%s to=%s"
            % (type_idx, status_idx, task_idx, target_idx)
        )

    # ===== add/remove operations =========================================
    def _add_type(self) -> None:
        shared_types = self._get_shared_types()
        if len(shared_types) >= MAX_TOOL_TYPES:
            messagebox.showwarning(
                "Limit typów", f"Maksymalnie {MAX_TOOL_TYPES} typów narzędzi."
            )
            return
        value = simpledialog.askstring("Nowy typ", "Nazwa typu:", parent=self)
        if not value:
            return
        value = value.strip()
        if not value:
            return
        if any(str(t.get("name", "")).lower() == value.lower() for t in shared_types):
            messagebox.showinfo("Typy", "Taki typ już istnieje.")
            return
        existing_ids = {
            str(t.get("id"))
            for t in shared_types
            if str(t.get("id"))
        }
        type_id = _make_unique_id(value, existing_ids)
        shared_types.append({"id": type_id, "name": value, "statuses": []})
        sn_types = self._data["collections"]["SN"].setdefault("types", [])
        sn_types.append({"id": type_id, "name": value, "statuses": []})
        new_index = len(shared_types) - 1
        _wm(f"added type idx={new_index} id={type_id} name={value}")
        try:
            self._search_var.set("")
        except tk.TclError:
            pass
        self._refresh_types(preferred_idx=new_index)
        if self._write_through:
            self._save_now()

    def _del_type(self) -> None:
        idx = self._selected_type_true_index()
        if idx is None:
            return
        label = str(
            self._get_shared_types()[idx].get("name")
            or self._get_shared_types()[idx].get("id")
            or ""
        )
        if not messagebox.askyesno(
            "Usunąć typ?",
            f"Typ „{label}” zostanie usunięty z obu kolekcji. Kontynuować?",
        ):
            return
        for cid in COLLECTIONS:
            types = self._data["collections"][cid].setdefault("types", [])
            if 0 <= idx < len(types):
                types.pop(idx)
        shared_types = self._get_shared_types()
        preferred_idx = None
        if shared_types:
            preferred_idx = idx - 1
            if preferred_idx < 0:
                preferred_idx = 0
            if preferred_idx >= len(shared_types):
                preferred_idx = len(shared_types) - 1
        self._current_type_index = None
        self._current_status_index = None
        self._refresh_types(preferred_idx=preferred_idx)
        if self._write_through:
            self._save_now()

    def _add_status(self) -> None:
        type_idx = self._selected_type_true_index()
        if type_idx is None:
            if len(self._visible_type_indexes) == 1:
                auto_idx = self._visible_type_indexes[0]
                self._select_type_by_index(auto_idx)
                type_idx = auto_idx
                _wm(f"add_status: auto-selected type_idx={type_idx} for single visible type")
            else:
                messagebox.showinfo(
                    "Wybierz typ",
                    "Najpierw wybierz typ narzędzia z listy po lewej.",
                )
                _wm("add_status blocked: no type selected")
                return
        statuses = self._get_statuses_for_current(type_idx)
        if len(statuses) >= MAX_STATUSES_PER_TYPE:
            messagebox.showwarning(
                "Limit statusów",
                f"Maksymalnie {MAX_STATUSES_PER_TYPE} statusów dla typu.",
            )
            return
        value = simpledialog.askstring("Nowy status", "Nazwa statusu:", parent=self)
        if not value:
            return
        value = value.strip()
        if not value:
            return
        if any(str(s.get("name", "")).lower() == value.lower() for s in statuses):
            messagebox.showinfo("Statusy", "Taki status już istnieje.")
            return
        existing_ids = {
            str(s.get("id"))
            for s in statuses
            if str(s.get("id"))
        }
        status_id = _make_unique_id(value, existing_ids)
        statuses.append({"id": status_id, "name": value, "tasks": []})
        new_index = len(statuses) - 1
        _wm(
            "added status idx=%s type_idx=%s coll=%s"
            % (new_index, type_idx, self._current_collection)
        )
        self._refresh_statuses(preferred_idx=new_index)
        if self._write_through:
            self._save_now()

    def _del_status(self) -> None:
        type_idx = self._selected_type_true_index()
        status_idx = self._selected_status_index()
        if type_idx is None or status_idx is None:
            return
        if not messagebox.askyesno(
            "Usunąć status?", "Status oraz jego zadania zostaną usunięte."
        ):
            return
        statuses = self._get_statuses_for_current(type_idx)
        if 0 <= status_idx < len(statuses):
            statuses.pop(status_idx)
        self._current_status_index = None
        self._refresh_statuses()
        if self._write_through:
            self._save_now()

    def _add_task(self) -> None:
        type_idx = self._selected_type_true_index()
        status_idx = self._selected_status_index()
        if type_idx is None or status_idx is None:
            return
        statuses = self._get_statuses_for_current(type_idx)
        status = statuses[status_idx]
        tasks = status.setdefault("tasks", [])
        if len(tasks) >= MAX_TASKS_PER_STATUS:
            messagebox.showwarning(
                "Limit zadań",
                f"Maksymalnie {MAX_TASKS_PER_STATUS} zadań dla statusu.",
            )
            return
        value = simpledialog.askstring("Nowe zadanie", "Treść zadania:", parent=self)
        if not value:
            return
        value = value.strip()
        if not value:
            return
        tasks.append(value)
        _wm(
            "added task type_idx=%s status_idx=%s coll=%s"
            % (type_idx, status_idx, self._current_collection)
        )
        self._refresh_tasks()
        if self._write_through:
            self._save_now()

    def _del_task(self) -> None:
        type_idx = self._selected_type_true_index()
        status_idx = self._selected_status_index()
        if type_idx is None or status_idx is None:
            return
        sel = self.tasks_list.curselection()
        if not sel:
            return
        task_idx = sel[0]
        statuses = self._get_statuses_for_current(type_idx)
        status = statuses[status_idx]
        tasks = status.setdefault("tasks", [])
        if not (0 <= task_idx < len(tasks)):
            return
        if not messagebox.askyesno("Usunąć zadanie?", "Czy usunąć wybrane zadanie?"):
            return
        tasks.pop(task_idx)
        self._refresh_tasks()
        if self._write_through:
            self._save_now()

    # ===== save ===========================================================
    def _save_now(self) -> bool:
        """Persist current configuration without closing the dialog."""

        self._ensure_shared_types_integrity()
        folder = os.path.dirname(self.path) or "."
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(
                "Błąd zapisu",
                f"Nie udało się utworzyć katalogu docelowego:\n{exc}",
            )
            return False
        try:
            _make_backup(self.path)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
        except (OSError, TypeError, ValueError) as exc:
            messagebox.showerror(
                "Błąd zapisu",
                f"Nie udało się zapisać konfiguracji narzędzi:\n{exc}",
            )
            return False
        try:
            LZ.invalidate_cache()
        except Exception as exc:  # pragma: no cover - best effort
            print(f"[WM-DBG][TOOLS_ADV] invalidate_cache error: {exc}")
        if callable(self.on_save) and self.on_save is not LZ.invalidate_cache:
            try:
                self.on_save()
            except Exception as exc:  # pragma: no cover - best effort
                print(f"[WM-DBG][TOOLS_ADV] on_save callback error: {exc}")
        _wm(f"auto-saved configuration to {self.path}")
        return True

    def _save(self) -> None:
        if not self._save_now():
            return
        messagebox.showinfo("Zapisano", "Konfiguracja narzędzi została zapisana.")
        self.destroy()

