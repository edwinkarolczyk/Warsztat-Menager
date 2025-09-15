from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional, List
import json


# Wspólna ścieżka magazynu
MAGAZYN_PATH = Path("data/magazyn/magazyn.json")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load() -> Dict[str, Any]:
    """Ładuje pełną strukturę magazynu.
    Zabezpiecza przed brakiem pliku i uszkodzonym JSON."""
    if not MAGAZYN_PATH.exists():
        return {"items": {}, "meta": {}}
    try:
        txt = MAGAZYN_PATH.read_text(encoding="utf-8")
        data = json.loads(txt) if txt.strip() else {"items": {}, "meta": {}}
        # minimalny sanity-check
        if not isinstance(data, dict):
            return {"items": {}, "meta": {}, "_warning": "invalid_root"}
        data.setdefault("items", {})
        data.setdefault("meta", {})
        return data
    except json.JSONDecodeError:
        # Uszkodzony plik — nie wysadzamy aplikacji
        return {"items": {}, "meta": {}, "_warning": "invalid_json"}


def save(data: Dict[str, Any]) -> None:
    """Zapisuje pełną strukturę magazynu."""
    if not isinstance(data, dict):
        raise ValueError("magazyn_io.save: oczekiwano dict")
    data.setdefault("items", {})
    data.setdefault("meta", {})
    _ensure_parent(MAGAZYN_PATH)
    MAGAZYN_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def append_history(
    items: Dict[str, Any],
    item_id: str,
    *,
    user: str = "",
    op: str,
    qty: float = 0.0,
    komentarz: Optional[str] = None,
    comment: Optional[str] = None,
) -> None:
    """Dodaje wpis historii do elementu magazynu.
    Obsługuje alias klucza komentarza: 'komentarz' lub 'comment'."""
    it = items.setdefault(item_id, {})
    hist = it.setdefault("historia", [])
    txt = komentarz if komentarz is not None else comment
    hist.append(
        {
            "user": user or "",
            "op": op,
            "qty": float(qty or 0),
            "comment": (txt or "").strip(),
        }
    )

