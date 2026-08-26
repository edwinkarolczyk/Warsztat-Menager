from __future__ import annotations

import subprocess
from pathlib import Path

EXPECTED = {
    "gui_profile.py": "c86a3a0b7c665fd636f2a2948bc2b03beeef5507",
    "gui_dyspozycje_creator.py": "9517d2a5179b3ce32509762bdb1cfcb2c1743ca6",
    "dyspozycje_sources.py": "fee7e15e70473a95fbdab879d292b0425e99311d",
}


def blob_sha(path: str) -> str:
    return subprocess.check_output(["git", "hash-object", path], text=True).strip()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, got {count}")
    return text.replace(old, new, 1)


def replace_region(text: str, start: str, end: str, replacement: str, label: str) -> str:
    i = text.find(start)
    if i < 0:
        raise RuntimeError(f"{label}: start marker not found")
    j = text.find(end, i + len(start))
    if j < 0:
        raise RuntimeError(f"{label}: end marker not found")
    return text[:i] + replacement + text[j:]


for path, expected in EXPECTED.items():
    actual = blob_sha(path)
    if actual != expected:
        raise RuntimeError(f"{path}: source changed, expected {expected}, got {actual}")

# ---------------------------------------------------------------------------
# gui_profile.py — aktywny ProfileView tylko dla zalogowanego użytkownika,
# z aktualnymi Dyspozycjami jako źródłem pracy.
# ---------------------------------------------------------------------------
path = Path("gui_profile.py")
text = path.read_text(encoding="utf-8")
text = replace_once(text, "# version: 1.0\n", "# version: 1.7.0\n", "profile top version")
text = replace_once(
    text,
    "# Wersja: 1.6.4 (H2c FULL)\n",
    "# Wersja: 1.7.0\n# Zmiany 1.7.0:\n# - Aktywny Profil pokazuje tylko dane zalogowanego użytkownika i jego bieżące Dyspozycje.\n# - Usunięto z aktywnego widoku Oś/PW/Narzędzia/ranking oraz stare źródła zadań.\n",
    "profile version",
)

new_init = '''    def __init__(
        self,
        master,
        login: str | None = None,
        display_name: str | None = None,
        rola: str | None = None,
        zatrudniony_od: str | None = None,
        staz_lata: int = 0,
        forced_login: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self.configure(style="WM.Container.TFrame")
        self.forced_login = forced_login
        active_login = (
            forced_login
            or login
            or ProfileService.ensure_active_user_or_none()
            or ""
        )
        self.login = str(active_login).strip()
        self.display_name = display_name or ""
        self.rola = rola or ""
        self.zatrudniony_od = zatrudniony_od or ""
        self.staz_lata = staz_lata
        self.active_tab = tk.StringVar(value="Dyspozycje")
        self._tab_widgets: dict[str, ttk.Frame] = {}
        self._tab_contents: dict[str, ttk.Frame] = {}
        self._tab_builders = {}
        self._user_data: dict[str, object] = {}
        self._tasks_cache: list[dict] = []
        self._inbox_cache: list[dict] = []
        self._sent_cache: list[dict] = []
        self._dysp_cache: list[dict] = []
        self._staz_days: int = 0
        self._about_container = None
        self._shortcuts_container = None
        self._center_container = None
        self._header_container = None
        self._simple_container = None
        self.btn_send_pw = None

        self._reload_profile_data()
        self._init_styles()
        self._build_cover_header()
        self._build_simple_profile()
        log_akcja("[WM-DBG][PROFILE] Uproszczony profil z Dyspozycjami zainicjalizowany.")

'''
text = replace_region(
    text,
    "    def __init__(\n",
    "    def load_by_login(",
    new_init,
    "ProfileView.__init__",
)

