"""Obsługa zapisu i odczytu danych hal."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, Tuple

from utils.path_utils import cfg_path
from .const import HALLS_FILE as HALLS_NAME
from .models import Hala, Machine, WallSegment

try:
    # centralne pobieranie ścieżek z konfiguracji
    from config.paths import get_path
except Exception:  # pragma: no cover - fallback kiedy brak konfiguracji

    def get_path(key: str, default: str = "") -> str:
        """Awaryjnie zwróć wartość domyślną."""

        return default


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


# ---------- helpers ----------

def _read_json_list(path: str | None) -> List[Dict[str, Any]]:
    """Bezpiecznie wczytaj listę obiektów z pliku JSON."""

    if not path:
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    except FileNotFoundError:
        return []
    except Exception as exc:  # pragma: no cover - defensywnie logujemy błąd
        _log(f"[HALA][IO] Błąd odczytu {path}: {exc}")
    return []


def resolve_machines_file() -> Tuple[str | None, str]:
    """Ustal plik maszyn wraz z etykietą wariantu źródła."""

    explicit = get_path("hall.machines_file", "")
    layout_dir = get_path("paths.layout_dir", "")
    layout_default = os.path.join(layout_dir, "maszyny.json") if layout_dir else ""

    repo_97 = os.path.join(os.getcwd(), "data", "maszyny", "maszyny.json")
    repo_11 = os.path.join(os.getcwd(), "data", "maszyny.json")

    candidates = [
        ("hall.machines_file", explicit),
        ("paths.layout_dir/maszyny.json", layout_default),
        ("data/maszyny/maszyny.json", repo_97),
        ("data/maszyny.json", repo_11),
    ]
    for label, candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate, label
    return None, "missing"


def _resolve_machines_save_path() -> str:
    """Wybierz docelowy plik zapisu maszyn."""

    path, _ = resolve_machines_file()
    if path:
        return path

    explicit = get_path("hall.machines_file", "")
    if explicit:
        return explicit

    layout_dir = get_path("paths.layout_dir", "")
    if layout_dir:
        return os.path.join(layout_dir, "maszyny.json")

    # na końcu wracamy do repozytoryjnego domyślnego pliku
    return MACHINES_FILE


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


def load_machines() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Wczytaj listę maszyn oraz meta-dane źródła."""

    path, label = resolve_machines_file()
    rows = _read_json_list(path)
    meta: Dict[str, Any] = {"path": path, "label": label, "count": len(rows)}
    if not path:
        _log("[HALA][IO] Nie znaleziono pliku z maszynami")
    return rows, meta


def load_machines_models() -> List[Machine]:
    """Zwróć listę modeli :class:`Machine` na podstawie danych JSON."""

    rows, meta = load_machines()
    machines: List[Machine] = []
    source = meta.get("path") or MACHINES_FILE
    for item in rows:
        machine_id = str(item.get("id") or item.get("nr_ewid") or "").strip()
        missing = [
            key
            for key in ("nazwa", "hala", "x", "y", "status")
            if key not in item
        ]
        if missing or not machine_id:
            _log(
                f"[HALA][IO] Maszyna {item!r} brak pól {missing} lub id w {source}"
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
        except Exception as exc:  # pragma: no cover - defensywnie
            _log(f"[HALA][IO] Błąd tworzenia maszyny {machine_id}: {exc}")
    return machines


def save_machines(machines: Iterable[Machine]) -> None:
    """Zapisz listę maszyn do pliku ``maszyny.json``."""

    target = _resolve_machines_save_path()
    existing = _read_json_list(target)
    existing_map = {
        str(item.get("id") or item.get("nr_ewid")): dict(item)
        for item in existing
        if isinstance(item, dict)
    }

    for machine in machines:
        item = existing_map.get(machine.id, {})
        item.update(
            {
                "id": machine.id,
                "nazwa": machine.nazwa,
                "hala": machine.hala,
                "x": machine.x,
                "y": machine.y,
                "status": machine.status,
            }
        )
        existing_map[machine.id] = item

    directory = os.path.dirname(target)
    if directory:
        os.makedirs(directory, exist_ok=True)
    data = list(existing_map.values())
    try:
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        _log(f"[HALA][IO] Zapisano {len(data)} maszyn do {target}")
    except Exception as exc:  # pragma: no cover - defensive
        _log(f"[HALA][IO] Błąd zapisu {target}: {exc}")


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
            content = "\n".join(
                line for line in fh if not line.lstrip().startswith("#")
            )
            data = json.loads(content) if content.strip() else {}
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


def get_machines() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Zachowaj kompatybilność ze starszym API."""

    return load_machines()
