from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import json
import logging
from datetime import datetime, timezone


# Ścieżki używane przez moduł
MAGAZYN_PATH = Path("data/magazyn/magazyn.json")
PRZYJECIA_PATH = Path("data/magazyn/przyjecia.json")
STANY_PATH = Path("data/magazyn/stany.json")
KATALOG_PATH = Path("data/magazyn/katalog.json")
HISTORY_PATH = Path("data/magazyn/historia.json")
SEQ_PZ_PATH = Path("data/magazyn/_seq_pz.json")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load(path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Ładuje pełną strukturę magazynu z opcjonalnej ścieżki."""
    p = Path(path) if path else MAGAZYN_PATH
    if not p.exists():
        return {"items": {}, "meta": {}}
    try:
        txt = p.read_text(encoding="utf-8")
        data = json.loads(txt) if txt.strip() else {"items": {}, "meta": {}}
        if not isinstance(data, dict):
            logging.error("Niepoprawny format JSON")
            return {"items": {}, "meta": {}}
        data.setdefault("items", {})
        data.setdefault("meta", {})
        return data
    except json.JSONDecodeError:
        logging.error("Niepoprawny format JSON")
        return {"items": {}, "meta": {}}


def save(data: Dict[str, Any], path: Optional[str | Path] = None) -> None:
    """Zapisuje pełną strukturę magazynu."""
    if not isinstance(data, dict):
        raise ValueError("magazyn_io.save: oczekiwano dict")
    data.setdefault("items", {})
    data.setdefault("meta", {})
    p = Path(path) if path else MAGAZYN_PATH
    _ensure_parent(p)
    p.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def append_history(
    items: Dict[str, Any],
    item_id: str,
    user: str,
    op: str,
    qty: float,
    komentarz: Optional[str] = None,
    *,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    """Dodaje wpis historii do elementu magazynu i pliku historii."""
    txt = komentarz if komentarz is not None else comment
    entry = {
        "user": user or "",
        "op": op,
        "qty": float(qty or 0),
        "comment": (txt or "").strip(),
    }

    it = items.setdefault(item_id, {})
    hist = it.setdefault("historia", [])
    hist.append(entry)

    path = Path(HISTORY_PATH)
    _ensure_parent(path)
    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content) if content.strip() else []
    except FileNotFoundError:
        data = []
    except json.JSONDecodeError:
        data = []
    data.append(entry)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return entry


def generate_pz_id(now: Optional[datetime] = None) -> str:
    """Zwraca nowy numer PZ i aktualizuje licznik."""
    now = now or datetime.now(timezone.utc)
    year = str(now.year)
    path = Path(SEQ_PZ_PATH)
    _ensure_parent(path)
    try:
        txt = path.read_text(encoding="utf-8")
        seq_data = json.loads(txt) if txt.strip() else {}
    except FileNotFoundError:
        seq_data = {}
    except json.JSONDecodeError:
        seq_data = {}
    seq = int(seq_data.get(year, 0)) + 1
    seq_data[year] = seq
    path.write_text(
        json.dumps(seq_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return f"PZ/{year}/{seq:04d}"


def save_pz(data: Dict[str, Any]) -> str:
    """Zapisuje przyjęcie z magazynu i zwraca numer PZ."""
    pz_id = generate_pz_id()
    entry = {"pz_id": pz_id, **data}
    path = Path(PRZYJECIA_PATH)
    _ensure_parent(path)
    try:
        txt = path.read_text(encoding="utf-8")
        pz_list = json.loads(txt) if txt.strip() else []
    except FileNotFoundError:
        pz_list = []
    except json.JSONDecodeError:
        pz_list = []
    pz_list.append(entry)
    path.write_text(
        json.dumps(pz_list, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logging.info("[INFO] Zapisano PZ %s", pz_id)
    return pz_id


def update_stany_after_pz(pz: Dict[str, Any]) -> None:
    """Aktualizuje stany magazynowe po przyjęciu."""
    item_id = pz.get("item_id")
    qty = float(pz.get("qty", 0))
    path = Path(STANY_PATH)
    _ensure_parent(path)
    try:
        txt = path.read_text(encoding="utf-8")
        stany = json.loads(txt) if txt.strip() else {}
    except FileNotFoundError:
        stany = {}
    except json.JSONDecodeError:
        stany = {}
    new_qty = float(stany.get(item_id, 0)) + qty
    stany[item_id] = new_qty
    path.write_text(
        json.dumps(stany, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logging.info("[INFO] Zaktualizowano stan %s: %s", item_id, new_qty)


def ensure_in_katalog(item: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Dodaje pozycję do katalogu jeśli jej brak."""
    item_id = item.get("item_id")
    if not item_id:
        return None
    path = Path(KATALOG_PATH)
    _ensure_parent(path)
    try:
        txt = path.read_text(encoding="utf-8")
        katalog = json.loads(txt) if txt.strip() else {}
    except FileNotFoundError:
        katalog = {}
    except json.JSONDecodeError:
        katalog = {}
    if item_id in katalog:
        existing = katalog[item_id]
        unit_old = existing.get("jednostka")
        unit_new = item.get("jednostka")
        if unit_old and unit_new and unit_old != unit_new:
            return {
                "warning": f"Jednostka różni się: katalog={unit_old}, PZ={unit_new}",
            }
        return None
    katalog[item_id] = {
        "nazwa": item.get("nazwa", ""),
        "jednostka": item.get("jednostka", ""),
    }
    path.write_text(
        json.dumps(katalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return None

