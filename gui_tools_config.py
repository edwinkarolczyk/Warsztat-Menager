"""GUI for editing tool tasks configuration."""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config_manager import ConfigManager

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Return an ASCII slug generated from ``name``."""

    base = (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()
    return base or "id"


class ToolsConfigWindow(tk.Toplevel):
    """Topmost window allowing configuration of tool tasks."""

    def __init__(self, master: tk.Widget | None = None, on_save=None) -> None:
        super().__init__(master)
        self.title("Konfiguracja zadań narzędzi")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.on_save = on_save

        self.cfg = ConfigManager()
        LZ = __import__("logika_zadan")
        LZ._load_tool_tasks(force=True)
        with open(LZ.TOOL_TASKS_PATH, "r", encoding="utf-8") as fh:
            self.data = json.load(fh).get("collections", {})

        coll_frame = ttk.Frame(self)
        coll_frame.pack(fill=tk.X, padx=4, pady=4)
        ttk.Label(coll_frame, text="Kolekcja:").pack(side=tk.LEFT)
        self.collection_var = tk.StringVar()
        collections = self.cfg.get("tools.collections_enabled", []) or []
        self.collection_box = ttk.Combobox(
            coll_frame,
            textvariable=self.collection_var,
            values=collections,
            state="readonly",
            width=5,
        )
        self.collection_box.pack(side=tk.LEFT, padx=4)
        if collections:
            self.collection_var.set(
                self.cfg.get("tools.default_collection", collections[0])
            )
        self.collection_box.bind("<<ComboboxSelected>>", lambda e: self._refresh_types())

        lists_frame = ttk.Frame(self)
        lists_frame.pack(padx=4, pady=4)

        self.types_lb = tk.Listbox(lists_frame, width=20, height=10)
        self.statuses_lb = tk.Listbox(lists_frame, width=20, height=10)
        self.tasks_lb = tk.Listbox(lists_frame, width=30, height=10)

        self.types_lb.grid(row=0, column=0)
        self.statuses_lb.grid(row=0, column=1)
        self.tasks_lb.grid(row=0, column=2)

        btn_frames = [ttk.Frame(lists_frame) for _ in range(3)]
        for idx, frame in enumerate(btn_frames):
            frame.grid(row=1, column=idx, pady=(4, 0))

        # Column 1 buttons
        ttk.Button(btn_frames[0], text="Dodaj", command=self._add_type).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frames[0], text="Usuń", command=self._remove_type).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frames[0], text="Zmień", command=self._rename_type).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frames[0], text="↑", command=lambda: self._move_type(-1)).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frames[0], text="↓", command=lambda: self._move_type(1)).pack(
            side=tk.LEFT
        )

        # Column 2 buttons
        ttk.Button(btn_frames[1], text="Dodaj", command=self._add_status).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frames[1], text="Usuń", command=self._remove_status).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frames[1], text="Zmień", command=self._rename_status).pack(
            side=tk.LEFT
        )
        ttk.Button(
            btn_frames[1], text="↑", command=lambda: self._move_status(-1)
        ).pack(side=tk.LEFT)
        ttk.Button(
            btn_frames[1], text="↓", command=lambda: self._move_status(1)
        ).pack(side=tk.LEFT)

        # Column 3 buttons
        ttk.Button(btn_frames[2], text="Dodaj", command=self._add_task).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frames[2], text="Usuń", command=self._remove_task).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frames[2], text="Edytuj", command=self._edit_task).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frames[2], text="↑", command=lambda: self._move_task(-1)).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frames[2], text="↓", command=lambda: self._move_task(1)).pack(
            side=tk.LEFT
        )

        self.auto_var = tk.BooleanVar()
        ttk.Checkbutton(
            self,
            text="auto_check_on_entry",
            variable=self.auto_var,
            command=self._update_auto_flag,
        ).pack(anchor=tk.W, padx=4, pady=(2, 4))

        ctrl = ttk.Frame(self)
        ctrl.pack(pady=4)
        ttk.Button(ctrl, text="Zapisz", command=self._save).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctrl, text="Anuluj", command=self.destroy).pack(side=tk.LEFT)

        self.types_lb.bind("<<ListboxSelect>>", lambda e: self._refresh_statuses())
        self.statuses_lb.bind("<<ListboxSelect>>", lambda e: self._refresh_tasks())
        self._refresh_types()

    # Helpers ---------------------------------------------------------------
    def _current_collection(self) -> str:
        return self.collection_var.get()

    def _types_list(self) -> list:
        return self.data.setdefault(self._current_collection(), {}).setdefault(
            "types", []
        )

    def _current_type(self):
        sel = self.types_lb.curselection()
        if not sel:
            return None, -1
        idx = sel[0]
        return self._types_list()[idx], idx

    def _statuses_list(self):
        typ, _ = self._current_type()
        if not typ:
            return []
        return typ.setdefault("statuses", [])

    def _current_status(self):
        sel = self.statuses_lb.curselection()
        if not sel:
            return None, -1
        idx = sel[0]
        sts = self._statuses_list()
        return (sts[idx], idx) if sts else (None, -1)

    # Refresh listboxes ----------------------------------------------------
    def _refresh_types(self) -> None:
        self.types_lb.delete(0, tk.END)
        for t in self._types_list():
            self.types_lb.insert(tk.END, t.get("name", t.get("id")))
        self.statuses_lb.delete(0, tk.END)
        self.tasks_lb.delete(0, tk.END)
        self.auto_var.set(False)

    def _refresh_statuses(self) -> None:
        self.statuses_lb.delete(0, tk.END)
        typ, _ = self._current_type()
        if not typ:
            self.tasks_lb.delete(0, tk.END)
            self.auto_var.set(False)
            return
        for s in self._statuses_list():
            self.statuses_lb.insert(tk.END, s.get("name", s.get("id")))
        self.tasks_lb.delete(0, tk.END)
        self.auto_var.set(False)

    def _refresh_tasks(self) -> None:
        self.tasks_lb.delete(0, tk.END)
        st, _ = self._current_status()
        if not st:
            self.auto_var.set(False)
            return
        for task in st.get("tasks", []):
            self.tasks_lb.insert(tk.END, task)
        self.auto_var.set(bool(st.get("auto_check_on_entry")))

    # Types operations -----------------------------------------------------
    def _add_type(self) -> None:
        types = self._types_list()
        if len(types) >= 8:
            messagebox.showerror(
                "Błąd", "Maksymalnie 8 typów", parent=self
            )
            return
        name = simpledialog.askstring("Nowy typ", "Nazwa", parent=self)
        if not name:
            return
        slug = _slugify(name)
        if any(t.get("id") == slug for t in types):
            messagebox.showerror(
                "Błąd", "Id typu już istnieje", parent=self
            )
            return
        types.append({"id": slug, "name": name, "statuses": []})
        self._refresh_types()

    def _remove_type(self) -> None:
        _, idx = self._current_type()
        if idx >= 0:
            del self._types_list()[idx]
            self._refresh_types()

    def _rename_type(self) -> None:
        typ, idx = self._current_type()
        if idx < 0:
            return
        name = simpledialog.askstring(
            "Zmień typ", "Nowa nazwa", initialvalue=typ.get("name"), parent=self
        )
        if not name:
            return
        slug = _slugify(name)
        types = self._types_list()
        if any(t.get("id") == slug and t is not typ for t in types):
            messagebox.showerror(
                "Błąd", "Id typu już istnieje", parent=self
            )
            return
        typ.update({"id": slug, "name": name})
        self._refresh_types()
        self.types_lb.selection_set(idx)

    def _move_type(self, delta: int) -> None:
        typ, idx = self._current_type()
        if idx < 0:
            return
        types = self._types_list()
        new = idx + delta
        if 0 <= new < len(types):
            types[idx], types[new] = types[new], types[idx]
            self._refresh_types()
            self.types_lb.selection_set(new)

    # Status operations ----------------------------------------------------
    def _add_status(self) -> None:
        typ, _ = self._current_type()
        if not typ:
            return
        statuses = self._statuses_list()
        if len(statuses) >= 8:
            messagebox.showerror(
                "Błąd", "Maksymalnie 8 statusów", parent=self
            )
            return
        name = simpledialog.askstring("Nowy status", "Nazwa", parent=self)
        if not name:
            return
        slug = _slugify(name)
        if any(s.get("id") == slug for s in statuses):
            messagebox.showerror(
                "Błąd", "Id statusu już istnieje", parent=self
            )
            return
        statuses.append({"id": slug, "name": name, "tasks": []})
        self._refresh_statuses()

    def _remove_status(self) -> None:
        st, idx = self._current_status()
        if idx >= 0:
            del self._statuses_list()[idx]
            self._refresh_statuses()

    def _rename_status(self) -> None:
        st, idx = self._current_status()
        if idx < 0:
            return
        name = simpledialog.askstring(
            "Zmień status", "Nowa nazwa", initialvalue=st.get("name"), parent=self
        )
        if not name:
            return
        slug = _slugify(name)
        statuses = self._statuses_list()
        if any(s.get("id") == slug and s is not st for s in statuses):
            messagebox.showerror(
                "Błąd", "Id statusu już istnieje", parent=self
            )
            return
        st.update({"id": slug, "name": name})
        self._refresh_statuses()
        self.statuses_lb.selection_set(idx)

    def _move_status(self, delta: int) -> None:
        st, idx = self._current_status()
        if idx < 0:
            return
        statuses = self._statuses_list()
        new = idx + delta
        if 0 <= new < len(statuses):
            statuses[idx], statuses[new] = statuses[new], statuses[idx]
            self._refresh_statuses()
            self.statuses_lb.selection_set(new)

    # Tasks operations -----------------------------------------------------
    def _tasks_list(self):
        st, _ = self._current_status()
        if not st:
            return []
        return st.setdefault("tasks", [])

    def _current_task(self):
        sel = self.tasks_lb.curselection()
        if not sel:
            return None, -1
        idx = sel[0]
        tasks = self._tasks_list()
        return (tasks[idx], idx) if tasks else (None, -1)

    def _add_task(self) -> None:
        st, _ = self._current_status()
        if not st:
            return
        text = simpledialog.askstring("Nowe zadanie", "Treść", parent=self)
        if not text:
            return
        self._tasks_list().append(text)
        self._refresh_tasks()

    def _remove_task(self) -> None:
        _, idx = self._current_task()
        if idx >= 0:
            del self._tasks_list()[idx]
            self._refresh_tasks()

    def _edit_task(self) -> None:
        task, idx = self._current_task()
        if idx < 0:
            return
        text = simpledialog.askstring(
            "Edytuj zadanie", "Treść", initialvalue=task, parent=self
        )
        if not text:
            return
        self._tasks_list()[idx] = text
        self._refresh_tasks()
        self.tasks_lb.selection_set(idx)

    def _move_task(self, delta: int) -> None:
        task, idx = self._current_task()
        if idx < 0:
            return
        tasks = self._tasks_list()
        new = idx + delta
        if 0 <= new < len(tasks):
            tasks[idx], tasks[new] = tasks[new], tasks[idx]
            self._refresh_tasks()
            self.tasks_lb.selection_set(new)

    def _update_auto_flag(self) -> None:
        st, _ = self._current_status()
        if st is not None:
            st["auto_check_on_entry"] = bool(self.auto_var.get())

    # Saving ---------------------------------------------------------------
    def _save(self) -> None:
        path = os.path.join("data", "zadania_narzedzia.json")
        collections = self.cfg.get("tools.collections_enabled", []) or []
        for cid in collections:
            self.data.setdefault(cid, {"types": []})
        payload = {"collections": self.data}
        tmp = path + ".tmp"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            logger.info("[WM-DBG][TOOLS-CFG] saved %s", path)
        except OSError as exc:
            messagebox.showerror("Błąd", str(exc), parent=self)
            try:
                os.remove(tmp)
            except OSError:
                pass
            return
        if self.on_save:
            try:
                self.on_save()
            except Exception:  # pragma: no cover
                logger.warning("on_save callback failed", exc_info=True)
        self.destroy()


def open_tools_config(master: tk.Widget | None = None, on_save=None) -> ToolsConfigWindow:
    """Convenience function to open :class:`ToolsConfigWindow`."""

    return ToolsConfigWindow(master=master, on_save=on_save)

