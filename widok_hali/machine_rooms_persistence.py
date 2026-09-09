# version: 1.0
"""Ochrona zapisu lokalizacji pomieszczeń przez istniejący callback Maszyn.

Renderer hali pracuje na rekordach widoku, natomiast callback starego modułu
potrafi po każdym zapisie przeładować ``rows_cache``. Przy seryjnej migracji
(np. po zmianie nazwy lub geometrii pomieszczenia) drugi rekord nie może więc
polegać na tym, że zmodyfikowany obiekt z widoku nadal jest tym samym obiektem
co rekord w cache. Ten adapter robi migawkę pól lokalizacji przed zapisem i
przenosi ją do istniejącego ``upsert_machine`` bez zmiany formatu danych.
"""
from __future__ import annotations

import logging
from typing import Any, MutableMapping, Optional

from .rooms import sync_location_fields

log = logging.getLogger(__name__)

_LOCATION_KEYS = ("lokalizacja", "lokalizacja_id", "placement_status")


def _machine_id(row: MutableMapping[str, Any]) -> str:
    return str(row.get("id") or row.get("nr_ewid") or "").strip()


def _location_signature(row: MutableMapping[str, Any]) -> tuple[object, object, object]:
    return tuple(row.get(key) for key in _LOCATION_KEYS)  # type: ignore[return-value]


def _location_patch(row: MutableMapping[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in _LOCATION_KEYS}


def install_machine_room_persistence(legacy_module) -> None:
    """Zainstaluj ochronę callbacka dokładnie raz."""
    if getattr(legacy_module, "_WM_ROOM_PERSISTENCE_INSTALLED", False):
        return

    base_renderer = legacy_module.MachineHallRenderer
    base_upsert = legacy_module.upsert_machine
    pending: dict[str, dict[str, Any]] = {}

    def upsert_with_location_snapshot(rows, new_row):
        candidate = dict(new_row or {})
        mid = _machine_id(candidate)
        patch = pending.get(mid)
        if patch:
            candidate.update(patch)
        return base_upsert(rows, candidate)

    class PersistenceSafeMachineHallRenderer(base_renderer):
        """Renderer z bezpiecznym mostem między widokiem i rows_cache."""

        def __init__(
            self,
            parent,
            rows,
            cfg=None,
            on_drag_commit=None,
            bg_path=None,
        ):
            self._wm_original_drag_commit = on_drag_commit
            super().__init__(
                parent,
                rows,
                cfg=cfg,
                on_drag_commit=self._wm_commit_with_current_location,
                bg_path=bg_path,
            )

        def _wm_row(self, mid: str) -> Optional[MutableMapping[str, Any]]:
            for row in self.rows or []:
                if isinstance(row, dict) and _machine_id(row) == mid:
                    return row
            return None

        def _wm_call_original_commit(
            self,
            mid: str,
            x: int,
            y: int,
            patch: Optional[dict[str, Any]] = None,
        ):
            callback = self._wm_original_drag_commit
            if not callable(callback):
                return None
            if patch:
                pending[mid] = dict(patch)
            try:
                return callback(mid, x, y)
            finally:
                pending.pop(mid, None)

        def _wm_commit_with_current_location(self, mid: str, x: int, y: int):
            row = self._wm_row(mid)
            patch = _location_patch(row) if row is not None else None
            return self._wm_call_original_commit(mid, x, y, patch)

        def _sync_and_persist_machine_locations(self) -> None:
            """Synchronizuj wiele rekordów bez utraty zmian po pierwszym reloadzie."""
            changes: list[tuple[str, int, int, dict[str, Any]]] = []

            # Najpierw obliczamy WSZYSTKIE zmiany i robimy ich migawkę. Dopiero
            # później uruchamiamy callbacki, które mogą przeładować self.rows.
            for row in list(self.rows or []):
                if not isinstance(row, dict):
                    continue
                before = _location_signature(row)
                sync_location_fields(row, self._rooms)
                if before == _location_signature(row):
                    continue
                mid = _machine_id(row)
                x, y = row.get("x"), row.get("y")
                if mid and isinstance(x, int) and isinstance(y, int):
                    changes.append((mid, x, y, _location_patch(row)))

            for mid, x, y, patch in changes:
                try:
                    self._wm_call_original_commit(mid, x, y, patch)
                except Exception:
                    log.exception(
                        "[Maszyny][HALL][ROOMS] Błąd seryjnego zapisu lokalizacji %s",
                        mid,
                    )

    PersistenceSafeMachineHallRenderer.__name__ = "MachineHallRenderer"
    PersistenceSafeMachineHallRenderer.__qualname__ = "MachineHallRenderer"

    legacy_module.upsert_machine = upsert_with_location_snapshot
    legacy_module.MachineHallRenderer = PersistenceSafeMachineHallRenderer
    legacy_module._WM_ROOM_LOCATION_PATCHES = pending
    legacy_module._WM_ROOM_PERSISTENCE_INSTALLED = True
    log.info("[Maszyny][HALL][ROOMS] Ochrona seryjnego zapisu aktywna")


__all__ = ["install_machine_room_persistence"]
