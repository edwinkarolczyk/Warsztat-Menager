# WM-VERSION: 0.1
# Plik: gui_planowanie.py
# version: 2.1
# Zmiany 2.1:
# - Planista jest osadzany w głównym prawym panelu WM zamiast otwierać Toplevel.
# - osobne okna pozostają tylko dla małych dialogów (termin, rozliczenie).
# Zmiany 2.0.1:
# - nazwa "Planista" aktualizuje również gotową kopię SIDEBAR_MODULES_EXT w gui_panel.

from __future__ import annotations

import sys

from gui_planista_panel import panel_planista


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
    try:
        panel_module = sys.modules.get("gui_panel")
        if panel_module is not None:
            _rename_in_list(getattr(panel_module, "SIDEBAR_MODULES_EXT", None))
    except Exception:
        pass


_rename_sidebar_entry()


def panel_planowanie(root, frame, login=None, rola=None):
    """Adapter zgodności: klucz modułu pozostaje ``planowanie``, UI to Planista."""
    return panel_planista(root, frame, login=login, rola=rola)


def open_planner(root, login=None, rola=None):
    """Zgodność dla starych wywołań; osadza Planistę w aktywnym kontenerze WM."""
    frame = getattr(root, "content", None) or getattr(root, "main_content", None)
    if frame is None:
        raise RuntimeError("Brak głównego kontenera WM dla Planisty.")
    return panel_planista(root, frame, login=login, rola=rola)
