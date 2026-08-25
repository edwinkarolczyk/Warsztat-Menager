from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# gui_zlecenia.py
# ---------------------------------------------------------------------------
path = Path("gui_zlecenia.py")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '# version: 1.0\n"""Panel Dyspozycji (dawniej: Zlecenia) – lista oparta o wspólny store Dyspozycji."""\n',
    '# version: 1.1\n# Zmiany 1.1:\n# - Nowe i zamykane Dyspozycje zapisują faktycznie zalogowanego użytkownika.\n# - Anulowanie okna uwag nie zamyka Dyspozycji.\n"""Panel Dyspozycji (dawniej: Zlecenia) – lista oparta o wspólny store Dyspozycji."""\n',
    "gui_zlecenia header",
)

text = replace_once(
    text,
    'from dyspozycje_sources import load_machine_choices, load_tool_choices\n\nfrom ui_dialogs_safe import error_box\n',
    'from dyspozycje_sources import load_machine_choices, load_tool_choices\nfrom services.profile_service import ProfileService\n\nfrom ui_dialogs_safe import error_box\n',
    "gui_zlecenia profile import",
)

old_resolve = '''    def _resolve_login_user(self) -> str:\n        candidates = [\n            getattr(self.master, "login_sesji", None),\n            getattr(self.master, "current_user", None),\n            getattr(self.master, "user_login", None),\n        ]\n        for value in candidates:\n            if isinstance(value, str) and value.strip():\n                return value.strip()\n        try:\n            root = self.winfo_toplevel()\n        except Exception:\n            root = None\n        if root is not None:\n            for attr in ("login_sesji", "current_user", "user_login"):\n                value = getattr(root, attr, None)\n                if isinstance(value, str) and value.strip():\n                    return value.strip()\n        return ""\n'''
new_resolve = '''    def _resolve_login_user(self) -> str:\n        attrs = (\n            "login_sesji",\n            "current_user",\n            "user_login",\n            "active_login",\n            "_wm_login",\n            "login",\n        )\n        for attr in attrs:\n            value = getattr(self.master, attr, None)\n            if isinstance(value, str) and value.strip():\n                return value.strip()\n        try:\n            root = self.winfo_toplevel()\n        except Exception:\n            root = None\n        if root is not None:\n            for attr in attrs:\n                value = getattr(root, attr, None)\n                if isinstance(value, str) and value.strip():\n                    return value.strip()\n        try:\n            active = ProfileService.ensure_active_user_or_none()\n        except Exception:\n            active = None\n        return str(active or "").strip()\n'''
text = replace_once(text, old_resolve, new_resolve, "gui_zlecenia resolve login")

text = replace_once(
    text,
    '''            self._open_order_creator(\n                self,\n                autor="uzytkownik",\n                context={"modul_zrodlowy": "dyspozycje"},\n            )\n''',
    '''            self._open_order_creator(\n                self,\n                autor=self._login_user,\n                context={"modul_zrodlowy": "dyspozycje"},\n            )\n''',
    "gui_zlecenia add author",
)

text = replace_once(
    text,
    '''            self._open_order_creator(\n                self,\n                autor=str(mapped.get("autor") or ""),\n                context=mapped,\n            )\n''',
    '''            self._open_order_creator(\n                self,\n                autor=self._login_user or str(mapped.get("autor") or ""),\n                context=mapped,\n            )\n''',
    "gui_zlecenia edit author",
)

text = replace_once(
    text,
    '''        note = simpledialog.askstring(\n            "Zamknij Dyspozycję",\n            "Uwagi przy zamknięciu (opcjonalnie):",\n            parent=self,\n        )\n        who = self._login_user or str(mapped.get("autor") or "").strip()\n''',
    '''        note = simpledialog.askstring(\n            "Zamknij Dyspozycję",\n            "Uwagi przy zamknięciu (opcjonalnie):",\n            parent=self,\n        )\n        if note is None:\n            return\n        who = self._login_user or str(mapped.get("autor") or "").strip()\n''',
    "gui_zlecenia close cancel",
)

