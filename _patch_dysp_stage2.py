from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


# --- dyspozycje_store.py ---
path = Path("dyspozycje_store.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "# version: 1.0\n# -*- coding: utf-8 -*-",
    "# version: 1.1\n# Zmiany 1.1:\n# - Dodano kontrolowane przejścia statusów Nowa -> W toku -> Wstrzymana/Zamknięta.\n# - Każda zmiana statusu zapisuje użytkownika i czas w meta.historia_statusow.\n# - Zamknięcie korzysta ze wspólnego mechanizmu zmiany statusu.\n# -*- coding: utf-8 -*-",
    "store header",
)

old_close = '''def close_dyspozycja(
    dyspozycja_id: str,
    *,
    uwagi: str = "",
    closed_by: str = "",
) -> dict[str, Any] | None:
    updates = {
        "status": "zamknieta",
        "wykonano": _now_iso(),
        "zamknieto_at": _now_iso(),
        "zamkniete_przez": _normalize_login(closed_by),
    }
    if str(uwagi or "").strip():
        updates["uwagi"] = str(uwagi).strip()
    return update_dyspozycja(dyspozycja_id, updates)
'''
new_close = '''def set_dyspozycja_status(
    dyspozycja_id: str,
    new_status: str,
    *,
    changed_by: str = "",
    uwagi: str = "",
) -> dict[str, Any] | None:
    """Zmień status zgodnie z obiegiem i dopisz historię kto/kiedy."""

    target = str(new_status or "").strip().lower()
    if target not in DISP_ALLOWED_STATUSES:
        return None

    current_item = get_dyspozycja(dyspozycja_id)
    if not current_item:
        return None

    current = _normalize_status(current_item.get("status"))
    if target == current:
        return deepcopy(current_item)

    allowed_transitions = {
        "nowa": {"w_toku"},
        "w_toku": {"wstrzymana", "zamknieta"},
        "wstrzymana": {"w_toku", "zamknieta"},
        "zamknieta": set(),
    }
    if target not in allowed_transitions.get(current, set()):
        return None

    now = _now_iso()
    who = _normalize_login(changed_by)
    meta = dict(current_item.get("meta") or {})
    history_raw = meta.get("historia_statusow")
    history = list(history_raw) if isinstance(history_raw, list) else []
    history.append(
        {
            "z": current,
            "na": target,
            "kto": who,
            "kiedy": now,
        }
    )
    meta["historia_statusow"] = history

    updates: dict[str, Any] = {
        "status": target,
        "meta": meta,
    }
    if target == "zamknieta":
        updates.update(
            {
                "wykonano": now,
                "zamknieto_at": now,
                "zamkniete_przez": who,
            }
        )
        if str(uwagi or "").strip():
            updates["uwagi"] = str(uwagi).strip()

    return update_dyspozycja(dyspozycja_id, updates)


def close_dyspozycja(
    dyspozycja_id: str,
    *,
    uwagi: str = "",
    closed_by: str = "",
) -> dict[str, Any] | None:
    return set_dyspozycja_status(
        dyspozycja_id,
        "zamknieta",
        changed_by=closed_by,
        uwagi=uwagi,
    )
'''
text = replace_once(text, old_close, new_close, "store status function")
text = replace_once(
    text,
    '    "save_dyspozycje",\n    "update_dyspozycja",',
    '    "save_dyspozycje",\n    "set_dyspozycja_status",\n    "update_dyspozycja",',
    "store __all__",
)
path.write_text(text, encoding="utf-8")


