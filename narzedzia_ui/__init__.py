# version: 2.0
# Zmiany 2.0:
# - Podłączono narzędzia wieloetapowe (maks. 6 etapów), większy numer w nagłówku
#   oraz przywrócono podpowiedź wolnego numeru przy dodawaniu NN/SN.
# Zmiany 1.9:
# - Podłączono odchudzenie nowego dashboardu NN/SN, usunięcie fioletu i poprawę obsługi zdjęć.
# Zmiany 1.8:
# - Podłączono pełny dashboard nowego edytora NN/SN i strażnika zgodności ze starszym runtime'em okna.
# Zmiany 1.7:
# - Podłączono uproszczoną konwersję NN -> SN: zostaje tylko checkbox przeniesienia, zadania są zachowywane.
# Zmiany 1.6:
# - Zawersjonowano integrację przełączanego edytora NN/SN po podpięciu wariantu z miniaturą.
# Zmiany 1.5:
# - Podłączono opcjonalny nowy widok edytora NN/SN z kartą i miniaturą; klasyczny widok pozostaje dostępny.
# Zmiany 1.4:
# - START wizyty narzędzia zachowuje bieżące zadania; lista jest czyszczona dopiero przy prawidłowym STOP.
# Zmiany 1.3:
# - Podłączono precyzyjne poprawki głównego edytora narzędzi NN/SN.
# Zmiany 1.2:
# - Łączny czas wizyt i czas ostatniej wizyty pokazują minuty zamiast zaokrąglać
#   każdy czas poniżej godziny do 1h.
# Zmiany 1.1:
# - Nie pokazuj ostrzeżenia o braku globalnych statusów narzędzi, gdy aktualne definicje
#   typów narzędzi zawierają statusy. Ostrzeżenia o realnym braku statusów dla
#   konkretnego typu pozostają bez zmian.
"""Pakiet pomocniczy dla modułu GUI narzędzi."""

from __future__ import annotations

from tkinter import messagebox as _messagebox

from .state import ToolsPanelState, STATE
from .editor_runtime import install_tools_editor_runtime
from .visit_tasks_runtime import install_visit_tasks_runtime
from .editor_variant_runtime import install_tools_editor_variant_runtime
from .editor_variant_guard_runtime import install_editor_variant_guard_runtime
from .editor_variant_tuning_runtime import install_editor_variant_tuning_runtime
from .multistage_runtime import install_multistage_runtime
from .conversion_runtime import install_tools_conversion_runtime


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


def _install_precise_visit_duration_formatter() -> None:
    """Podmień wyłącznie formatter czasu wizyt używany przez listę Narzędzi."""

    try:
        from . import list_panel as _list_panel
    except Exception:
        return

    if getattr(_list_panel, "_wm_precise_visit_duration_installed", False):
        return

    def _precise_duration(seconds: float) -> str:
        try:
            total_seconds = max(0.0, float(seconds or 0))
        except (TypeError, ValueError):
            total_seconds = 0.0

        total_minutes = int(total_seconds // 60)
        if total_minutes < 60:
            return f"{total_minutes}m"

        hours = total_minutes // 60
        minutes = total_minutes % 60
        if hours < 24:
            return f"{hours}h {minutes:02d}m" if minutes else f"{hours}h"

        days = hours // 24
        rem_hours = hours % 24
        if days < 30:
            return f"{days}d {rem_hours}h" if rem_hours else f"{days}d"

        months = days // 30
        rem_days = days % 30
        if months < 12:
            return f"{months} mies. {rem_days}d" if rem_days else f"{months} mies."

        years = months // 12
        rem_months = months % 12
        return f"{years}r {rem_months} mies." if rem_months else f"{years}r"

    _list_panel._human_duration_from_seconds = _precise_duration
    _list_panel._wm_precise_visit_duration_installed = True


_install_missing_global_status_warning_guard()
_install_precise_visit_duration_formatter()
install_tools_editor_runtime()
install_visit_tasks_runtime()
install_editor_variant_guard_runtime()
install_tools_editor_variant_runtime()
install_editor_variant_tuning_runtime()
install_multistage_runtime()
install_tools_conversion_runtime()

__all__ = ["ToolsPanelState", "STATE"]
