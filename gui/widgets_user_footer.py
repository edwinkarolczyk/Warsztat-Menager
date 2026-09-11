# version: 1.1
"""Widgets related to the user footer (tasks + shift progress)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import tkinter as tk
from tkinter import ttk

from grafiki import shifts_schedule
from logger import log_akcja
from profile_tasks import get_tasks_for as _profile_get_tasks

try:  # optional during tests
    from config_manager import ConfigManager
except Exception:  # pragma: no cover - import fallback for tests
    ConfigManager = None  # type: ignore

_DEFAULT_TASK_DEADLINE = "9999-12-31"


def _alert_candidates() -> List[Path]:
    paths: List[Path] = []
    try:
        if ConfigManager is not None:
            cfg = ConfigManager()
            paths.append(Path(cfg.path_data("alerts.json")))
    except Exception:
        pass
    for candidate in (
        Path("alerts.json"),
        Path("data") / "alerts.json",
        Path("logi") / "alerts.json",
    ):
        if candidate not in paths:
            paths.append(candidate)
    return paths


def _parse_deadline_value(value) -> datetime:
    if not value:
        return datetime.max.replace(tzinfo=timezone.utc)
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.max.replace(tzinfo=timezone.utc)


def _load_recent_tasks(login: str, limit: int = 5) -> List[dict]:
    try:
        rows = _profile_get_tasks(login) or []
    except Exception as exc:  # pragma: no cover - defensive logging
        log_akcja(f"[FOOTER][TASKS] Błąd odczytu zadań dla {login}: {exc}")
        return []
    tasks = [row for row in rows if isinstance(row, dict)]
    tasks.sort(
        key=lambda row: _parse_deadline_value(
            row.get("deadline") or row.get("termin") or _DEFAULT_TASK_DEADLINE
        )
    )
    return tasks[:limit]


def _load_alerts(limit: int = 5) -> List[dict]:
    for candidate in _alert_candidates():
        try:
            if not candidate.exists():
                continue
            with candidate.open(encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            log_akcja(f"[FOOTER][ALERTS] Błąd odczytu {candidate}: {exc}")
            continue

        if isinstance(payload, dict):
            rows = [record for record in payload.values() if isinstance(record, dict)]
        elif isinstance(payload, list):
            rows = [record for record in payload if isinstance(record, dict)]
        else:
            rows = []

        rows.sort(key=lambda row: str(row.get("created_at") or row.get("ts") or ""))
        return rows[:limit]
    return []


def _is_task_urgent(task: dict) -> bool:
    status = str(task.get("status") or task.get("stan") or "").strip().lower()
    if status in {"pilne", "urgent", "overdue", "alert"}:
        return True
    deadline = _parse_deadline_value(task.get("deadline") or task.get("termin"))
    return deadline < datetime.now(timezone.utc)


def _format_task_summary(task: dict) -> str:
    ident = str(task.get("id") or task.get("nr") or task.get("kod") or "").strip()
    title = (
        task.get("title")
        or task.get("tytul")
        or task.get("nazwa")
        or task.get("opis")
        or "Zadanie"
    )
    status = str(task.get("status") or task.get("stan") or "").strip()
    deadline = str(task.get("deadline") or task.get("termin") or "").strip()
    text = title
    if ident:
        text = f"{ident} • {title}"
    info_parts: List[str] = []
    if status:
        info_parts.append(status)
    if deadline and deadline != _DEFAULT_TASK_DEADLINE:
        info_parts.append(deadline)
    if info_parts:
        text = f"{text} ({', '.join(info_parts)})"
    return text


def _is_alert_active(alert: dict) -> bool:
    status = str(alert.get("status") or alert.get("stan") or "").strip().lower()
    return status in {"", "pending", "nowe", "open", "w toku", "active"}


def _format_alert_summary(alert: dict) -> str:
    shift = str(alert.get("zmiana") or alert.get("shift") or "?").strip()
    owner = str(alert.get("login") or alert.get("user") or "?").strip()
    status = str(alert.get("status") or alert.get("stan") or "").strip()
    minutes = alert.get("minutes")
    note = str(alert.get("note") or "").strip()

    parts: List[str] = []
    if shift:
        parts.append(f"Zmiana {shift}")
    if owner:
        parts.append(f"@{owner}")
    if status:
        parts.append(status)
    if isinstance(minutes, (int, float)) and minutes:
        parts.append(f"{int(minutes)} min")
    summary = " • ".join(parts) if parts else "Alert"
    if note:
        summary = f"{summary} — {note}"
    return summary


def _build_tasks_tile(parent: tk.Widget, login: str) -> ttk.Frame:
    wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=8)
    wrap.tasks_summary = tasks = _load_recent_tasks(login)
    wrap.alerts_summary = alerts = _load_alerts()

    header_text = f"Twoje zadania ({len(tasks)})"
    if alerts:
        header_text = f"{header_text} • Alerty ({len(alerts)})"

    ttk.Label(
        wrap,
        text=header_text,
        style="WM.CardLabel.TLabel",
    ).pack(anchor="w", pady=(0, 4))

    if not tasks:
        ttk.Label(
            wrap,
            text="Brak przydzielonych zadań",
            style="WM.Muted.TLabel",
        ).pack(anchor="w")
    else:
        for task in tasks:
            row = ttk.Frame(wrap, style="WM.Card.TFrame")
            row.pack(fill="x", pady=2)
            if _is_task_urgent(task):
                dot = tk.Canvas(row, width=10, height=10, highlightthickness=0, bd=0)
                dot.configure(bg="#1b1f24")
                dot.create_oval(2, 2, 8, 8, fill="#ff6b1a", outline="#ff6b1a")
                dot.pack(side="left", padx=(0, 6))
            ttk.Label(
                row,
                text=_format_task_summary(task),
                style="WM.Muted.TLabel",
                anchor="w",
                justify="left",
            ).pack(side="left", fill="x", expand=True)

    ttk.Separator(wrap, orient="horizontal").pack(fill="x", pady=6)

    ttk.Label(
        wrap,
        text="Alerty",
        style="WM.CardMuted.TLabel",
    ).pack(anchor="w")

    if not alerts:
        ttk.Label(
            wrap,
            text="Brak aktywnych alertów",
            style="WM.Muted.TLabel",
        ).pack(anchor="w", pady=(2, 0))
    else:
        for alert in alerts:
            row = ttk.Frame(wrap, style="WM.Card.TFrame")
            row.pack(fill="x", pady=2)
            if _is_alert_active(alert):
                dot = tk.Canvas(row, width=10, height=10, highlightthickness=0, bd=0)
                dot.configure(bg="#1b1f24")
                dot.create_oval(2, 2, 8, 8, fill="#ff6b1a", outline="#ff6b1a")
                dot.pack(side="left", padx=(0, 6))
            ttk.Label(
                row,
                text=_format_alert_summary(alert),
                style="WM.Muted.TLabel",
                anchor="w",
                justify="left",
            ).pack(side="left", fill="x", expand=True)

    return wrap


def _shift_bounds(moment: datetime) -> Tuple[datetime, datetime, str]:
    date_ref = moment.date()
    times = shifts_schedule._shift_times()

    def _at(day, value):
        return datetime.combine(day, value).replace(tzinfo=moment.tzinfo)

    early = _at(date_ref, times["R_START"])
    mid = _at(date_ref, times["P_START"])
    night_start = _at(date_ref, times["P_END"])
    if moment < early:
        prev = date_ref - timedelta(days=1)
        return _at(prev, times["P_END"]), early, "NOC"
    if moment < mid:
        return early, _at(date_ref, times["R_END"]), "RANO"
    if moment < night_start:
        return mid, night_start, "POŁUDNIE"
    next_day = date_ref + timedelta(days=1)
    return night_start, _at(next_day, times["R_START"]), "NOC"


def _shift_progress(now: datetime) -> Tuple[int, bool]:
    start, end, _label = _shift_bounds(now)
    total = max((end - start).total_seconds(), 1)
    elapsed = (now - start).total_seconds()
    if elapsed <= 0:
        return 0, False
    if elapsed >= total:
        return 100, False
    return int((elapsed / total) * 100), True


def _current_shift_label(moment: datetime | None = None) -> str:
    _, _, label = _shift_bounds(moment or datetime.now())
    return label


def create_user_footer(parent: tk.Widget, ctx: dict | None = None) -> ttk.Frame:
    ctx = ctx or {}
    login = str(ctx.get("login") or "").strip() or "uzytkownik"
    container = ttk.Frame(parent, style="WM.TFrame")

    tasks_tile = _build_tasks_tile(container, login)
    tasks_tile.pack(fill="x", padx=(0, 12), pady=(0, 8))
    container.tasks_tile = tasks_tile

    shift_wrap = ttk.Frame(container, style="WM.Card.TFrame")
    shift_wrap.pack(fill="x")
    ttk.Label(shift_wrap, text="Zmiana", style="WM.Card.TLabel").pack(
        anchor="w", padx=8, pady=(6, 0)
    )
    canvas = tk.Canvas(
        shift_wrap,
        width=480,
        height=18,
        highlightthickness=0,
        bd=0,
        bg="#1b1f24",
    )
    canvas.pack(padx=8, pady=6)
    info = ttk.Label(shift_wrap, text="", style="WM.Muted.TLabel")
    info.pack(anchor="w", padx=8, pady=(0, 6))

    state = {"job": None}

    def _draw() -> None:
        if not canvas.winfo_exists():
            return
        now = datetime.now()
        percent, running = _shift_progress(now)
        start, end, label = _shift_bounds(now)
        done_w = int(480 * (percent / 100.0))
        canvas.delete("all")
        bar_bg = "#2a2f36"
        canvas.create_rectangle(0, 0, 480, 18, fill=bar_bg, outline=bar_bg)
        done_color = "#34a853" if running and percent > 0 else "#3a4a3f"
        remain_color = "#8d8d8d"
        if done_w > 0:
            canvas.create_rectangle(0, 0, done_w, 18, fill=done_color, outline=done_color)
        if done_w < 480:
            canvas.create_rectangle(done_w, 0, 480, 18, fill=remain_color, outline=remain_color)
        info.config(
            text=(
                f"Zmiana {label}: {start.strftime('%H:%M')} - {end.strftime('%H:%M')}    {percent}%"
            )
        )

    def _tick() -> None:
        if not canvas.winfo_exists():
            state["job"] = None
            return
        _draw()
        state["job"] = canvas.after(1000, _tick)

    def _on_destroy(_event=None) -> None:
        job = state.get("job")
        if job is not None:
            try:
                canvas.after_cancel(job)
            except Exception:
                pass
            state["job"] = None

    _tick()
    canvas.bind("<Destroy>", _on_destroy, add="+")

    return container


__all__ = [
    "create_user_footer",
    "_shift_bounds",
    "_shift_progress",
    "_current_shift_label",
]
