# version: 2.0
"""Pulpit informacyjny Warsztat Menager dla niezalogowanego użytkownika.

Zastępuje centralną kartę logowania trzema widokami tylko do odczytu:
Narzędzia w toku, Maszyny wymagające uwagi i aktywne Dyspozycje.
Logowanie pozostaje w prawym górnym rogu panelu.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

_GUEST_NAMES = {"guest", "gość", "gosc", "niezalogowany", ""}
_REFRESH_MS = 30_000
_BLINK_MS = 650

_TOOL_PROGRESS_COLORS = {
    "progress_0": "#9ca3af",
    "progress_low": "#f87171",
    "progress_mid": "#facc15",
    "progress_high": "#86efac",
    "progress_done": "#22c55e",
}
_DYSP_COLORS = {
    "nowa": "#facc15",
    "w_toku": "#60a5fa",
    "wstrzymana": "#fb923c",
}


def _is_guest(root) -> bool:
    for attr in ("active_login", "current_user", "username", "_wm_login"):
        try:
            value = str(getattr(root, attr, "") or "").strip().casefold()
        except Exception:
            value = ""
        if value:
            return value in _GUEST_NAMES
    return True


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    if isinstance(raw, dict):
        for key in ("narzedzie", "tool"):
            nested = raw.get(key)
            if isinstance(nested, dict):
                return dict(nested)
        return dict(raw)
    return {}


def _tool_number(tool: Mapping[str, Any]) -> str:
    value = str(tool.get("id") or tool.get("nr") or tool.get("numer") or "").strip()
    return value.zfill(3) if value.isdigit() and len(value) <= 3 else value


def _load_tools() -> list[dict[str, Any]]:
    try:
        from tool_data_bridge import ToolDataBridge

        bridge = ToolDataBridge()
        bridge.reload_index()
        rows = [dict(row) for row in bridge.list_index_rows() if isinstance(row, dict)]
        tool_dir = Path(bridge.tools_dir())
    except Exception:
        logger.exception("[GUEST_DASHBOARD] Nie udało się wczytać indeksu Narzędzi.")
        return []

    by_nr: dict[str, dict[str, Any]] = {}
    for row in rows:
        nr = _tool_number(row)
        if nr:
            by_nr[nr] = row

    # Indeks bywa lżejszy od dokumentu narzędzia. Do podglądu pobieramy również
    # bieżące zadania/wizyty/status z pliku konkretnego narzędzia.
    try:
        for path in tool_dir.glob("*.json"):
            stem = path.stem.strip()
            if not stem.isdigit():
                continue
            doc = _safe_json(path)
            if not doc:
                continue
            nr = _tool_number(doc) or stem.zfill(3)
            merged = dict(by_nr.get(nr, {}))
            merged.update(doc)
            merged.setdefault("nr", nr)
            by_nr[nr] = merged
    except Exception:
        pass

    def _sort_key(item: Mapping[str, Any]):
        nr = _tool_number(item)
        return (0, int(nr)) if nr.isdigit() else (1, nr.casefold())

    return sorted(by_nr.values(), key=_sort_key)


def _tool_values(tool: Mapping[str, Any]) -> tuple[tuple[Any, ...], str]:
    try:
        from narzedzia_ui.list_panel import (
            _progress_tag,
            _tool_progress_pct,
            _tool_status_label,
            _tool_tasks_counts,
            _tool_type_label,
            _tool_visits_count,
            _visit_duration_label,
        )

        progress = _tool_progress_pct(tool)
        active, total = _tool_tasks_counts(tool)
        values = (
            _tool_number(tool),
            str(tool.get("nazwa") or tool.get("name") or ""),
            _tool_type_label(tool),
            _tool_status_label(tool),
            _visit_duration_label(tool),
            progress,
            f"{active}/{total}",
            _tool_visits_count(tool),
        )
        return values, _progress_tag(progress)
    except Exception:
        tasks = tool.get("zadania") or tool.get("tasks") or []
        tasks = tasks if isinstance(tasks, list) else []
        active = sum(1 for task in tasks if isinstance(task, Mapping) and task.get("done") is not True)
        total = len(tasks)
        progress = int(round(((total - active) / total) * 100)) if total else int(tool.get("postep") or 0)
        tag = "progress_done" if progress >= 100 else "progress_mid" if progress >= 50 else "progress_low" if progress > 0 else "progress_0"
        return (
            _tool_number(tool),
            str(tool.get("nazwa") or tool.get("name") or ""),
            str(tool.get("typ") or tool.get("type") or ""),
            str(tool.get("status") or ""),
            "—",
            f"{progress}%",
            f"{active}/{total}",
            len(tool.get("wizyty") or []) if isinstance(tool.get("wizyty"), list) else 0,
        ), tag


def _tool_in_progress(tool: Mapping[str, Any]) -> bool:
    values, _tag = _tool_values(tool)
    status = str(values[3] or "").strip().casefold()
    if not status:
        return False
    finished = {
        "sprawna", "sprawne", "sprawny", "dostępne", "dostepne", "gotowe",
        "gotowy", "wycofany", "wycofane", "zamknięty", "zamkniety", "zakończony",
        "zakonczony",
    }
    return status not in finished


def _load_machines() -> list[dict[str, Any]]:
    try:
        from utils_maszyny import load_machines

        result = load_machines()
        rows = result[0] if isinstance(result, tuple) and result else []
        return [dict(row) for row in rows if isinstance(row, dict)]
    except Exception:
        logger.exception("[GUEST_DASHBOARD] Nie udało się wczytać Maszyn.")
        return []


def _machine_values(machine: dict[str, Any]) -> tuple[tuple[Any, ...], str]:
    try:
        from gui_maszyny import (
            _combined_machine_schedule_summary,
            _machine_status_label,
            _normalize_machine_status,
        )

        status_key = _normalize_machine_status(machine.get("status"))
        status_label = _machine_status_label(machine.get("status"))
        summary = _combined_machine_schedule_summary(machine)
        next_label = str(summary.get("next_label") or "—")
        time_label = str(summary.get("status_label") or "—")
    except Exception:
        raw = str(machine.get("status") or "ok").strip().casefold()
        status_key = "ok" if raw in {"ok", "sprawna", "sprawne", "sprawny"} else "warn" if raw in {"awaria", "warn", "uszkodzona", "uszkodzone"} else "alert"
        status_label = "Sprawna" if status_key == "ok" else "Awaria" if status_key == "warn" else "Serwis / przegląd"
        next_label = "—"
        time_label = "—"

    number = str(machine.get("nr_ewid") or machine.get("id") or machine.get("nr") or "").strip()
    name = str(machine.get("nazwa") or machine.get("name") or machine.get("opis") or "").strip()
    return (number, name, status_label, next_label, time_label), status_key


def _load_active_dysp() -> list[dict[str, Any]]:
    try:
        from dyspozycje_store import load_dyspozycje

        rows = load_dyspozycje()
    except Exception:
        logger.exception("[GUEST_DASHBOARD] Nie udało się wczytać Dyspozycji.")
        return []
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip().casefold()
        if status in {"nowa", "w_toku"}:
            out.append(dict(row))
    return out


def _parse_deadline(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw.replace(" ", "T", 1))
    except Exception:
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw[:10], fmt)
            except Exception:
                continue
    return None


def _is_overdue(row: Mapping[str, Any]) -> bool:
    deadline = _parse_deadline(row.get("termin"))
    if deadline is None:
        return False
    now = datetime.now(tz=deadline.tzinfo) if deadline.tzinfo else datetime.now()
    return deadline < now


def _dysp_values(row: Mapping[str, Any]) -> tuple[Any, ...]:
    status = str(row.get("status") or "").strip().casefold()
    status_label = {"nowa": "Nowa", "w_toku": "W toku", "wstrzymana": "Wstrzymana"}.get(status, status.replace("_", " ").title())
    type_label = str(row.get("typ_dyspozycji") or "").replace("_", " ").title()
    assigned = str(row.get("przypisane_do") or ("Wszyscy" if row.get("dla_wszystkich") else "—"))
    executor = str(row.get("wykonuje") or "—")
    return (
        str(row.get("tytul") or row.get("opis") or row.get("id") or ""),
        status_label,
        type_label,
        assigned,
        executor,
        str(row.get("termin") or "—"),
        str(row.get("priorytet") or "normalny").title(),
    )


def _tree(parent, columns, headings, widths, height=5):
    from tkinter import ttk

    frame = ttk.Frame(parent, style="WM.Card.TFrame")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=height, selectmode="none")
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    for col, heading in zip(columns, headings):
        tree.heading(col, text=heading)
        tree.column(col, width=widths.get(col, 110), minwidth=55, anchor="w", stretch=True)
    try:
        style = ttk.Style(tree)
        style.configure("Guest.Treeview", font=("Segoe UI", 10), rowheight=27)
        style.configure("Guest.Treeview.Heading", font=("Segoe UI", 10, "bold"))
        tree.configure(style="Guest.Treeview")
    except Exception:
        pass
    tree.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    return frame, tree


def _repair_topbar(root) -> None:
    """Ustaw Zaloguj przed Motyw i dołącz pewną obsługę przełączania motywu."""

    try:
        from tkinter import ttk
    except Exception:
        return

    def walk(widget):
        yield widget
        try:
            for child in widget.winfo_children():
                yield from walk(child)
        except Exception:
            return

    login_button = None
    theme_label = None
    theme_box = None
    for widget in walk(root):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == "Zaloguj":
                login_button = widget
            elif isinstance(widget, ttk.Label) and str(widget.cget("text")) == "Motyw:":
                theme_label = widget
        except Exception:
            pass

    if theme_label is not None:
        try:
            siblings = theme_label.master.winfo_children()
            for widget in siblings:
                if isinstance(widget, ttk.Combobox):
                    theme_box = widget
                    break
        except Exception:
            pass

    if login_button is not None and theme_label is not None and theme_box is not None and login_button.master is theme_label.master:
        try:
            login_button.pack_forget()
            theme_label.pack_forget()
            theme_box.pack_forget()
            login_button.pack(side="left", padx=(0, 8))
            theme_label.pack(side="left", padx=(8, 4))
            theme_box.pack(side="left", padx=(0, 8))
        except Exception:
            pass

    if theme_box is None or getattr(theme_box, "_wm_guest_theme_fix", False):
        return

    def _apply_selected_theme(_event=None):
        selected = str(theme_box.get() or "default").strip()
        try:
            from config_manager import ConfigManager

            cfg = ConfigManager()
            cfg.set("ui.theme", selected)
            # Zostawiamy również klucz legacy, bo część starszych ekranów nadal go czyta.
            cfg.set("theme", selected)
            if hasattr(cfg, "save_all"):
                cfg.save_all()
            else:
                cfg.save()
        except Exception:
            logger.exception("[GUEST_DASHBOARD] Nie udało się zapisać motywu %s", selected)
        try:
            from ui_theme import apply_theme_safe

            apply_theme_safe(root, scheme=selected)
        except Exception:
            logger.exception("[GUEST_DASHBOARD] Nie udało się zastosować motywu %s", selected)
        try:
            root.event_generate("<<ThemeChanged>>", when="tail")
        except Exception:
            pass

    try:
        theme_box.bind("<<ComboboxSelected>>", _apply_selected_theme, add="+")
        setattr(theme_box, "_wm_guest_theme_fix", True)
    except Exception:
        pass


def _install_login_summary_hook() -> None:
    """Podepnij podsumowanie do każdego przejścia Gość -> zalogowany panel."""

    try:
        import gui_panel
    except Exception:
        return
    current = getattr(gui_panel, "uruchom_panel", None)
    if current is None or getattr(current, "_wm_login_summary_hook", False):
        return

    original = current

    def wrapped(root, login, rola, *args, **kwargs):
        result = original(root, login, rola, *args, **kwargs)
        role_key = str(rola or "").strip().casefold()
        login_key = str(login or "").strip().casefold()
        if role_key not in _GUEST_NAMES and login_key not in _GUEST_NAMES:
            def _show():
                try:
                    from login_summary_runtime import show_login_summary

                    show_login_summary(root, str(login))
                except Exception:
                    logger.exception("[LOGIN_SUMMARY] Nie udało się pokazać podsumowania.")
            try:
                root.after_idle(_show)
            except Exception:
                _show()
        return result

    setattr(wrapped, "_wm_login_summary_hook", True)
    setattr(wrapped, "_wm_login_summary_original", original)
    gui_panel.uruchom_panel = wrapped


def install_guest_login_card(root) -> bool:
    """Zgodna wstecznie nazwa instalatora — od v2 montuje pulpit Gościa."""

    if root is None or not _is_guest(root):
        return False

    _install_login_summary_hook()
    try:
        setattr(root, "_wm_login_summary_shown", "")
    except Exception:
        pass

    content = getattr(root, "content", None) or getattr(root, "main_content", None)
    if content is None:
        return False
    try:
        if not content.winfo_exists():
            return False
    except Exception:
        return False

    try:
        if getattr(content, "_wm_guest_dashboard", False):
            _repair_topbar(root)
            return True
    except Exception:
        pass

    try:
        from tkinter import ttk
    except Exception:
        return False

    try:
        for child in content.winfo_children():
            child.destroy()
    except Exception:
        pass

    try:
        source_var = getattr(root, "wm_current_source_var", None)
        if source_var is not None:
            source_var.set("Aktualnie: Pulpit informacyjny — podgląd bez logowania")
    except Exception:
        pass

    host = ttk.Frame(content, style="WM.Card.TFrame", padding=(10, 8))
    host.pack(fill="both", expand=True)
    host.columnconfigure(0, weight=1)
    host.rowconfigure(1, weight=5)
    host.rowconfigure(3, weight=3)
    host.rowconfigure(5, weight=4)

    title_row = ttk.Frame(host, style="WM.Card.TFrame")
    title_row.grid(row=0, column=0, sticky="ew", pady=(0, 4))
    ttk.Label(title_row, text="🔧 Narzędzia — w toku", style="WM.H2.TLabel").pack(side="left")
    tools_count = ttk.Label(title_row, text="", style="WM.Muted.TLabel")
    tools_count.pack(side="right")

    tools_frame, tools_tree = _tree(
        host,
        ("nr", "nazwa", "typ", "status", "czas", "postep", "zadania", "wizyty"),
        ("Nr", "Nazwa", "Typ", "Status", "Czas wizyty", "Postęp", "Zadania (A/W)", "Wizyty"),
        {"nr": 70, "nazwa": 310, "typ": 140, "status": 170, "czas": 115, "postep": 85, "zadania": 115, "wizyty": 70},
        height=7,
    )
    tools_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
    for tag, color in _TOOL_PROGRESS_COLORS.items():
        tools_tree.tag_configure(tag, foreground=color)

    machines_title = ttk.Frame(host, style="WM.Card.TFrame")
    machines_title.grid(row=2, column=0, sticky="ew", pady=(0, 4))
    ttk.Label(machines_title, text="⚙ Maszyny — wymagające uwagi", style="WM.H2.TLabel").pack(side="left")
    machines_count = ttk.Label(machines_title, text="", style="WM.Muted.TLabel")
    machines_count.pack(side="right")

    machines_frame, machines_tree = _tree(
        host,
        ("nr", "nazwa", "status", "przeglad", "za_ile"),
        ("Nr", "Maszyna", "Status", "Najbliższy przegląd", "Termin"),
        {"nr": 80, "nazwa": 360, "status": 190, "przeglad": 220, "za_ile": 160},
        height=4,
    )
    machines_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
    try:
        from gui_maszyny import MACHINE_STATUS_ROW_COLORS
        machine_colors = MACHINE_STATUS_ROW_COLORS
    except Exception:
        machine_colors = {
            "ok": {"background": "#dcfce7", "foreground": "#166534"},
            "alert": {"background": "#fef3c7", "foreground": "#854d0e"},
            "warn": {"background": "#fee2e2", "foreground": "#7f1d1d"},
        }
    for status_key, colors in machine_colors.items():
        try:
            machines_tree.tag_configure(f"machine_{status_key}", **dict(colors))
        except Exception:
            pass
    machines_tree.tag_configure("machine_warn_blink", foreground="#ef4444")

    dysp_title = ttk.Frame(host, style="WM.Card.TFrame")
    dysp_title.grid(row=4, column=0, sticky="ew", pady=(0, 4))
    ttk.Label(dysp_title, text="📋 Dyspozycje — do zrobienia / rozpoczęte", style="WM.H2.TLabel").pack(side="left")
    dysp_count = ttk.Label(dysp_title, text="", style="WM.Muted.TLabel")
    dysp_count.pack(side="right")

    dysp_frame, dysp_tree = _tree(
        host,
        ("dysp", "status", "typ", "przypisane", "wykonuje", "termin", "priorytet"),
        ("Dyspozycja", "Status", "Typ", "Przypisane", "Wykonuje", "Termin", "Priorytet"),
        {"dysp": 340, "status": 100, "typ": 130, "przypisane": 130, "wykonuje": 120, "termin": 135, "priorytet": 95},
        height=5,
    )
    dysp_frame.grid(row=5, column=0, sticky="nsew")
    for status_key, color in _DYSP_COLORS.items():
        dysp_tree.tag_configure(f"dysp_{status_key}", foreground=color)
    dysp_tree.tag_configure("dysp_overdue", foreground="#ef4444")

    state = {
        "refresh_job": None,
        "blink_job": None,
        "blink_on": False,
        "overdue": {},
        "machine_warn": set(),
    }

    def _clear(tree):
        for iid in tree.get_children(""):
            tree.delete(iid)

    def _refresh():
        try:
            if not host.winfo_exists() or not _is_guest(root):
                state["refresh_job"] = None
                return
        except Exception:
            state["refresh_job"] = None
            return

        _clear(tools_tree)
        shown_tools = 0
        for tool in _load_tools():
            if not _tool_in_progress(tool):
                continue
            values, tag = _tool_values(tool)
            tools_tree.insert("", "end", values=values, tags=(tag,))
            shown_tools += 1
        tools_count.configure(text=f"{shown_tools} pozycji • odświeżanie co 30 s")

        _clear(machines_tree)
        state["machine_warn"].clear()
        shown_machines = 0
        for machine in _load_machines():
            values, status_key = _machine_values(machine)
            if status_key == "ok":
                continue
            iid = machines_tree.insert("", "end", values=values, tags=(f"machine_{status_key}",))
            if status_key == "warn":
                state["machine_warn"].add(str(iid))
            shown_machines += 1
        machines_count.configure(text=f"{shown_machines} wymagających uwagi")

        _clear(dysp_tree)
        state["overdue"].clear()
        rows = _load_active_dysp()
        for row in rows:
            status_key = str(row.get("status") or "nowa").strip().casefold()
            iid = dysp_tree.insert("", "end", values=_dysp_values(row), tags=(f"dysp_{status_key}",))
            if _is_overdue(row):
                state["overdue"][str(iid)] = status_key
        dysp_count.configure(text=f"{len(rows)} aktywnych")

        try:
            state["refresh_job"] = host.after(_REFRESH_MS, _refresh)
        except Exception:
            state["refresh_job"] = None

    def _blink():
        try:
            if not host.winfo_exists() or not _is_guest(root):
                state["blink_job"] = None
                return
        except Exception:
            state["blink_job"] = None
            return
        state["blink_on"] = not state["blink_on"]
        alarm = bool(state["blink_on"])
        for iid, status_key in list(state["overdue"].items()):
            try:
                if dysp_tree.exists(iid):
                    dysp_tree.item(iid, tags=("dysp_overdue",) if alarm else (f"dysp_{status_key}",))
            except Exception:
                pass
        for iid in list(state["machine_warn"]):
            try:
                if machines_tree.exists(iid):
                    machines_tree.item(iid, tags=("machine_warn_blink",) if alarm else ("machine_warn",))
            except Exception:
                pass
        try:
            state["blink_job"] = host.after(_BLINK_MS, _blink)
        except Exception:
            state["blink_job"] = None

    def _destroy(_event=None):
        for key in ("refresh_job", "blink_job"):
            job = state.get(key)
            if job:
                try:
                    host.after_cancel(job)
                except Exception:
                    pass
                state[key] = None

    host.bind("<Destroy>", _destroy, add="+")
    setattr(content, "_wm_guest_dashboard", True)
    _repair_topbar(root)
    _refresh()
    _blink()
    return True


__all__ = ["install_guest_login_card"]