path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# gui_dyspozycje_creator.py
# ---------------------------------------------------------------------------
path = Path("gui_dyspozycje_creator.py")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '# version: 1.0\n"""Wspólny kreator Dyspozycji z dynamicznymi listami obiektów."""\n',
    '# version: 1.1\n# Zmiany 1.1:\n# - Termin jest edytowany jako DD-MM-RR, z kalendarzem oraz skrótami +2 dni, +1 tydzień i +2 tygodnie.\n# - Do pliku termin nadal trafia jako YYYY-MM-DD; błędny format jest blokowany.\n# - Brak przypisanego użytkownika automatycznie ustawia Dyspozycję dla wszystkich.\n# - Autor zapisu jest pobierany z bieżącej sesji.\n"""Wspólny kreator Dyspozycji z dynamicznymi listami obiektów."""\n',
    "creator header",
)

text = replace_once(
    text,
    '''from __future__ import annotations\n\nimport tkinter as tk\nfrom pathlib import Path\n''',
    '''from __future__ import annotations\n\nimport calendar\nimport datetime as _dt\nimport tkinter as tk\nfrom pathlib import Path\n''',
    "creator imports",
)

insert_after_profiles = '''except Exception:  # pragma: no cover\n    load_profiles_users = None  # type: ignore\n    resolve_profiles_path = None  # type: ignore\n\n\n'''
helpers = '''except Exception:  # pragma: no cover\n    load_profiles_users = None  # type: ignore\n    resolve_profiles_path = None  # type: ignore\n\n\ndef _deadline_to_display(value: Any) -> str:\n    raw = str(value or "").strip()\n    if not raw:\n        return ""\n    for fmt in ("%Y-%m-%d", "%d-%m-%y", "%d-%m-%Y"):\n        try:\n            return _dt.datetime.strptime(raw, fmt).strftime("%d-%m-%y")\n        except ValueError:\n            continue\n    return raw\n\n\ndef _deadline_to_iso(value: Any) -> str:\n    raw = str(value or "").strip()\n    if not raw:\n        return ""\n    for fmt in ("%d-%m-%y", "%d-%m-%Y", "%Y-%m-%d"):\n        try:\n            return _dt.datetime.strptime(raw, fmt).date().isoformat()\n        except ValueError:\n            continue\n    raise ValueError("Termin musi mieć format DD-MM-RR, np. 27-08-26.")\n\n\n'''
text = replace_once(text, insert_after_profiles, helpers, "creator deadline helpers")

old_deadline_ui = '''    ttk.Label(frame, text="Termin (YYYY-MM-DD):").grid(row=6, column=0, sticky="w", pady=4)\n    var_deadline = tk.StringVar(value=str(ctx.get("termin") or ""))\n    ent_deadline = ttk.Entry(frame, textvariable=var_deadline, width=24)\n    ent_deadline.grid(row=6, column=1, sticky="w", pady=4)\n\n'''
new_deadline_ui = '''    ttk.Label(frame, text="Termin (DD-MM-RR):").grid(row=6, column=0, sticky="w", pady=4)\n    var_deadline = tk.StringVar(value=_deadline_to_display(ctx.get("termin") or ""))\n    deadline_frame = ttk.Frame(frame)\n    deadline_frame.grid(row=6, column=1, sticky="w", pady=4)\n    ent_deadline = ttk.Entry(deadline_frame, textvariable=var_deadline, width=14)\n    ent_deadline.pack(side="left")\n    ttk.Button(\n        deadline_frame,\n        text="📅 Kalendarz",\n        command=lambda: _open_deadline_calendar(),\n    ).pack(side="left", padx=(8, 0))\n    ttk.Button(\n        deadline_frame,\n        text="+2 dni",\n        command=lambda: _set_deadline_offset(2),\n    ).pack(side="left", padx=(8, 0))\n    ttk.Button(\n        deadline_frame,\n        text="+1 tydzień",\n        command=lambda: _set_deadline_offset(7),\n    ).pack(side="left", padx=(8, 0))\n    ttk.Button(\n        deadline_frame,\n        text="+2 tygodnie",\n        command=lambda: _set_deadline_offset(14),\n    ).pack(side="left", padx=(8, 0))\n\n'''
text = replace_once(text, old_deadline_ui, new_deadline_ui, "creator deadline ui")

