# version: 1.0
"""Wspólne, lekkie poprawki kalendarzy WM.

Zakres runtime'u jest celowo wąski:
- dodaje przycisk kalendarza do pola „Planowana data” w dialogu przeglądu maszyny,
- podświetla dzień dzisiejszy zieloną ramką w istniejących kalendarzach WM,
- nie zmienia formatu zapisu dat ani logiki biznesowej.
"""
from __future__ import annotations

import calendar
import datetime as dt
import re
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

_TODAY_BORDER = "#22c55e"
_PLANNING_OLD_TODAY_BORDER = "#f39c12"
_MACHINE_DIALOG_TITLE = "Dodaj przegląd / serwis"
_EMPLOYMENT_DIALOG_TITLE = "Data zatrudnienia"
_MONTHS_PL = (
    "",
    "Styczeń",
    "Luty",
    "Marzec",
    "Kwiecień",
    "Maj",
    "Czerwiec",
    "Lipiec",
    "Sierpień",
    "Wrzesień",
    "Październik",
    "Listopad",
    "Grudzień",
)
_MONTH_BY_NAME = {name.casefold(): idx for idx, name in enumerate(_MONTHS_PL) if name}
_INSTALLED = False


def _safe_title(widget: Any) -> str:
    try:
        return str(widget.winfo_toplevel().title() or "")
    except Exception:
        return ""


def _safe_widget_text(widget: Any) -> str:
    values: list[str] = []
    try:
        text = str(widget.cget("text") or "").strip()
        if text:
            values.append(text)
    except Exception:
        pass
    try:
        variable = str(widget.cget("textvariable") or "").strip()
        if variable:
            value = str(widget.getvar(variable) or "").strip()
            if value:
                values.append(value)
    except Exception:
        pass
    return " ".join(values)


def _walk_widgets(root: Any):
    try:
        children = list(root.winfo_children())
    except Exception:
        return
    for child in children:
        yield child
        yield from _walk_widgets(child)


def _visible_employment_month(top: Any) -> tuple[int, int] | None:
    month = 0
    year = 0
    for widget in _walk_widgets(top):
        text = _safe_widget_text(widget)
        folded = text.casefold()
        if not month:
            for name, idx in _MONTH_BY_NAME.items():
                if name in folded:
                    month = idx
                    break
        if not year:
            match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", text)
            if match:
                year = int(match.group(1))
        if month and year:
            break
    return (year, month) if year and month else None


def _add_green_grid_border(widget: Any) -> None:
    """Dodaj 2-pikselową zieloną ramkę pod istniejącym widżetem grid."""
    try:
        if getattr(widget, "_wm_today_border_installed", False):
            return
        info = dict(widget.grid_info())
        parent = widget.master
        row = info.get("row")
        column = info.get("column")
        if row in (None, "") or column in (None, ""):
            return
        frame = tk.Frame(parent, bg=_TODAY_BORDER, bd=0, highlightthickness=0)
        frame.grid(
            row=row,
            column=column,
            rowspan=info.get("rowspan", 1),
            columnspan=info.get("columnspan", 1),
            sticky=info.get("sticky", "nsew") or "nsew",
            padx=0,
            pady=0,
        )
        widget.lift(frame)
        widget._wm_today_border_installed = True
        widget._wm_today_border_frame = frame
    except Exception:
        return


