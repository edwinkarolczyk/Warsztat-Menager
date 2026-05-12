# gui_tool_editor.py
# version: 1.0
# Moduł: Narzędzia – Edytor (one source of truth z Ustawień)
# Logi: [WM-DBG] / [INFO] / [ERROR]
# Język: PL (UI i komentarze)
# Linia max ~100 znaków
import json
import os
from pathlib import Path
import tkinter as tk
from datetime import datetime
from typing import ClassVar, Optional, Callable
from tkinter import ttk, messagebox
try:
    from ui_theme import apply_theme_safe as apply_theme
except Exception:
    def apply_theme(_root):
        # Fallback, gdy motyw nie jest dostępny – brak awarii okna
        pass
from logger import get_logger
from config_manager import ConfigManager
from logika_zadan import (
    get_collections,
    get_default_collection,
    get_statuses,
    get_tasks,
    get_tool_types,
)
log = get_logger(__name__)

try:
    from tool_card_pdf import generate_tool_card
except Exception:
    generate_tool_card = None  # type: ignore


def _wm_norm_str(x):
    return (x or "").strip()
def _wm_dedupe_merge_list(dst_list, src_list, key_fn):
    """Minimalny merge list bez duplikatów wg key_fn; zachowuje kolejność: dst potem nowe."""
    if not src_list:
        return
    seen = set()
    for it in dst_list:
        try:
            seen.add(key_fn(it))
        except Exception:
            pass
    for it in src_list:
        try:
            k = key_fn(it)
        except Exception:
            k = None
        if k is None or k not in seen:
            dst_list.append(it)
            if k is not None:
                seen.add(k)
def _wm_merge_type_def(dst_def, src_def):
    """
    Minimalne scalanie:
    - statusy: deduplikacja po id, fallback po nazwa
    - zadania: deduplikacja po title, fallback po nazwa
    - inne dict: tylko brakujące klucze (nie nadpisuj istniejących bez powodu)
    """
    if not src_def:
        return
    # listy (najczęstsze)
    if "statusy" in src_def:
        dst_def.setdefault("statusy", [])
        def _k_status(s):
            if isinstance(s, dict):
                sid = _wm_norm_str(s.get("id"))
                if sid:
                    return "id:" + sid
                return "name:" + _wm_norm_str(s.get("nazwa"))
            return str(s)
        _wm_dedupe_merge_list(
            dst_def["statusy"], src_def.get("statusy") or [], _k_status
        )
    if "zadania" in src_def:
        dst_def.setdefault("zadania", [])
        def _k_task(t):
            if isinstance(t, dict):
                ttl = _wm_norm_str(t.get("title"))
                if ttl:
                    return "title:" + ttl
                return "name:" + _wm_norm_str(t.get("nazwa"))
            return str(t)
        _wm_dedupe_merge_list(dst_def["zadania"], src_def.get("zadania") or [], _k_task)
    # pozostałe klucze: dopisz tylko jeśli nie ma
    for k, v in src_def.items():
        if k in ("statusy", "zadania"):
            continue
        if k not in dst_def:
            dst_def[k] = v
        else:
            # jeśli oba są dict — dopisz tylko brakujące klucze (bez nadpisywania)
            if isinstance(dst_def.get(k), dict) and isinstance(v, dict):
                for kk, vv in v.items():
                    if kk not in dst_def[k]:
                        dst_def[k][kk] = vv
            elif isinstance(dst_def.get(k), list) and isinstance(v, list):
                _wm_dedupe_merge_list(dst_def[k], v, lambda item: _wm_norm_str(item))


def _tool_card_output_dir() -> Path:
    try:
        cfg = ConfigManager()
        return Path(cfg.path_data("narzedzia", "wydruki"))
    except Exception:
        try:
            from core import root_paths as wm_root_paths
            return wm_root_paths.get_data_root() / "narzedzia" / "wydruki"
        except Exception:
            return Path("data") / "narzedzia" / "wydruki"