new_header = '''    def _build_header(self, parent: ttk.Frame) -> None:
        wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrap.pack(fill="x")

        user = get_user(self.login) or {}
        display = (
            user.get("display_name")
            or self.display_name
            or " ".join(
                part
                for part in (
                    str(user.get("imie") or "").strip(),
                    str(user.get("nazwisko") or "").strip(),
                )
                if part
            )
            or self.login
            or "—"
        )
        role = user.get("rola") or self.rola or "—"
        login_label = f"@{self.login}" if self.login else "@—"

        ttk.Label(wrap, text=str(display), style="WM.H1.TLabel").pack(anchor="w")
        ttk.Label(wrap, text=login_label, style="WM.Muted.TLabel").pack(anchor="w", pady=(2, 0))
        ttk.Label(wrap, text=f"Rola: {role}", style="WM.Muted.TLabel").pack(anchor="w", pady=(2, 0))

'''
text = replace_region(
    text,
    "    def _build_header(",
    "    def _build_cover_header(",
    new_header,
    "ProfileView._build_header",
)

new_reload = '''    def _reload_profile_data(self) -> None:
        if not self.login:
            self._user_data = {}
            self._tasks_cache = []
            self._inbox_cache = []
            self._sent_cache = []
            self._dysp_cache = []
            self._staz_days = 0
            return

        self._user_data = get_user(self.login) or {}
        self._tasks_cache = []
        self._inbox_cache = []
        self._sent_cache = []
        try:
            self._dysp_cache = list(visible_for_login(self.login) or [])
        except Exception as exc:
            log_akcja(f"[WM-DBG][PROFILE] Nie udało się wczytać Dyspozycji: {exc}")
            self._dysp_cache = []
        self._staz_days = staz_days_for_login(self.login)
        display_candidates = [
            self._user_data.get("display_name"),
            " ".join(
                part
                for part in (
                    str(self._user_data.get("imie", "")).strip() or "",
                    str(self._user_data.get("nazwisko", "")).strip() or "",
                )
                if part
            ),
            self._user_data.get("nazwa"),
            self.display_name,
            self.login,
        ]
        for candidate in display_candidates:
            value = str(candidate or "").strip()
            if value:
                self.display_name = value
                break
        role = self._user_data.get("rola")
        if role:
            self.rola = str(role)
        zatr = self._user_data.get("zatrudniony_od")
        if zatr:
            self.zatrudniony_od = str(zatr)
        self.staz_lata = staz_years_floor_for_login(self.login) or self.staz_lata

'''
text = replace_region(
    text,
    "    def _reload_profile_data(",
    "    def _render_tab(",
    new_reload,
    "ProfileView._reload_profile_data",
)

new_refresh = '''    def _refresh_view(self) -> None:
        self._reload_profile_data()
        if self._header_container is not None:
            for child in self._header_container.winfo_children():
                child.destroy()
            self._build_header(self._header_container)
        if self._simple_container is not None:
            for child in self._simple_container.winfo_children():
                child.destroy()
            self._render_simple_profile(self._simple_container)

'''
text = replace_region(
    text,
    "    def _refresh_view(",
    "    def _parse_timestamp(",
    new_refresh,
    "ProfileView._refresh_view",
)

