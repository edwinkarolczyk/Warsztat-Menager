# gui_tool_editor.py
# Wersja pliku: 1.0.0
# Zmiany:
# - [NOWE] Edytor narzędzia oparty o definicje z Ustawień (one source of truth)
# - [NOWE] Usunięta możliwość dodawania typu z poziomu edytora
# - [NOWE] Comboboxy (Typ, Status) + lista zadań tylko-do-odczytu z konfiguracji
# - [NOWE] Walidacje statusów: "w serwisie" (wymagane zadania + komentarz), "sprawne" (auto-odhacz zadania)
# - [NOWE] Lokalizacja PL + ciemny motyw (ui_theme.apply_theme)
#
# ⏹ KONIEC KODU – stopka dodana na końcu pliku

import json
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

try:
    from ui_theme import apply_theme
except Exception:
    def apply_theme(_):
        """Fallback gdy brak motywu – nie wybuchamy."""

        pass

from logger import get_logger
from config_manager import ConfigManager

log = get_logger(__name__)


class ToolEditorDialog(tk.Toplevel):
    """Okno edycji narzędzia spięte z definicjami z Ustawień (Typ/Status/Zadania)."""

    def __init__(self, master, tool_path: str, current_user: str = "unknown"):
        super().__init__(master)
        self.title("Edycja narzędzia")
        self.resizable(True, True)
        apply_theme(self)
        self.current_user = current_user

        self.tool_path = tool_path
        self.tool_data = self._load_tool_file(tool_path)
        self.defs = self._load_tool_definitions_from_settings()

        ttk.Label(self, text="Typ narzędzia:").grid(
            row=0, column=0, sticky="w", padx=8, pady=(10, 4)
        )
        self.var_typ = tk.StringVar()
        self.cb_typ = ttk.Combobox(self, textvariable=self.var_typ, state="readonly")
        self.cb_typ["values"] = sorted(self.defs.keys())
        self.cb_typ.grid(row=0, column=1, sticky="ew", padx=8, pady=(10, 4))

        ttk.Label(self, text="Status:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.var_status = tk.StringVar()
        self.cb_status = ttk.Combobox(
            self, textvariable=self.var_status, state="readonly"
        )
        self.cb_status.grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(
            self,
            text="Zadania (zdefiniowane w Ustawieniach):",
        ).grid(row=2, column=0, sticky="w", padx=8, pady=(8, 4))
        self.tasks_list = tk.Listbox(self, height=6)
        self.tasks_list.grid(row=2, column=1, sticky="nsew", padx=8, pady=(8, 4))

        ttk.Label(self, text="Komentarz:").grid(
            row=3, column=0, sticky="nw", padx=8, pady=4
        )
        self.txt_comment = tk.Text(self, height=4)
        self.txt_comment.grid(row=3, column=1, sticky="nsew", padx=8, pady=4)

        btns = ttk.Frame(self)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=8, pady=10)
        ttk.Button(btns, text="Zapisz", command=self._on_save).pack(
            side="right", padx=4
        )
        ttk.Button(btns, text="Anuluj", command=self.destroy).pack(
            side="right", padx=4
        )

        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)
        self.rowconfigure(3, weight=1)

        self._init_from_tool()
        self.cb_typ.bind("<<ComboboxSelected>>", lambda e: self._refresh_status_values())
        self.cb_status.bind(
            "<<ComboboxSelected>>", lambda e: self._refresh_tasks_list()
        )

        log.info(
            "[WM-DBG][TOOLS-EDITOR] Okno edycji uruchomione; definicje z Ustawień wczytane."
        )

    def _load_tool_file(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data
        except Exception as exc:
            log.error(
                "[WM-DBG][TOOLS-EDITOR] Nie udało się wczytać pliku narzędzia: %s -> %s",
                path,
                exc,
            )
            return {}

    def _save_tool_file(self, path: str, data: dict):
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
        except Exception as exc:
            log.error(
                "[WM-DBG][TOOLS-EDITOR] Błąd zapisu pliku narzędzia: %s -> %s",
                path,
                exc,
            )
            raise

    def _load_tool_definitions_from_settings(self) -> dict:
        cfg = ConfigManager().config or {}
        tools = cfg.get("tools", {})
        definitions = tools.get("definitions", {})

        if not definitions:
            log.warning(
                "[WM-DBG][TOOLS-EDITOR] Brak config['tools']['definitions']; używam pustych."
            )
        return definitions

    def _init_from_tool(self):
        typ = self.tool_data.get("typ", "")
        status = self.tool_data.get("status", "")

        all_types = list(self.defs.keys())
        if typ in all_types:
            self.var_typ.set(typ)
        elif all_types:
            self.var_typ.set(all_types[0])

        self._refresh_status_values()
        if status and status in self.cb_status["values"]:
            self.var_status.set(status)

        self._refresh_tasks_list()

    def _refresh_status_values(self):
        typ = self.var_typ.get()
        statuses = []
        if typ and typ in self.defs:
            statuses = sorted(self.defs[typ].keys())
        self.cb_status["values"] = statuses
        if statuses and self.var_status.get() not in statuses:
            self.var_status.set(statuses[0])
        self._refresh_tasks_list()

    def _refresh_tasks_list(self):
        self.tasks_list.delete(0, tk.END)
        typ = self.var_typ.get()
        status = self.var_status.get()
        tasks = []
        if typ and status and typ in self.defs and status in self.defs[typ]:
            tasks = self.defs[typ][status] or []
        for task in tasks:
            self.tasks_list.insert(tk.END, f"• {task}")

    def _on_save(self):
        typ = self.var_typ.get().strip()
        status = self.var_status.get().strip()
        comment = self.txt_comment.get("1.0", "end").strip()

        if not typ:
            messagebox.showerror(
                "Błąd", "Wybierz typ narzędzia (zdefiniowany w Ustawieniach)."
            )
            return
        if not status:
            messagebox.showerror(
                "Błąd", "Wybierz status (zdefiniowany w Ustawieniach)."
            )
            return

        if status.lower() == "w serwisie":
            tasks = self._get_tasks_for_current()
            if not tasks:
                messagebox.showerror(
                    "Błąd",
                    "Dla statusu „w serwisie” muszą być zdefiniowane zadania w Ustawieniach.",
                )
                return
            if not comment:
                messagebox.showerror(
                    "Błąd",
                    "Dla statusu „w serwisie” wymagany jest komentarz użytkownika.",
                )
                return

        if status.lower() == "sprawne":
            self._auto_check_all_tasks_if_exist()

        self.tool_data["typ"] = typ
        self.tool_data["status"] = status
        self._append_history_entry(status, comment)

        try:
            self._save_tool_file(self.tool_path, self.tool_data)
            log.info(
                "[WM-DBG][TOOLS-EDITOR] Zapisano narzędzie z definicji Ustawień."
            )
            self.destroy()
        except Exception as exc:
            messagebox.showerror(
                "Błąd zapisu", f"Nie udało się zapisać zmian:\n{exc}"
            )

    def _get_tasks_for_current(self):
        typ = self.var_typ.get()
        status = self.var_status.get()
        if typ and status and typ in self.defs and status in self.defs[typ]:
            return self.defs[typ][status] or []
        return []

    def _auto_check_all_tasks_if_exist(self):
        tasks = self._get_tasks_for_current()
        if not tasks:
            return

        tool_tasks = self.tool_data.setdefault("zadania", {})
        status_bucket = tool_tasks.setdefault(self.var_status.get(), {})
        for task in tasks:
            status_bucket[task] = True
        log.info(
            "[WM-DBG][TOOLS-EDITOR] Auto-odhaczono zadania dla statusu 'sprawne' (jeśli istniały)."
        )

    def _append_history_entry(self, new_status: str, comment: str):
        history = self.tool_data.setdefault("historia", [])
        history.append(
            {
                "data": datetime.now().isoformat(timespec="seconds"),
                "uzytkownik": self.current_user,
                "operacja": f"zmiana statusu -> {new_status}",
                "komentarz": comment,
            }
        )


# ⏹ KONIEC KODU