def _parse_machine_date(value: Any) -> dt.date:
    text = str(value or "").strip()
    if not text:
        return dt.date.today()

    try:
        return dt.date.fromisoformat(text[:10])
    except Exception:
        pass

    cleaned = text.replace("–", "-").replace("r.", "r").strip()
    parts = cleaned.split()
    if len(parts) >= 3:
        try:
            day = int(parts[0])
            month = _MONTH_BY_NAME.get(parts[1].casefold(), 0)
            year_text = re.sub(r"[^0-9]", "", parts[2])
            year = int(year_text)
            if year < 100:
                year += 2000
            if month:
                return dt.date(year, month, day)
        except Exception:
            pass

    for fmt in ("%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except Exception:
            pass
    return dt.date.today()


def _format_machine_date(value: dt.date) -> str:
    return f"{value.day:02d} {_MONTHS_PL[value.month]} {value.year % 100:02d}r"


def _set_entry_text(entry: Any, value: str) -> None:
    try:
        entry.delete(0, "end")
        entry.insert(0, value)
        return
    except Exception:
        pass
    try:
        variable = str(entry.cget("textvariable") or "").strip()
        if variable:
            entry.setvar(variable, value)
    except Exception:
        pass


def open_date_picker(
    owner: Any,
    *,
    initial: dt.date | None = None,
    on_select: Callable[[dt.date], None],
    title: str = "Wybierz datę",
) -> Any:
    """Prosty kalendarz bez zewnętrznych zależności, ze stałą zieloną ramką dziś."""
    selected = initial or dt.date.today()
    state = {"year": selected.year, "month": selected.month}

    top = tk.Toplevel(owner)
    top.title(title)
    top.resizable(False, False)
    try:
        top.transient(owner.winfo_toplevel())
    except Exception:
        pass
    try:
        top.grab_set()
    except Exception:
        pass

    outer = ttk.Frame(top, padding=8)
    outer.pack(fill="both", expand=True)
    header = ttk.Frame(outer)
    header.pack(fill="x", pady=(0, 6))
    month_var = tk.StringVar(value="")
    ttk.Label(header, textvariable=month_var, width=22, anchor="center").pack(
        side="left", expand=True, fill="x", padx=6
    )
    grid = ttk.Frame(outer)
    grid.pack(fill="both", expand=True)

    def _change_month(delta: int) -> None:
        month = state["month"] + int(delta)
        year = state["year"]
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        state["year"], state["month"] = year, month
        _render()

    def _choose(day: int) -> None:
        chosen = dt.date(state["year"], state["month"], int(day))
        on_select(chosen)
        top.destroy()

    def _choose_today() -> None:
        today = dt.date.today()
        on_select(today)
        top.destroy()

    def _render() -> None:
        for child in grid.winfo_children():
            child.destroy()
        month_var.set(f"{_MONTHS_PL[state['month']]} {state['year']}")
        for col, label in enumerate(("Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd")):
            ttk.Label(grid, text=label, width=4, anchor="center").grid(
                row=0, column=col, padx=1, pady=1
            )

        today = dt.date.today()
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(
            state["year"], state["month"]
        )
        for row_idx, week in enumerate(weeks, start=1):
            for col_idx, day in enumerate(week):
                if not day:
                    ttk.Label(grid, text="", width=4).grid(
                        row=row_idx, column=col_idx, padx=1, pady=1
                    )
                    continue
                current = dt.date(state["year"], state["month"], day)
                is_today = current == today
                if is_today:
                    border = tk.Frame(grid, bg=_TODAY_BORDER, bd=0)
                    border.grid(
                        row=row_idx,
                        column=col_idx,
                        sticky="nsew",
                        padx=0,
                        pady=0,
                    )
                    button = ttk.Button(
                        grid,
                        text=str(day),
                        width=4,
                        command=lambda d=day: _choose(d),
                    )
                    button.grid(
                        row=row_idx,
                        column=col_idx,
                        padx=2,
                        pady=2,
                    )
                    button.lift(border)
                else:
                    ttk.Button(
                        grid,
                        text=str(day),
                        width=4,
                        command=lambda d=day: _choose(d),
                    ).grid(row=row_idx, column=col_idx, padx=1, pady=1)

    ttk.Button(header, text="◀", width=3, command=lambda: _change_month(-1)).pack(
        side="left", before=header.winfo_children()[0]
    )
    ttk.Button(header, text="▶", width=3, command=lambda: _change_month(1)).pack(
        side="right"
    )
    footer = ttk.Frame(outer)
    footer.pack(fill="x", pady=(6, 0))
    ttk.Button(footer, text="Dzisiaj", command=_choose_today).pack(side="left")
    ttk.Button(footer, text="Anuluj", command=top.destroy).pack(side="right")

    _render()
    return top


def _machine_entry_is_plan_date(entry: Any) -> bool:
    if _safe_title(entry) != _MACHINE_DIALOG_TITLE:
        return False
    try:
        entry_info = dict(entry.grid_info())
        entry_row = str(entry_info.get("row"))
        for sibling in entry.master.winfo_children():
            if sibling is entry:
                continue
            if str(sibling.cget("text") or "").strip() != "Planowana data:":
                continue
            sibling_info = dict(sibling.grid_info())
            if str(sibling_info.get("row")) == entry_row:
                return True
    except Exception:
        return False
    return False


def _decorate_machine_plan_date_entry(entry: Any) -> None:
    try:
        if getattr(entry, "_wm_machine_calendar_button", None) is not None:
            return
        if not _machine_entry_is_plan_date(entry):
            return
        info = dict(entry.grid_info())
        row = int(info.get("row", 1))
        column = int(info.get("column", 1))

        def _open() -> None:
            initial = _parse_machine_date(entry.get())
            open_date_picker(
                entry,
                initial=initial,
                on_select=lambda chosen: _set_entry_text(
                    entry, _format_machine_date(chosen)
                ),
                title="Planowana data przeglądu / serwisu",
            )

        button = ttk.Button(entry.master, text="📅", width=3, command=_open)
        button.grid(row=row, column=column + 1, sticky="w", padx=(0, 4), pady=4)
        entry._wm_machine_calendar_button = button
    except Exception:
        return


def _is_employment_today_button(button: Any) -> bool:
    if _safe_title(button) != _EMPLOYMENT_DIALOG_TITLE:
        return False
    try:
        raw = str(button.cget("text") or "").strip()
        if not raw.isdigit():
            return False
        visible = _visible_employment_month(button.winfo_toplevel())
        if visible is None:
            return False
        year, month = visible
        return dt.date(year, month, int(raw)) == dt.date.today()
    except Exception:
        return False


def install() -> None:
    """Zainstaluj idempotentnie poprawki UI; bez zmian w modelach danych."""
    global _INSTALLED
    if _INSTALLED:
        return

    # Planowanie: istniejąca pomarańczowa ramka dotyczy wyłącznie dnia dzisiejszego.
    try:
        original_frame_init = tk.Frame.__init__
        if not getattr(original_frame_init, "_wm_calendar_runtime", False):
            def _frame_init(self, *args, **kwargs):
                if (
                    str(kwargs.get("highlightbackground") or "").lower()
                    == _PLANNING_OLD_TODAY_BORDER
                    and int(kwargs.get("highlightthickness") or 0) > 0
                ):
                    kwargs["highlightbackground"] = _TODAY_BORDER
                    kwargs["highlightcolor"] = _TODAY_BORDER
                return original_frame_init(self, *args, **kwargs)

            _frame_init._wm_calendar_runtime = True
            tk.Frame.__init__ = _frame_init
    except Exception:
        pass

    # Profil/urlopy: zachowaj istniejące kolory statusów, dodaj tylko zewnętrzną ramkę.
    try:
        original_tk_button_grid = tk.Button.grid
        if not getattr(original_tk_button_grid, "_wm_calendar_runtime", False):
            def _tk_button_grid(self, *args, **kwargs):
                result = original_tk_button_grid(self, *args, **kwargs)
                try:
                    if "DZIŚ" in str(self.cget("text") or "").upper():
                        _add_green_grid_border(self)
                except Exception:
                    pass
                return result

            _tk_button_grid._wm_calendar_runtime = True
            tk.Button.grid = _tk_button_grid
    except Exception:
        pass

    # Ustawienia użytkownika: dzień dziś w kalendarzu daty zatrudnienia.
    try:
        original_ttk_button_grid = ttk.Button.grid
        if not getattr(original_ttk_button_grid, "_wm_calendar_runtime", False):
            def _ttk_button_grid(self, *args, **kwargs):
                result = original_ttk_button_grid(self, *args, **kwargs)
                if _is_employment_today_button(self):
                    _add_green_grid_border(self)
                return result

            _ttk_button_grid._wm_calendar_runtime = True
            ttk.Button.grid = _ttk_button_grid
    except Exception:
        pass

    # Maszyny: po umieszczeniu konkretnego pola „Planowana data” dodaj kalendarz.
    try:
        original_entry_grid = ttk.Entry.grid
        if not getattr(original_entry_grid, "_wm_calendar_runtime", False):
            def _entry_grid(self, *args, **kwargs):
                result = original_entry_grid(self, *args, **kwargs)
                _decorate_machine_plan_date_entry(self)
                return result

            _entry_grid._wm_calendar_runtime = True
            ttk.Entry.grid = _entry_grid
    except Exception:
        pass

    _INSTALLED = True


__all__ = ["install", "open_date_picker"]
