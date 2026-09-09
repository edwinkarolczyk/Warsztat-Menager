# version: 1.1
"""Końcowa spójność logowania z Obecnością i czytelne kafelki Kalendarza.

Zakres jest celowo mały:
- stare ``attendance_utils.mark_login`` nadal działa dla kompatybilności,
  ale ten sam zapis jest następnie uzupełniany przez kanoniczny AttendanceService,
- Kalendarz Brygadzisty wykorzystuje już wczytany snapshot miesiąca,
- każdy dzień pokazuje do sześciu osób w siatce 2 kolumn x 3 wiersze,
  z osobnym obramowaniem zamiast wyrównywania nazw spacjami.
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


def _team_tile_entries(rows: list[dict], *, max_people: int = 6) -> tuple[list[str], int]:
    """Zwróć wpisy pracowników i liczbę ukrytych ponad limit."""
    visible = [row for row in rows if str(row.get("status_code") or "") != "WOLNE"]
    shown = visible[: max(0, int(max_people))]
    entries: list[str] = []
    for row in shown:
        name = str(row.get("short_name") or row.get("login") or "—").strip()
        summary = str(row.get("summary") or "").strip()
        entries.append(f"{name} {summary}".strip()[:18])
    return entries, max(0, len(visible) - len(shown))


def _team_tile_lines(day_number: int, rows: list[dict], *, max_people: int = 6) -> list[str]:
    """Tekstowy odpowiednik układu 2x3, używany m.in. w testach regresyjnych."""
    entries, extra = _team_tile_entries(rows, max_people=max_people)
    paired: list[str] = []
    for idx in range(0, len(entries), 2):
        left = entries[idx]
        right = entries[idx + 1] if idx + 1 < len(entries) else ""
        paired.append(" | ".join(part for part in (left, right) if part))
    if extra:
        if paired:
            paired[-1] = f"{paired[-1]}  +{extra}"
        else:
            paired.append(f"+{extra}")
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


def _bind_tile_click(widget, button: tk.Button) -> None:
    def invoke(_event=None):
        try:
            button.invoke()
        except Exception:
            pass
        return "break"

    try:
        widget.bind("<Button-1>", invoke, add="+")
        widget.configure(cursor="hand2")
    except Exception:
        pass


def _tile_background(button: tk.Button) -> str:
    try:
        return str(button.cget("background") or "#1A1D1F")
    except Exception:
        return "#1A1D1F"


def _build_team_overlay(calendar_box, button: tk.Button, day_number: int, rows: list[dict]):
    """Połóż na przycisku dnia prawdziwą siatkę 2x3 z osobnymi ramkami."""
    try:
        grid = button.grid_info()
    except Exception:
        return None
    if not grid:
        return None

    bg = _tile_background(button)
    frame = tk.Frame(
        calendar_box,
        bg=bg,
        bd=1,
        relief="solid",
        highlightthickness=0,
        takefocus=0,
    )
    frame.grid(
        row=int(grid.get("row", 0)),
        column=int(grid.get("column", 0)),
        rowspan=int(grid.get("rowspan", 1)),
        columnspan=int(grid.get("columnspan", 1)),
        sticky=str(grid.get("sticky") or "nsew"),
        padx=grid.get("padx", 0),
        pady=grid.get("pady", 0),
    )
    frame.grid_columnconfigure(0, weight=1, uniform="team")
    frame.grid_columnconfigure(1, weight=1, uniform="team")

    header = tk.Label(
        frame,
        text=str(day_number),
        bg=bg,
        fg="#f3f4f6",
        anchor="nw",
        justify="left",
        font=("Segoe UI", 9, "bold"),
        padx=3,
        pady=1,
        bd=0,
    )
    header.grid(row=0, column=0, columnspan=2, sticky="ew")
    _bind_tile_click(header, button)

    entries, extra = _team_tile_entries(rows)
    if extra and entries:
        entries[-1] = f"{entries[-1]} +{extra}"[:22]

    row_count = (len(entries) + 1) // 2
    for pair_index in range(row_count):
        for column in (0, 1):
            item_index = pair_index * 2 + column
            text = entries[item_index] if item_index < len(entries) else ""
            cell = tk.Label(
                frame,
                text=text,
                bg=bg,
                fg="#e5e7eb",
                anchor="w",
                justify="left",
                font=("Segoe UI", 8),
                padx=3,
                pady=1,
                bd=1,
                relief="solid",
            )
            cell.grid(row=pair_index + 1, column=column, sticky="nsew")
            _bind_tile_click(cell, button)

    _bind_tile_click(frame, button)
    try:
        frame.lift()
    except Exception:
        pass
    return frame


def _install_calendar_tiles() -> None:
    import gui_profile_calendar as calendar_ui
    import profile_calendar_team_runtime as team_runtime

    cls = calendar_ui.ProfileCalendarPanel
    if getattr(cls, "_wm_two_column_team_tiles_v2", False):
        return

    original_render = cls._render_calendar

    def render(self):
        for overlay in list(getattr(self, "_wm_team_tile_overlays", []) or []):
            try:
                overlay.destroy()
            except Exception:
                pass
        self._wm_team_tile_overlays = []
        self._wm_team_tile_frames = {}

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

        overlays = []
        frames_by_day = {}
        for child in list(self.calendar_box.winfo_children()):
            if not isinstance(child, tk.Button):
                continue
            try:
                day_number = int(str(child.cget("text")).splitlines()[0])
            except Exception:
                continue
            try:
                child.configure(text=str(day_number), height=4, anchor="nw", justify="left")
            except Exception:
                pass
            overlay = _build_team_overlay(
                self.calendar_box,
                child,
                day_number,
                rows_by_day.get(day_number, []),
            )
            if overlay is not None:
                overlays.append(overlay)
                frames_by_day[day_number] = overlay

        self._wm_team_tile_overlays = overlays
        self._wm_team_tile_frames = frames_by_day
        return result

    cls._render_calendar = render
    cls._wm_two_column_team_tiles_v2 = True


def install() -> None:
    global _INSTALLED
    _install_login_bridge()
    _install_calendar_tiles()
    _INSTALLED = True


__all__ = [
    "install",
    "_bridge_mark_login",
    "_team_tile_entries",
    "_team_tile_lines",
    "_build_team_overlay",
]
