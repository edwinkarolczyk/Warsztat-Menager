"""Zaawansowany edytor konfiguracji zadań narzędzi."""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import logika_zadan as LZ


MAX_TOOL_TYPES = 8
MAX_STATUSES_PER_TYPE = 8


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
        self.combo_coll.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 4))
        self.combo_coll.bind("<<ComboboxSelected>>", self._on_collection_change)

        self.search_var = tk.StringVar()
        search_row = ttk.Frame(top)
        search_row.grid(row=0, column=1, columnspan=2, sticky="ew", padx=2)
        ttk.Label(search_row, text="Szukaj:").pack(side="left")
        search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=26)
        search_entry.pack(side="left", fill="x", expand=True)
        self.search_var.trace_add("write", lambda *_: self._on_search_change())

        ttk.Label(top, text="Typ:").grid(row=1, column=1, sticky="w")
        self.list_types = tk.Listbox(top, height=8)
        self.list_types.grid(row=2, column=1, sticky="nsew", padx=2)
        self.list_types.bind("<<ListboxSelect>>", self._on_type_select)
        self.list_types.bind("<Double-Button-1>", lambda _e: self.edit_selected_type())

        ttk.Label(top, text="Status:").grid(row=1, column=2, sticky="w")
        self.list_status = tk.Listbox(top, height=8)
        self.list_status.grid(row=2, column=2, sticky="nsew", padx=2)
        self.list_status.bind("<<ListboxSelect>>", self._on_status_select)
        self.list_status.bind("<Double-Button-1>", lambda _e: self.edit_selected_status())

        type_btns = ttk.Frame(top)
        type_btns.grid(row=3, column=1, sticky="ew", padx=2, pady=(4, 0))
        ttk.Button(type_btns, text="Dodaj typ", command=self.add_type).pack(side="left")
        ttk.Button(type_btns, text="Usuń", command=self.delete_type).pack(side="left", padx=(4, 0))

        status_btns = ttk.Frame(top)
        status_btns.grid(row=3, column=2, sticky="ew", padx=2, pady=(4, 0))
        ttk.Button(status_btns, text="Dodaj status", command=self.add_status).pack(side="left")
        ttk.Button(status_btns, text="Usuń", command=self.delete_status).pack(side="left", padx=(4, 0))

        for i in range(3):
            top.columnconfigure(i, weight=1)
        top.rowconfigure(2, weight=1)

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
        self._types = list(types or [])
        self._type_name_to_id = {
            self._display_label(t): t.get("id") for t in self._types
        }
        self._apply_type_filter()

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
        self._statuses = list(statuses or [])
        self._status_name_to_id = {
            self._display_label(st): st.get("id") for st in self._statuses
        }
        self._apply_status_filter()

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

    def _on_search_change(self) -> None:
        if self._ui_updating:
            return
        self._apply_type_filter()

    def _apply_type_filter(self) -> None:
        query = (self.search_var.get() or "").strip().lower()
        preferred = self._display_label(self.current_type)
        shown: list[str] = []
        with self._suspend_ui():
            self.list_types.delete(0, tk.END)
            for t in self._types:
                name = self._display_label(t)
                if query and query not in name.lower():
                    continue
                idx = len(shown)
                self.list_types.insert(tk.END, name)
                shown.append(name)
                if preferred and name == preferred:
                    self.list_types.selection_set(idx)
            if shown and not self.list_types.curselection():
                self.list_types.selection_set(0)
            if not shown:
                self.current_type = None
        self._on_type_select()

    def _apply_status_filter(self) -> None:
        query = (self.search_var.get() or "").strip().lower()
        preferred = self._display_label(self.current_status)
        shown: list[str] = []
        with self._suspend_ui():
            self.list_status.delete(0, tk.END)
            for st in self._statuses:
                name = self._display_label(st)
                if query and query not in name.lower():
                    continue
                idx = len(shown)
                self.list_status.insert(tk.END, name)
                shown.append(name)
                if preferred and name == preferred:
                    self.list_status.selection_set(idx)
            if shown and not self.list_status.curselection():
                self.list_status.selection_set(0)
            if not shown:
                self.current_status = None
        self._on_status_select()

    @staticmethod
    def _display_label(item: dict | None) -> str:
        if not item:
            return ""
        return str(item.get("name") or item.get("id") or "")

    @staticmethod
    def _make_unique_id(label: str, existing: set[str]) -> str:
        slug = re.sub(r"[^0-9A-Za-z]+", "_", label.strip())
        slug = slug.strip("_") or "ID"
        candidate = slug.upper()
        counter = 2
        while candidate in existing:
            candidate = f"{slug}_{counter}".upper()
            counter += 1
        return candidate

    def add_type(self) -> None:
        if not self.current_collection:
            messagebox.showinfo("Typy", "Najpierw wybierz kolekcję.")
            return
        types = self.current_collection.setdefault("types", [])
        if len(types) >= MAX_TOOL_TYPES:
            messagebox.showwarning(
                "Limit typów",
                f"Nie można dodać więcej niż {MAX_TOOL_TYPES} typów w kolekcji.",
            )
            return
        name = simpledialog.askstring("Nowy typ", "Nazwa typu:", parent=self)
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        if any((self._display_label(t).lower() == name.lower()) for t in types):
            messagebox.showinfo("Typy", "Taki typ już istnieje.")
            return
        existing_ids = {t.get("id", "") for t in types if t.get("id")}
        type_id = self._make_unique_id(name, existing_ids)
        new_type = {"id": type_id, "name": name, "statuses": []}
        types.append(new_type)
        self.current_type = new_type
        self.current_status = None
        self.search_var.set("")
        self._populate_types()

    def delete_type(self) -> None:
        if not self.current_collection or not self.current_type:
            return
        label = self._display_label(self.current_type)
        if not messagebox.askyesno("Usuń typ", f"Czy na pewno usunąć typ „{label}”?"):
            return
        type_id = self.current_type.get("id")
        types = self.current_collection.setdefault("types", [])
        types[:] = [t for t in types if t.get("id") != type_id]
        self.current_type = None
        self.current_status = None
        self._populate_types()

    def edit_selected_type(self) -> None:
        if not self.current_type:
            return
        current_label = self._display_label(self.current_type)
        name = simpledialog.askstring(
            "Edytuj typ", "Nazwa typu:", initialvalue=current_label, parent=self
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        types = self.current_collection.setdefault("types", []) if self.current_collection else []
        if any(
            (self._display_label(t).lower() == name.lower() and t is not self.current_type)
            for t in types
        ):
            messagebox.showinfo("Typy", "Taki typ już istnieje.")
            return
        self.current_type["name"] = name
        self._populate_types()

    def add_status(self) -> None:
        if not self.current_type:
            messagebox.showinfo("Statusy", "Najpierw wybierz typ narzędzia.")
            return
        statuses = self.current_type.setdefault("statuses", [])
        if len(statuses) >= MAX_STATUSES_PER_TYPE:
            messagebox.showwarning(
                "Limit statusów",
                f"Nie można dodać więcej niż {MAX_STATUSES_PER_TYPE} statusów dla typu.",
            )
            return
        name = simpledialog.askstring("Nowy status", "Nazwa statusu:", parent=self)
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        if any((self._display_label(s).lower() == name.lower()) for s in statuses):
            messagebox.showinfo("Statusy", "Taki status już istnieje.")
            return
        existing_ids = {s.get("id", "") for s in statuses if s.get("id")}
        status_id = self._make_unique_id(name, existing_ids)
        new_status = {"id": status_id, "name": name, "tasks": []}
        statuses.append(new_status)
        self.current_status = new_status
        self.search_var.set("")
        self._populate_statuses()

    def delete_status(self) -> None:
        if not self.current_type or not self.current_status:
            return
        label = self._display_label(self.current_status)
        if not messagebox.askyesno("Usuń status", f"Czy na pewno usunąć status „{label}”?"):
            return
        status_id = self.current_status.get("id")
        statuses = self.current_type.setdefault("statuses", [])
        self.current_type["statuses"] = [
            st for st in statuses if st.get("id") != status_id
        ]
        self.current_status = None
        self._populate_statuses()

    def edit_selected_status(self) -> None:
        if not self.current_status:
            return
        current_label = self._display_label(self.current_status)
        name = simpledialog.askstring(
            "Edytuj status", "Nazwa statusu:", initialvalue=current_label, parent=self
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        statuses = self.current_type.setdefault("statuses", []) if self.current_type else []
        if any(
            (self._display_label(st).lower() == name.lower() and st is not self.current_status)
            for st in statuses
        ):
            messagebox.showinfo("Statusy", "Taki status już istnieje.")
            return
        self.current_status["name"] = name
        self._populate_statuses()

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