class ToolEditorDialog(tk.Toplevel):
    """
    Okno edycji narzędzia. Definicje typ/status/zadania wczytywane z Ustawień.
    Brak możliwości dodawania nowych typów w tym oknie (tylko wybór).
    Auto-odhaczanie następuje przy zmianie na OSTATNI status (wg konfiguracji).
    """
    _active_dialog: ClassVar[Optional["ToolEditorDialog"]] = None
    def __init__(
        self,
        master,
        tool_path: str,
        current_user: str = "unknown",
        current_role: Optional[str] = None,
        role: Optional[str] = None,
        on_saved: Optional[Callable[[str, dict], None]] = None,
    ):
        super().__init__(master)
        self._is_primary_instance = False
        if not self._ensure_single_instance(master):
            return
        self.title("Edycja narzędzia")
        self._base_title = "Edycja narzędzia"
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.lift()
        try:
            self.grab_set()
        except Exception:
            log.debug("[WM-DBG][TOOLS-EDITOR] Nie udało się ustawić grab na oknie edycji.")
        try:
            self.focus_force()
        except Exception:
            log.debug("[WM-DBG][TOOLS-EDITOR] Nie udało się ustawić fokusu na oknie edycji.")
        self.bind("<FocusIn>", lambda _event: self._keep_on_top())
        apply_theme(self) # ciemny motyw WM
        self.current_user = current_user
        self.role = role if role is not None else current_role
        if self.role is None:
            self.role = self._infer_role_from_master(master)
        role_norm = (self.role or "").strip().lower()
        log.info(
            "[WM-DBG][tool_editor] role=%r norm=%r",
            self.role,
            role_norm,
        )
        self.tool_path = tool_path
        self.tool_data = self._load_tool_file(tool_path)
        self.defs = self._load_tool_definitions_from_settings()
        self.on_saved = on_saved
        # DIRTY state (niezapisane zmiany)
        self._dirty = False
        self._init_save_button_styles()
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
        tasks_frame = ttk.Frame(self)
        tasks_frame.grid(row=2, column=1, sticky="nsew", padx=8, pady=(8, 4))
        self.tasks_list = tk.Listbox(tasks_frame, height=6, exportselection=False)
        self.tasks_list.pack(side="left", fill="both", expand=True)
        task_arrows = ttk.Frame(tasks_frame)
        task_arrows.pack(side="left", fill="y", padx=(6, 0))
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
        ttk.Label(self, text="Komentarz:").grid(
            row=3, column=0, sticky="nw", padx=8, pady=4
        )
        self.txt_comment = tk.Text(self, height=4)
        self.txt_comment.grid(row=3, column=1, sticky="nsew", padx=8, pady=4)
        self.txt_comment.bind("<KeyRelease>", lambda e: self._mark_dirty())
        btns = ttk.Frame(self)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=8, pady=10)
        # Ramka-obrys dla przycisku "Zapisz" (pewny outline niezależnie od motywu ttk)
        self.save_wrap = tk.Frame(
            btns,
            highlightthickness=2,
            highlightbackground="#44cc44", # zielony = clean
            highlightcolor="#44cc44",
            bd=0,
        )
        self.save_wrap.pack(side="right", padx=4)
        self.btn_save = ttk.Button(
            self.save_wrap,
            text="Zapisz",
            command=self._on_save,
            style="WM.SaveClean.TButton",
        )
        self.btn_save.pack()
        # Kropka stanu zapisu (zielona = zapisane, czerwona = niezapisane) – tk.Label (pewne w każdym motywie)
        self.lbl_save_state = tk.Label(
            btns,
            text="●",
            fg="#44cc44", # start = clean
            bg=btns.cget("background"),
            font=("Segoe UI", 12, "bold"),
        )
        self.lbl_save_state.pack(side="right", padx=(0, 6))
        ttk.Button(btns, text="Zamknij okno", command=self._on_close).pack(
            side="right", padx=4
        )
        ttk.Button(
            btns,
            text="Drukuj kartę",
            command=self._on_print_card,
        ).pack(
            side="right", padx=4
        )
        if role_norm == "brygadzista":
            ttk.Button(
                btns,
                text="Usuń narzędzie",
                command=self._on_delete,
                style="WM.Danger.TButton",
            ).pack(side="left", padx=4)
        # --- SKRÓTY KLAWISZOWE (ToolEditor) ---
        self.bind("<Control-s>", lambda e: (self._on_save(), "break")[1])
        self.bind("<Escape>", lambda e: (self._on_close(), "break")[1])
        self.bind("<Control-w>", lambda e: (self._on_close(), "break")[1])
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)
        self.rowconfigure(3, weight=1)
        self._init_from_tool()
        self._mark_clean()
        self.cb_typ.bind(
            "<<ComboboxSelected>>",
            lambda e: (self._refresh_status_values(), self._mark_dirty())
        )
        self.cb_status.bind(
            "<<ComboboxSelected>>",
            lambda e: (self._on_status_selected(), self._mark_dirty())
        )
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # === NOWOŚĆ: Pytanie „Informacje czy Wizyty?” przy otwarciu edytora ===
        choice = messagebox.askyesnocancel(
            title="Tryb edycji narzędzia",
            message="Co chcesz edytować?\n\n"
                    "• TAK → Informacje ogólne narzędzia\n"
                    "• NIE → Wizyty serwisowe / historia napraw\n"
                    "• Anuluj → Zamknij okno",
            icon="question",
            default=messagebox.YES,
            parent=self
        )

        if choice is None:  # Anuluj
            self.destroy()
            return

        if choice is False:  # NIE → Wizyty serwisowe
            # Okno „W budowie”
            wip = tk.Toplevel(self)
            wip.title("Wizyty serwisowe")
            wip.geometry("460x280")
            wip.transient(self)
            wip.grab_set()
            wip.resizable(False, False)
            wip.configure(bg="#212121")

            frame = ttk.Frame(wip, padding=20)
            frame.pack(fill="both", expand=True)

            ttk.Label(
                frame,
                text="W BUDOWIE",
                font=("Helvetica", 32, "bold"),
                foreground="#ff6600",
                anchor="center"
            ).pack(pady=(10, 20))

            ttk.Label(
                frame,
                text="Moduł zarządzania wizytami serwisowymi\n"
                     "i historią napraw narzędzi\n"
                     "jest obecnie w trakcie разработки",
                font=("Helvetica", 13),
                foreground="#cccccc",
                justify="center",
                anchor="center"
            ).pack(pady=(0, 30))

            ttk.Button(
                frame,
                text="Zamknij",
                command=wip.destroy
            ).pack(pady=10)

            # Blokujemy dalsze działanie edytora
            return

        # === Kontynuacja normalnego edytora (gdy wybrano TAK) ===
        log.info(
            "[WM-DBG][TOOLS-EDITOR] Okno edycji uruchomione; "
            "definicje z Ustawień wczytane."
        )
    # ---------- I/O narzędzia ----------
    def destroy(self): # type: ignore[override]
        self._release_single_instance()
        super().destroy()
    def _infer_role_from_master(self, master) -> Optional[str]:
        role = None
        for owner in (self, master, getattr(master, "app", None)):
            if not owner:
                continue
            for attr in ("current_user", "current_profile"):
                data = getattr(owner, attr, None)
                if isinstance(data, dict):
                    role = data.get("rola") or data.get("role") or role
            if role:
                break
        return role
    def _ensure_single_instance(self, master) -> bool:
        existing = ToolEditorDialog._active_dialog
        if existing and existing.winfo_exists():
            try:
                existing.attributes("-topmost", True)
                existing.lift()
                existing.focus_force()
            except Exception:
                log.debug("[WM-DBG][TOOLS-EDITOR] Nie udało się podnieść aktywnego okna.")
            messagebox.showwarning(
                "Edycja narzędzia",
                "Okno edycji narzędzia jest już otwarte. Zamknij je, aby kontynuować.",
                parent=existing,
            )
            self.after_idle(lambda: super(ToolEditorDialog, self).destroy())
            return False
        ToolEditorDialog._active_dialog = self
        self._is_primary_instance = True
        try:
            self.transient(master)
        except Exception:
            log.debug("[WM-DBG][TOOLS-EDITOR] Nie udało się ustawić transient dla okna.")
        return True
    def _release_single_instance(self):
        if getattr(self, "_is_primary_instance", False) and ToolEditorDialog._active_dialog is self:
            ToolEditorDialog._active_dialog = None
            try:
                self.grab_release()
            except Exception:
                pass
            self._is_primary_instance = False
    def _keep_on_top(self):
        try:
            self.attributes("-topmost", True)
            self.lift()
        except Exception:
            log.debug("[WM-DBG][TOOLS-EDITOR] Nie udało się utrzymać okna nad innymi.")
    def _reload_from_disk(self):
        # twarde odświeżenie panelu po zapisie
        self.tool_data = self._load_tool_file(self.tool_path)
        self._init_from_tool()
        self.title(self._base_title)
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
            log.exception(
                f"[ERROR][TOOLS-EDITOR] Błąd zapisu pliku narzędzia: "
                f"{path} -> {exc}"
            )
            raise

    def _on_print_card(self):
        if generate_tool_card is None:
            messagebox.showerror(
                "Karta narzędzia",
                "Brak modułu generowania karty narzędzia.",
                parent=self,
            )
            return
        try:
            output_dir = _tool_card_output_dir()
            generated_path = generate_tool_card(
                dict(self.tool_data or {}),
                output_dir,
                open_after=True,
            )
            messagebox.showinfo(
                "Karta narzędzia",
                f"Wygenerowano kartę narzędzia:\n\n{generated_path}",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(
                "Karta narzędzia",
                f"Nie udało się wygenerować karty narzędzia:\n\n{exc}",
                parent=self,
            )

    # ---------- Definicje z Ustawień ----------
    def _load_tool_definitions_from_settings(
        self,
    ) -> dict[str, dict[str, list[str]]]:
        """Czyta ``data/zadania_narzedzia.json`` i buduje mapę definicji."""
        definitions: dict[str, dict[str, list[str]]] = {}
        try:
            collections = get_collections()
        except Exception as exc: # pragma: no cover - loguj i kontynuuj
            log.warning(
                "[WM-DBG][TOOLS-EDITOR] Nie można pobrać listy kolekcji: %s", exc
            )
            collections = []
        if not collections:
            default_collection = get_default_collection()
            if default_collection:
                collections = [{"id": default_collection, "name": default_collection}]
        any_loaded = False
        for collection in collections:
            coll_id = str(collection.get("id") or collection.get("name") or "").strip()
            if not coll_id:
                continue
            try:
                types = get_tool_types(collection=coll_id)
            except Exception as exc: # pragma: no cover - loguj i kontynuuj
                log.warning(
                    "[WM-DBG][TOOLS-EDITOR] Błąd pobierania typów (%s): %s",
                    coll_id,
                    exc,
                )
                continue
            for entry in types:
                type_name = str(entry.get("name") or entry.get("id") or "").strip()
                type_id = str(entry.get("id") or entry.get("name") or "").strip()
                if not type_name or not type_id:
                    continue
                any_loaded = True
                dst = definitions.setdefault(type_name, {})
                try:
                    statuses = get_statuses(type_id, collection=coll_id)
                except Exception as exc: # pragma: no cover - loguj i kontynuuj
                    log.warning(
                        "[WM-DBG][TOOLS-EDITOR] Błąd pobierania statusów (%s/%s): %s",
                        coll_id,
                        type_id,
                        exc,
                    )
                    statuses = []
                for status in statuses:
                    status_name = (
                        str(status.get("name") or status.get("id") or "").strip()
                    )
                    status_id = (
                        str(status.get("id") or status.get("name") or "").strip()
                    )
                    if not status_name or not status_id:
                        continue
                    try:
                        tasks = get_tasks(type_id, status_id, collection=coll_id)
                    except Exception as exc: # pragma: no cover - loguj i kontynuuj
                        log.warning(
                            "[WM-DBG][TOOLS-EDITOR] Błąd pobierania zadań (%s/%s/%s): %s",
                            coll_id,
                            type_id,
                            status_id,
                            exc,
                        )
                        tasks = []
                    _wm_merge_type_def(dst, {status_name: list(tasks or [])})
        if not any_loaded:
            log.warning(
                "[WM-DBG][TOOLS-EDITOR] Brak zdefiniowanych typów w data/zadania_narzedzia.json"
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

    def _move_task(self, delta: int):
        sel = self.tasks_list.curselection()
        if not sel:
            return
        typ = self.var_typ.get()
        status = self.var_status.get()
        if not typ or not status:
            return
        tasks = self.defs.get(typ, {}).get(status)
        if not isinstance(tasks, list):
            return
        i = sel[0]
        new_i = i + delta
        if new_i < 0 or new_i >= len(tasks):
            return
        tasks[i], tasks[new_i] = tasks[new_i], tasks[i]
        self._refresh_tasks_list()
        self.tasks_list.selection_set(new_i)
        self.tasks_list.activate(new_i)
        self._mark_dirty()
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
        prompt_on = ConfigManager().get(
            "tools.prompt_add_tasks_on_status_change", True
        )
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
            self._prev_status = old_status
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
            log.error("[ERROR][TOOLS-EDITOR] Brak typu narzędzia przy zapisie.")
            messagebox.showerror(
                "Błąd", "Wybierz typ narzędzia (zdefiniowany w Ustawieniach)."
            )
            return
        if not status:
            log.error("[ERROR][TOOLS-EDITOR] Brak statusu narzędzia przy zapisie.")
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
        old_status = _wm_norm_str(self.tool_data.get("status"))
        old_comment = _wm_norm_str(self.tool_data.get("komentarz"))
        new_status = status
        new_comment = _wm_norm_str(comment)
        self.tool_data["typ"] = typ
        self.tool_data["status"] = status
        self._notify_nn_ready_for_st(typ, status)
        self.tool_data["komentarz"] = comment
        status_changed = old_status != new_status
        comment_changed = _wm_norm_str(old_comment) != _wm_norm_str(new_comment)
        if status_changed or comment_changed:
            self._append_history_entry(status, comment)
        try:
            self._save_tool_file(self.tool_path, self.tool_data)
            log.info("[INFO][TOOLS-EDITOR] Zapisano narzędzie z definicji Ustawień.")
            # NIE zamykamy okna po zapisie
            self._prev_status = status
            try:
                messagebox.showinfo("Zapis", "Zapisano zmiany.", parent=self)
            except Exception:
                pass
            self._reload_from_disk()
            self._mark_clean()
        except Exception as exc:
            messagebox.showerror(
                "Błąd zapisu", f"Nie udało się zapisać zmian:\n{exc}"
            )
            log.exception("[ERROR][TOOLS-EDITOR] Wyjątek podczas zapisu narzędzia")
    def _on_delete(self):
        if not messagebox.askyesno(
            "Usuń narzędzie",
            "Czy na pewno chcesz trwale usunąć to narzędzie?",
            icon=messagebox.WARNING,
        ):
            return
        try:
            os.remove(self.tool_path)
            log.info(
                "[INFO][TOOLS-EDITOR] Usunięto narzędzie: %s", self.tool_path
            )
        except FileNotFoundError:
            messagebox.showinfo(
                "Usuń narzędzie", "Plik narzędzia był już usunięty."
            )
            log.warning(
                "[WM-DBG][TOOLS-EDITOR] Plik narzędzia nie istnieje: %s",
                self.tool_path,
            )
        except Exception as exc:
            messagebox.showerror(
                "Błąd usuwania", f"Nie udało się usunąć narzędzia:\n{exc}"
            )
            log.exception("[ERROR][TOOLS-EDITOR] Wyjątek podczas usuwania")
            return
        self._on_close()
    def _on_close(self):
        self.destroy()
    # ---------- Pomocnicze ----------
    def _notify_nn_ready_for_st(self, typ: str, status: str):
        """
        Wyświetla TYLKO komunikat informacyjny,
        gdy NN jest na ostatnim statusie.
        """
        if (typ or "").strip().upper() != "NN":
            return
        try:
            is_last = self._is_last_status(typ, status)
        except Exception:
            return
        if not is_last:
            return
        messagebox.showinfo(
            "NN → ST",
            "Narzędzie zakończyło proces NN.\n\nMoże zostać przekazane do ST.",
            parent=self,
        )
    def _get_tasks_for_current(self):
        typ = self.var_typ.get()
        status = self.var_status.get()
        if typ and status and typ in self.defs and status in self.defs[typ]:
            return self.defs[typ][status] or []
        return []
    def _ordered_statuses_for_type(self, typ: str, fallback: list[str]) -> list[str]:
        """Zwraca statusy w kolejności zadeklarowanej w pliku definicji."""
        if typ in self.defs:
            ordered = [status for status in self.defs[typ].keys() if status]
            if ordered:
                return ordered
        return list(fallback or [])
    def _is_last_status(self, typ: str, status: str) -> bool:
        """
        Zwraca True, gdy:
        - flaga tools.auto_check_on_last_status w configu jest True (domyślnie),
        - podany status jest ostatni w kolejności (patrz _ordered_statuses_for_type).
        """
        if ConfigManager().get("tools.auto_check_on_last_status", True) is not True:
            return False
        ordered = self._ordered_statuses_for_type(typ, [])
        return bool(ordered) and status == ordered[-1]
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
    def _init_save_button_styles(self):
        try:
            style = ttk.Style()
            style.configure("WM.SaveClean.TButton", relief="solid", borderwidth=2)
            style.configure("WM.SaveDirty.TButton", relief="solid", borderwidth=2)
            style.map("WM.SaveClean.TButton", bordercolor=[("!disabled", "#44cc44")])
            style.map("WM.SaveDirty.TButton", bordercolor=[("!disabled", "#ff4444")])
        except Exception:
            pass
    def _mark_dirty(self):
        if getattr(self, "_dirty", False):
            return
        self._dirty = True
        try:
            if hasattr(self, "btn_save") and self.btn_save.winfo_exists():
                self.btn_save.configure(style="WM.SaveDirty.TButton")
            if hasattr(self, "lbl_save_state") and self.lbl_save_state.winfo_exists():
                self.lbl_save_state.configure(fg="#ff4444")
            if hasattr(self, "save_wrap") and self.save_wrap.winfo_exists():
                self.save_wrap.configure(
                    highlightbackground="#ff4444",
                    highlightcolor="#ff4444",
                )
        except Exception:
            pass
    def _mark_clean(self):
        self._dirty = False
        try:
            if hasattr(self, "btn_save") and self.btn_save.winfo_exists():
                self.btn_save.configure(style="WM.SaveClean.TButton")
            if hasattr(self, "lbl_save_state") and self.lbl_save_state.winfo_exists():
                self.lbl_save_state.configure(fg="#44cc44")
            if hasattr(self, "save_wrap") and self.save_wrap.winfo_exists():
                self.save_wrap.configure(
                    highlightbackground="#44cc44",
                    highlightcolor="#44cc44",
                )
        except Exception:
            pass
# ⏹ KONIEC KODU
