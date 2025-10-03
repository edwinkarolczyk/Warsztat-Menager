"""Panel zleceń – prosta lista z obsługą kreatora i szczegółów."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from config_manager import resolve_rel

try:
    from config_manager import get_config  # type: ignore
except ImportError:  # pragma: no cover - fallback dla starszych wersji
    def get_config():
        try:
            from config_manager import ConfigManager  # type: ignore

            return ConfigManager().load()
        except Exception:
            return {}

from utils_orders import ensure_orders_sample_if_empty, load_orders_rows_with_fallback
from domain.orders import load_order, load_orders
from ui_dialogs_safe import error_box

logger = logging.getLogger(__name__)

try:  # pragma: no cover - środowiska testowe nie wymagają motywu
    from gui_zlecenia_creator import open_order_creator  # type: ignore
except Exception:  # pragma: no cover - fallback gdy kreator niedostępny
    open_order_creator = None  # type: ignore

try:  # pragma: no cover - opcjonalny moduł szczegółów
    from gui_zlecenia_detail import open_order_detail  # type: ignore
except Exception:  # pragma: no cover - fallback gdy moduł nie istnieje
    open_order_detail = None  # type: ignore


def _open_orders_panel():
    """
    Otwiera panel 'Zlecenia' ZAWSZE.
    Gdy plik pusty/niepoprawny – pokazuje pustą listę i informację,
    bez crashy i bez file-dialogów.
    """

    try:
        from start import CONFIG_MANAGER  # type: ignore

        cfg = CONFIG_MANAGER.load() if hasattr(CONFIG_MANAGER, "load") else {}
    except Exception:
        cfg = {}

    if not cfg:
        try:
            cfg = get_config()
        except Exception:
            logger.exception("[Zlecenia] Nie udało się uzyskać konfiguracji przez get_config().")
            cfg = {}

    rows, primary_path = load_orders_rows_with_fallback(cfg, resolve_rel)
    had_rows = bool(rows)
    rows = ensure_orders_sample_if_empty(rows, primary_path)

    win = tk.Toplevel()
    win.title("Zlecenia")
    win.geometry("960x560")

    info = tk.StringVar()
    if had_rows:
        info.set(f"Załadowano {len(rows)} pozycji.")
    else:
        info.set(
            "Brak zleceń w konfiguracji – dodano przykładowe wpisy do zlecenia/zlecenia.json."
        )
    ttk.Label(win, textvariable=info).pack(fill="x", padx=8, pady=8)

    tv = ttk.Treeview(
        win,
        columns=("id", "klient", "status", "data"),
        show="headings",
        height=20,
    )
    for column_id, width in (
        ("id", 160),
        ("klient", 360),
        ("status", 160),
        ("data", 200),
    ):
        tv.heading(column_id, text=column_id.upper())
        tv.column(column_id, width=width, anchor="w")
    for row in rows:
        tv.insert(
            "",
            "end",
            values=(
                row.get("id", ""),
                row.get("klient", ""),
                row.get("status", ""),
                row.get("data", ""),
            ),
        )
    tv.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    ttk.Button(win, text="Zamknij", command=win.destroy).pack(side="right", padx=8, pady=8)
    logger.info("[Zlecenia] Panel otwarty; rekordów: %d; plik=%s", len(rows), primary_path)
    return win


def _load_orders_rows() -> list[dict]:
    try:
        cfg = get_config()
    except Exception:
        cfg = {}
    rows, primary_path = load_orders_rows_with_fallback(cfg, resolve_rel)
    rows = ensure_orders_sample_if_empty(rows, primary_path)
    return rows


class _AfterGuard:
    """Helper zabezpieczający wywołania `after` przed zniszczeniem widgetu."""

    def __init__(self, widget: tk.Misc) -> None:
        self._widget = widget
        self._tokens: list[str] = []

    def call_later(self, ms: int, callback: Callable[[], None]) -> str | None:
        try:
            token = self._widget.after(ms, callback)
        except Exception:  # pragma: no cover - brak w testach GUI
            logger.exception("[ORD] after() failed")
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
    """Widok listy zleceń z automatycznym odświeżaniem."""

    _REFRESH_INTERVAL_MS = 5000

    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master, padding=8)
        self._after = _AfterGuard(self)
        self._refresh_error_shown = False
        self._order_rows: dict[str, dict] = {}
        self._order_ids: dict[str, str] = {}
        self._build_toolbar()
        self._build_tree()
        self.bind("<Destroy>", self._on_destroy, add=True)
        self._refresh()
        self._schedule_refresh()

    # region UI helpers -------------------------------------------------
    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 6))

        btn_add = ttk.Button(toolbar, text="Dodaj zlecenie (Kreator)")
        if open_order_creator:
            btn_add.configure(command=self._on_add)
        else:
            btn_add.state(["disabled"])
        btn_add.pack(side="left")

    def _build_tree(self) -> None:
        columns = ("rodzaj", "status", "opis")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for column in columns:
            self.tree.heading(column, text=column.capitalize())
            self.tree.column(column, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_double_click, add=True)

    # endregion ---------------------------------------------------------

    def _fill_orders_table(self, rows: list[dict]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._order_rows = {}
        self._order_ids = {}
        for idx, order in enumerate(rows):
            if not isinstance(order, dict):
                continue
            rodzaj = str(order.get("rodzaj") or order.get("typ") or "")
            status_txt = str(order.get("status") or "")
            opis = str(order.get("opis") or order.get("nazwa") or order.get("klient") or "")
            order_id = (
                order.get("id")
                or order.get("nr")
                or order.get("kod")
                or order.get("numer")
            )
            order_key = str(order_id) if order_id is not None else ""
            iid = order_key if order_key else f"row-{idx}"
            try:
                self.tree.insert("", "end", values=(rodzaj, status_txt, opis), iid=iid)
            except Exception as exc:  # pragma: no cover - wymagane GUI
                logger.exception("[ORD] Błąd dodawania zlecenia do listy: %s", exc)
                continue
            self._order_rows[iid] = order
            if order_key:
                self._order_ids[iid] = order_key

    # region Actions ----------------------------------------------------
    def _on_add(self) -> None:
        if not open_order_creator:
            return
        try:
            open_order_creator(self, "uzytkownik")
        except Exception as exc:  # pragma: no cover - wymagane GUI
            logger.exception("[ORD] Błąd otwierania kreatora: %s", exc)
            error_box(
                self,
                "Zlecenia",
                f"Nie udało się otworzyć kreatora.\n{exc}",
            )

    def _on_double_click(self, event: Any) -> None:
        if not open_order_detail:
            return
        selection = self.tree.selection()
        if not selection:
            return
        iid = selection[0]
        mapped = self._order_rows.get(iid, {})
        order_id = self._order_ids.get(iid) or (
            mapped.get("id")
            or mapped.get("nr")
            or mapped.get("kod")
            or mapped.get("numer")
        )
        order_data = {}
        if order_id:
            try:
                order_data = load_order(order_id)
            except Exception as exc:  # pragma: no cover - wymagane GUI
                logger.exception(
                    "[ORD] Błąd wczytywania zlecenia %s: %s",
                    order_id,
                    exc,
                )
                error_box(
                    self,
                    "Zlecenia",
                    f"Nie udało się wczytać szczegółów zlecenia {order_id}.\n{exc}",
                )
                return
        else:
            order_data = mapped
            order_id = iid
        if not order_data:
            logger.warning("[ORD] Brak danych zlecenia o ID %s", order_id)
            error_box(
                self,
                "Zlecenia",
                f"Nie znaleziono danych zlecenia o ID {order_id}.",
            )
            return
        try:
            open_order_detail(self, order_data)
        except Exception as exc:  # pragma: no cover - wymagane GUI
            logger.exception("[ORD] Błąd otwierania szczegółów: %s", exc)
            error_box(
                self,
                "Zlecenia",
                f"Nie udało się otworzyć szczegółów.\n{exc}",
            )

    # endregion ---------------------------------------------------------

    # region Refresh ----------------------------------------------------
    def _refresh(self) -> None:
        try:
            rows = _load_orders_rows()
        except Exception as exc:  # pragma: no cover - wymagane GUI
            logger.exception("[ORD] Błąd odświeżania listy zleceń: %s", exc)
            if not self._refresh_error_shown:
                error_box(
                    self,
                    "Zlecenia",
                    f"Nie udało się odświeżyć listy zleceń.\n{exc}",
                )
            self._refresh_error_shown = True
            return

        if not rows:
            try:
                fallback = load_orders()
            except Exception as exc:  # pragma: no cover - wymagane GUI
                logger.exception("[ORD] Błąd odświeżania listy zleceń: %s", exc)
                if not self._refresh_error_shown:
                    error_box(
                        self,
                        "Zlecenia",
                        f"Nie udało się odświeżyć listy zleceń.\n{exc}",
                    )
                self._refresh_error_shown = True
                return
            rows = [order for order in fallback if isinstance(order, dict)]

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
