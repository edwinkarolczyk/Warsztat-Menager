import os
import json
import copy
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def ensure_json(path: str, default: dict | list | None = None) -> str:
    """
    Gwarantuje, że plik JSON istnieje.
    Jeśli go nie ma – tworzy katalogi i zapisuje 'default' (albo pusty {}).
    Zwraca ścieżkę ABS.
    """
    abs_path = os.path.abspath(path)
    try:
        if not os.path.exists(abs_path):
            os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
            data = default if default is not None else {}
            with open(abs_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.warning(
                "[AUTOJSON] Brak pliku %s – utworzono szablon (%s)",
                abs_path,
                type(data).__name__,
            )
        return abs_path
    except Exception as e:  # pragma: no cover - log + propagate
        logger.error("[AUTOJSON] Nie udało się utworzyć pliku %s: %s", abs_path, e)
        raise


def load_json(path: str, default: dict | list | None = None) -> dict | list:
    """
    Wczytuje JSON; jeśli brak – tworzy go z 'default' i zwraca zawartość.
    """
    abs_path = ensure_json(path, default)
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # pragma: no cover - fallback to default data
        logger.error("[AUTOJSON] Błąd wczytywania %s: %s", abs_path, e)
        return default if default is not None else {}


def ensure_dir_json(path: str, default):
    """Ensure directory for *path* exists and create JSON file if missing."""

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
    return path


def normalize_rows(obj, key: str):
    """Return a list of dictionaries regardless of JSON layout."""

    if isinstance(obj, list):
        return [row for row in obj if isinstance(row, dict)]
    if isinstance(obj, dict):
        rows = obj.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def safe_read_json(path: str, default):
    """Safely read JSON file creating it with ``default`` when needed."""

    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(default, handle, ensure_ascii=False, indent=2)
            logger.warning("[AUTOJSON] Brak pliku %s – utworzono szablon", path)
            return copy.deepcopy(default)
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.error("[JSON] Błąd czytania %s: %s", path, exc)
        return copy.deepcopy(default)


# --- Alias zgodności: jeśli w repo istnieje _safe_read_json, wystaw alias safe_read_json
try:
    safe_read_json  # type: ignore[attr-defined]
except NameError:
    try:
        safe_read_json = _safe_read_json  # type: ignore[name-defined]
    except Exception:
        pass  # brak starej nazwy – nic nie robimy (safe_read_json już może istnieć)


def normalize_rows(data: Any, list_key: Optional[str] = None) -> List[Dict]:
    """
    Zwraca listę rekordów (list[dict]) niezależnie od formatu źródła:
    - dict + list_key -> data[list_key] (gdy istnieje i jest listą)
    - list na top-level -> bezpośrednio
    - inaczej -> []
    Filtruje tylko elementy typu dict (bezpieczne dla UI).
    """

    if isinstance(data, dict):
        raw = data.get(list_key, []) if list_key else []
    elif isinstance(data, list):
        raw = data
    else:
        raw = []
    return [r for r in raw if isinstance(r, dict)]