# --- gui_zlecenia.py ---
path = Path("gui_zlecenia.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "# version: 1.1\n# Zmiany 1.1:",
    "# version: 1.2\n# Zmiany 1.2:\n# - Dodano obieg statusów: Nowa -> W toku -> Wstrzymana -> Zamknięta.\n# - Przyciski Rozpocznij/Wstrzymaj/Wznów/Zamknij są aktywne zależnie od statusu.\n# - Statusy mają czytelne polskie etykiety i kolory; zmiany zapisują kto i kiedy.\n# Zmiany 1.1:",
    "gui header",
)
text = replace_once(
    text,
    '''from dyspozycje_store import (
    close_dyspozycja,
    delete_dyspozycja,
    get_dyspozycje_path,
    load_dyspozycje,
)''',
    '''from dyspozycje_store import (
    delete_dyspozycja,
    get_dyspozycje_path,
    load_dyspozycje,
    set_dyspozycja_status,
)''',
    "gui imports",
)
text = replace_once(
    text,
    '        "new_foreground": "#facc15",\n        "new_blink_foreground": "#ffffff",',
    '        "new_foreground": "#facc15",\n        "in_progress_foreground": "#60a5fa",\n        "paused_foreground": "#fb923c",\n        "new_blink_foreground": "#ffffff",',
    "gui status colors defaults",
)
text = replace_once(
    text,
    '''def _dysp_is_new(item: dict[str, Any]) -> bool:
    return _dysp_status(item) in {"nowa", "new"}


def _dysp_is_overdue''',
    '''def _dysp_is_new(item: dict[str, Any]) -> bool:
    return _dysp_status(item) in {"nowa", "new"}


def _dysp_is_in_progress(item: dict[str, Any]) -> bool:
    return _dysp_status(item) == "w_toku"


def _dysp_is_paused(item: dict[str, Any]) -> bool:
    return _dysp_status(item) == "wstrzymana"


def _dysp_is_overdue''',
    "gui status helpers",
)
text = replace_once(
    text,
    '''def _dysp_status_label(item: dict[str, Any]) -> str:
    return str(item.get("status") or "nowa").strip() or "nowa"
''',
    '''def _dysp_status_label(item: dict[str, Any]) -> str:
    labels = {
        "nowa": "Nowa",
        "w_toku": "W toku",
        "wstrzymana": "Wstrzymana",
        "zamknieta": "Zamknięta",
    }
    status = _dysp_status(item) or "nowa"
    return labels.get(status, str(item.get("status") or "Nowa").strip() or "Nowa")
''',
    "gui status labels",
)
old_toolbar = '''        ttk.Button(toolbar, text="Zamknij Dyspozycję", command=self._on_close).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(toolbar, text="Usuń Dyspozycję", command=self._on_delete).pack(
            side="left", padx=(8, 0)
        )
'''
new_toolbar = '''        self.btn_start = ttk.Button(toolbar, text="Rozpocznij", command=self._on_start)
        self.btn_start.pack(side="left", padx=(8, 0))

        self.btn_pause = ttk.Button(toolbar, text="Wstrzymaj", command=self._on_pause)
        self.btn_pause.pack(side="left", padx=(8, 0))

        self.btn_resume = ttk.Button(toolbar, text="Wznów", command=self._on_resume)
        self.btn_resume.pack(side="left", padx=(8, 0))

        self.btn_close = ttk.Button(
            toolbar, text="Zamknij Dyspozycję", command=self._on_close
        )
        self.btn_close.pack(side="left", padx=(8, 0))

        ttk.Button(toolbar, text="Usuń Dyspozycję", command=self._on_delete).pack(
            side="left", padx=(8, 0)
        )
'''
text = replace_once(text, old_toolbar, new_toolbar, "gui toolbar")
text = replace_once(
    text,
    '''        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_double_click, add=True)
        self._ensure_blink_started()
''',
    '''        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_double_click, add=True)
        self.tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self._update_status_actions(),
            add=True,
        )
        self._update_status_actions()
        self._ensure_blink_started()
''',
    "gui selection binding",
)
text = replace_once(
    text,
    '''        self.tree.tag_configure("dysp_closed", foreground=ui["closed_foreground"])
        self.tree.tag_configure("dysp_new", foreground=ui["new_foreground"])
''',
    '''        self.tree.tag_configure("dysp_closed", foreground=ui["closed_foreground"])
        self.tree.tag_configure(
            "dysp_in_progress", foreground=ui["in_progress_foreground"]
        )
        self.tree.tag_configure("dysp_paused", foreground=ui["paused_foreground"])
        self.tree.tag_configure("dysp_new", foreground=ui["new_foreground"])
''',
    "gui tag colors",
)
text = replace_once(
    text,
    '''            if _dysp_is_closed(order):
                tags.append("dysp_closed")
            elif _dysp_is_overdue(order):
                tags.append("dysp_overdue")
            elif _dysp_is_new(order):
                tags.append("dysp_new")
''',
    '''            if _dysp_is_closed(order):
                tags.append("dysp_closed")
            elif _dysp_is_overdue(order):
                tags.append("dysp_overdue")
            elif _dysp_is_new(order):
                tags.append("dysp_new")
            elif _dysp_is_in_progress(order):
                tags.append("dysp_in_progress")
            elif _dysp_is_paused(order):
                tags.append("dysp_paused")
''',
    "gui row status tags",
)
text = replace_once(
    text,
    '''            if order_key:
                self._order_ids[iid] = order_key

    def _reload_orders''',
    '''            if order_key:
                self._order_ids[iid] = order_key
        self._update_status_actions()

    def _reload_orders''',
    "gui action refresh",
)
old_selected = '''    def _selected_row(self) -> dict[str, Any] | None:
        selection = self.tree.selection()
        if not selection:
            return None
        iid = selection[0]
        mapped = dict(self._order_rows.get(iid, {}) or {})
        return mapped or None

    def _on_close(self) -> None:
'''
new_selected = '''    def _selected_row(self) -> dict[str, Any] | None:
        selection = self.tree.selection()
        if not selection:
            return None
        iid = selection[0]
        mapped = dict(self._order_rows.get(iid, {}) or {})
        return mapped or None

    def _update_status_actions(self) -> None:
        mapped = self._selected_row()
        status = _dysp_status(mapped or {})
        enabled = {
            "start": status == "nowa",
            "pause": status == "w_toku",
            "resume": status == "wstrzymana",
            "close": status in {"w_toku", "wstrzymana"},
        }
        for button, key in (
            (getattr(self, "btn_start", None), "start"),
            (getattr(self, "btn_pause", None), "pause"),
            (getattr(self, "btn_resume", None), "resume"),
            (getattr(self, "btn_close", None), "close"),
        ):
            if button is None:
                continue
            try:
                button.state(["!disabled"] if enabled[key] else ["disabled"])
            except Exception:
                pass

    def _change_status(self, target: str) -> None:
        mapped = self._selected_row()
        if not mapped:
            messagebox.showinfo(
                "Dyspozycje",
                "Najpierw wybierz Dyspozycję.",
                parent=self,
            )
            return
        dysp_id = str(mapped.get("id") or "").strip()
        if not dysp_id:
            return
        who = self._login_user or str(mapped.get("autor") or "").strip()
        changed = set_dyspozycja_status(dysp_id, target, changed_by=who)
        if not changed:
            messagebox.showerror(
                "Dyspozycje",
                "Ta zmiana statusu nie jest dozwolona.",
                parent=self,
            )
            return
        try:
            self.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")
        except Exception:
            self._reload_orders()

    def _on_start(self) -> None:
        self._change_status("w_toku")

    def _on_pause(self) -> None:
        self._change_status("wstrzymana")

    def _on_resume(self) -> None:
        self._change_status("w_toku")

    def _on_close(self) -> None:
'''
text = replace_once(text, old_selected, new_selected, "gui status actions")
text = replace_once(
    text,
    '''        if str(mapped.get("status") or "").strip().lower() == "zamknieta":
            messagebox.showinfo(
                "Dyspozycje",
                "Ta Dyspozycja jest już zamknięta.",
                parent=self,
            )
            return
''',
    '''        if _dysp_status(mapped) not in {"w_toku", "wstrzymana"}:
            messagebox.showinfo(
                "Dyspozycje",
                "Zamknąć można Dyspozycję W toku albo Wstrzymaną.",
                parent=self,
            )
            return
''',
    "gui close guard",
)
text = replace_once(
    text,
    '''        changed = close_dyspozycja(
            dysp_id,
            uwagi=note or "",
            closed_by=who,
        )
''',
    '''        changed = set_dyspozycja_status(
            dysp_id,
            "zamknieta",
            changed_by=who,
            uwagi=note or "",
        )
''',
    "gui close status call",
)
path.write_text(text, encoding="utf-8")

print("Dyspozycje stage 2 patch applied")