old_source_block = '''    options_map: dict[str, str] = {}\n    all_labels: list[str] = []\n    source_module = {"value": ""}\n\n    def _current_dyspozycja_for_print() -> dict[str, Any]:\n        return {\n            "opis": txt_desc.get("1.0", "end").strip(),\n            "termin": var_deadline.get().strip(),\n            "przypisane_do": (\n                "" if var_all.get() else var_assigned.get().strip()\n            ),\n            "priorytet": var_priority.get().strip(),\n            "autor": str(autor or ctx.get("autor") or "").strip(),\n        }\n'''
new_source_block = '''    options_map: dict[str, str] = {}\n    all_labels: list[str] = []\n    source_module = {"value": ""}\n\n    def _set_deadline_offset(days: int) -> None:\n        target = _dt.date.today() + _dt.timedelta(days=int(days))\n        var_deadline.set(target.strftime("%d-%m-%y"))\n\n    def _open_deadline_calendar() -> None:\n        try:\n            initial_iso = _deadline_to_iso(var_deadline.get())\n            initial = _dt.date.fromisoformat(initial_iso) if initial_iso else _dt.date.today()\n        except Exception:\n            initial = _dt.date.today()\n\n        picker = tk.Toplevel(win)\n        picker.title("Wybierz termin")\n        picker.resizable(False, False)\n        picker.transient(win)\n        state = {"year": initial.year, "month": initial.month}\n        month_names = [\n            "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",\n            "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień",\n        ]\n\n        top = ttk.Frame(picker, padding=(10, 10, 10, 4))\n        top.pack(fill="x")\n        title_var = tk.StringVar()\n        ttk.Button(top, text="◀", width=3, command=lambda: _move_month(-1)).pack(side="left")\n        ttk.Label(top, textvariable=title_var, width=20, anchor="center").pack(side="left", padx=8)\n        ttk.Button(top, text="▶", width=3, command=lambda: _move_month(1)).pack(side="left")\n\n        body = ttk.Frame(picker, padding=(10, 4, 10, 10))\n        body.pack(fill="both", expand=True)\n\n        def _close_picker() -> None:\n            try:\n                picker.grab_release()\n            except Exception:\n                pass\n            try:\n                picker.destroy()\n            finally:\n                try:\n                    win.grab_set()\n                except Exception:\n                    pass\n\n        def _pick_day(day: int) -> None:\n            chosen = _dt.date(state["year"], state["month"], int(day))\n            var_deadline.set(chosen.strftime("%d-%m-%y"))\n            _close_picker()\n\n        def _render_month() -> None:\n            for child in body.winfo_children():\n                child.destroy()\n            title_var.set(f"{month_names[state['month'] - 1]} {state['year']}")\n            for col, label in enumerate(("Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd")):\n                ttk.Label(body, text=label, width=4, anchor="center").grid(\n                    row=0, column=col, padx=1, pady=(0, 4)\n                )\n            weeks = calendar.monthcalendar(state["year"], state["month"])\n            for row_idx, week in enumerate(weeks, start=1):\n                for col_idx, day in enumerate(week):\n                    if day == 0:\n                        ttk.Label(body, text="", width=4).grid(row=row_idx, column=col_idx)\n                    else:\n                        ttk.Button(\n                            body,\n                            text=str(day),\n                            width=4,\n                            command=lambda d=day: _pick_day(d),\n                        ).grid(row=row_idx, column=col_idx, padx=1, pady=1)\n\n        def _move_month(delta: int) -> None:\n            month = state["month"] + int(delta)\n            year = state["year"]\n            if month < 1:\n                month = 12\n                year -= 1\n            elif month > 12:\n                month = 1\n                year += 1\n            state["year"] = year\n            state["month"] = month\n            _render_month()\n\n        picker.protocol("WM_DELETE_WINDOW", _close_picker)\n        _render_month()\n        picker.update_idletasks()\n        try:\n            x = win.winfo_rootx() + max(0, (win.winfo_width() - picker.winfo_width()) // 2)\n            y = win.winfo_rooty() + max(0, (win.winfo_height() - picker.winfo_height()) // 2)\n            picker.geometry(f"+{x}+{y}")\n        except Exception:\n            pass\n        try:\n            picker.grab_set()\n        except Exception:\n            pass\n\n    def _current_dyspozycja_for_print() -> dict[str, Any]:\n        try:\n            deadline = _deadline_to_iso(var_deadline.get())\n        except ValueError:\n            deadline = var_deadline.get().strip()\n        assigned = var_assigned.get().strip()\n        for_all = bool(var_all.get()) or not assigned\n        return {\n            "opis": txt_desc.get("1.0", "end").strip(),\n            "termin": deadline,\n            "przypisane_do": "" if for_all else assigned,\n            "priorytet": var_priority.get().strip(),\n            "autor": str(autor or ctx.get("autor") or "").strip(),\n        }\n'''
text = replace_once(text, old_source_block, new_source_block, "creator calendar block")