simple_methods = '''    def _profile_shift_text(self) -> str:
        if not self.login:
            return "—"
        try:
            now = datetime.now()
            if now.weekday() == 6:
                return "Wolne"
            times = _shift_times()
            mode = _user_mode(str(self.login))
            slot = _slot_for_mode(mode, _week_idx(now.date()))
            # Zachowujemy dotychczasową regułę soboty z modułu Profil.
            if now.weekday() == 5:
                slot = "RANO"
            if slot == "RANO":
                return f"1 zmiana {times['R_START'].strftime('%H:%M')}–{times['R_END'].strftime('%H:%M')}"
            return f"2 zmiana {times['P_START'].strftime('%H:%M')}–{times['P_END'].strftime('%H:%M')}"
        except Exception as exc:
            log_akcja(f"[WM-DBG][PROFILE] Błąd ustalania zmiany: {exc}")
            return "—"

    @staticmethod
    def _profile_deadline_display(value: object) -> str:
        raw = str(value or "").strip()
        if not raw:
            return "—"
        try:
            parsed = _dt.strptime(raw[:10], "%Y-%m-%d")
        except Exception:
            return raw
        days = ("Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nie")
        return f"{days[parsed.weekday()]} {parsed.strftime('%d-%m-%y')}"

    @staticmethod
    def _profile_type_label(value: object) -> str:
        labels = {
            "narzedzie": "Narzędzie",
            "maszyna": "Maszyna",
            "magazyn": "Magazyn",
            "zlecenie_wykonania": "Wykonanie produkcji",
            "zamowienie": "Wykonanie produkcji",
        }
        raw = str(value or "").strip().lower()
        return labels.get(raw, str(value or "—"))

    @staticmethod
    def _profile_status_label(value: object) -> str:
        labels = {
            "nowa": "Nowa",
            "w_toku": "W toku",
            "wstrzymana": "Wstrzymana",
            "zamknieta": "Zamknięta",
        }
        raw = str(value or "").strip().lower()
        return labels.get(raw, str(value or "—"))

    def _build_simple_profile(self) -> None:
        body = ttk.Frame(self, style="WM.Container.TFrame")
        body.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self._simple_container = body
        self._render_simple_profile(body)

    def _render_simple_profile(self, parent: ttk.Frame) -> None:
        user = self._user_data or {}

        work = ttk.LabelFrame(parent, text="Praca", style="WM.Section.TLabelframe", padding=12)
        work.pack(fill="x", pady=(0, 10))

        def info_row(label: str, value: str) -> None:
            row = ttk.Frame(work, style="WM.TFrame")
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{label}:", style="WM.Muted.TLabel", width=20).pack(side="left")
            ttk.Label(row, text=value or "—", style="WM.TLabel").pack(side="left")

        employed = str(user.get("zatrudniony_od") or self.zatrudniony_od or "—")
        if self._staz_days:
            tenure = f"{self.staz_lata} lat ({self._staz_days} dni)"
        else:
            tenure = f"{self.staz_lata} lat"
        info_row("Dzisiejsza zmiana", self._profile_shift_text())
        info_row("Zatrudniony od", employed)
        info_row("Staż", tenure)

        box = ttk.LabelFrame(parent, text="Moje Dyspozycje", style="WM.Section.TLabelframe", padding=12)
        box.pack(fill="both", expand=True)

        rows = [row for row in self._dysp_cache if isinstance(row, dict)]
        counts = {"nowa": 0, "w_toku": 0, "wstrzymana": 0, "zamknieta": 0}
        for row in rows:
            status = str(row.get("status") or "").strip().lower()
            if status in counts:
                counts[status] += 1

        counters = ttk.Frame(box, style="WM.TFrame")
        counters.pack(fill="x", pady=(0, 8))
        for text_value in (
            f"Nowe: {counts['nowa']}",
            f"W toku: {counts['w_toku']}",
            f"Wstrzymane: {counts['wstrzymana']}",
            f"Zamknięte: {counts['zamknieta']}",
        ):
            ttk.Label(counters, text=text_value, style="WM.TLabel", relief="groove").pack(side="left", padx=(0, 8))

        style = ttk.Style(self)
        style.configure("Profile.Dyspozycje.Treeview", font=("Segoe UI", 11), rowheight=30)
        style.configure("Profile.Dyspozycje.Treeview.Heading", font=("Segoe UI", 11, "bold"))

        table_wrap = ttk.Frame(box, style="WM.TFrame")
        table_wrap.pack(fill="both", expand=True)
        columns = ("termin", "dyspozycja", "typ", "status", "priorytet")
        tree = ttk.Treeview(
            table_wrap,
            columns=columns,
            show="headings",
            style="Profile.Dyspozycje.Treeview",
            height=12,
        )
        headings = {
            "termin": "Termin",
            "dyspozycja": "Dyspozycja",
            "typ": "Typ",
            "status": "Status",
            "priorytet": "Priorytet",
        }
        widths = {"termin": 150, "dyspozycja": 480, "typ": 180, "status": 130, "priorytet": 120}
        for key in columns:
            tree.heading(key, text=headings[key])
            tree.column(key, width=widths[key], anchor="w", stretch=(key == "dyspozycja"))
        scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        active_rows = [row for row in rows if str(row.get("status") or "").strip().lower() != "zamknieta"]
        active_rows.sort(
            key=lambda row: (
                str(row.get("termin") or "9999-12-31"),
                str(row.get("tytul") or "").casefold(),
            )
        )
        for row in active_rows:
            title = str(row.get("tytul") or row.get("opis") or row.get("id") or "Dyspozycja").strip()
            if bool(row.get("dla_wszystkich")):
                title = f"{title} • dla wszystkich"
            priority = str(row.get("priorytet") or "normalny").strip().capitalize()
            tree.insert(
                "",
                "end",
                values=(
                    self._profile_deadline_display(row.get("termin")),
                    title,
                    self._profile_type_label(row.get("typ_dyspozycji")),
                    self._profile_status_label(row.get("status")),
                    priority,
                ),
            )

        if not active_rows:
            ttk.Label(
                box,
                text="Brak aktywnych Dyspozycji dla tego użytkownika.",
                style="WM.Muted.TLabel",
            ).pack(anchor="w", pady=(8, 0))

'''
marker = "    def _make_avatar(self, parent: tk.Widget) -> tk.Widget:\n"
if marker not in text:
    raise RuntimeError("ProfileView._make_avatar marker missing")
