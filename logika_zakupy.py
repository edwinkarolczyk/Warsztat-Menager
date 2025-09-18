import json
import os
from datetime import datetime
from pathlib import Path

ZAMOWIENIA_DIR = Path("data") / "zamowienia"
PENDING_ORDERS_PATH = Path("data") / "zamowienia_oczekujace.json"
STANY_PATH = Path("data") / "magazyn" / "stany.json"
PENDING_TYPE = "magazyn_item"


def _ensure_dir() -> None:
    os.makedirs(ZAMOWIENIA_DIR, exist_ok=True)


def _next_id() -> str:
    _ensure_dir()
    nums = []
    for f in ZAMOWIENIA_DIR.glob("*.json"):
        try:
            nums.append(int(f.stem))
        except Exception:
            pass
    nid = max(nums) + 1 if nums else 1
    return f"{nid:06d}"


def utworz_zlecenie_zakupow(braki):
    """Tworzy plik zlecenia zakupu na podstawie listy braków."""
    _ensure_dir()
    nr = _next_id()
    zam = {
        "id": nr,
        "utworzono": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pozycje": braki,
    }
    path = ZAMOWIENIA_DIR / f"{nr}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(zam, f, ensure_ascii=False, indent=2)
    return nr, str(path)


def _load_json(path: Path, default):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
    except Exception:
        pass
    return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _orders_raw():
    data = _load_json(PENDING_ORDERS_PATH, [])
    return data if isinstance(data, list) else []


def load_pending_orders():
    """Zwraca listę pozycji dodanych z Magazynu do oczekujących zamówień."""

    rows = []
    for entry in _orders_raw():
        if not isinstance(entry, dict):
            continue
        if entry.get("type") == PENDING_TYPE:
            qty = entry.get("qty", entry.get("ilosc"))
            try:
                qty_val = float(qty)
            except Exception:
                qty_val = None
            rows.append(
                {
                    "id": entry.get("id", ""),
                    "qty": qty_val,
                    "comment": entry.get("comment", ""),
                    "ts": entry.get("ts", ""),
                }
            )
            continue
        if entry.get("id") and ("qty" in entry or "ilosc" in entry):
            qty = entry.get("qty", entry.get("ilosc"))
            try:
                qty_val = float(qty)
            except Exception:
                qty_val = None
            rows.append(
                {
                    "id": entry.get("id", ""),
                    "qty": qty_val,
                    "comment": entry.get("comment", ""),
                    "ts": entry.get("ts", entry.get("data", "")),
                }
            )
    return rows


def save_pending_orders(orders):
    """Nadpisuje wpisy magazynowe w pliku zamówień oczekujących."""

    if not isinstance(orders, list):
        raise ValueError("orders must be a list")

    updated = []
    for item in orders:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        qty = item.get("qty", item.get("ilosc"))
        try:
            qty_val = float(qty)
        except Exception:
            qty_val = None
        updated.append(
            {
                "type": PENDING_TYPE,
                "id": item.get("id"),
                "qty": qty_val,
                "comment": item.get("comment", ""),
                "ts": item.get("ts", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            }
        )

    raw = [
        entry
        for entry in _orders_raw()
        if not isinstance(entry, dict) or entry.get("type") != PENDING_TYPE
    ]
    raw.extend(updated)
    _save_json(PENDING_ORDERS_PATH, raw)


def add_item_to_orders(item_id: str, qty, comment: str = "") -> bool:
    if not item_id:
        return False
    try:
        qty_val = float(qty)
    except Exception:
        return False

    raw = _orders_raw()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    replaced = False
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            continue
        is_mag_entry = entry.get("type") == PENDING_TYPE
        is_legacy = entry.get("id") == item_id and (
            "qty" in entry or "ilosc" in entry
        )
        if is_mag_entry or is_legacy:
            if entry.get("id") != item_id:
                continue
            raw[idx] = {
                "type": PENDING_TYPE,
                "id": item_id,
                "qty": qty_val,
                "comment": comment or entry.get("comment", ""),
                "ts": now,
            }
            replaced = True
            break

    if not replaced:
        raw.append(
            {
                "type": PENDING_TYPE,
                "id": item_id,
                "qty": qty_val,
                "comment": comment or "",
                "ts": now,
            }
        )

    _save_json(PENDING_ORDERS_PATH, raw)
    return True


def _detect_min_field(data: dict):
    for key in ("min", "min_qty", "prog_min", "min_poziom"):
        if key in data:
            try:
                return float(data[key])
            except Exception:
                return None
    return None


def auto_order_missing(get_stock_func=None) -> int:
    """
    Dodaje do oczekujących zamówień wszystkie pozycje poniżej progu minimalnego.

    get_stock_func: opcjonalne wywołanie, które przyjmuje identyfikator pozycji
        i zwraca aktualny stan magazynowy.
    """

    stany = _load_json(STANY_PATH, {})
    if not isinstance(stany, dict):
        return 0

    added = 0
    for item_id, meta in stany.items():
        if not isinstance(meta, dict):
            continue
        min_qty = _detect_min_field(meta)
        if min_qty is None:
            continue
        if get_stock_func is not None:
            try:
                current = float(get_stock_func(item_id))
            except Exception:
                current = 0.0
        else:
            try:
                current = float(meta.get("qty", meta.get("stan", 0)))
            except Exception:
                current = 0.0
        if current < min_qty:
            need = max(min_qty - current, 0.0)
            if need > 0 and add_item_to_orders(item_id, need, comment="auto: poniżej progu"):
                added += 1
    return added
