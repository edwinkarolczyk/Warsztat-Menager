# WM-VERSION: 0.1
# Plik: gui_planowanie.py
# version: 2.0
# Zmiany 2.0:
# - stary moduł Planowanie został wycofany z interfejsu;
# - wejście otwiera prosty Planista służący tylko do ustawiania terminu;
# - nazwa pozycji w bocznym menu jest zmieniana na "Planista".

from __future__ import annotations

from gui_planista import open_planista


def _rename_sidebar_entry():
    try:
        import profile_utils
        modules = getattr(profile_utils, "SIDEBAR_MODULES", None)
        if not isinstance(modules, list):
            return
        for idx, entry in enumerate(list(modules)):
            if isinstance(entry, tuple) and len(entry) >= 2 and entry[0] == "planowanie":
                modules[idx] = ("planowanie", "Planista")
    except Exception:
        pass


_rename_sidebar_entry()


def panel_planowanie(root, frame, login=None, rola=None):
    """Adapter zgodności dla istniejącego klucza modułu ``planowanie``.

    Nie buduje już dawnego wielozakładkowego panelu. Kliknięcie pozycji
    w bocznym menu otwiera osobne, proste okno Planisty.
    """
    return open_planista(root, login=login, rola=rola)


def open_planner(root, login=None, rola=None):
    return open_planista(root, login=login, rola=rola)
