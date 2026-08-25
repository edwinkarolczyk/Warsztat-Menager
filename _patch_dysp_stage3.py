from pathlib import Path

path = Path("gui_zlecenia.py")
text = path.read_text(encoding="utf-8")

old_header = '''# version: 1.2
# Zmiany 1.2:
'''
new_header = '''# version: 1.3
# Zmiany 1.3:
# - Dodano filtry widoku: Moje + Dla wszystkich, Moje, Dla wszystkich oraz Wszystkie dla brygadzisty/administratora.
# - Dodano filtr statusu: Aktywne, Nowa, W toku, Wstrzymana, Zamknięte i Wszystkie statusy.
# - Sortowanie aktywnych Dyspozycji uwzględnia priorytet przed terminem.
# Zmiany 1.2:
'''
assert old_header in text, "header 1.2 not found"
text = text.replace(old_header, new_header, 1)

old_sort = '''def _dysp_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str, str]:
    closed = 1 if _dysp_is_closed(item) else 0
    overdue = 0 if _dysp_is_overdue(item) else 1
    new = 0 if _dysp_is_new(item) else 1
    termin = str(item.get("termin") or "")
    created = str(item.get("utworzono") or "")
    return (closed, overdue, new, termin, created)
'''
new_sort = '''def _dysp_priority_rank(item: dict[str, Any]) -> int:
    value = str(item.get("priorytet") or "normalny").strip().lower()
    ranks = {
        "krytyczny": 0,
        "critical": 0,
        "wysoki": 1,
        "high": 1,
        "normalny": 2,
        "normal": 2,
        "niski": 3,
        "low": 3,
    }
    return ranks.get(value, 4)


def _dysp_sort_key(item: dict[str, Any]) -> tuple[int, int, str, str]:
    closed = 1 if _dysp_is_closed(item) else 0
    priority = _dysp_priority_rank(item)
    termin = str(item.get("termin") or "9999-12-31")
    created = str(item.get("utworzono") or "")
    return (closed, priority, termin, created)
'''
assert old_sort in text, "sort block not found"
text = text.replace(old_sort, new_sort, 1)

old_init = '''        self._login_user = self._resolve_login_user()
        self._after = _AfterGuard(self)
'''
new_init = '''        self._login_user = self._resolve_login_user()
        self._login_role = self._resolve_login_role()
        self._can_view_all = self._login_role in {"brygadzista", "administrator", "admin"}
        self._after = _AfterGuard(self)
'''
assert old_init in text, "init login block not found"
text = text.replace(old_init, new_init, 1)

old_method_tail = '''        try:
            active = ProfileService.ensure_active_user_or_none()
        except Exception:
            active = None
        return str(active or "").strip()

    # region UI helpers -------------------------------------------------
'''
new_method_tail = '''        try:
            active = ProfileService.ensure_active_user_or_none()
        except Exception:
            active = None
        return str(active or "").strip()

    def _resolve_login_role(self) -> str:
        login = str(self._login_user or "").strip().lower()
        try:
            profile = ProfileService.get_active_profile()
        except Exception:
            profile = None
        if isinstance(profile, dict):
            role = str(profile.get("rola") or profile.get("role") or "").strip().lower()
            if role:
                return role
        if login:
            try:
                for profile in ProfileService.list_profiles():
                    if str(profile.get("login") or "").strip().lower() != login:
                        continue
                    return str(profile.get("role") or "").strip().lower()
            except Exception:
                pass
        return ""

    # region UI helpers -------------------------------------------------
'''
assert old_method_tail in text, "resolve login tail not found"
text = text.replace(old_method_tail, new_method_tail, 1)

old_toolbar_end = '''        ttk.Button(toolbar, text="Usuń Dyspozycję", command=self._on_delete).pack(
            side="left", padx=(8, 0)
        )

    def _build_tree(self) -> None:
'''
new_toolbar_end = '''        ttk.Button(toolbar, text="Usuń Dyspozycję", command=self._on_delete).pack(
            side="left", padx=(8, 0)
        )

        filters = ttk.Frame(toolbar)
        filters.pack(side="right")

        ttk.Label(filters, text="Widok:").pack(side="left", padx=(0, 4))
        scope_values = ["Moje + Dla wszystkich", "Moje", "Dla wszystkich"]
        if self._can_view_all:
            scope_values.append("Wszystkie")
        self._scope_filter_var = tk.StringVar(value="Moje + Dla wszystkich")
        self.scope_filter = ttk.Combobox(
            filters,
            textvariable=self._scope_filter_var,
            values=scope_values,
            state="readonly",
            width=22,
        )
        self.scope_filter.pack(side="left", padx=(0, 10))
        self.scope_filter.bind("<<ComboboxSelected>>", self._on_filters_changed, add=True)

        ttk.Label(filters, text="Status:").pack(side="left", padx=(0, 4))
        self._status_filter_var = tk.StringVar(value="Aktywne")
        self.status_filter = ttk.Combobox(
            filters,
            textvariable=self._status_filter_var,
            values=(
                "Aktywne",
                "Nowa",
                "W toku",
                "Wstrzymana",
                "Zamknięte",
                "Wszystkie statusy",
            ),
            state="readonly",
            width=17,
        )
        self.status_filter.pack(side="left")
        self.status_filter.bind("<<ComboboxSelected>>", self._on_filters_changed, add=True)

    def _build_tree(self) -> None:
'''
assert old_toolbar_end in text, "toolbar end not found"
text = text.replace(old_toolbar_end, new_toolbar_end, 1)

old_fill = '''    def _fill_orders_table(self, rows: list[dict]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._order_rows = {}
        self._order_ids = {}
        for idx, order in enumerate(sorted(rows, key=_dysp_sort_key)):
'''
new_fill = '''    def _on_filters_changed(self, _event: Any = None) -> None:
        self._refresh()

    def _filter_rows(self, rows: list[dict]) -> list[dict]:
        login = str(self._login_user or "").strip().lower()
        scope = str(self._scope_filter_var.get() or "Moje + Dla wszystkich").strip()
        status_filter = str(self._status_filter_var.get() or "Aktywne").strip()
        filtered: list[dict] = []

        for item in rows:
            if not isinstance(item, dict):
                continue

            assigned = str(item.get("przypisane_do") or "").strip().lower()
            for_all = item.get("dla_wszystkich") is True
            mine = bool(login and assigned == login and not for_all)

            if scope == "Moje":
                scope_match = mine
            elif scope == "Dla wszystkich":
                scope_match = for_all
            elif scope == "Wszystkie" and self._can_view_all:
                scope_match = True
            else:
                scope_match = mine or for_all

            if not scope_match:
                continue

            status = _dysp_status(item)
            if status_filter == "Aktywne":
                status_match = not _dysp_is_closed(item)
            elif status_filter == "Nowa":
                status_match = _dysp_is_new(item)
            elif status_filter == "W toku":
                status_match = _dysp_is_in_progress(item)
            elif status_filter == "Wstrzymana":
                status_match = _dysp_is_paused(item)
            elif status_filter == "Zamknięte":
                status_match = _dysp_is_closed(item)
            else:
                status_match = True

            if status_match:
                filtered.append(item)

        return filtered

    def _fill_orders_table(self, rows: list[dict]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._order_rows = {}
        self._order_ids = {}
        filtered_rows = self._filter_rows(rows)
        for idx, order in enumerate(sorted(filtered_rows, key=_dysp_sort_key)):
'''
assert old_fill in text, "fill table block not found"
text = text.replace(old_fill, new_fill, 1)

path.write_text(text, encoding="utf-8")
print("patched gui_zlecenia.py -> 1.3")
