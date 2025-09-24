# gui_tool_editor.py
# Wersja pliku: 1.2.0
# Moduł: Narzędzia – Edytor (one source of truth z Ustawień)
# Logi: [WM-DBG] / [INFO] / [ERROR]
# Język: PL (UI i komentarze)
# Linia max ~100 znaków

import json
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

try:
    from ui_theme import apply_theme_safe as apply_theme
except Exception:
    def apply_theme(_root):
        # Fallback, gdy motyw nie jest dostępny – brak awarii okna
        pass

from logger import get_logger
from config_manager import ConfigManager

log = get_logger(__name__)


class ToolEditorDialog(tk.Toplevel):
    """
    Okno edycji narzędzia. Definicje typ/status/zadania wczytywane z Ustawień.
    Brak możliwości dodawania nowych typów w tym oknie (tylko wybór).
    Auto-odhaczanie następuje przy zmianie na OSTATNI status (wg konfiguracji).
    """

    def __init__(self, master, tool_path: str, current_user: str = "unknown"):
        super().__init__(master)
        self.title("Edycja narzędzia")
        self.resizable(True, True)
        apply_theme(self)  # ciemny motyw WM
        self.current_user = current_user

        self.tool_path = tool_path
        self.tool_data = self._load_tool_file(tool_path)
        self.defs = self._load_tool_definitions_from_settings()
        # poprzedni status do obsługi Anuluj
        self._prev_status = str(self.tool_data.get("status", "")).strip()
        # defs: { "typ": { "status": [zadania...] } }

        ttk.Label(self, text="Typ narzędzia:").grid(
            row=0, column=0, sticky="w", padx=8, pady=(10, 4)
        )
        self.var_typ = tk.StringVar()
        self.cb_typ = ttk.Combobox(self, textvariable=self.var_typ, state="readonly")
        self.cb_typ["values"] = sorted(self.defs.keys())
        self.cb_typ.grid(row=0, column=1, sticky="ew", padx=8, pady=(10, 4))

        ttk.Label(self, text="Status:").grid(
            row=1, column=0, sticky="w", padx=8, pady=4
        )
        self.var_status = tk.StringVar()
        self.cb_status = ttk.Combobox(self, textvariable=self.var_status, state="readonly")
        self.cb_status.grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Zadania (z Ustawień):").grid(
            row=2, column=0, sticky="w", padx=8, pady=(8, 4)
        )
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
            "<<ComboboxSelected>>",
            lambda e: self._on_status_selected()
        )

        log.info(
            "[WM-DBG][TOOLS-EDITOR] Okno edycji uruchomione; "
            "definicje z Ustawień wczytane."
        )

    # ---------- I/O narzędzia ----------

    def _load_tool_file(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log.error(
                f"[ERROR][TOOLS-EDITOR] Błąd wczytywania pliku narzędzia: "
                f"{path} -> {exc}"
            )
            return {}

    def _save_tool_file(self, path: str, data: dict):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            log.error(
                f"[ERROR][TOOLS-EDITOR] Błąd zapisu pliku narzędzia: "
                f"{path} -> {exc}"
            )
            raise

    # ---------- Definicje z Ustawień ----------

    def _load_tool_definitions_from_settings(self) -> dict:
        """
        Czyta ConfigManager().config['tools']['definitions'] i zwraca:
        { typ: { status: [zadania] } }. Gdy brak, zwraca pusty dict.
        """

        cfg = ConfigManager().config or {}
        tools = cfg.get("tools", {})
        definitions = tools.get("definitions", {})
        if not isinstance(definitions, dict):
            definitions = {}
        if not definitions:
            log.warning(
                "[WM-DBG][TOOLS-EDITOR] Brak config['tools']['definitions'] – pusto."
            )
        return definitions

    # ---------- Inicjalizacja UI ----------

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
        self._prev_status = str(self.var_status.get()).strip()

    def _refresh_status_values(self):
        typ = self.var_typ.get()
        statuses = []
        if typ and typ in self.defs:
            statuses = list(self.defs[typ].keys())
        # Jeśli globalnie zdefiniowano kolejność statusów – użyjmy jej
        ordered = self._ordered_statuses_for_type(typ, statuses)
        self.cb_status["values"] = ordered
        if ordered and self.var_status.get() not in ordered:
            self.var_status.set(ordered[0])
        self._refresh_tasks_list()
        self._prev_status = str(self.var_status.get()).strip()

    def _refresh_tasks_list(self):
        self.tasks_list.delete(0, tk.END)
        typ = self.var_typ.get()
        status = self.var_status.get()
        tasks = []
        if typ and status and typ in self.defs and status in self.defs[typ]:
            tasks = self.defs[typ][status] or []
        for task in tasks:
            self.tasks_list.insert(tk.END, f"• {task}")

    def _on_status_selected(self):
        """
        Po zmianie statusu: zapytaj, czy dodać brakujące zadania z definicji
        do puli zadań dla nowego statusu. Obsługa: Dodaj/Pomiń/Anuluj.
        Flaga config: tools.prompt_add_tasks_on_status_change (domyślnie True).
        """

        new_status = str(self.var_status.get()).strip()
        old_status = str(self._prev_status).strip()
        if new_status == old_status:
            self._refresh_tasks_list()
            return

        cfg = ConfigManager().config or {}
        tools = cfg.get("tools", {})
        prompt_on = tools.get("prompt_add_tasks_on_status_change", True)
        if not prompt_on:
            self._prev_status = new_status
            self._refresh_tasks_list()
            return

        typ = self.var_typ.get()
        tasks_def = self.defs.get(typ, {}).get(new_status, []) or []
        bucket = self.tool_data.setdefault("zadania", {}).setdefault(new_status, {})
        candidates = [task for task in tasks_def if task not in bucket]
        if not candidates:
            self._prev_status = new_status
            self._refresh_tasks_list()
            return

        log.info(
            f"[WM-DBG][TOOLS_UI] prompt add tasks status='{new_status}' "
            f"candidates={len(candidates)}"
        )

        ans = messagebox.askyesnocancel(
            "Zadania",
            (
                f"Dodać {len(candidates)} zadań dla statusu „{new_status}” "
                "do puli?\n(Dodaj = Tak, Pomiń = Nie, Anuluj = Anuluj)"
            ),
        )
        if ans is None:
            self.var_status.set(old_status)
            self._refresh_tasks_list()
            log.info(
                f"[INFO][TOOLS_UI] tasks prompt cancelled status='{new_status}'"
            )
            return

        if ans is True:
            for task in candidates:
                bucket[task] = False
            log.info(
                f"[INFO][TOOLS_UI] tasks added status='{new_status}' "
                f"added={len(candidates)}"
            )
        else:
            log.info(
                f"[INFO][TOOLS_UI] tasks skipped status='{new_status}'"
            )

        self._prev_status = new_status
        self._refresh_tasks_list()

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

        # Auto-odhaczanie: tylko jeśli to OSTATNI status i flaga w configu = True
        if self._is_last_status(typ, status):
            self._auto_check_all_tasks_if_exist()

        self.tool_data["typ"] = typ
        self.tool_data["status"] = status
        self._append_history_entry(status, comment)

        try:
            self._save_tool_file(self.tool_path, self.tool_data)
            log.info("[INFO][TOOLS-EDITOR] Zapisano narzędzie z definicji Ustawień.")
            self.destroy()
        except Exception as exc:
            messagebox.showerror(
                "Błąd zapisu", f"Nie udało się zapisać zmian:\n{exc}"
            )

    # ---------- Pomocnicze ----------

    def _get_tasks_for_current(self):
        typ = self.var_typ.get()
        status = self.var_status.get()
        if typ and status and typ in self.defs and status in self.defs[typ]:
            return self.defs[typ][status] or []
        return []

    def _ordered_statuses_for_type(self, typ: str, fallback: list[str]) -> list[str]:
        """
        Zwraca listę statusów w kolejności:
        1) z configu (tools.statuses), jeśli istnieje i niepusta,
        2) w przeciwnym razie kolejność z definicji typu (keys),
        3) w przeciwnym razie przekazany fallback.
        """

        cfg = ConfigManager().config or {}
        tools = cfg.get("tools", {})
        statuses = tools.get("statuses")
        if isinstance(statuses, list) and statuses:
            clean = [str(s).strip() for s in statuses if str(s).strip()]
            # przefiltruj do statusów istniejących dla danego typu (jeśli podano)
            if typ in self.defs:
                allowed = set(self.defs[typ].keys())
                clean = [s for s in clean if s in allowed]
            if clean:
                return clean
        if typ in self.defs:
            return list(self.defs[typ].keys())
        return list(fallback or [])

    def _is_last_status(self, typ: str, status: str) -> bool:
        """
        Zwraca True, gdy:
        - flaga tools.auto_check_on_last_status w configu jest True (domyślnie),
        - podany status jest ostatni w kolejności (patrz _ordered_statuses_for_type).
        """

        cfg = ConfigManager().config or {}
        tools = cfg.get("tools", {})
        if tools.get("auto_check_on_last_status", True) is not True:
            return False
        ordered = self._ordered_statuses_for_type(typ, [])
        return bool(ordered) and status == ordered[-1]

    def _auto_check_all_tasks_if_exist(self):
        tasks = self._get_tasks_for_current()
        if not tasks:
            return

        z = self.tool_data.setdefault("zadania", {})
        st = self.var_status.get()
        bucket = z.setdefault(st, {})
        for t in tasks:
            bucket[t] = True
        log.info(
            "[WM-DBG][TOOLS-EDITOR] Auto-odhaczono zadania dla ostatniego statusu."
        )

    def _append_history_entry(self, new_status: str, comment: str):
        hist = self.tool_data.setdefault("historia", [])
        hist.append(
            {
                "data": datetime.now().isoformat(timespec="seconds"),
                "uzytkownik": self.current_user,
                "operacja": f"zmiana statusu -> {new_status}",
                "komentarz": comment,
            }
        )


# ⏹ KONIEC KODU
