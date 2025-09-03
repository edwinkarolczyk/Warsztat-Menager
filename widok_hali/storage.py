"""Obsługa zapisu i odczytu danych hal."""

from __future__ import annotations

import json
import os
from typing import Iterable, List

from utils.path_utils import cfg_path
from .const import HALLS_FILE as HALLS_NAME
from .models import Hala, Machine, WallSegment

HALLS_FILE = cfg_path(os.path.join("data", HALLS_NAME))
MACHINES_FILE = cfg_path(os.path.join("data", "maszyny.json"))
WALLS_FILE = cfg_path(os.path.join("data", "sciany.json"))
AWARIE_FILE = cfg_path(os.path.join("data", "awarie.json"))
CONFIG_FILE = cfg_path("config.json")

try:  # pragma: no cover - logger may not exist in tests
    from logger import log_akcja as _log
except Exception:  # pragma: no cover - fallback for logger
    def _log(msg: str) -> None:
        print(msg)


def load_hale() -> List[Hala]:
    """Wczytaj listę hal z pliku JSON."""
    if not os.path.exists(HALLS_FILE):
        _log(f"[HALA][WARN] Brak pliku {HALLS_FILE}; tworzę pusty")
        with open(HALLS_FILE, "w", encoding="utf-8") as fh:
            json.dump([], fh, indent=2, ensure_ascii=False)
        return []

    try:
        with open(HALLS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[HALA][WARN] Błąd odczytu {HALLS_FILE}: {e}")
        return []

    hale: List[Hala] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            _log(f"[HALA][WARN] Pominięto rekord {i} – nie jest dict")
            continue
        missing = [k for k in ("nazwa", "x1", "y1", "x2", "y2") if k not in item]
        if missing:
            _log(f"[HALA][WARN] Rekord {i} bez kluczy {missing}")
            continue
        try:
            hale.append(Hala(**item))
        except Exception as e:  # pragma: no cover - defensive
            _log(f"[HALA][WARN] Rekord {i} nieprawidłowy: {e}")
    return hale


def save_hale(hale: List[Hala]) -> None:
    """Zapisz listę hal do pliku JSON."""
    try:
        with open(HALLS_FILE, "w", encoding="utf-8") as fh:
            json.dump(
                [h.__dict__ for h in hale], fh, indent=2, ensure_ascii=False
            )
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[HALA][WARN] Błąd zapisu {HALLS_FILE}: {e}")


def load_machines() -> List[Machine]:
    """Wczytaj listę maszyn z pliku ``maszyny.json``."""

    try:
        with open(MACHINES_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        _log(f"[HALA][IO] Brak pliku {MACHINES_FILE}; zwracam pustą listę")
        return []
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[HALA][IO] Błąd odczytu {MACHINES_FILE}: {e}")
        return []

    machines: List[Machine] = []
    if not isinstance(data, list):
        _log(f"[HALA][IO] {MACHINES_FILE} nie zawiera listy")
        return machines
    for item in data:
        if not isinstance(item, dict):
            _log("[HALA][IO] Pominięto rekord maszyny – nie jest dict")
            continue
        machine_id = str(item.get("id") or item.get("nr_ewid"))
        missing = [
            k
            for k in ("nazwa", "hala", "x", "y", "status")
            if k not in item
        ]
        if missing or not machine_id:
            _log(
                f"[HALA][IO] Maszyna {item!r} brak pól {missing} lub id"
            )
            continue
        try:
            machines.append(
                Machine(
                    id=machine_id,
                    nazwa=str(item.get("nazwa", "")),
                    hala=str(item.get("hala")),
                    x=int(item.get("x", 0)),
                    y=int(item.get("y", 0)),
                    status=str(item.get("status", "")),
                )
            )
        except Exception as e:  # pragma: no cover - defensive
            _log(f"[HALA][IO] Błąd tworzenia maszyny {machine_id}: {e}")
    return machines


def save_machines(machines: Iterable[Machine]) -> None:
    """Zapisz listę maszyn do pliku ``maszyny.json``."""

    try:
        if os.path.exists(MACHINES_FILE):
            with open(MACHINES_FILE, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
            if not isinstance(existing, list):
                existing = []
        else:
            existing = []
    except Exception:
        existing = []

    existing_map = {
        str(item.get("id") or item.get("nr_ewid")): item for item in existing
        if isinstance(item, dict)
    }

    for m in machines:
        item = existing_map.get(m.id, {})
        item.update(
            {
                "id": m.id,
                "nazwa": m.nazwa,
                "hala": m.hala,
                "x": m.x,
                "y": m.y,
                "status": m.status,
            }
        )
        existing_map[m.id] = item

    data = list(existing_map.values())
    try:
        with open(MACHINES_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        _log(f"[HALA][IO] Zapisano {len(data)} maszyn")
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[HALA][IO] Błąd zapisu {MACHINES_FILE}: {e}")


def load_walls() -> List[WallSegment]:
    """Wczytaj definicję ścian z pliku ``sciany.json``."""

    try:
        with open(WALLS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        _log(f"[HALA][IO] Brak pliku {WALLS_FILE}; tworzę pusty")
        with open(WALLS_FILE, "w", encoding="utf-8") as fh:
            json.dump([], fh, indent=2, ensure_ascii=False)
        return []
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[HALA][IO] Błąd odczytu {WALLS_FILE}: {e}")
        return []

    walls: List[WallSegment] = []
    if not isinstance(data, list):
        _log(f"[HALA][IO] {WALLS_FILE} nie zawiera listy")
        return walls
    for item in data:
        if not isinstance(item, dict):
            _log("[HALA][IO] Pominięto rekord ściany – nie jest dict")
            continue
        missing = [k for k in ("hala", "x1", "y1", "x2", "y2") if k not in item]
        if missing:
            _log(f"[HALA][IO] Ściana {item!r} brak pól {missing}")
            continue
        try:
            walls.append(WallSegment(**{k: item[k] for k in ("hala", "x1", "y1", "x2", "y2")}))
        except Exception as e:  # pragma: no cover - defensive
            _log(f"[HALA][IO] Błąd tworzenia ściany: {e}")
    return walls


def load_config_hala() -> dict:
    """Wczytaj konfigurację sekcji ``hala`` z ``config.json``."""

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[HALA][IO] Błąd odczytu {CONFIG_FILE}: {e}")
        return {}
    return data.get("hala", {})


def load_awarie() -> List[dict]:
    """Wczytaj listę awarii maszyn."""

    try:
        with open(AWARIE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        _log(f"[HALA][IO] Brak pliku {AWARIE_FILE}; tworzę pusty")
        with open(AWARIE_FILE, "w", encoding="utf-8") as fh:
            json.dump([], fh, indent=2, ensure_ascii=False)
        return []
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[HALA][IO] Błąd odczytu {AWARIE_FILE}: {e}")
        return []

    if not isinstance(data, list):
        _log(f"[HALA][IO] {AWARIE_FILE} nie zawiera listy")
        return []
    return data


def save_awarie(entries: Iterable[dict]) -> None:
    """Zapisz listę awarii do ``awarie.json``."""

    data = [e for e in entries if isinstance(e, dict)]
    try:
        with open(AWARIE_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        _log(f"[HALA][IO] Zapisano {len(data)} awarii")
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[HALA][IO] Błąd zapisu {AWARIE_FILE}: {e}")
