# WM-VERSION: 0.1
# Plik: gui_planowanie.py
# version: 2.6
# Zmiany 2.6:
# - dodano konfigurowalny słownik operacji technologicznych Planisty.
# Zmiany 2.5:
# - warstwy runtime Planisty są instalowane tylko raz na proces.
# Zmiany 2.4:
# - dodano obsługę wersji i rewizji produktu z archiwizacją poprzedniej wersji.
# Zmiany 2.3:
# - dodano rollback magazynu dla wieloetapowego przeliczania i rozliczania zleceń.
# Zmiany 2.2:
# - włączono wspólną warstwę bezpieczeństwa i spójności Planisty.
# Zmiany 2.1:
# - Planista jest osadzany w głównym prawym panelu WM zamiast otwierać Toplevel.
# - osobne okna pozostają tylko dla małych dialogów (termin, rozliczenie).
# Zmiany 2.0.1:
# - nazwa "Planista" aktualizuje również gotową kopię SIDEBAR_MODULES_EXT w gui_panel.

from __future__ import annotations

import sys

from gui_planista_panel import panel_planista
from planista_operations_runtime import install_planista_operations_runtime
from planista_safety_runtime import install_planista_safety_runtime
from planista_transaction_runtime import install_planista_transaction_runtime
from planista_versions_runtime import install_planista_versions_runtime


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


_runtime_ready = False


def _install_planista_runtime():
    global _runtime_ready
    if _runtime_ready:
        return
    install_planista_safety_runtime()
    install_planista_transaction_runtime()
    install_planista_versions_runtime()
    install_planista_operations_runtime()
    _runtime_ready = True


_rename_sidebar_entry()
_install_planista_runtime()


def panel_planowanie(root, frame, login=None, rola=None):
    """Adapter zgodności: klucz modułu pozostaje ``planowanie``, UI to Planista."""
    _install_planista_runtime()
    return panel_planista(root, frame, login=login, rola=rola)


def open_planner(root, login=None, rola=None):
    """Zgodność dla starych wywołań; osadza Planistę w aktywnym kontenerze WM."""
    _install_planista_runtime()
    frame = getattr(root, "content", None) or getattr(root, "main_content", None)
    if frame is None:
        raise RuntimeError("Brak głównego kontenera WM dla Planisty.")
    return panel_planista(root, frame, login=login, rola=rola)
