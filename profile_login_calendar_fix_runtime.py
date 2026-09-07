# version: 1.0
"""Końcowa spójność logowania z Obecnością i kompaktowe kafelki Kalendarza.

Zakres jest celowo mały:
- stare ``attendance_utils.mark_login`` nadal działa dla kompatybilności,
  ale ten sam zapis jest następnie uzupełniany przez kanoniczny AttendanceService,
- Kalendarz Brygadzisty wykorzystuje już wczytany snapshot miesiąca i układa
  maksymalnie sześć osób po dwie w wierszu, bez dodatkowego odczytu danych.
"""
from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

from services import attendance_service

_INSTALLED = False


def _bridge_mark_login(
    legacy_mark: Callable[[str, str, str, str], Any],
    date_ymd: str,
    slot: str,
    login: str,
    ts_iso: str,
) -> None:
    """Zachowaj legacy zapis i od razu uzupełnij go kanonicznym modelem Obecności."""
    legacy_mark(date_ymd, slot, login, ts_iso)
    attendance_service.mark_login(date_ymd, slot, login, ts_iso)


def _team_tile_lines(day_number: int, rows: list[dict], *, max_people: int = 6) -> list[str]:
    """Zwróć tekst kafelka: dwie osoby w wierszu, maksymalnie trzy wiersze."""
    visible = [row for row in rows if str(row.get("status_code") or "") != "WOLNE"]
    shown = visible[: max(0, int(max_people))]

    entries: list[str] = []
    for row in shown:
        name = str(row.get("short_name") or row.get("login") or "—").strip()
        summary = str(row.get("summary") or "").strip()
        text = f"{name} {summary}".strip()
        # Kafelek ma dwie kolumny; nie pozwól pojedynczej nazwie zająć całej szerokości.
        entries.append(text[:16])

    paired: list[str] = []
    for idx in range(0, len(entries), 2):
        left = entries[idx]
        right = entries[idx + 1] if idx + 1 < len(entries) else ""
        paired.append(f"{left:<18}{right}".rstrip() if right else left)

    extra = max(0, len(visible) - len(shown))
    if extra:
        marker = f"+{extra}"
        if paired:
            paired[-1] = f"{paired[-1]}  {marker}"
        else:
            paired.append(marker)

    return [str(int(day_number)), *paired]


def _install_login_bridge() -> None:
    import attendance_utils

    if getattr(attendance_utils, "_wm_canonical_login_bridge_v1", False):
        return

    legacy_mark = attendance_utils.mark_login

    def mark_login(date_ymd: str, slot: str, login: str, ts_iso: str) -> None:
        _bridge_mark_login(legacy_mark, date_ymd, slot, login, ts_iso)

    attendance_utils.mark_login = mark_login
    attendance_utils._wm_canonical_login_bridge_v1 = True


def _install_calendar_tiles() -> None:
    import gui_profile_calendar as calendar_ui
    import profile_calendar_team_runtime as team_runtime

    cls = calendar_ui.ProfileCalendarPanel
    if getattr(cls, "_wm_two_column_team_tiles_v1", False):
        return

    original_render = cls._render_calendar

    def render(self):
        # Finalny render Kalendarza sam pobiera snapshot miesiąca. Przechwytujemy
        # dokładnie ten wynik, żeby nie wykonywać drugiego kosztownego odczytu.
        captured: dict[str, dict[int, list[dict]]] = {}
        original_month_rows = team_runtime._team_month_rows

        def capture_month_rows(year: int, month: int) -> dict[int, list[dict]]:
            rows = original_month_rows(year, month)
            captured["rows"] = rows
            return rows

        team_runtime._team_month_rows = capture_month_rows
        try:
            result = original_render(self)
        finally:
            if team_runtime._team_month_rows is capture_month_rows:
                team_runtime._team_month_rows = original_month_rows

        if not team_runtime._is_foreman():
            return result
        rows_by_day = captured.get("rows")
        if not isinstance(rows_by_day, dict):
            return result

        for child in self.calendar_box.winfo_children():
            if not isinstance(child, tk.Button):
                continue
            try:
                day_number = int(str(child.cget("text")).splitlines()[0])
            except Exception:
                continue
            lines = _team_tile_lines(day_number, rows_by_day.get(day_number, []))
            child.configure(
                text="\n".join(lines),
                height=4,
                justify="left",
                anchor="nw",
                font=("Segoe UI", 8),
            )
        return result

    cls._render_calendar = render
    cls._wm_two_column_team_tiles_v1 = True


def install() -> None:
    global _INSTALLED
    _install_login_bridge()
    _install_calendar_tiles()
    _INSTALLED = True


__all__ = ["install", "_bridge_mark_login", "_team_tile_lines"]