old_actor = '''    def _actor_login() -> str:\n        for candidate in (\n            autor,\n            ctx.get("autor"),\n            getattr(root, "active_login", ""),\n            getattr(root, "_wm_login", ""),\n            getattr(root, "login", ""),\n        ):\n            text = str(candidate or "").strip()\n            if text:\n                return text\n        return ""\n'''
new_actor = '''    def _actor_login() -> str:\n        for candidate in (\n            getattr(root, "active_login", ""),\n            getattr(root, "_wm_login", ""),\n            getattr(root, "login", ""),\n            autor,\n            ctx.get("autor"),\n        ):\n            text = str(candidate or "").strip()\n            if text:\n                return text\n        return ""\n'''
text = replace_once(text, old_actor, new_actor, "creator actor")

old_save_prefix = '''    def _save() -> None:\n        selected_label = var_object_display.get().strip()\n        object_id = options_map.get(selected_label, "").strip()\n        if not object_id:\n            messagebox.showwarning(\n                "Dyspozycje",\n                "Wybierz obiekt z listy.",\n                parent=win,\n            )\n            return\n\n        title = str(ctx.get("tytul") or "").strip() or selected_label or var_type.get().strip()\n        payload = {\n            "typ_dyspozycji": var_type.get().strip(),\n            "tytul": title,\n            "opis": txt_desc.get("1.0", "end").strip(),\n            "autor": str(autor or ctx.get("autor") or "").strip(),\n            "przypisane_do": (\n                "" if var_all.get() else var_assigned.get().strip()\n            ),\n            "dla_wszystkich": bool(var_all.get()),\n            "termin": var_deadline.get().strip(),\n            "priorytet": var_priority.get().strip(),\n            "modul_zrodlowy": source_module["value"],\n            "obiekt_id": object_id,\n            "meta": {"object_label": selected_label},\n        }\n'''
new_save_prefix = '''    def _save() -> None:\n        selected_label = var_object_display.get().strip()\n        object_id = options_map.get(selected_label, "").strip()\n        if not object_id:\n            messagebox.showwarning(\n                "Dyspozycje",\n                "Wybierz obiekt z listy.",\n                parent=win,\n            )\n            return\n\n        try:\n            deadline_iso = _deadline_to_iso(var_deadline.get())\n        except ValueError:\n            messagebox.showwarning(\n                "Dyspozycje",\n                "Termin musi mieć format DD-MM-RR, np. 27-08-26.",\n                parent=win,\n            )\n            ent_deadline.focus_set()\n            return\n\n        assigned = var_assigned.get().strip()\n        for_all = bool(var_all.get()) or not assigned\n        if for_all:\n            assigned = ""\n            if not var_all.get():\n                var_all.set(True)\n\n        title = str(ctx.get("tytul") or "").strip() or selected_label or var_type.get().strip()\n        payload = {\n            "typ_dyspozycji": var_type.get().strip(),\n            "tytul": title,\n            "opis": txt_desc.get("1.0", "end").strip(),\n            "autor": _actor_login(),\n            "przypisane_do": assigned,\n            "dla_wszystkich": for_all,\n            "termin": deadline_iso,\n            "priorytet": var_priority.get().strip(),\n            "modul_zrodlowy": source_module["value"],\n            "obiekt_id": object_id,\n            "meta": {"object_label": selected_label},\n        }\n'''
text = replace_once(text, old_save_prefix, new_save_prefix, "creator save")

path.write_text(text, encoding="utf-8")

print("patched Dyspozycje stage 1")