text = text.replace(marker, simple_methods + marker, 1)

# Static scope checks for the active view.
class_tail = text[text.index("class ProfileView"):]
reload_slice = class_tail[class_tail.index("    def _reload_profile_data("):class_tail.index("    def _render_tab(")]
if "visible_for_login(self.login)" not in reload_slice:
    raise RuntimeError("active profile is not using visible_for_login")
if "get_tasks_for(" in reload_slice or "_collect_tool_tasks(" in reload_slice:
    raise RuntimeError("legacy task sources still used by active profile reload")
if "self._build_simple_profile()" not in class_tail[class_tail.index("    def __init__("):class_tail.index("    def load_by_login(")]:
    raise RuntimeError("simplified profile layout not active")
path.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# gui_dyspozycje_creator.py — polskie etykiety typów bez zmiany wartości JSON.
# ---------------------------------------------------------------------------
path = Path("gui_dyspozycje_creator.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "# version: 1.4\n# Zmiany 1.4:\n",
    "# version: 1.5\n# Zmiany 1.5:\n# - Kreator pokazuje polskie nazwy typów Dyspozycji, zachowując techniczne wartości w danych.\n# Zmiany 1.4:\n",
    "creator version",
)
insert_after = "from maszyny_dyspozycje import sync_machine_review_from_dyspozycja\n\n"
type_helpers = '''from maszyny_dyspozycje import sync_machine_review_from_dyspozycja\n\n_DYSP_TYPE_LABELS = {
    "narzedzie": "Narzędzie",
    "maszyna": "Maszyna",
    "magazyn": "Magazyn",
    "zlecenie_wykonania": "Wykonanie produkcji",
}


def _dysp_type_value(value: Any) -> str:
    raw = str(value or "").strip()
    if raw == "zamowienie":
        return "zlecenie_wykonania"
    for key, label in _DYSP_TYPE_LABELS.items():
        if raw.casefold() == label.casefold():
            return key
    return raw


def _dysp_type_label(value: Any) -> str:
    key = _dysp_type_value(value)
    return _DYSP_TYPE_LABELS.get(key, str(value or ""))

'''
text = replace_once(text, insert_after, type_helpers, "creator type helpers")
old_combo = '''    var_type = tk.StringVar(value=str(ctx.get("typ_dyspozycji") or "narzedzie"))
    cb_type = ttk.Combobox(
        frame,
        textvariable=var_type,
        values=["narzedzie", "maszyna", "magazyn", "zlecenie_wykonania"],
        state="readonly",
        width=24,
    )
'''
new_combo = '''    initial_type = _dysp_type_value(ctx.get("typ_dyspozycji") or "narzedzie")
    var_type = tk.StringVar(value=initial_type)
    var_type_display = tk.StringVar(value=_dysp_type_label(initial_type))
    cb_type = ttk.Combobox(
        frame,
        textvariable=var_type_display,
        values=list(_DYSP_TYPE_LABELS.values()),
        state="readonly",
        width=24,
    )
'''
text = replace_once(text, old_combo, new_combo, "creator type combobox")
old_bind = '''    cb_type.bind("<<ComboboxSelected>>", _refresh_object_choices)
    _refresh_object_choices()
'''
new_bind = '''    def _on_type_selected(*_args) -> None:
        var_type.set(_dysp_type_value(var_type_display.get()))
        _refresh_object_choices()

    cb_type.bind("<<ComboboxSelected>>", _on_type_selected)
    _refresh_object_choices()
'''
text = replace_once(text, old_bind, new_bind, "creator type binding")
if 'values=["narzedzie", "maszyna", "magazyn", "zlecenie_wykonania"]' in text:
    raise RuntimeError("raw type values are still exposed in creator combobox")
