# version: 1.0
"""Drobne kontrolki UX dla pomieszczeń w module Maszyny.

Warstwa jest instalowana po istniejącym rozszerzeniu pomieszczeń i ochronie
zapisu. Nie zmienia starego formularza ani renderera w miejscu; rozszerza je
przez adapter ttk, wrapper upsert oraz podklasę renderera.
"""
from __future__ import annotations

import math
import weakref
from typing import Any, MutableMapping, Optional

from .rooms import (
    Room,
    load_rooms,
    location_values,
    point_in_polygon,
    room_by_id,
    room_by_name,
    sync_location_fields,
)


def _machine_id(row: MutableMapping[str, Any]) -> str:
    return str(row.get("id") or row.get("nr_ewid") or "").strip()


def _room_for_record(row: MutableMapping[str, Any], rooms: list[Room]) -> Optional[Room]:
    room = room_by_id(rooms, row.get("lokalizacja_id"))
    if room is not None:
        return room
    return room_by_name(rooms, row.get("lokalizacja"))


def _candidate_room_points(room: Room) -> list[tuple[int, int]]:
    xs = [x for x, _ in room.polygon]
    ys = [y for _, y in room.polygon]
    if not xs or not ys:
        return []

    cx = int(round(sum(xs) / len(xs)))
    cy = int(round(sum(ys) / len(ys)))
    candidates: list[tuple[int, int]] = []
    if point_in_polygon(cx, cy, room.polygon):
        candidates.append((cx, cy))

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max(1, max_x - min_x)
    height = max(1, max_y - min_y)
    step = max(20, min(80, max(20, min(width, height) // 8)))

    y = min_y + max(5, step // 2)
    while y < max_y:
        x = min_x + max(5, step // 2)
        while x < max_x:
            if point_in_polygon(x, y, room.polygon):
                candidates.append((int(x), int(y)))
            x += step
        y += step

    # Najpierw punkty najbliżej środka pomieszczenia.
    unique = list(dict.fromkeys(candidates))
    unique.sort(key=lambda point: math.hypot(point[0] - cx, point[1] - cy))
    return unique


def _find_free_room_point(
    room: Room,
    rows,
    *,
    exclude_machine_id: str = "",
) -> Optional[tuple[int, int]]:
    occupied: list[tuple[int, int]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if exclude_machine_id and _machine_id(row) == exclude_machine_id:
            continue
        x, y = row.get("x"), row.get("y")
        if isinstance(x, int) and isinstance(y, int):
            occupied.append((x, y))

    candidates = _candidate_room_points(room)
    if not candidates:
        return None

    # W pierwszej kolejności szukamy wyraźnie wolnego miejsca; gdy pomieszczenie
    # jest ciasne, stopniowo zmniejszamy wymagany odstęp zamiast odmawiać zapisu.
    for minimum_distance in (70.0, 50.0, 35.0, 20.0, 0.0):
        for x, y in candidates:
            if all(math.hypot(x - ox, y - oy) >= minimum_distance for ox, oy in occupied):
                return x, y
    return candidates[0]


def _make_location_ttk_proxy(wrapped_ttk, values_provider):
    real_ttk = getattr(wrapped_ttk, "_real", wrapped_ttk)

    class RoomLocationCombobox(real_ttk.Combobox):
        """Readonly combobox zgodny z row_entry(), które inicjalizuje przez insert()."""

        def __init__(self, master=None, *args, **kwargs):
            kwargs = dict(kwargs)
            kwargs["state"] = "readonly"
            kwargs["values"] = tuple(values_provider())
            kwargs["postcommand"] = self._refresh_values
            super().__init__(master, *args, **kwargs)

        def _refresh_values(self) -> None:
            current = self.get().strip()
            values = list(values_provider())
            if current and current not in values:
                values.append(current)
            self.configure(values=tuple(values))

        def insert(self, index, string):  # zgodność z ttk.Entry użytym przez row_entry
            value = str(string or "")
            values = list(values_provider())
            if value and value not in values:
                values.append(value)
            self.configure(state="normal", values=tuple(values))
            try:
                super().delete(0, "end")
                super().insert(index, value)
            finally:
                self.configure(state="readonly")

    class LocationTtkProxy:
        def __init__(self):
            self._wrapped = wrapped_ttk
            self._real = real_ttk
            self._entry_counts: "weakref.WeakKeyDictionary[object, int]" = (
                weakref.WeakKeyDictionary()
            )

        def __getattr__(self, name: str):
            return getattr(self._wrapped, name)

        @staticmethod
        def _is_machine_edit_form(master) -> bool:
            if master is None:
                return False
            try:
                top = master.winfo_toplevel()
                return str(top.title() or "") == "Edycja maszyny" and master.master is top
            except Exception:
                return False

        def Entry(self, master=None, *args, **kwargs):  # noqa: N802
            if self._is_machine_edit_form(master):
                count = int(self._entry_counts.get(master, 0)) + 1
                self._entry_counts[master] = count
                # row_entry: ID, Nazwa, Typ, Lokalizacja, x, y
                if count == 4:
                    return RoomLocationCombobox(master, *args, **kwargs)
                # Nie delegujemy tych pięciu pól do poprzedniego proxy, żeby
                # jego licznik nie przesunął Lokalizacji na pole x/y.
                return real_ttk.Entry(master, *args, **kwargs)
            return self._wrapped.Entry(master, *args, **kwargs)

    return LocationTtkProxy()


def install_machine_room_ui(legacy_module) -> None:
    """Zainstaluj jawny wybór pomieszczenia i kontrolki tła/siatki."""
    if getattr(legacy_module, "_WM_ROOM_UI_INSTALLED", False):
        return

    base_renderer = legacy_module.MachineHallRenderer
    base_upsert = legacy_module.upsert_machine
    wrapped_ttk = legacy_module.ttk
    tk = legacy_module.tk
    real_ttk = getattr(wrapped_ttk, "_real", wrapped_ttk)

    def values_provider() -> tuple[str, ...]:
        return location_values(load_rooms())

    def upsert_with_room_relocation(rows, new_row):
        candidate = dict(new_row or {})
        mid = _machine_id(candidate)
        existing = next(
            (
                row
                for row in rows or []
                if isinstance(row, dict) and _machine_id(row) == mid
            ),
            None,
        )
        rooms = load_rooms()

        # Formularz zapisuje nazwę Lokalizacji. Zamieniamy ją na stabilne ID
        # jeszcze przed dotychczasowym upsert-em.
        if "lokalizacja" in candidate or "lokalizacja_id" in candidate:
            sync_location_fields(candidate, rooms)

        new_room = _room_for_record(candidate, rooms)
        old_room = _room_for_record(existing, rooms) if isinstance(existing, dict) else None
        room_changed = bool(
            new_room is not None
            and (old_room is None or old_room.id != new_room.id)
        )

        if room_changed and new_room is not None:
            x, y = candidate.get("x"), candidate.get("y")
            already_inside = (
                isinstance(x, int)
                and isinstance(y, int)
                and point_in_polygon(x, y, new_room.polygon)
            )
            if not already_inside:
                point = _find_free_room_point(
                    new_room,
                    rows,
                    exclude_machine_id=mid,
                )
                if point is not None:
                    candidate["x"], candidate["y"] = point
                    candidate["lokalizacja_id"] = new_room.id
                    candidate["lokalizacja"] = new_room.name
                    candidate["placement_status"] = "placed"

        return base_upsert(rows, candidate)

    class MachineHallRendererWithViewControls(base_renderer):
        """Istniejący renderer plus niezależne przełączniki JPG i siatki."""

        def _build_room_toolbar(self) -> None:
            super()._build_room_toolbar()
            self._show_background_var = tk.BooleanVar(master=self.parent, value=True)
            self._show_grid_var = tk.BooleanVar(master=self.parent, value=True)
            real_ttk.Checkbutton(
                self._toolbar,
                text="Tło JPG",
                variable=self._show_background_var,
                command=self._wm_refresh_visibility,
            ).pack(side="left", padx=(8, 2))
            real_ttk.Checkbutton(
                self._toolbar,
                text="Siatka",
                variable=self._show_grid_var,
                command=self._wm_refresh_visibility,
            ).pack(side="left", padx=2)

        def _wm_refresh_visibility(self) -> None:
            self._draw_all()

        def _draw_background_and_grid(self) -> None:
            super()._draw_background_and_grid()
            if not bool(self._show_background_var.get()):
                try:
                    self.canvas.itemconfigure("hall-background", state="hidden")
                except Exception:
                    pass
            if not bool(self._show_grid_var.get()):
                for tag in ("hall-grid", "hall-border"):
                    try:
                        self.canvas.itemconfigure(tag, state="hidden")
                    except Exception:
                        pass

    MachineHallRendererWithViewControls.__name__ = "MachineHallRenderer"
    MachineHallRendererWithViewControls.__qualname__ = "MachineHallRenderer"

    legacy_module.upsert_machine = upsert_with_room_relocation
    legacy_module.ttk = _make_location_ttk_proxy(wrapped_ttk, values_provider)
    legacy_module.MachineHallRenderer = MachineHallRendererWithViewControls
    legacy_module._WM_ROOM_UI_INSTALLED = True


__all__ = [
    "_find_free_room_point",
    "install_machine_room_ui",
]
