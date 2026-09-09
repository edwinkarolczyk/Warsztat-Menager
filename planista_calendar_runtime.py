# WM-VERSION: 0.1
# Plik: planista_calendar_runtime.py
# version: 1.0
"""Planista korzysta ze wspolnego kalendarza WM z zielona ramka dnia dzisiejszego."""
from __future__ import annotations

from datetime import date, datetime

from calendar_ui_runtime import open_date_picker


def _initial_date(variable):
    """Odczytaj date poczatkowa bez zmiany formatu danych Planisty."""
    try:
        raw = str(variable.get() or "").strip()
    except Exception:
        raw = ""
    for fmt in ("%d-%m-%y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return date.today()


def _restore_parent_grab(parent) -> None:
    """Po zamknieciu kalendarza przywroc modalnosc dialogu nadrzednego."""
    try:
        parent.after_idle(parent.grab_set)
    except Exception:
        pass


def _walk_widgets(root):
    try:
        children = list(root.winfo_children())
    except Exception:
        return
    for child in children:
        yield child
        yield from _walk_widgets(child)


def _open_planista_calendar(parent, variable):
    """Adapter Planisty do wspolnego date pickera WM."""
    def on_select(chosen):
        variable.set(chosen.strftime("%d-%m-%y"))
        _restore_parent_grab(parent)

    picker = open_date_picker(
        parent,
        initial=_initial_date(variable),
        on_select=on_select,
        title="Wybierz termin",
    )

    def close_picker():
        try:
            picker.destroy()
        finally:
            _restore_parent_grab(parent)

    try:
        picker.protocol("WM_DELETE_WINDOW", close_picker)
    except Exception:
        pass

    # Wspolny picker ma przycisk Anuluj. Podmieniamy tylko jego zamkniecie,
    # aby zachowac dotychczasowe zachowanie modalnego dialogu Planisty.
    try:
        for child in _walk_widgets(picker):
            try:
                if str(child.cget("text") or "") == "Anuluj":
                    child.configure(command=close_picker)
                    break
            except Exception:
                continue
    except Exception:
        pass

    return picker


def install_planista_calendar_runtime() -> None:
    """Podmien oba odwolania Planisty na wspolny kalendarz WM."""
    import gui_planista as GP
    import gui_planista_panel as GPP

    GP._open_date_calendar = _open_planista_calendar
    # gui_planista_panel importuje funkcje przez `from ... import`, wiec jego
    # lokalne odwolanie trzeba podmienic osobno.
    GPP._open_date_calendar = _open_planista_calendar


__all__ = ["install_planista_calendar_runtime", "_open_planista_calendar"]
