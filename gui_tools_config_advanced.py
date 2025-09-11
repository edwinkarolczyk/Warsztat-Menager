"""Zaawansowany edytor konfiguracji zadań narzędzi."""

from __future__ import annotations

import json
from contextlib import contextmanager
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import logika_zadan as LZ


class ToolsConfigDialog(tk.Toplevel):
    """Okno z listami Kolekcja → Typ → Status i edycją zadań."""

    def __init__(self, master: tk.Widget | None = None, *, path: str, on_save=None) -> None:
        super().__init__(master)
        self.title("Konfiguracja zadań narzędzi")
        self.resizable(True, True)
        self.path = path
        self.on_save = on_save
        self._ui_updating = False

        self.data = self._load_data()
        self.current_collection: dict | None = None
        self.current_type: dict | None = None
        self.current_status: dict | None = None

        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        top = ttk.Frame(main)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Kolekcja:").grid(row=0, column=0, sticky="w")
        self.combo_coll = ttk.Combobox(top, state="readonly")
        self.combo_coll.grid(row=1, column=0, sticky="nsew", padx=2)
        self.combo_coll.bind("<<ComboboxSelected>>", self._on_collection_change)

        ttk.Label(top, text="Typ:").grid(row=0, column=1, sticky="w")
        self.list_types = tk.Listbox(top, height=8)
        self.list_types.grid(row=1, column=1, sticky="nsew", padx=2)
        self.list_types.bind("<<ListboxSelect>>", self._on_type_select)

        ttk.Label(top, text="Status:").grid(row=0, column=2, sticky="w")
        self.list_status = tk.Listbox(top, height=8)
        self.list_status.grid(row=1, column=2, sticky="nsew", padx=2)
        self.list_status.bind("<<ListboxSelect>>", self._on_status_select)

        for i in range(3):
            top.columnconfigure(i, weight=1)

        ttk.Label(main, text="Zadania:").pack(anchor="w", pady=(4, 0))
        self.list_tasks = tk.Listbox(main, height=10)
        self.list_tasks.pack(fill=tk.BOTH, expand=True)

        btns = ttk.Frame(main)
        btns.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btns, text="Dodaj", command=self.add_task).pack(side=tk.LEFT)
        ttk.Button(btns, text="Edytuj", command=self.edit_task).pack(side=tk.LEFT)
        ttk.Button(btns, text="Usuń", command=self.delete_task).pack(side=tk.LEFT)
        ttk.Button(btns, text="Zapisz", command=self._save).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Anuluj", command=self.destroy).pack(side=tk.RIGHT)

        self._populate_collections()

    # ------------------------- UI helpers ---------------------------------
    @contextmanager
    def _suspend_ui(self):
        self._ui_updating = True
        try:
            yield
        finally:
            self._ui_updating = False

    def _load_data(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            return {"collections": {}}
        except json.JSONDecodeError as exc:
            messagebox.showerror("Błąd", f"Niepoprawny JSON: {exc}")
            return {"collections": {}}

    def _populate_collections(self) -> None:
        collections = sorted((self.data.get("collections") or {}).keys())
        with self._suspend_ui():
            self.combo_coll["values"] = collections
            if collections:
                self.combo_coll.set(collections[0])
        self._on_collection_change()

    def _on_collection_change(self, event=None) -> None:  # noqa: ANN001
        if self._ui_updating:
            return
        cid = self.combo_coll.get()
        self.current_collection = (self.data.get("collections") or {}).get(cid, {})
        self._populate_types()

    def _populate_types(self) -> None:
        types = self.current_collection.get("types") if self.current_collection else []
        self._type_name_to_id: dict[str, str] = {}
        with self._suspend_ui():
            self.list_types.delete(0, tk.END)
            for t in types or []:
                name = t.get("name", t.get("id"))
                self.list_types.insert(tk.END, name)
                self._type_name_to_id[name] = t.get("id")
            if types:
                self.list_types.selection_set(0)
        self._on_type_select()

    def _on_type_select(self, event=None) -> None:  # noqa: ANN001
        if self._ui_updating:
            return
        sel = self.list_types.curselection()
        if not sel:
            self.current_type = None
            self._populate_statuses()
            return
        name = self.list_types.get(sel[0])
        tid = self._type_name_to_id.get(name)
        types = self.current_collection.get("types") if self.current_collection else []
        self.current_type = next((t for t in types if t.get("id") == tid), None)
        self._populate_statuses()

    def _populate_statuses(self) -> None:
        statuses = self.current_type.get("statuses") if self.current_type else []
        self._status_name_to_id: dict[str, str] = {}
        with self._suspend_ui():
            self.list_status.delete(0, tk.END)
            for st in statuses or []:
                name = st.get("name", st.get("id"))
                self.list_status.insert(tk.END, name)
                self._status_name_to_id[name] = st.get("id")
            if statuses:
                self.list_status.selection_set(0)
        self._on_status_select()

    def _on_status_select(self, event=None) -> None:  # noqa: ANN001
        if self._ui_updating:
            return
        sel = self.list_status.curselection()
        if not sel:
            self.current_status = None
            self._refresh_tasks()
            return
        name = self.list_status.get(sel[0])
        sid = self._status_name_to_id.get(name)
        statuses = self.current_type.get("statuses") if self.current_type else []
        self.current_status = next((s for s in statuses if s.get("id") == sid), None)
        self._refresh_tasks()

    def _refresh_tasks(self) -> None:
        tasks = self.current_status.get("tasks") if self.current_status else []
        with self._suspend_ui():
            self.list_tasks.delete(0, tk.END)
            for t in tasks or []:
                self.list_tasks.insert(tk.END, t)

    # -------------------------- task ops ----------------------------------
    def add_task(self) -> None:
        if not self.current_status:
            return
        name = simpledialog.askstring("Dodaj zadanie", "Opis zadania:", parent=self)
        if name:
            self.current_status.setdefault("tasks", []).append(name)
            self._refresh_tasks()

    def edit_task(self) -> None:
        if not self.current_status:
            return
        sel = self.list_tasks.curselection()
        if not sel:
            return
        idx = sel[0]
        tasks = self.current_status.setdefault("tasks", [])
        old = tasks[idx]
        name = simpledialog.askstring(
            "Edytuj zadanie", "Opis zadania:", initialvalue=old, parent=self
        )
        if name:
            tasks[idx] = name
            self._refresh_tasks()

    def delete_task(self) -> None:
        if not self.current_status:
            return
        sel = self.list_tasks.curselection()
        if not sel:
            return
        idx = sel[0]
        if messagebox.askyesno("Usuń zadanie", "Czy na pewno usunąć wybrane zadanie?"):
            tasks = self.current_status.setdefault("tasks", [])
            del tasks[idx]
            self._refresh_tasks()

    # -------------------------- save --------------------------------------
    def _save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        LZ.invalidate_cache()
        if callable(self.on_save) and self.on_save is not LZ.invalidate_cache:
            self.on_save()
        self.destroy()
