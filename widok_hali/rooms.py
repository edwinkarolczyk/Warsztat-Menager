# version: 1.1
"""Pomieszczenia i lokalizacje dla widoku hali WM.

Geometria jest zapisywana w układzie współrzędnych tła planu (piksele obrazu),
nie we współrzędnych aktualnego okna Tkinter. Dzięki temu zmiana rozmiaru okna
nie przesuwa maszyn ani pomieszczeń względem planu.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import shutil
import tempfile
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Sequence

from utils.path_utils import cfg_path

SCHEMA_VERSION = 1
ROOMS_FILE = cfg_path(os.path.join("data", "pomieszczenia_hali.json"))
NON_SPATIAL_LOCATIONS = (
    "Serwis zewnętrzny",
    "Poza zakładem",
    "Magazyn zewnętrzny",
    "Brak lokalizacji",
)


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def normalize_room_name(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def room_name_key(value: object) -> str:
    return normalize_room_name(value).casefold()


def normalize_hall_id(value: object) -> str:
    text = str(value or "").strip()
    return text or "1"


@dataclass
class Room:
    id: str
    name: str
    polygon: list[tuple[int, int]]
    hala: str = "1"
    active: bool = True

    @classmethod
    def from_dict(cls, item: Mapping[str, Any]) -> "Room":
        room_id = str(item.get("id") or "").strip()
        name = normalize_room_name(item.get("name") or item.get("nazwa"))
        hala = normalize_hall_id(item.get("hala") or item.get("nr_hali"))
        raw_polygon = item.get("polygon") or item.get("punkty") or []
        polygon: list[tuple[int, int]] = []
        if isinstance(raw_polygon, Sequence) and not isinstance(raw_polygon, (str, bytes)):
            for point in raw_polygon:
                if (
                    isinstance(point, Sequence)
                    and not isinstance(point, (str, bytes))
                    and len(point) >= 2
                ):
                    polygon.append((_as_int(point[0]), _as_int(point[1])))
        return cls(
            id=room_id,
            name=name,
            polygon=polygon,
            hala=hala,
            active=bool(item.get("active", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "hala": self.hala,
            "polygon": [[int(x), int(y)] for x, y in self.polygon],
            "active": bool(self.active),
        }


def next_room_id(rooms: Iterable[Room]) -> str:
    highest = 0
    used: set[str] = set()
    for room in rooms:
        rid = str(room.id or "").strip().upper()
        used.add(rid)
        if rid.startswith("POM_"):
            try:
                highest = max(highest, int(rid.split("_", 1)[1]))
            except (TypeError, ValueError):
                pass
    candidate = highest + 1
    while f"POM_{candidate:04d}" in used:
        candidate += 1
    return f"POM_{candidate:04d}"


def validate_room(room: Room, *, existing: Iterable[Room] = ()) -> None:
    if not room.id.strip():
        raise ValueError("Pomieszczenie nie ma ID.")
    if not room.name.strip():
        raise ValueError("Pomieszczenie nie ma nazwy.")
    if len(room.polygon) < 3:
        raise ValueError("Pomieszczenie musi mieć co najmniej 3 punkty.")
    key = room_name_key(room.name)
    for other in existing:
        if other.id != room.id and room_name_key(other.name) == key:
            raise ValueError(f'Pomieszczenie o nazwie "{room.name}" już istnieje.')


def load_rooms(path: str | None = None) -> list[Room]:
    target = path or ROOMS_FILE
    try:
        with open(target, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        return []
    except Exception:
        return []

    if isinstance(payload, dict):
        raw_rooms = payload.get("rooms", [])
    elif isinstance(payload, list):
        # kompatybilność z ewentualnym wcześniejszym formatem listowym
        raw_rooms = payload
    else:
        raw_rooms = []

    rooms: list[Room] = []
    if not isinstance(raw_rooms, list):
        return rooms
    for item in raw_rooms:
        if not isinstance(item, dict):
            continue
        room = Room.from_dict(item)
        try:
            validate_room(room, existing=rooms)
        except ValueError:
            continue
        rooms.append(room)
    return rooms


def save_rooms(rooms: Iterable[Room], path: str | None = None) -> None:
    target = os.path.normpath(path or ROOMS_FILE)
    rows = list(rooms)
    checked: list[Room] = []
    for room in rows:
        validate_room(room, existing=checked)
        checked.append(room)

    directory = os.path.dirname(target) or "."
    os.makedirs(directory, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "coordinate_space": "background_px",
        "rooms": [room.to_dict() for room in rows],
    }

    fd, tmp_path = tempfile.mkstemp(
        prefix=".pomieszczenia_hali_",
        suffix=".tmp",
        dir=directory,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass

        if os.path.isfile(target):
            backup = target + ".bak"
            try:
                shutil.copy2(target, backup)
            except OSError:
                pass
        os.replace(tmp_path, target)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def room_by_id(rooms: Iterable[Room], room_id: object) -> Optional[Room]:
    target = str(room_id or "").strip()
    if not target:
        return None
    return next((room for room in rooms if room.active and room.id == target), None)


def room_by_name(rooms: Iterable[Room], name: object) -> Optional[Room]:
    key = room_name_key(name)
    if not key:
        return None
    return next(
        (room for room in rooms if room.active and room_name_key(room.name) == key),
        None,
    )


def _point_on_segment(
    x: float,
    y: float,
    a: tuple[int, int],
    b: tuple[int, int],
    tolerance: float = 1e-6,
) -> bool:
    x1, y1 = a
    x2, y2 = b
    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    if abs(cross) > tolerance * max(1.0, abs(x2 - x1) + abs(y2 - y1)):
        return False
    return (
        min(x1, x2) - tolerance <= x <= max(x1, x2) + tolerance
        and min(y1, y2) - tolerance <= y <= max(y1, y2) + tolerance
    )


def point_in_polygon(x: float, y: float, polygon: Sequence[tuple[int, int]]) -> bool:
    """Zwróć True również dla punktu leżącego dokładnie na krawędzi."""
    if len(polygon) < 3:
        return False

    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if _point_on_segment(x, y, (xj, yj), (xi, yi)):
            return True
        intersects = (yi > y) != (yj > y)
        if intersects:
            cross_x = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < cross_x:
                inside = not inside
        j = i
    return inside


def room_at_point(
    rooms: Iterable[Room],
    x: object,
    y: object,
    *,
    hala: object | None = None,
) -> Optional[Room]:
    px = _as_int(x)
    py = _as_int(y)
    hall_key = normalize_hall_id(hala) if hala not in (None, "") else None
    # odwrócona kolejność: ostatnio zapisany obrys jest "na wierzchu"
    candidates = list(rooms)
    for room in reversed(candidates):
        if not room.active:
            continue
        if hall_key is not None and normalize_hall_id(room.hala) != hall_key:
            continue
        if point_in_polygon(px, py, room.polygon):
            return room
    return None


def location_values(
    rooms: Iterable[Room],
    *,
    legacy_values: Iterable[object] = (),
    hala: object | None = None,
) -> tuple[str, ...]:
    hall_key = normalize_hall_id(hala) if hala not in (None, "") else None
    values: list[str] = []
    seen: set[str] = set()

    def add(value: object) -> None:
        text = normalize_room_name(value)
        key = room_name_key(text)
        if text and key not in seen:
            seen.add(key)
            values.append(text)

    for room in rooms:
        if room.active and (hall_key is None or normalize_hall_id(room.hala) == hall_key):
            add(room.name)
    for value in NON_SPATIAL_LOCATIONS:
        add(value)
    for value in legacy_values:
        add(value)
    return tuple(values)


def sync_location_fields(
    record: MutableMapping[str, Any],
    rooms: Iterable[Room],
) -> MutableMapping[str, Any]:
    """Ujednolić ID/nazwę lokalizacji bez kasowania starych danych."""
    room_list = list(rooms)
    hall = record.get("nr_hali") or record.get("hala") or "1"
    room = room_by_id(room_list, record.get("lokalizacja_id"))
    display = normalize_room_name(record.get("lokalizacja"))
    special_keys = {room_name_key(value) for value in NON_SPATIAL_LOCATIONS}

    # Jawny wybór zewnętrznej lokalizacji ma pierwszeństwo przed starym ID.
    if display and room_name_key(display) in special_keys:
        record["lokalizacja_id"] = ""
        record["lokalizacja"] = display
        record["placement_status"] = "external"
        return record

    # Jawnie wybrana nazwa istniejącego pomieszczenia również ma pierwszeństwo
    # przed ewentualnym nieaktualnym ID (np. po zmianie pola w formularzu).
    if display:
        candidate = room_by_name(room_list, display)
        if candidate is not None and normalize_hall_id(candidate.hala) == normalize_hall_id(hall):
            room = candidate

    if room is None and not display:
        x, y = record.get("x"), record.get("y")
        if x is not None and y is not None:
            room = room_at_point(room_list, x, y, hala=hall)

    if room is not None:
        record["lokalizacja_id"] = room.id
        record["lokalizacja"] = room.name
        x, y = record.get("x"), record.get("y")
        if x is None or y is None:
            record["placement_status"] = "unplaced"
        elif point_in_polygon(_as_int(x), _as_int(y), room.polygon):
            record["placement_status"] = "placed"
        else:
            record["placement_status"] = "outside_room"
        return record

    record["lokalizacja_id"] = ""
    if display:
        record["lokalizacja"] = display
        if room_name_key(display) in {room_name_key(x) for x in NON_SPATIAL_LOCATIONS}:
            record["placement_status"] = "external"
        else:
            record["placement_status"] = "legacy"
    else:
        record["placement_status"] = "unplaced"
    return record


def sync_record_from_point(
    record: MutableMapping[str, Any],
    x: object,
    y: object,
    rooms: Iterable[Room],
) -> MutableMapping[str, Any]:
    """Synchronizuj pozycję po drag&drop z pomieszczeniem pod punktem.

    Drag&drop jest źródłem prawdy dla położenia na planie: punkt wewnątrz
    pomieszczenia przypisuje je do maszyny, a punkt poza wszystkimi
    pomieszczeniami czyści przypisanie i oznacza maszynę jako nieumieszczoną.
    """
    px, py = _as_int(x), _as_int(y)
    record["x"], record["y"] = px, py
    hall = record.get("nr_hali") or record.get("hala") or "1"
    room = room_at_point(rooms, px, py, hala=hall)
    if room is None:
        record["lokalizacja_id"] = ""
        record["lokalizacja"] = ""
        record["placement_status"] = "unplaced"
        return record
    record["lokalizacja_id"] = room.id
    record["lokalizacja"] = room.name
    record["placement_status"] = "placed"
    return record


def room_wall_segments(room: Room) -> list[tuple[int, int, int, int]]:
    points = room.polygon
    if len(points) < 3:
        return []
    out: list[tuple[int, int, int, int]] = []
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        out.append((x1, y1, x2, y2))
    return out


__all__ = [
    "NON_SPATIAL_LOCATIONS",
    "ROOMS_FILE",
    "Room",
    "load_rooms",
    "location_values",
    "next_room_id",
    "normalize_room_name",
    "point_in_polygon",
    "room_at_point",
    "room_by_id",
    "room_by_name",
    "room_wall_segments",
    "save_rooms",
    "sync_location_fields",
    "sync_record_from_point",
    "validate_room",
]
