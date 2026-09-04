# version: 1.11
# Zmiany 1.11:
# - Brygadzista i administrator domyślnie widzą wszystkie Dyspozycje; pozostali zachowują widok Moje + Dla wszystkich.
# Zmiany 1.10:
# - Widok Dyspozycji odpina globalny event po zniszczeniu i nie odświeża nieistniejącego Treeview.
# - Usunięto TclError 'invalid command name' po ponownym otwieraniu/przełączaniu Dyspozycji.
# Zmiany 1.9:
# - Termin w tabeli Dyspozycji jest wyświetlany w formacie jak w Maszynach: dzień tygodnia + DD-MM-RR.
# - Zapis terminu w danych pozostaje bez zmian (ISO), zmienia się wyłącznie prezentacja.
# Zmiany 1.8:
# - Automatyczna Dyspozycja przeglądu maszyny synchronizuje start i zamknięcie z wpisem serwisowym maszyny.
# Zmiany 1.7:
# - Dyspozycje automatycznie dodają zadanie dla cyklicznego przeglądu maszyny do 7 dni przed terminem.
# - Automatyczny wpis zachowuje typ Maszyna, konkretną maszynę, opis źródła oraz roczny klucz bez duplikatów.
# Zmiany 1.6:
# - Rozpoczęcie Dyspozycji wykonania rezerwuje potrzebne dostępne stany Magazynu.
# - Zamknięcie rozlicza faktyczną ilość, zużywa rezerwacje i dopiero potem księguje naddatek półproduktu.
# - Usunięcie aktywnej Dyspozycji wykonania zwalnia jej rezerwacje; edycja po rozpoczęciu jest blokowana.
# Zmiany 1.5:
# - Zamknięcie Dyspozycji wykonania zapisuje faktyczną ilość wykonaną.
# - Dla półproduktu naddatek ponad plan automatycznie zwiększa stan Magazynu.
# - Rozliczenie naddatku jest chronione przed podwójnym zaksięgowaniem po ID Dyspozycji.
# Zmiany 1.4:
# - Kolumna przypisania pokazuje osobno zleconego i faktycznego wykonawcę.
# - Rozpoczęcie cudzej Dyspozycji wymaga potwierdzenia i nie zmienia przypisania.
# - Dyspozycja dla wszystkich po rozpoczęciu pokazuje osobę, która ją podjęła.
# Zmiany 1.3:
# - Dodano filtry widoku: Moje + Dla wszystkich, Moje, Dla wszystkich oraz Wszystkie dla brygadzisty/administratora.
# - Dodano filtr statusu: Aktywne, Nowa, W toku, Wstrzymana, Zamknięte i Wszystkie statusy.
# - Sortowanie aktywnych Dyspozycji uwzględnia priorytet przed terminem.
# Zmiany 1.2:
# - Dodano obieg statusów: Nowa -> W toku -> Wstrzymana -> Zamknięta.
# - Przyciski Rozpocznij/Wstrzymaj/Wznów/Zamknij są aktywne zależnie od statusu.
# - Statusy mają czytelne polskie etykiety i kolory; zmiany zapisują kto i kiedy.
# Zmiany 1.1:
# - Nowe i zamykane Dyspozycje zapisują faktycznie zalogowanego użytkownika.
# - Anulowanie okna uwag nie zamyka Dyspozycji.
"""Panel Dyspozycji (dawniej: Zlecenia) – lista oparta o wspólny store Dyspozycji."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from config_manager import ConfigManager
from dyspozycje_store import (
    delete_dyspozycja,
    get_dyspozycje_path,
    load_dyspozycje,
    set_dyspozycja_status,
    update_dyspozycja,
)
from dyspozycje_sources import load_machine_choices, load_tool_choices
from maszyny_dyspozycje import (
    ensure_due_machine_cycle_dyspozycje,
    sync_machine_review_from_dyspozycja,
)
from services.profile_service import ProfileService
from planowanie_magazyn import (
    WarehouseIntegrationError,
    add_semiproduct_surplus,
    get_operation_settlement,
    reconcile_and_consume_execution,
    release_execution_reservations,
    reserve_execution_requirements,
    stock_snapshot_for_operation,
)

from ui_dialogs_safe import error_box


logger = logging.getLogger(__name__)


def _dysp_ui_config() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "blink_enabled": True,
        "closed_foreground": "#9ca3af",
        "new_foreground": "#facc15",
        "in_progress_foreground": "#60a5fa",
        "paused_foreground": "#fb923c",
        "new_blink_foreground": "#ffffff",
        "overdue_foreground": "#ef4444",
        "overdue_blink_foreground": "#ffffff",
        "overdue_blink_background": "#7f1d1d",
        "new_blink_ms": 2000,
        "overdue_blink_ms": 500,
    }
    try:
        cfg = ConfigManager()
        data = cfg.load()
        ui = (((data or {}).get("dyspozycje") or {}).get("ui") or {})
        out = dict(defaults)
        out.update({k: v for k, v in ui.items() if v not in (None, "")})
        out["new_blink_ms"] = int(
            out.get("new_blink_ms") or defaults["new_blink_ms"]
        )
        out["overdue_blink_ms"] = int(
            out.get("overdue_blink_ms") or defaults["overdue_blink_ms"]
        )
        blink_enabled = out.get("blink_enabled", True)
        if isinstance(blink_enabled, str):
            blink_enabled = blink_enabled.strip().lower() not in {
                "0",
                "false",
                "nie",
                "no",
                "off",
            }
        out["blink_enabled"] = bool(blink_enabled)
        return out
    except Exception:
        return defaults


def _dysp_status(item: dict[str, Any]) -> str:
    return str(item.get("status") or "").strip().lower()


def _dysp_is_closed(item: dict[str, Any]) -> bool:
    return _dysp_status(item) in {
        "zamknieta",
        "zamknięta",
        "closed",
        "done",
        "wykonane",
    }


def _dysp_is_new(item: dict[str, Any]) -> bool:
    return _dysp_status(item) in {"nowa", "new"}


def _dysp_is_in_progress(item: dict[str, Any]) -> bool:
    return _dysp_status(item) == "w_toku"


def _dysp_is_paused(item: dict[str, Any]) -> bool:
    return _dysp_status(item) == "wstrzymana"


def _dysp_is_overdue(item: dict[str, Any]) -> bool:
    if _dysp_is_closed(item):
        return False
    raw = str(item.get("termin") or item.get("deadline") or "").strip()
    if not raw:
        return False
    try:
        deadline = _dt.date.fromisoformat(raw[:10])
        return deadline < _dt.date.today()
    except Exception:
        return False


def _dysp_priority_rank(item: dict[str, Any]) -> int:
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


def _dysp_object_label(item: dict[str, Any]) -> str:
    object_id = str(
        item.get("obiekt_id")
        or item.get("object_id")
        or item.get("narzedzie_id")
        or item.get("maszyna_id")
        or ""
    ).strip()
    if object_id:
        return object_id
    return "—"


_DYSP_TOOL_STATUS_CACHE: dict[str, str] | None = None
_DYSP_MACHINE_STATUS_CACHE: dict[str, str] | None = None


def _normalize_object_id(value: Any) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    out = {raw, raw.lower()}
    if raw.isdigit():
        out.add(str(int(raw)))
        out.add(raw.zfill(3))
    return {item for item in out if item}


def _load_tool_status_cache() -> dict[str, str]:
    global _DYSP_TOOL_STATUS_CACHE
    if _DYSP_TOOL_STATUS_CACHE is not None:
        return _DYSP_TOOL_STATUS_CACHE

    cache: dict[str, str] = {}
    try:
        from gui_narzedzia import _external_load_tools_rows

        rows = _external_load_tools_rows()
    except Exception:
        rows = []

    for row in rows or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or row.get("nr") or row.get("numer") or "").strip()
        status = str(row.get("status") or "").strip()
        if not rid or not status:
            continue
        for key in _normalize_object_id(rid):
            cache[key] = status

    _DYSP_TOOL_STATUS_CACHE = cache
    return cache


def _load_machine_rows_with_status_label() -> tuple[
    list[dict], Callable[[Any], str] | None
]:
    from gui_maszyny import _machine_status_label, load_machines_rows

    return load_machines_rows(), _machine_status_label


def _load_machine_status_cache() -> dict[str, str]:
    global _DYSP_MACHINE_STATUS_CACHE
    if _DYSP_MACHINE_STATUS_CACHE is not None:
        return _DYSP_MACHINE_STATUS_CACHE

    cache: dict[str, str] = {}
    try:
        rows, machine_status_label = _load_machine_rows_with_status_label()
    except Exception:
        rows = []
        machine_status_label = None

    for row in rows or []:
        if not isinstance(row, dict):
            continue
        rid = str(
            row.get("id")
            or row.get("nr_ewid")
            or row.get("nr")
            or row.get("numer")
            or ""
        ).strip()
        raw_status = row.get("status")
        if machine_status_label is not None:
            status = machine_status_label(raw_status)
        else:
            status = str(raw_status or "").strip()
        if not rid or not status:
            continue
        for key in _normalize_object_id(rid):
            cache[key] = status

    _DYSP_MACHINE_STATUS_CACHE = cache
    return cache


def _resolve_related_status(item: dict[str, Any]) -> str:
    typ = str(item.get("typ_dyspozycji") or item.get("typ") or "").strip().lower()
    object_id = _dysp_object_label(item)
    variants = _normalize_object_id(object_id)
    if not variants:
        return "—"

    if typ == "narzedzie":
        cache = _load_tool_status_cache()
    elif typ == "maszyna":
        cache = _load_machine_status_cache()
    else:
        return "—"

    for key in variants:
        value = cache.get(key)
        if value:
            return value
    return "—"


def _dysp_title_label(item: dict[str, Any]) -> str:
    return str(item.get("tytul") or item.get("opis") or "Dyspozycja").strip()


def _dysp_status_label(item: dict[str, Any]) -> str:
    labels = {
        "nowa": "Nowa",
        "w_toku": "W toku",
        "wstrzymana": "Wstrzymana",
        "zamknieta": "Zamknięta",
    }
    status = _dysp_status(item) or "nowa"
    return labels.get(status, str(item.get("status") or "Nowa").strip() or "Nowa")


def _dysp_type_label(item: dict[str, Any]) -> str:
    value = str(item.get("typ_dyspozycji") or item.get("typ") or "").strip()
    if value == "zlecenie_wykonania":
        return "zlecenie wykonania"
    return value or "—"


def _dysp_assigned_label(item: dict[str, Any]) -> str:
    for_all = item.get("dla_wszystkich") is True
    assigned = str(item.get("przypisane_do") or "").strip()
    base = "wszyscy" if for_all else (assigned or "—")
    performer = str(item.get("wykonuje") or "").strip()
    if not performer:
        return base
    mismatch = bool(
        not for_all
        and assigned
        and assigned.lower() != performer.lower()
    )
    prefix = "⚠ " if mismatch else ""
    return f"{prefix}{base} → {performer}"


def _dysp_related_status_label(item: dict[str, Any]) -> str:
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    value = str(
        item.get("status_obiektu")
        or item.get("status_narzedzia")
        or item.get("status_maszyny")
        or meta.get("status_obiektu")
        or meta.get("status")
        or ""
    ).strip()
    if value:
        return value
    return _resolve_related_status(item)


_DYSP_WEEKDAY_LABELS_PL = ("Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nie")


def _format_dysp_deadline(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    try:
        parsed_date = _dt.date.fromisoformat(raw[:10])
    except Exception:
        return raw

    weekday = _DYSP_WEEKDAY_LABELS_PL[parsed_date.weekday()]
    date_text = parsed_date.strftime("%d-%m-%y")

    time_text = ""
    if len(raw) >= 16 and ("T" in raw[:16] or " " in raw[:16]):
        candidate = raw[11:16]
        if len(candidate) == 5 and candidate[2] == ":":
            time_text = candidate

    return f"{weekday} {date_text}" + (f" {time_text}" if time_text else "")


def _dysp_due_in_label(item: dict[str, Any]) -> str:
    if _dysp_is_closed(item):
        return "—"
    raw = str(item.get("termin") or item.get("deadline") or "").strip()
    if not raw:
        return "—"
    try:
        deadline = _dt.date.fromisoformat(raw[:10])
    except Exception:
        return "—"
    days = (deadline - _dt.date.today()).days
    if days == 0:
        return "dziś"
    if days == 1:
        return "jutro"
    return f"{days} dni"


def _dysp_priority_label(item: dict[str, Any]) -> str:
    return str(item.get("priorytet") or "normalny").strip() or "normalny"


def _resolve_creator() -> Callable[..., tk.Toplevel] | None:
    try:
        from gui_dyspozycje_creator import open_dyspozycje_creator  # type: ignore

        return open_dyspozycje_creator
    except Exception:
        return None


def _load_orders_rows() -> list[dict]:
    try:
        rows = load_dyspozycje()
    except Exception:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


class _AfterGuard:
    """Helper zabezpieczający wywołania `after` przed zniszczeniem widgetu."""

    def __init__(self, widget: tk.Misc) -> None:
        self._widget = widget
        self._tokens: list[str] = []

    def call_later(self, ms: int, callback: Callable[[], None]) -> str | None:
        try:
            token = self._widget.after(ms, callback)
        except Exception:  # pragma: no cover - brak w testach GUI
            logger.exception("[DYSP] after() failed")
            return None
        self._tokens.append(token)
        return token

    def cancel_all(self) -> None:
        for token in self._tokens:
            try:
                self._widget.after_cancel(token)
            except Exception:  # pragma: no cover - brak w testach GUI
                continue
        self._tokens.clear()


class ZleceniaView(ttk.Frame):
    """Widok listy Dyspozycji z automatycznym odświeżaniem."""

    _REFRESH_INTERVAL_MS = 5000

    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master, padding=8)
        self._login_user = self._resolve_login_user()
        self._login_role = self._resolve_login_role()
        self._can_view_all = self._login_role in {"brygadzista", "administrator", "admin"}
        self._after = _AfterGuard(self)
        self._refresh_error_shown = False
        self._order_rows: dict[str, dict] = {}
        self._order_ids: dict[str, str] = {}
        self._dysp_ui = _dysp_ui_config()
        self._open_order_creator = _resolve_creator()
        self._dysp_event_root: tk.Misc | None = None
        self._dysp_event_bind_id: str | None = None
        self._build_toolbar()
        self._build_tree()
        self._bind_orders_event()
        self.bind("<Destroy>", self._on_destroy, add=True)
        self._refresh()
        self._schedule_refresh()

    def _resolve_login_user(self) -> str:
        attrs = (
            "login_sesji",
            "current_user",
            "user_login",
            "active_login",
            "_wm_login",
            "login",
        )
        for attr in attrs:
            value = getattr(self.master, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        try:
            root = self.winfo_toplevel()
        except Exception:
            root = None
        if root is not None:
            for attr in attrs:
                value = getattr(root, attr, None)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        try:
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
    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 6))

        btn_add = ttk.Button(toolbar, text="Dodaj Dyspozycję")
        if self._open_order_creator:
            btn_add.configure(command=self._on_add)
        else:
            btn_add.state(["disabled"])
        btn_add.pack(side="left")

        btn_edit = ttk.Button(toolbar, text="Edytuj Dyspozycję")
        if self._open_order_creator:
            btn_edit.configure(command=self._on_edit)
        else:
            btn_edit.state(["disabled"])
        btn_edit.pack(side="left", padx=(8, 0))

        self.btn_start = ttk.Button(toolbar, text="Rozpocznij", command=self._on_start)
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

        filters = ttk.Frame(toolbar)
        filters.pack(side="right")

        ttk.Label(filters, text="Widok:").pack(side="left", padx=(0, 4))
        scope_values = ["Moje + Dla wszystkich", "Moje", "Dla wszystkich"]
        if self._can_view_all:
            scope_values.append("Wszystkie")
        default_scope = "Wszystkie" if self._can_view_all else "Moje + Dla wszystkich"
        self._scope_filter_var = tk.StringVar(value=default_scope)
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
        columns = (
            "obiekt",
            "dyspozycja",
            "status_dyspozycji",
            "typ",
            "przypisane",
            "status_obiektu",
            "termin",
            "za_ile",
            "priorytet",
        )
        self.tree = ttk.Treeview(self, columns=columns, show="headings")

        headings = {
            "obiekt": "Obiekt",
            "dyspozycja": "Dyspozycja",
            "status_dyspozycji": "Status dyspozycji",
            "typ": "Typ",
            "przypisane": "Przypisane",
            "status_obiektu": "Status narzędzia/maszyny",
            "termin": "Termin",
            "za_ile": "Za ile",
            "priorytet": "Priorytet",
        }
        widths = {
            "obiekt": 90,
            "dyspozycja": 420,
            "status_dyspozycji": 150,
            "typ": 130,
            "przypisane": 190,
            "status_obiektu": 210,
            "termin": 110,
            "za_ile": 85,
            "priorytet": 100,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=widths[column],
                anchor="w" if column == "dyspozycja" else "center",
                stretch=column == "dyspozycja",
            )
        self._apply_dysp_ui_config()
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_double_click, add=True)
        self.tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self._update_status_actions(),
            add=True,
        )
        self._update_status_actions()
        self._ensure_blink_started()

    def _apply_dysp_ui_config(self) -> None:
        self._dysp_ui = _dysp_ui_config()
        ui = self._dysp_ui
        try:
            style = ttk.Style(self.tree)
            style.configure(
                "Dyspozycje.Treeview", font=("Segoe UI", 11), rowheight=30
            )
            style.configure(
                "Dyspozycje.Treeview.Heading", font=("Segoe UI", 11, "bold")
            )
            self.tree.configure(style="Dyspozycje.Treeview")
        except Exception:
            pass

        self.tree.tag_configure("dysp_closed", foreground=ui["closed_foreground"])
        self.tree.tag_configure(
            "dysp_in_progress", foreground=ui["in_progress_foreground"]
        )
        self.tree.tag_configure("dysp_paused", foreground=ui["paused_foreground"])
        self.tree.tag_configure("dysp_new", foreground=ui["new_foreground"])
        self.tree.tag_configure(
            "dysp_new_blink", foreground=ui["new_blink_foreground"]
        )
        self.tree.tag_configure("dysp_overdue", foreground=ui["overdue_foreground"])
        self.tree.tag_configure(
            "dysp_overdue_blink",
            foreground=ui["overdue_blink_foreground"],
            background=ui["overdue_blink_background"],
        )

    def _ensure_blink_started(self) -> None:
        if not self._dysp_ui.get("blink_enabled", True):
            return
        if getattr(self.tree, "_wm_dysp_blink_started", False):
            return
        self.tree._wm_dysp_blink_started = True
        self._blink_state = {"new": False, "overdue": False}
        self._blink_dysp_new()
        self._blink_dysp_overdue()

    def _blink_dysp_new(self) -> None:
        self._blink_state["new"] = not self._blink_state["new"]
        for iid in self.tree.get_children(""):
            tags = set(self.tree.item(iid, "tags") or ())
            if "dysp_new" in tags or "dysp_new_blink" in tags:
                tags.discard("dysp_new")
                tags.discard("dysp_new_blink")
                tags.add("dysp_new_blink" if self._blink_state["new"] else "dysp_new")
                self.tree.item(iid, tags=tuple(tags))
        if not self._dysp_ui.get("blink_enabled", True):
            self.tree._wm_dysp_blink_started = False
            return
        try:
            self.tree.after(
                int(self._dysp_ui.get("new_blink_ms", 2000)),
                self._blink_dysp_new,
            )
        except Exception:
            pass

    def _blink_dysp_overdue(self) -> None:
        self._blink_state["overdue"] = not self._blink_state["overdue"]
        for iid in self.tree.get_children(""):
            tags = set(self.tree.item(iid, "tags") or ())
            if "dysp_overdue" in tags or "dysp_overdue_blink" in tags:
                tags.discard("dysp_overdue")
                tags.discard("dysp_overdue_blink")
                if self._blink_state["overdue"]:
                    tags.add("dysp_overdue_blink")
                else:
                    tags.add("dysp_overdue")
                self.tree.item(iid, tags=tuple(tags))
        if not self._dysp_ui.get("blink_enabled", True):
            self.tree._wm_dysp_blink_started = False
            return
        try:
            self.tree.after(
                int(self._dysp_ui.get("overdue_blink_ms", 500)),
                self._blink_dysp_overdue,
            )
        except Exception:
            pass

    # endregion ---------------------------------------------------------

    def _view_is_alive(self) -> bool:
        try:
            return bool(self.winfo_exists() and self.tree.winfo_exists())
        except Exception:
            return False

    def _on_dyspozycje_updated(self, _event: Any = None) -> None:
        if not self._view_is_alive():
            return
        self._reload_orders()

    def _bind_orders_event(self) -> None:
        # kompatybilność wsteczna – lokalny bind znika razem z widokiem
        self.bind("<<OrdersUpdated>>", self._on_dyspozycje_updated, add=True)
        try:
            root = self.winfo_toplevel()
        except Exception:
            root = None
        if not root:
            return
        # Event jest emitowany na root, więc zapamiętujemy identyfikator binda
        # i odpinamy dokładnie ten callback przy niszczeniu ZleceniaView.
        try:
            bind_id = root.bind(
                "<<DyspozycjeUpdated>>",
                self._on_dyspozycje_updated,
                add="+",
            )
        except Exception:
            bind_id = None
        self._dysp_event_root = root
        self._dysp_event_bind_id = str(bind_id) if bind_id else None

    def _on_filters_changed(self, _event: Any = None) -> None:
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
            if not isinstance(order, dict):
                continue
            order_id = (
                order.get("id")
                or order.get("nr")
                or order.get("kod")
                or order.get("numer")
            )
            order_key = str(order_id) if order_id is not None else ""
            iid = order_key if order_key else f"row-{idx}"
            tags: list[str] = []
            if _dysp_is_closed(order):
                tags.append("dysp_closed")
            elif _dysp_is_overdue(order):
                tags.append("dysp_overdue")
            elif _dysp_is_new(order):
                tags.append("dysp_new")
            elif _dysp_is_in_progress(order):
                tags.append("dysp_in_progress")
            elif _dysp_is_paused(order):
                tags.append("dysp_paused")
            try:
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        _dysp_object_label(order),
                        _dysp_title_label(order),
                        _dysp_status_label(order),
                        _dysp_type_label(order),
                        _dysp_assigned_label(order),
                        _dysp_related_status_label(order),
                        _format_dysp_deadline(order.get("termin") or order.get("deadline")),
                        _dysp_due_in_label(order),
                        _dysp_priority_label(order),
                    ),
                    iid=iid,
                    tags=tuple(tags),
                )
            except Exception as exc:  # pragma: no cover - wymagane GUI
                logger.exception("[DYSP] Błąd dodawania Dyspozycji do listy: %s", exc)
                continue
            self._order_rows[iid] = order
            if order_key:
                self._order_ids[iid] = order_key
        self._update_status_actions()

    def _reload_orders(self) -> None:
        if not self._view_is_alive():
            return
        global _DYSP_TOOL_STATUS_CACHE, _DYSP_MACHINE_STATUS_CACHE
        _DYSP_TOOL_STATUS_CACHE = None
        _DYSP_MACHINE_STATUS_CACHE = None
        self._apply_dysp_ui_config()
        self._ensure_blink_started()
        try:
            rows = load_dyspozycje()
        except Exception as exc:  # pragma: no cover - wymagane GUI
            logger.exception("[DYSP] Błąd wczytywania listy Dyspozycji: %s", exc)
            rows = []
        cleaned = [row for row in rows if isinstance(row, dict)]
        self._fill_orders_table(cleaned)

    # region Actions ----------------------------------------------------
    def _on_add(self) -> None:
        if not self._open_order_creator:
            return
        try:
            self._open_order_creator(
                self,
                autor=self._login_user,
                context={"modul_zrodlowy": "dyspozycje"},
            )
        except Exception as exc:  # pragma: no cover - wymagane GUI
            logger.exception("[DYSP] Błąd otwierania kreatora: %s", exc)
            error_box(
                self,
                "Dyspozycje",
                f"Nie udało się otworzyć kreatora Dyspozycji.\
{exc}",
            )

    def _on_edit(self) -> None:
        if not self._open_order_creator:
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "Dyspozycje",
                "Najpierw wybierz Dyspozycję do edycji.",
                parent=self,
            )
            return
        iid = selection[0]
        mapped = dict(self._order_rows.get(iid, {}) or {})
        if not mapped:
            return
        if (
            str(mapped.get("typ_dyspozycji") or "").strip().lower() == "zlecenie_wykonania"
            and _dysp_status(mapped) != "nowa"
        ):
            messagebox.showinfo(
                "Dyspozycje",
                "Dyspozycji wykonania nie można edytować po rozpoczęciu, ponieważ ma już powiązane rezerwacje Magazynu.",
                parent=self,
            )
            return
        mapped["edit_mode"] = True
        try:
            self._open_order_creator(
                self,
                autor=self._login_user or str(mapped.get("autor") or ""),
                context=mapped,
            )
        except Exception as exc:  # pragma: no cover - wymagane GUI
            logger.exception("[DYSP] Błąd otwierania edycji Dyspozycji: %s", exc)
            error_box(
                self,
                "Dyspozycje",
                f"Nie udało się otworzyć edycji Dyspozycji.\
{exc}",
            )

    def _selected_row(self) -> dict[str, Any] | None:
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

    def _change_status(self, target: str) -> bool:
        mapped = self._selected_row()
        if not mapped:
            messagebox.showinfo(
                "Dyspozycje",
                "Najpierw wybierz Dyspozycję.",
                parent=self,
            )
            return False
        dysp_id = str(mapped.get("id") or "").strip()
        if not dysp_id:
            return False
        who = self._login_user or str(mapped.get("autor") or "").strip()
        changed = set_dyspozycja_status(dysp_id, target, changed_by=who)
        if not changed:
            messagebox.showerror(
                "Dyspozycje",
                "Ta zmiana statusu nie jest dozwolona.",
                parent=self,
            )
            return False
        try:
            sync_machine_review_from_dyspozycja(changed, actor=who)
        except Exception as exc:
            logger.exception(
                "[DYSP][MASZYNY] Nie udało się zsynchronizować statusu przeglądu: %s",
                exc,
            )
        try:
            self.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")
        except Exception:
            self._reload_orders()
        return True

    def _calculate_execution_requirements(self, mapped: dict[str, Any], qty: float, *, stock_snapshot=None) -> dict[str, Any]:
        meta = dict(mapped.get("meta") or {}) if isinstance(mapped.get("meta"), dict) else {}
        level = str(meta.get("poziom_wykonania") or "").strip().lower()
        from produkty_store import ProductCatalog
        from polprodukty_store import SemiProductCatalog
        from planowanie_zapotrzebowanie import RequirementCalculator, RequirementError
        products = ProductCatalog()
        calc = RequirementCalculator(products, SemiProductCatalog(products.cfg))
        if level in {"zlecenie", "produkt"}:
            code = str(meta.get("product_code") or "").strip()
            if not code:
                raise RequirementError("Brak produktu w Dyspozycji wykonania.")
            return calc.calculate_with_stock(code, qty, stock_snapshot=stock_snapshot)
        if level == "polprodukt":
            code = str(meta.get("polprodukt_code") or "").strip()
            if not code:
                raise RequirementError("Brak półproduktu w Dyspozycji wykonania.")
            return calc.calculate_semi_with_stock(code, qty, ignore_root_stock=True, stock_snapshot=stock_snapshot)
        raise RequirementError("Nieznany poziom wykonania Dyspozycji.")

    def _on_start(self) -> None:
        mapped = self._selected_row()
        if not mapped:
            messagebox.showinfo(
                "Dyspozycje",
                "Najpierw wybierz Dyspozycję.",
                parent=self,
            )
            return
        who = str(self._login_user or mapped.get("autor") or "").strip()
        assigned = str(mapped.get("przypisane_do") or "").strip()
        for_all = mapped.get("dla_wszystkich") is True
        if (
            not for_all
            and assigned
            and who
            and assigned.lower() != who.lower()
        ):
            ok = messagebox.askyesno(
                "Rozpocznij cudzą Dyspozycję",
                f"Dyspozycja jest przypisana do: {assigned}.\
"
                f"Jesteś zalogowany jako: {who}.\
\
"
                "Czy na pewno chcesz ją rozpocząć?",
                parent=self,
            )
            if not ok:
                return
        dysp_id = str(mapped.get("id") or "").strip()
        is_execution = str(mapped.get("typ_dyspozycji") or "").strip().lower() == "zlecenie_wykonania"
        if is_execution:
            meta = dict(mapped.get("meta") or {}) if isinstance(mapped.get("meta"), dict) else {}
            try:
                planned = float(str(meta.get("ilosc_do_wykonania") or 0).replace(",", "."))
                requirements = self._calculate_execution_requirements(mapped, planned)
                reservations = reserve_execution_requirements(
                    dysp_id,
                    list(requirements.get("rows") or []),
                    user=who,
                    context=f"Rozpoczęcie Dyspozycji {dysp_id}",
                )
            except Exception as exc:
                messagebox.showerror(
                    "Rezerwacja Magazynu",
                    f"Nie udało się przygotować Dyspozycji wykonania:\
{exc}",
                    parent=self,
                )
                return
            meta["zapotrzebowanie_start"] = list(requirements.get("rows") or [])
            meta["magazyn_rezerwacje"] = reservations
            updated = update_dyspozycja(dysp_id, {"meta": meta})
            if not updated:
                try:
                    release_execution_reservations(dysp_id, user=who, context="Błąd zapisu Dyspozycji")
                except Exception:
                    pass
                messagebox.showerror("Dyspozycje", "Nie udało się zapisać rezerwacji w Dyspozycji.", parent=self)
                return
        if not self._change_status("w_toku") and is_execution:
            try:
                release_execution_reservations(dysp_id, user=who, context="Nieudane rozpoczęcie Dyspozycji")
            except Exception:
                pass

    def _on_pause(self) -> None:
        self._change_status("wstrzymana")

    def _on_resume(self) -> None:
        self._change_status("w_toku")

    def _on_close(self) -> None:
        mapped = self._selected_row()
        if not mapped:
            messagebox.showinfo(
                "Dyspozycje",
                "Najpierw wybierz Dyspozycję do zamknięcia.",
                parent=self,
            )
            return
        dysp_id = str(mapped.get("id") or "").strip()
        if not dysp_id:
            return
        if _dysp_status(mapped) not in {"w_toku", "wstrzymana"}:
            messagebox.showinfo(
                "Dyspozycje",
                "Zamknąć można Dyspozycję W toku albo Wstrzymaną.",
                parent=self,
            )
            return
        note = simpledialog.askstring(
            "Zamknij Dyspozycję",
            "Uwagi przy zamknięciu (opcjonalnie):",
            parent=self,
        )
        if note is None:
            return
        who = self._login_user or str(mapped.get("autor") or "").strip()
        typ = str(mapped.get("typ_dyspozycji") or "").strip().lower()
        if typ == "zlecenie_wykonania":
            meta = dict(mapped.get("meta") or {}) if isinstance(mapped.get("meta"), dict) else {}
            try:
                planned = float(str(meta.get("ilosc_do_wykonania") or 0).replace(",", "."))
            except (TypeError, ValueError):
                planned = 0.0
            actual = simpledialog.askfloat(
                "Rozlicz wykonanie",
                "Ile faktycznie wykonano?",
                initialvalue=planned if planned > 0 else 1,
                minvalue=0.0,
                parent=self,
            )
            if actual is None:
                return
            meta["ilosc_wykonana"] = actual
            meta["brak_wykonania"] = max(0.0, planned - actual)
            level = str(meta.get("poziom_wykonania") or "").strip().lower()

            try:
                if actual <= 0:
                    release_execution_reservations(
                        dysp_id,
                        user=who,
                        context=f"Zamknięcie bez wykonania {dysp_id}",
                    )
                    requirements_actual = {"rows": [], "warnings": []}
                    consumption = []
                else:
                    own_snapshot = stock_snapshot_for_operation(dysp_id)
                    requirements_actual = self._calculate_execution_requirements(
                        mapped,
                        actual,
                        stock_snapshot=own_snapshot,
                    )
                    raw_shortages = []
                    for row in requirements_actual.get("rows") or []:
                        if str(row.get("typ") or "").strip().lower() != "surowiec":
                            continue
                        try:
                            missing = float(row.get("brak") or 0)
                        except (TypeError, ValueError):
                            missing = 0.0
                        if missing > 1e-9:
                            raw_shortages.append(
                                f"{row.get('kod','')}: {missing:g} {row.get('jednostka','')}"
                            )
                    critical_warnings = [
                        str(x) for x in (requirements_actual.get("warnings") or [])
                        if str(x).startswith("Brak definicji półproduktu")
                        or "nie ma surowca ani własnego składu" in str(x)
                    ]
                    if raw_shortages or critical_warnings:
                        details = []
                        if raw_shortages:
                            details.append("Braki surowców:\
" + "\
".join(raw_shortages[:15]))
                        if critical_warnings:
                            details.append("Braki definicji:\
" + "\
".join(critical_warnings[:10]))
                        messagebox.showerror(
                            "Rozliczenie produkcji",
                            "Nie można zamknąć wykonania, bo Magazyn/Skład nie pozwala rozliczyć podanej ilości.\
\
"
                            + "\
\
".join(details),
                            parent=self,
                        )
                        return
                    consumption = reconcile_and_consume_execution(
                        dysp_id,
                        list(requirements_actual.get("rows") or []),
                        user=who,
                        context=f"Dyspozycja {dysp_id}",
                    )
            except WarehouseIntegrationError as exc:
                messagebox.showerror(
                    "Rozliczenie produkcji",
                    f"Nie udało się rozliczyć Magazynu:\
{exc}\
\
Dyspozycja nie została zamknięta.",
                    parent=self,
                )
                return
            except Exception as exc:
                messagebox.showerror(
                    "Rozliczenie produkcji",
                    f"Nie udało się przeliczyć wykonanej ilości:\
{exc}\
\
Dyspozycja nie została zamknięta.",
                    parent=self,
                )
                return

            meta["zapotrzebowanie_wykonane"] = list(requirements_actual.get("rows") or [])
            meta["magazyn_zuzycie"] = consumption
            if level == "polprodukt":
                surplus = max(0.0, actual - planned)
                meta["naddatek"] = surplus
                if surplus > 0:
                    code = str(meta.get("polprodukt_code") or "").strip()
                    name = str(meta.get("polprodukt_name") or code)
                    try:
                        result = add_semiproduct_surplus(
                            code,
                            surplus,
                            name=name,
                            user=who,
                            context=f"Dyspozycja {dysp_id}",
                            operation_id=dysp_id,
                        )
                    except WarehouseIntegrationError as exc:
                        messagebox.showerror(
                            "Rozliczenie produkcji",
                            f"Zużycie zostało rozliczone, ale nie udało się zaksięgować naddatku:\
{exc}\
\
"
                            "Dyspozycja nie została zamknięta. Ponowna próba nie zużyje materiału drugi raz.",
                            parent=self,
                        )
                        return
                    meta["naddatek_zaksiegowany"] = bool(result.get("dodano") or result.get("already_settled"))
            updated = update_dyspozycja(dysp_id, {"meta": meta})
            if updated:
                mapped = updated

        changed = set_dyspozycja_status(
            dysp_id,
            "zamknieta",
            changed_by=who,
            uwagi=note or "",
        )
        if not changed:
            messagebox.showerror(
                "Dyspozycje",
                "Nie udało się zamknąć Dyspozycji.",
                parent=self,
            )
            return
        try:
            sync_machine_review_from_dyspozycja(
                changed,
                actor=who,
                result_note=note or "",
            )
        except Exception as exc:
            logger.exception(
                "[DYSP][MASZYNY] Nie udało się zamknąć wpisu przeglądu maszyny: %s",
                exc,
            )
        try:
            self.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")
        except Exception:
            pass
        messagebox.showinfo(
            "Dyspozycje",
            f"Dyspozycja została zamknięta przez: {who or '-'}",
            parent=self,
        )

    def _on_delete(self) -> None:
        mapped = self._selected_row()
        if not mapped:
            messagebox.showinfo(
                "Dyspozycje",
                "Najpierw wybierz Dyspozycję do usunięcia.",
                parent=self,
            )
            return
        dysp_id = str(mapped.get("id") or "").strip()
        if not dysp_id:
            return
        if str(mapped.get("typ_dyspozycji") or "").strip().lower() == "zlecenie_wykonania":
            settlement = get_operation_settlement(dysp_id)
            settlement_status = str(settlement.get("status") or "")
            if settlement_status in {"consumed", "done"} and not _dysp_is_closed(mapped):
                messagebox.showerror(
                    "Dyspozycje",
                    "Ta Dyspozycja ma już rozliczone zużycie Magazynu. Najpierw dokończ jej zamknięcie.",
                    parent=self,
                )
                return
        ok = messagebox.askyesno(
            "Usuń Dyspozycję",
            f"Czy na pewno usunąć Dyspozycję:\
{dysp_id}?",
            parent=self,
        )
        if not ok:
            return
        if str(mapped.get("typ_dyspozycji") or "").strip().lower() == "zlecenie_wykonania":
            try:
                release_execution_reservations(
                    dysp_id,
                    user=self._login_user or str(mapped.get("autor") or ""),
                    context=f"Usunięcie Dyspozycji {dysp_id}",
                )
            except WarehouseIntegrationError as exc:
                messagebox.showerror(
                    "Dyspozycje",
                    f"Nie można usunąć Dyspozycji, bo nie udało się zwolnić jej rezerwacji:\
{exc}",
                    parent=self,
                )
                return
        deleted = delete_dyspozycja(dysp_id)
        if not deleted:
            messagebox.showerror(
                "Dyspozycje",
                "Nie udało się usunąć Dyspozycji.",
                parent=self,
            )
            return
        try:
            self.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")
        except Exception:
            pass
        messagebox.showinfo(
            "Dyspozycje",
            "Dyspozycja została usunięta.",
            parent=self,
        )

    def _on_double_click(self, event: Any) -> None:
        del event
        selection = self.tree.selection()
        if not selection:
            return
        iid = selection[0]
        mapped = self._order_rows.get(iid, {})
        if not mapped:
            return
        self._on_edit()

    # endregion ---------------------------------------------------------

    # region Refresh ----------------------------------------------------
    def _refresh(self) -> None:
        self._apply_dysp_ui_config()
        self._ensure_blink_started()
        try:
            try:
                ensure_due_machine_cycle_dyspozycje(today=_dt.date.today())
            except Exception as exc:
                logger.exception(
                    "[DYSP][MASZYNY] Nie udało się zsynchronizować cyklicznych przeglądów: %s",
                    exc,
                )
            rows = _load_orders_rows()
            try:
                from gui_panel import wm_set_module_source

                wm_set_module_source(
                    self.winfo_toplevel(),
                    "Dyspozycje / Zlecenia",
                    str(get_dyspozycje_path()),
                )
            except Exception:
                pass
        except Exception as exc:  # pragma: no cover - wymagane GUI
            logger.exception("[DYSP] Błąd odświeżania listy Dyspozycji: %s", exc)
            if not self._refresh_error_shown:
                error_box(
                    self,
                    "Dyspozycje",
                    f"Nie udało się odświeżyć listy Dyspozycji.\
{exc}",
                )
            self._refresh_error_shown = True
            return

        self._refresh_error_shown = False
        self._fill_orders_table(rows)

    def _schedule_refresh(self) -> None:
        if not self.winfo_exists():  # pragma: no cover - brak w testach GUI
            return
        self._after.call_later(self._REFRESH_INTERVAL_MS, self._on_refresh_timer)

    def _on_refresh_timer(self) -> None:
        if not self.winfo_exists():  # pragma: no cover - brak w testach GUI
            self._after.cancel_all()
            return
        self._refresh()
        self._schedule_refresh()

    # endregion ---------------------------------------------------------

    def _on_destroy(self, event: Any) -> None:
        if getattr(event, "widget", None) is not self:
            return
        self._after.cancel_all()
        root = self._dysp_event_root
        bind_id = self._dysp_event_bind_id
        self._dysp_event_root = None
        self._dysp_event_bind_id = None
        if root is not None and bind_id:
            try:
                root.unbind("<<DyspozycjeUpdated>>", bind_id)
            except Exception:
                pass


def panel_zlecenia(parent: tk.Widget) -> ttk.Frame:
    view = ZleceniaView(parent)
    view.pack(fill="both", expand=True)
    return view
