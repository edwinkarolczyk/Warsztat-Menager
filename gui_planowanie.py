# WM-VERSION: 0.1
# Plik: gui_planowanie.py
# version: 2.0.1
# Zmiany 2.0.1:
# - nazwa "Planista" aktualizuje również gotową kopię SIDEBAR_MODULES_EXT w gui_panel.
# Zmiany 2.0:
# - stary moduł Planowanie został wycofany z interfejsu;
# - wejście otwiera prosty Planista służący tylko do ustawiania terminu;
# - nazwa pozycji w bocznym menu jest zmieniana na "Planista".

from __future__ import annotations

import sys

from gui_planista import open_planista


def _rename_in_list(modules):
    if not isinstance(modules, list):
        return
    for idx, entry in enumerate(list(modules)):
        if isinstance(entry, tuple) and len(entry) >= 2 and entry[0] == "planowanie":
            modules[idx] = ("planowanie", "Planista")


def _rename_sidebar_entry():
    try:
        import profile_utils
        _rename_in_list(getattr(profile_utils, "SIDEBAR_MODULES", None))
    except Exception:
        pass

    # gui_panel tworzy SIDEBAR_MODULES_EXT zanim importuje ten moduł,
    # więc aktualizujemy także tę istniejącą kopię listy.
    try:
        panel_module = sys.modules.get("gui_panel")
        if panel_module is not None:
            _rename_in_list(getattr(panel_module, "SIDEBAR_MODULES_EXT", None))
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
