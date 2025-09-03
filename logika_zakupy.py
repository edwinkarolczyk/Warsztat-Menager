import json
import os
from datetime import datetime
from pathlib import Path

ZAMOWIENIA_DIR = Path("data") / "zamowienia"


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
