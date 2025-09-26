"""I/O helpers for warehouse history."""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict
import logging

try:
    import logger

    _log_mag = getattr(
        logger, "log_magazyn", lambda a, d: logging.info(f"[MAGAZYN] {a}: {d}")
    )
except Exception:  # pragma: no cover - logger optional
    def _log_mag(akcja, dane):
        logging.info(f"[MAGAZYN] {akcja}: {dane}")

import logger

ALLOWED_OPS = {
    "CREATE",
    "PZ",
    "ZW",
    "RW",
    "RESERVE",
    "UNRESERVE",
}

MAGAZYN_PATH = Path("data/magazyn/magazyn.json")
PRZYJECIA_PATH = "data/magazyn/przyjecia.json"
STANY_PATH = "data/magazyn/stany.json"
KATALOG_PATH = "data/magazyn/katalog.json"
SEQ_PZ_PATH = "data/magazyn/_seq_pz.json"
HISTORY_PATH = os.path.join(os.path.dirname(MAGAZYN_PATH), "magazyn_history.json")


def _ensure_dirs(path: str | os.PathLike[str]) -> None:
    """Ensure parent directory for *path* exists.

    When *path* points to a file in the current working directory the parent
    directory is an empty string. ``os.makedirs('')`` raises ``FileNotFoundError``
    so we skip directory creation in that case.  This keeps behaviour correct
    for relative filenames while still creating nested directories when needed.
    """

    directory = os.path.dirname(os.fspath(path))
    if not directory:
        return
    os.makedirs(directory, exist_ok=True)


def _load_json(path: str | os.PathLike[str], default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, type(default)):
                return default
            return data
    except FileNotFoundError:
        return default
    except Exception:
        return default