path.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# dyspozycje_sources.py — Magazyn z jednego, canonical loadera.
# ---------------------------------------------------------------------------
path = Path("dyspozycje_sources.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "# version: 1.1\n\"\"\"Źródła danych dla Dyspozycji (bez GUI).\"\"\"\n# Zmiany 1.1:\n",
    "# version: 1.2\n\"\"\"Źródła danych dla Dyspozycji (bez GUI).\"\"\"\n# Zmiany 1.2:\n# - Lista Magazynu w kreatorze korzysta z logika_magazyn.load_magazyn(include_external=True).\n# - Klucze techniczne items/meta nie są już traktowane jak pozycje magazynowe.\n# Zmiany 1.1:\n",
    "sources version",
)
new_mag = '''def load_magazyn_choices() -> List[Tuple[str, str]]:
    """Zwróć realne pozycje z tego samego loadera, którego używa moduł Magazyn."""
    try:
        from logika_magazyn import load_magazyn

        data = load_magazyn(include_external=True) or {}
    except Exception as exc:
        try:
            print(f"[WM-DBG][DYSP][SRC] canonical magazyn load failed: {exc}")
        except Exception:
            pass
        return []

    rows = data.get("pozycje") or data.get("items") or {}
    if isinstance(rows, dict):
        iterable = list(rows.items())
    elif isinstance(rows, list):
        iterable = [("", row) for row in rows]
    else:
        return []

    type_labels = {
        "surowiec": "Surowiec",
        "półprodukt": "Półprodukt",
        "polprodukt": "Półprodukt",
        "produkt": "Produkt",
    }
    type_order = {"surowiec": 0, "półprodukt": 1, "polprodukt": 1, "produkt": 2}
    out: List[Tuple[str, str]] = []
    seen: set[str] = set()

    for key, raw in iterable:
        if not isinstance(raw, dict):
            continue
        code = str(
            raw.get("id")
            or raw.get("kod")
            or raw.get("nr")
            or raw.get("symbol")
            or key
            or ""
        ).strip()
        if not code:
            continue
        folded = code.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        name = str(raw.get("nazwa") or raw.get("name") or raw.get("opis") or "").strip()
        raw_type = str(raw.get("typ") or "").strip().lower()
        section = type_labels.get(raw_type, raw_type.capitalize() if raw_type else "Magazyn")
        main = f"{code} - {name}" if name and name != code else code
        out.append((code, f"{section} | {main}"))

    def _sort_key(item: Tuple[str, str]):
        code, label = item
        raw = rows.get(code) if isinstance(rows, dict) else None
        typ = str((raw or {}).get("typ") or "").strip().lower() if isinstance(raw, dict) else ""
        return (type_order.get(typ, 9), label.casefold())

    out.sort(key=_sort_key)
    return out


'''
text = replace_region(
    text,
    "def load_magazyn_choices() -> List[Tuple[str, str]]:\n",
    "# =========================================================\n# ZLECENIE WYKONANIA\n# =========================================================\n",
    new_mag,
    "canonical magazyn choices",
)
mag_slice = text[text.index("def load_magazyn_choices()"):text.index("# ZLECENIE WYKONANIA")]
if "load_magazyn(include_external=True)" not in mag_slice:
    raise RuntimeError("canonical magazyn loader missing")
if "magazyn_candidates" in mag_slice:
    raise RuntimeError("legacy direct magazyn parsing still active")
path.write_text(text, encoding="utf-8")

print("Patch prepared successfully")
