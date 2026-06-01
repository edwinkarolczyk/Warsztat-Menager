# version: 1.0
"""Panel Dyspozycji (dawniej: Zlecenia) – lista oparta o wspólny store Dyspozycji."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from config_manager import ConfigManager
from dyspozycje_store import (
    close_dyspozycja,
    delete_dyspozycja,
    get_dyspozycje_path,
    load_dyspozycje,
)

from ui_dialogs_safe import error_box


logger = logging.getLogger(__name__)


def _dysp_ui_config() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "blink_enabled": True,
        "closed_foreground": "#9ca3af",
        "new_foreground": "#facc15",
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


def _dysp_is_overdue(item: dict[str, Any]) -> bool:
    if _dysp_is_closed(item):
        return False
    raw = str(item.get("termin") or item.get("deadline") or "").strip()
    if not raw:
        return False
    try:
        import datetime as _dt

        deadline = _dt.date.fromisoformat(raw[:10])
        return deadline < _dt.date.today()
    except Exception:
        return False


def _dysp_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str, str]:
    closed = 1 if _dysp_is_closed(item) else 0
    overdue = 0 if _dysp_is_overdue(item) else 1
    new = 0 if _dysp_is_new(item) else 1
    termin = str(item.get("termin") or "")
    created = str(item.get("utworzono") or "")
    return (closed, overdue, new, termin, created)


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
        self._after = _AfterGuard(self)
        self._refresh_error_shown = False
        self._order_rows: dict[str, dict] = {}
        self._order_ids: dict[str, str] = {}
        self._dysp_ui = _dysp_ui_config()
        self._open_order_creator = _resolve_creator()
        self._build_toolbar()
        self._build_tree()
        self._bind_orders_event()
        self.bind("<Destroy>", self._on_destroy, add=True)
        self._refresh()
        self._schedule_refresh()

    def _resolve_login_user(self) -> str:
        candidates = [
            getattr(self.master, "login_sesji", None),
            getattr(self.master, "current_user", None),
            getattr(self.master, "user_login", None),
        ]
        for value in candidates:
            if isinstance(value, str) and value.strip():
                return value.strip()
        try:
            root = self.winfo_toplevel()
        except Exception:
            root = None
        if root is not None:
            for attr in ("login_sesji", "current_user", "user_login"):
                value = getattr(root, attr, None)
                if isinstance(value, str) and value.strip():
                    return value.strip()
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

        ttk.Button(toolbar, text="Zamknij Dyspozycję", command=self._on_close).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(toolbar, text="Usuń Dyspozycję", command=self._on_delete).pack(
            side="left", padx=(8, 0)
        )

    def _build_tree(self) -> None:
        columns = ("typ", "status", "tytul", "przypisane", "termin")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for column in columns:
            self.tree.heading(column, text=column.capitalize())
            self.tree.column(column, anchor="center")
        self._apply_dysp_ui_config()
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_double_click, add=True)
        self._ensure_blink_started()

    def _apply_dysp_ui_config(self) -> None:
        self._dysp_ui = _dysp_ui_config()
        ui = self._dysp_ui
        self.tree.tag_configure("dysp_closed", foreground=ui["closed_foreground"])
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

    def _bind_orders_event(self) -> None:
        # kompatybilność wsteczna – jeśli gdzieś jeszcze leci OrdersUpdated
        self.bind("<<OrdersUpdated>>", lambda _event: self._reload_orders(), add=True)
        try:
            root = self.winfo_toplevel()
        except Exception:
            root = None
        if not root:
            return
        # nowy event dla Dyspozycji
        root.bind(
            "<<DyspozycjeUpdated>>",
            lambda _event: self._reload_orders(),
            add=True,
        )

    def _fill_orders_table(self, rows: list[dict]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._order_rows = {}
        self._order_ids = {}
        for idx, order in enumerate(sorted(rows, key=_dysp_sort_key)):
            if not isinstance(order, dict):
                continue
            rodzaj = str(order.get("typ_dyspozycji") or "")
            if rodzaj == "zlecenie_wykonania":
                rodzaj = "zlecenie wykonania"
            status_txt = str(order.get("status") or "")
            tytul = str(order.get("tytul") or "")
            przypisane = (
                "wszyscy"
                if order.get("dla_wszystkich") is True
                else str(order.get("przypisane_do") or "")
            )
            termin = str(order.get("termin") or "")
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
            try:
                self.tree.insert(
                    "",
                    "end",
                    values=(rodzaj, status_txt, tytul, przypisane, termin),
                    iid=iid,
                    tags=tuple(tags),
                )
            except Exception as exc:  # pragma: no cover - wymagane GUI
                logger.exception("[DYSP] Błąd dodawania Dyspozycji do listy: %s", exc)
                continue
            self._order_rows[iid] = order
            if order_key:
                self._order_ids[iid] = order_key

    def _reload_orders(self) -> None:
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
                autor="uzytkownik",
                context={"modul_zrodlowy": "dyspozycje"},
            )
        except Exception as exc:  # pragma: no cover - wymagane GUI
            logger.exception("[DYSP] Błąd otwierania kreatora: %s", exc)
            error_box(
                self,
                "Dyspozycje",
                f"Nie udało się otworzyć kreatora Dyspozycji.\n{exc}",
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
        mapped["edit_mode"] = True
        try:
            self._open_order_creator(
                self,
                autor=str(mapped.get("autor") or ""),
                context=mapped,
            )
        except Exception as exc:  # pragma: no cover - wymagane GUI
            logger.exception("[DYSP] Błąd otwierania edycji Dyspozycji: %s", exc)
            error_box(
                self,
                "Dyspozycje",
                f"Nie udało się otworzyć edycji Dyspozycji.\n{exc}",
            )

    def _selected_row(self) -> dict[str, Any] | None:
        selection = self.tree.selection()
        if not selection:
            return None
        iid = selection[0]
        mapped = dict(self._order_rows.get(iid, {}) or {})
        return mapped or None

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
        if str(mapped.get("status") or "").strip().lower() == "zamknieta":
            messagebox.showinfo(
                "Dyspozycje",
                "Ta Dyspozycja jest już zamknięta.",
                parent=self,
            )
            return
        note = simpledialog.askstring(
            "Zamknij Dyspozycję",
            "Uwagi przy zamknięciu (opcjonalnie):",
            parent=self,
        )
        who = self._login_user or str(mapped.get("autor") or "").strip()
        changed = close_dyspozycja(
            dysp_id,
            uwagi=note or "",
            closed_by=who,
        )
        if not changed:
            messagebox.showerror(
                "Dyspozycje",
                "Nie udało się zamknąć Dyspozycji.",
                parent=self,
            )
            return
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
        ok = messagebox.askyesno(
            "Usuń Dyspozycję",
            f"Czy na pewno usunąć Dyspozycję:\n{dysp_id}?",
            parent=self,
        )
        if not ok:
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
                    f"Nie udało się odświeżyć listy Dyspozycji.\n{exc}",
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

    def _on_destroy(self, _event: Any) -> None:
        self._after.cancel_all()


def panel_zlecenia(parent: tk.Widget) -> ttk.Frame:
    view = ZleceniaView(parent)
    view.pack(fill="both", expand=True)
    return view