def load(path: str | os.PathLike[str] = MAGAZYN_PATH) -> Dict[str, Any]:
    """Load warehouse data from ``path``.

    Returns a structure with ``items`` and ``meta`` keys. When the file is
    missing or contains invalid JSON the default ``{"items": {},
    "meta": {}}`` structure is returned.  A JSON decoding problem is logged to
    aid debugging.
    """

    default = {"items": {}, "meta": {}}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        logging.error("Niepoprawny format JSON w %s: %s", path, exc)
        return default
    except Exception as exc:  # unexpected issues
        logging.error("Błąd podczas odczytu %s: %s", path, exc)
        return default

    if not isinstance(data, dict):
        return default
    items = data.get("items") if isinstance(data.get("items"), dict) else {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    return {"items": items, "meta": meta}


def save(data: dict) -> None:
    """Zapisuje pełną strukturę magazynu.

    Plik jest tworzony z nową linią na końcu, a struktura wejściowa jest
    weryfikowana, aby upewnić się, że ma postać słownika.
    """

    if not isinstance(data, dict):
        raise ValueError("magazyn_io.save: oczekiwano dict")
    MAGAZYN_PATH.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(data, ensure_ascii=False, indent=2)
    MAGAZYN_PATH.write_text(txt + "\n", encoding="utf-8")


def append_history(
    items: Dict[str, Any],
    item_id: str,
    user: str,
    op: str,
    qty: float,
    comment: str = "",
    ts: str | None = None,
    *,
    komentarz: str | None = None,
) -> Dict[str, Any]:
    """Append a history entry for ``item_id``.

    Parameters:
        items: Mapping of warehouse items.
        item_id: Identifier of the item being modified.
        user: Name of the user performing the operation.
        op: Operation type. Must be one of :data:`ALLOWED_OPS`.
        qty: Positive quantity of the operation.
        comment: Optional comment stored with the entry.
        ts: Optional timestamp (ISO 8601). Generated when missing.
        komentarz: Polish alias for ``comment``. Overrides ``comment`` when
            provided.

    The entry is appended to ``items[item_id]['historia']``. For ``op == 'PZ'``
    an additional record is stored in :data:`PRZYJECIA_PATH`.
    """

    op = op.upper()
    if op not in ALLOWED_OPS:
        logging.error("Nieznana operacja magazynowa: %s", op)
        raise ValueError(f"Unknown op: {op}")

    qty = float(qty)
    if qty <= 0:
        logging.error("Ilość musi być dodatnia: %s", qty)
        raise ValueError("qty must be > 0")

    if not ts:
        ts = datetime.now(timezone.utc).isoformat()

    if komentarz is not None:
        comment = komentarz

    entry = {
        "ts": ts,
        "user": user,
        "op": op,
        "qty": qty,
        "comment": comment,
    }

    item = items.setdefault(item_id, {})
    history = item.setdefault("historia", [])
    history.append(entry)

    _ensure_dirs(HISTORY_PATH)
    hist = _load_json(HISTORY_PATH, [])
    hist.append({**entry, "item_id": item_id})
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

    if op == "PZ":
        _ensure_dirs(PRZYJECIA_PATH)
        data = _load_json(PRZYJECIA_PATH, [])
        data.append(
            {
                "ts": ts,
                "item_id": item_id,
                "qty": qty,
                "user": user,
                "comment": comment,
            }
        )
        with open(PRZYJECIA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    name = items.get(item_id, {}).get("nazwa", item_id)
    jm = items.get(item_id, {}).get("jednostka", "")
    _log_mag(op, {
        "item_id": item_id,
        "nazwa": name,
        "qty": qty,
        "jm": jm,
        "by": user,
        "comment": comment,
    })
    logging.info(
        "Zapisano %s %s: %s, %s %s, wystawił: %s",
        op,
        item_id,
        name,
        qty,
        jm,
        user,
    )

    return entry


def generate_pz_id(now: datetime | None = None) -> str:
    """Return a sequential PZ identifier.

    The identifier format is ``PZ/YYYY/XXXX`` where the counter ``XXXX`` is
    stored in :data:`SEQ_PZ_PATH` and resets every year. ``now`` can be
    provided for deterministic results in tests.
    """

    now = now or datetime.now(timezone.utc)
    _ensure_dirs(SEQ_PZ_PATH)
    seq_data = _load_json(SEQ_PZ_PATH, {})
    year = str(now.year)
    seq_data[year] = int(seq_data.get(year, 0)) + 1
    with open(SEQ_PZ_PATH, "w", encoding="utf-8") as f:
        json.dump(seq_data, f, ensure_ascii=False, indent=2)
    pz_id = f"PZ/{year}/{seq_data[year]:04d}"
    logger.log_magazyn("nadano_id_pz", {"id": pz_id})
    return pz_id


def save_pz(entry: Dict[str, Any]) -> str:
    """Append ``entry`` describing a PZ to ``przyjecia.json``.

    Missing ``id`` or ``ts`` fields are generated automatically.
    The function returns the PZ identifier.
    """

    data = dict(entry)
    data.setdefault("id", generate_pz_id())
    data.setdefault("ts", datetime.now(timezone.utc).isoformat())
    _ensure_dirs(PRZYJECIA_PATH)
    records = _load_json(PRZYJECIA_PATH, [])
    records.append(data)
    with open(PRZYJECIA_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    logging.info("[INFO] Zapisano PZ %s", data["id"])
    logger.log_magazyn(
        "zapis_przyjecia",
        {"pz_id": data["id"], "item_id": data.get("item_id"), "ilosc": data.get("qty")},
    )
    return data["id"]


def update_stany_after_pz(entry: Dict[str, Any]) -> None:
    """Update ``stany.json`` after recording a PZ.

    ``entry`` must contain ``item_id`` and ``qty``. When the item is
    missing in ``stany.json`` it is created using ``nazwa`` and
    optional ``prog_alert`` fields from ``entry``.
    """

    item_id = entry["item_id"]
    qty = float(entry.get("qty", 0))
    _ensure_dirs(STANY_PATH)
    stany = _load_json(STANY_PATH, {})
    rec = stany.setdefault(
        item_id,
        {
            "nazwa": entry.get("nazwa", item_id),
            "stan": 0.0,
            "prog_alert": float(entry.get("prog_alert", 0.0)),
        },
    )
    rec["stan"] = float(rec.get("stan", 0)) + qty
    with open(STANY_PATH, "w", encoding="utf-8") as f:
        json.dump(stany, f, ensure_ascii=False, indent=2)
    logging.info("[INFO] Zaktualizowano stan %s: %s", item_id, rec["stan"])
    logger.log_magazyn(
        "aktualizacja_stanow",
        {"item_id": item_id, "dodano": qty, "stan": rec["stan"]},
    )


def ensure_in_katalog(entry: Dict[str, Any]) -> Dict[str, str] | None:
    """Ensure that an item from ``entry`` exists in ``katalog.json``.

    Returns a warning dict when the unit in ``entry`` differs from the one
    stored in the catalogue, otherwise ``None``.
    """

    item_id = entry["item_id"]
    _ensure_dirs(KATALOG_PATH)
    katalog = _load_json(KATALOG_PATH, {})
    if item_id not in katalog:
        katalog[item_id] = {
            "nazwa": entry.get("nazwa", item_id),
            "jednostka": entry.get("jednostka", ""),
        }
        with open(KATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(katalog, f, ensure_ascii=False, indent=2)
        logger.log_magazyn("katalog_dodano", {"item_id": item_id})
        return None
    jm_kat = katalog[item_id].get("jednostka")
    jm_pz = entry.get("jednostka")
    if jm_kat and jm_pz and jm_kat != jm_pz:
        return {"warning": f"Jednostka różni się: katalog={jm_kat}, PZ={jm_pz}"}
    logger.log_magazyn("katalog_istnial", {"item_id": item_id})
    return None

