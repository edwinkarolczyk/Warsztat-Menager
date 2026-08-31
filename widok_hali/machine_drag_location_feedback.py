# version: 1.0
"""Informacja o lokalizacji po drag&drop maszyny na planie hali.

Warstwa jest instalowana jako ostatnia, po adapterach pomieszczeń i widoku
Użytkowanie maszyny. Nie zmienia bazowego modułu Maszyn: dodaje tylko komunikat
w istniejącym pasku statusu hali i rozstrzyga konflikt pomiędzy jawnym dragiem
a ochroną przed starym ``rows_cache``.
"""
from __future__ import annotations

from typing import Any, MutableMapping, Optional


def _machine_id(row: MutableMapping[str, Any]) -> str:
    return str(row.get("id") or row.get("nr_ewid") or row.get("nr") or "").strip()


def _row_for_machine(rows, machine_id: str) -> Optional[MutableMapping[str, Any]]:
    target = str(machine_id or "").strip()
    for row in rows or []:
        if isinstance(row, dict) and _machine_id(row) == target:
            return row
    return None


def _display_location(row: Optional[MutableMapping[str, Any]]) -> str:
    if row is None:
        return "Brak lokalizacji"
    value = str(row.get("lokalizacja") or "").strip()
    if not value or value.casefold() == "brak lokalizacji":
        return "Brak lokalizacji"
    return value


def install_machine_drag_location_feedback(legacy_module) -> None:
    """Dodaj symetryczne przypisanie/odpinanie lokalizacji i komunikat po dropie."""
    if getattr(legacy_module, "_WM_DRAG_LOCATION_FEEDBACK_INSTALLED", False):
        return

    base_upsert = legacy_module.upsert_machine
    base_renderer = legacy_module.MachineHallRenderer

    def upsert_with_explicit_drag_priority(rows, new_row):
        """Jawny drag ma pierwszeństwo przed strażnikiem starego rows_cache.

        Warstwa persistence ustawia wpis w ``_WM_ROOM_LOCATION_PATCHES`` tuż
        przed wywołaniem callbacka zapisu. To jednoznacznie oznacza, że zmiana
        lokalizacji pochodzi z aktualnego drag&drop, a nie ze starej kopii
        rekordu. W takim przypadku usuwamy historyczny override z okna
        Użytkowanie i pozwalamy persistence wstrzyknąć świeży patch.
        """
        candidate = dict(new_row or {})
        mid = _machine_id(candidate)
        pending = getattr(legacy_module, "_WM_ROOM_LOCATION_PATCHES", {})
        if mid and isinstance(pending, dict) and mid in pending:
            overrides = getattr(legacy_module, "_WM_USAGE_LOCATION_OVERRIDES", {})
            if isinstance(overrides, dict):
                overrides.pop(mid, None)
        return base_upsert(rows, candidate)

    class DragLocationFeedbackRenderer(base_renderer):
        def _on_release(self, event):
            layout_edit = bool(getattr(self, "_layout_edit", False))
            drag_active = bool(getattr(self, "_drag_active", False))
            mid = str(getattr(self, "_drag_id", "") or "").strip()
            is_machine_drop = bool(mid and drag_active and not layout_edit)
            before_row = _row_for_machine(getattr(self, "rows", []), mid)
            before_location = _display_location(before_row)

            result = super()._on_release(event)

            if not is_machine_drop:
                return result

            after_row = _row_for_machine(getattr(self, "rows", []), mid)
            after_location = _display_location(after_row)
            status_var = getattr(self, "_status_var", None)
            if status_var is not None:
                try:
                    if before_location != after_location:
                        status_var.set(f"Maszyna {mid} → {after_location}")
                    else:
                        status_var.set(f"Maszyna {mid}: {after_location}")
                except Exception:
                    pass
            return result

    DragLocationFeedbackRenderer.__name__ = "MachineHallRenderer"
    DragLocationFeedbackRenderer.__qualname__ = "MachineHallRenderer"

    legacy_module.upsert_machine = upsert_with_explicit_drag_priority
    legacy_module.MachineHallRenderer = DragLocationFeedbackRenderer
    legacy_module._WM_DRAG_LOCATION_FEEDBACK_INSTALLED = True


__all__ = [
    "_display_location",
    "install_machine_drag_location_feedback",
]
