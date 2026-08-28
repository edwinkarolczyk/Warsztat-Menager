# version: 1.1
# Zmiany 1.1:
# - Nie pokazuj ostrzeżenia o braku globalnych statusów, gdy aktualne definicje
#   typów narzędzi zawierają statusy. Ostrzeżenia o realnym braku statusów dla
#   konkretnego typu pozostają bez zmian.
"""Pakiet pomocniczy dla modułu GUI narzędzi."""

from __future__ import annotations

from tkinter import messagebox as _messagebox

from .state import ToolsPanelState, STATE


def _wm_has_defined_tool_statuses() -> bool:
    """Sprawdź, czy aktualne definicje Narzędzi zawierają choć jeden status."""

    try:
        import logika_zadan as _lz

        for collection in _lz.get_collections() or []:
            if not isinstance(collection, dict):
                continue
            collection_id = str(
                collection.get("id") or collection.get("name") or ""
            ).strip()
            if not collection_id:
                continue
            for tool_type in _lz.get_tool_types(collection=collection_id) or []:
                if not isinstance(tool_type, dict):
                    continue
                type_id = str(tool_type.get("id") or tool_type.get("name") or "").strip()
                if not type_id:
                    continue
                if _lz.get_statuses(type_id, collection=collection_id):
                    return True
    except Exception:
        return False
    return False


def _install_missing_global_status_warning_guard() -> None:
    """Pomiń wyłącznie stary, fałszywy warning o globalnych statusach."""

    if getattr(_messagebox, "_wm_tools_status_warning_guard", False):
        return

    original_showwarning = _messagebox.showwarning

    def _showwarning(title, message, *args, **kwargs):
        text = str(message or "").strip()
        if (
            str(title or "").strip() == "Konfiguracja narzędzi"
            and text.startswith("Brak globalnych statusów narzędzi.")
            and _wm_has_defined_tool_statuses()
        ):
            try:
                print(
                    "[WM-DBG][NARZ] Pominięto fałszywy warning o globalnych statusach; "
                    "statusy istnieją w definicjach typów."
                )
            except Exception:
                pass
            return "ok"
        return original_showwarning(title, message, *args, **kwargs)

    _messagebox.showwarning = _showwarning
    _messagebox._wm_tools_status_warning_guard = True


_install_missing_global_status_warning_guard()

__all__ = ["ToolsPanelState", "STATE"]
