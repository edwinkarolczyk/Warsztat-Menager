from pathlib import Path
import re

path = Path("gui_settings.py")
text = path.read_text(encoding="utf-8")

old_header = (
    "# version: 1.0.1\n"
    "# Moduł: gui_settings\n"
    "# Zmiany 1.0.1:\n"
    "# - refresh_panel sprawdza schema_path i używa settings_schema.json z katalogu programu, gdy ścieżka jest nieprawidłowa.\n"
)
new_header = (
    "# version: 1.0.2\n"
    "# Moduł: gui_settings\n"
    "# Zmiany 1.0.2:\n"
    "# - Dodano stały przycisk 'Zapisz wszystko' w stopce Ustawień.\n"
    "# - Dodano status ostatniego zapisu z czasem i nazwą aktywnej zakładki.\n"
    "# - Log zapisu rozróżnia zapis wykonany od zapisu oczekującego na debounce.\n"
    "# Zmiany 1.0.1:\n"
    "# - refresh_panel sprawdza schema_path i używa settings_schema.json z katalogu programu, gdy ścieżka jest nieprawidłowa.\n"
)
if text.count(old_header) != 1:
    raise SystemExit(f"header match count={text.count(old_header)}")
text = text.replace(old_header, new_header, 1)

old_footer = '''        self.btn_save: ttk.Button | None = None\n\n        self.master.winfo_toplevel().protocol("WM_DELETE_WINDOW", self.on_close)\n'''
new_footer = '''        if not hasattr(self, "_save_status_text"):\n            self._save_status_text = "Brak zapisu w tej sesji"\n\n        right_btns = ttk.Frame(self.btns)\n        right_btns.pack(side="right", padx=5)\n        self._save_status_var = tk.StringVar(value=self._save_status_text)\n        ttk.Label(right_btns, textvariable=self._save_status_var).pack(\n            side="left", padx=(5, 12)\n        )\n        self.btn_save = ttk.Button(\n            right_btns, text="Zapisz wszystko", command=self._save_from_footer\n        )\n        self.btn_save.pack(side="left", padx=5)\n\n        self.master.winfo_toplevel().protocol("WM_DELETE_WINDOW", self.on_close)\n'''
if text.count(old_footer) != 1:
    raise SystemExit(f"footer match count={text.count(old_footer)}")
text = text.replace(old_footer, new_footer, 1)

insert_anchor = '''    def _confirm_save_changes(self, *, parent=None, allow_cancel: bool = False) -> bool:\n'''
helpers = '''    def _active_settings_tab_name(self) -> str:\n        """Return the visible top-level settings tab name."""\n\n        try:\n            selected = self.nb.select()\n            name = str(self.nb.tab(selected, "text") or "").strip()\n            return name or "Ustawienia"\n        except Exception:\n            return "Ustawienia"\n\n    def _set_save_status_text(self, text: str) -> None:\n        self._save_status_text = str(text)\n        var = getattr(self, "_save_status_var", None)\n        if var is not None:\n            try:\n                var.set(self._save_status_text)\n            except Exception:\n                pass\n\n    def _mark_save_dirty(self) -> None:\n        self._set_save_status_text("Niezapisane zmiany")\n\n    def _save_from_footer(self) -> None:\n        try:\n            self.save()\n        except Exception as exc:\n            self._set_save_status_text(f"Błąd zapisu: {exc}")\n            logger.exception("[SETTINGS] ręczny zapis wszystkich ustawień nie powiódł się")\n            messagebox.showerror(\n                "Ustawienia",\n                f"Nie udało się zapisać ustawień:\\n{exc}",\n                parent=self.master,\n            )\n\n    def _record_settings_save(self, source_tab: str) -> None:\n        now = datetime.datetime.now()\n        pending = bool(getattr(self.cfg, "_pending_save", False))\n        state_text = "Zapis oczekuje" if pending else "Zapisano"\n        self._set_save_status_text(\n            f"{state_text}: {now:%H:%M:%S} | zakładka: {source_tab}"\n        )\n        state_log = "queued" if pending else "saved"\n        message = (\n            f"[SETTINGS] SAVE | zakładka={source_tab} | "\n            f"czas={now:%Y-%m-%d %H:%M:%S} | stan={state_log}"\n        )\n        logger.info(message)\n        try:\n            log_akcja(message)\n        except Exception:\n            logger.debug("[SETTINGS] Nie udało się dopisać wpisu log_akcja", exc_info=True)\n\n'''
if text.count(insert_anchor) != 1:
    raise SystemExit(f"helper anchor match count={text.count(insert_anchor)}")
text = text.replace(insert_anchor, helpers + insert_anchor, 1)

save_anchor = '''    def save(self) -> None:\n        special_orders: dict[str, Any] = {}\n'''
save_repl = '''    def save(self) -> None:\n        source_tab = self._active_settings_tab_name()\n        special_orders: dict[str, Any] = {}\n'''
if text.count(save_anchor) != 1:
    raise SystemExit(f"save start match count={text.count(save_anchor)}")
text = text.replace(save_anchor, save_repl, 1)

save_end = '''                log_akcja(\n                    f"[SETTINGS] zapisano moduły {uid}: {', '.join(disabled)}"\n                )\n\n    def refresh_panel(self) -> None:\n'''
save_end_repl = '''                log_akcja(\n                    f"[SETTINGS] zapisano moduły {uid}: {', '.join(disabled)}"\n                )\n        self._record_settings_save(source_tab)\n\n    def refresh_panel(self) -> None:\n'''
if text.count(save_end) != 1:
    raise SystemExit(f"save end match count={text.count(save_end)}")
text = text.replace(save_end, save_end_repl, 1)

# Każda realna zmiana ustawień, która ustawia dirty=True, ma od razu zmienić status stopki.
pattern = re.compile(r'(?m)^(?P<indent>[ \t]*)self\._dirty = True[ \t]*$')
matches = list(pattern.finditer(text))
if not matches:
    raise SystemExit("no dirty=True markers found")

def dirty_repl(match: re.Match[str]) -> str:
    indent = match.group("indent")
    return f"{indent}self._dirty = True\n{indent}self._mark_save_dirty()"

text = pattern.sub(dirty_repl, text)

path.write_text(text, encoding="utf-8")
print(f"patched gui_settings.py; dirty markers={len(matches)}")
