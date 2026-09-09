# version: 1.0
"""Krótkie, spersonalizowane podsumowanie po zalogowaniu do WM.

Warstwa jest tylko do odczytu. W szczególności samo wyświetlenie podsumowania
NIE oznacza prywatnych wiadomości jako przeczytanych i nie zmienia statusów
Dyspozycji ani zadań.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


_GUESTS = {"", "guest", "gość", "gosc", "niezalogowany"}
_STATE_FILE = "login_summary_state.json"


def _login_key(value: object) -> str:
    return str(value or "").strip().casefold()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_dt(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    if "T" not in raw and " " in raw:
        raw = raw.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _state_path() -> Path:
    try:
        from config_manager import ConfigManager

        manager = ConfigManager()
        try:
            return Path(manager.path_data(_STATE_FILE))
        except TypeError:
            return Path(manager.path_data()) / _STATE_FILE
    except Exception:
        return Path("data") / _STATE_FILE


def _read_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_state(payload: Mapping[str, Any]) -> None:
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(dict(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except Exception:
        # Podsumowanie nie może blokować logowania z powodu problemu z zapisem markera.
        pass


def _last_login(login: str) -> datetime | None:
    state = _read_state()
    item = state.get(_login_key(login))
    if not isinstance(item, dict):
        return None
    return _parse_dt(item.get("last_login"))


def _save_login_marker(login: str, when: datetime) -> None:
    state = _read_state()
    key = _login_key(login)
    state[key] = {
        "login": str(login or "").strip(),
        "last_login": _to_iso(when),
    }
    _write_state(state)


def _after(value: object, threshold: datetime | None) -> bool:
    if threshold is None:
        return True
    parsed = _parse_dt(value)
    return parsed is not None and parsed > threshold


def _fmt_dt(value: object) -> str:
    parsed = _parse_dt(value)
    if parsed is None:
        raw = str(value or "").strip()
        return raw[:16].replace("T", " ") if raw else ""
    return parsed.astimezone().strftime("%d-%m-%y %H:%M")


def _unread_pm(login: str) -> list[dict[str, Any]]:
    try:
        from services.messages_service import list_inbox

        rows = list_inbox(login)
    except Exception:
        return []
    return [
        dict(row)
        for row in rows
        if isinstance(row, dict) and not bool(row.get("read"))
    ]


def _dysp_changed_at(row: Mapping[str, Any]) -> datetime | None:
    candidates: list[object] = [
        row.get("zamknieto_at"),
        row.get("rozpoczal_at"),
        row.get("utworzono"),
    ]
    meta = row.get("meta")
    if isinstance(meta, Mapping):
        history = meta.get("historia_statusow")
        if isinstance(history, list):
            for item in history:
                if isinstance(item, Mapping):
                    candidates.extend(
                        [item.get("ts"), item.get("timestamp"), item.get("data")]
                    )
    parsed = [item for item in (_parse_dt(value) for value in candidates) if item]
    return max(parsed) if parsed else None


def _active_user_dysp(login: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    key = _login_key(login)
    try:
        from dyspozycje_store import load_dyspozycje

        rows = load_dyspozycje()
    except Exception:
        return [], []

    active: list[dict[str, Any]] = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or "").strip().casefold()
        if status not in {"nowa", "w_toku"}:
            continue
        assigned = _login_key(raw.get("przypisane_do"))
        executor = _login_key(raw.get("wykonuje"))
        for_all = bool(raw.get("dla_wszystkich"))
        if assigned == key or executor == key or for_all:
            active.append(dict(raw))
    return active, rows


def _activity_since(login: str, previous: datetime | None) -> list[dict[str, Any]]:
    if previous is None:
        return []
    try:
        from services.activity_service import list_activity_filtered

        return list_activity_filtered(login, date_from=previous, limit=50)
    except Exception:
        return []


def _active_tool_tasks(login: str) -> list[dict[str, str]]:
    """Bieżące, niewykonane zadania narzędzi przypisane do użytkownika."""

    key = _login_key(login)
    if not key:
        return []
    try:
        from tool_data_bridge import ToolDataBridge

        bridge = ToolDataBridge()
        rows = bridge.list_index_rows()
    except Exception:
        return []

    out: list[dict[str, str]] = []
    for tool in rows or []:
        if not isinstance(tool, Mapping):
            continue
        tasks = tool.get("zadania") or tool.get("tasks") or []
        if not isinstance(tasks, list):
            continue
        tool_id = str(tool.get("id") or tool.get("nr") or tool.get("numer") or "").strip()
        tool_name = str(tool.get("nazwa") or tool.get("name") or "").strip()
        for task in tasks:
            if not isinstance(task, Mapping) or task.get("done") is True:
                continue
            assigned = _login_key(
                task.get("assigned_to") or task.get("przypisane") or task.get("do_kogo")
            )
            if assigned != key:
                continue
            out.append(
                {
                    "tool": tool_id,
                    "tool_name": tool_name,
                    "task": str(task.get("tytul") or task.get("title") or task.get("nazwa") or "Zadanie").strip(),
                }
            )
    return out


def _short_event(row: Mapping[str, Any]) -> str:
    event = str(row.get("event") or "Zmiana").strip().replace("_", " ")
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        detail = (
            payload.get("title")
            or payload.get("tytul")
            or payload.get("name")
            or payload.get("nazwa")
            or payload.get("object")
            or payload.get("obiekt")
            or ""
        )
        if detail:
            return f"{event}: {detail}"
    return event


def build_login_summary(login: str) -> dict[str, Any]:
    """Zbuduj snapshot podsumowania i ustaw nowy marker logowania."""

    now = _now_utc()
    previous = _last_login(login)
    unread = _unread_pm(login)
    dysp_active, _all_dysp = _active_user_dysp(login)
    tool_tasks = _active_tool_tasks(login)
    activity = _activity_since(login, previous)

    new_pm = [row for row in unread if _after(row.get("ts"), previous)]
    changed_dysp: list[dict[str, Any]] = []
    if previous is not None:
        for row in dysp_active:
            changed = _dysp_changed_at(row)
            if changed is not None and changed > previous:
                changed_dysp.append(row)

    result = {
        "login": login,
        "now": now,
        "previous": previous,
        "unread_pm": unread,
        "new_pm": new_pm,
        "active_dysp": dysp_active,
        "changed_dysp": changed_dysp,
        "tool_tasks": tool_tasks,
        "activity": activity,
    }
    _save_login_marker(login, now)
    return result


def _center_window(win, root) -> None:
    try:
        win.update_idletasks()
        width = max(640, win.winfo_reqwidth())
        height = max(420, win.winfo_reqheight())
        root.update_idletasks()
        x = root.winfo_rootx() + max(0, (root.winfo_width() - width) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - height) // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass


def show_login_summary(root, login: str) -> bool:
    """Pokaż jedno zwarte okno „co zmieniło się od ostatniego logowania”."""

    login = str(login or "").strip()
    if _login_key(login) in _GUESTS or root is None:
        return False

    # Jedno podsumowanie na jedno wejście do zalogowanego panelu. Tryb Gościa
    # zeruje ten znacznik, więc ponowne logowanie w tej samej aplikacji pokaże
    # świeży snapshot.
    marker = str(getattr(root, "_wm_login_summary_shown", "") or "")
    if marker == _login_key(login):
        return False
    setattr(root, "_wm_login_summary_shown", _login_key(login))

    try:
        snapshot = build_login_summary(login)
    except Exception:
        return False

    try:
        import tkinter as tk
        from tkinter import ttk
        from ui_theme import ensure_theme_applied
    except Exception:
        return False

    try:
        win = tk.Toplevel(root)
        win.title("Co zmieniło się od ostatniego logowania")
        win.transient(root)
        ensure_theme_applied(win)
    except Exception:
        return False

    outer = ttk.Frame(win, style="WM.TFrame", padding=(20, 16))
    outer.pack(fill="both", expand=True)

    ttk.Label(
        outer,
        text=f"Dzień dobry, {login} — krótkie podsumowanie",
        style="WM.H1.TLabel",
    ).pack(anchor="w")

    previous = snapshot.get("previous")
    if isinstance(previous, datetime):
        since_text = "Zmiany od ostatniego logowania: " + previous.astimezone().strftime("%d-%m-%y %H:%M")
    else:
        since_text = "Pierwsze podsumowanie — pokazuję bieżące sprawy związane z Twoim kontem."
    ttk.Label(outer, text=since_text, style="WM.Muted.TLabel").pack(anchor="w", pady=(2, 12))

    stats = ttk.Frame(outer, style="WM.TFrame")
    stats.pack(fill="x", pady=(0, 10))
    unread = snapshot["unread_pm"]
    active_dysp = snapshot["active_dysp"]
    tasks = snapshot["tool_tasks"]
    activity = snapshot["activity"]
    for text in (
        f"PM nieprzeczytane: {len(unread)}",
        f"Aktywne Dyspozycje: {len(active_dysp)}",
        f"Zadania narzędzi: {len(tasks)}",
        f"Zmiany konta: {len(activity)}",
    ):
        ttk.Label(stats, text=text, style="WM.Card.TLabel", padding=(10, 6)).pack(side="left", padx=(0, 8))

    box = tk.Text(
        outer,
        height=14,
        wrap="word",
        borderwidth=0,
        highlightthickness=0,
        padx=8,
        pady=8,
    )
    box.pack(fill="both", expand=True)

    lines: list[str] = []
    new_pm = snapshot["new_pm"]
    if unread:
        lines.append(f"WIADOMOŚCI PRYWATNE — {len(unread)} nieprzeczytanych")
        source = new_pm if previous is not None and new_pm else unread
        for msg in source[:6]:
            who = str(msg.get("from") or "?")
            subject = str(msg.get("subject") or "(bez tematu)")
            lines.append(f"  • {_fmt_dt(msg.get('ts'))}  {who}: {subject}")
        if len(source) > 6:
            lines.append(f"  • … i jeszcze {len(source) - 6}")
        lines.append("")

    changed_dysp = snapshot["changed_dysp"]
    if active_dysp:
        title = "DYSPOZYCJE ZWIĄZANE Z TOBĄ"
        if previous is not None and changed_dysp:
            title += f" — {len(changed_dysp)} zmienione od ostatniego logowania"
        lines.append(title)
        source = changed_dysp if previous is not None and changed_dysp else active_dysp
        for row in source[:6]:
            status = str(row.get("status") or "").replace("_", " ").title()
            title_value = str(row.get("tytul") or row.get("opis") or row.get("id") or "Dyspozycja")
            lines.append(f"  • [{status}] {title_value}")
        if len(source) > 6:
            lines.append(f"  • … i jeszcze {len(source) - 6}")
        lines.append("")

    if tasks:
        lines.append("AKTYWNE ZADANIA NARZĘDZI PRZYPISANE DO CIEBIE")
        for task in tasks[:6]:
            tool_label = " ".join(part for part in (task.get("tool", ""), task.get("tool_name", "")) if part).strip()
            lines.append(f"  • {tool_label}: {task.get('task', 'Zadanie')}")
        if len(tasks) > 6:
            lines.append(f"  • … i jeszcze {len(tasks) - 6}")
        lines.append("")

    if activity:
        lines.append("ZMIANY OD OSTATNIEGO LOGOWANIA")
        for row in activity[:8]:
            lines.append(f"  • {_fmt_dt(row.get('ts'))}  {_short_event(row)}")
        if len(activity) > 8:
            lines.append(f"  • … i jeszcze {len(activity) - 8}")

    if not lines:
        lines.append("Brak nowych zmian wymagających Twojej uwagi.")

    box.insert("1.0", "\n".join(lines))
    box.configure(state="disabled")

    footer = ttk.Frame(outer, style="WM.TFrame")
    footer.pack(fill="x", pady=(12, 0))
    ttk.Label(
        footer,
        text="PM pozostają nieprzeczytane, dopóki nie otworzysz ich w Czacie.",
        style="WM.Muted.TLabel",
    ).pack(side="left")
    ttk.Button(footer, text="Zamknij", command=win.destroy, style="WM.Side.TButton").pack(side="right")

    try:
        win.bind("<Escape>", lambda _event: win.destroy())
    except Exception:
        pass
    _center_window(win, root)
    return True


__all__ = ["build_login_summary", "show_login_summary"]
