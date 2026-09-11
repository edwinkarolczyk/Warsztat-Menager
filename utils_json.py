# version: 1.1
# Zmiany 1.1:
# - Pojedyncze pliki narzędzi data/narzedzia/<nr>.json są zapisywane atomowo.
# - Ich zapis korzysta ze wspólnej blokady pliku używanej także przez WMM.
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import uuid

from machine_file_guard import file_write_lock

try:
    from config_manager import get_root, resolve_rel
except Exception:  # fallback na bardzo stare wersje

    def _fallback_data_root(cfg: dict | None = None) -> str:
        cfg = cfg or {}
        paths_cfg = cfg.get("paths") or {}
        candidates = (
            paths_cfg.get("data_root"),
            cfg.get("data_root"),
            os.environ.get("WM_DATA_ROOT"),
        )
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                value = os.path.expanduser(candidate.strip())
                if not os.path.isabs(value):
                    value = os.path.normpath(os.path.join(os.getcwd(), value))
                return os.path.normpath(value)
        return os.path.normpath(os.path.join(os.getcwd(), "data"))

    def get_root(cfg: dict | None = None) -> str:
        return _fallback_data_root(cfg)

    def resolve_rel(cfg, key, *extra):
        root = _fallback_data_root(cfg)
        return os.path.join(root, *(extra or ()))


logger = logging.getLogger(__name__)


def _ensure_parent(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def ensure_json(path: str, default: dict | list | None = None) -> str:
    """Ensure *path* exists with ``default`` content."""

    abs_path = os.path.abspath(path)
    payload = default if default is not None else {}
    try:
        if not os.path.exists(abs_path):
            _ensure_parent(abs_path)
            with open(abs_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
            logger.warning(
                "[AUTOJSON] Brak pliku %s – utworzono szablon (%s)",
                abs_path,
                type(payload).__name__,
            )
        return abs_path
    except Exception as exc:  # pragma: no cover - propagate for diagnostics
        logger.error("[AUTOJSON] Nie udało się utworzyć pliku %s: %s", abs_path, exc)
        raise


def load_json(path: str, default: dict | list | None = None) -> dict | list:
    """Load JSON ensuring the file exists beforehand."""

    abs_path = ensure_json(path, default)
    try:
        with open(abs_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:  # pragma: no cover - fall back to default data
        logger.error("[AUTOJSON] Błąd wczytywania %s: %s", abs_path, exc)
        return copy.deepcopy(default) if default is not None else {}


def ensure_dir_json(path: str, default: Any) -> str:
    """Ensure directory for ``path`` exists and write ``default`` if missing."""

    _ensure_parent(path)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(default, handle, ensure_ascii=False, indent=2)
        try:
            preview = json.dumps(default, ensure_ascii=False)
        except TypeError:
            preview = str(default)
        logger.info(
            "[AUTOJSON] Utworzono %s z domyślnymi wartościami: %s",
            path,
            preview,
        )
    return path


def normalize_rows(data: Any, list_key: Optional[str] = None) -> List[Dict]:
    """Return list of dictionaries regardless of JSON layout."""

    if isinstance(data, dict):
        raw = data.get(list_key, []) if list_key else []
    elif isinstance(data, list):
        raw = data
    else:
        raw = []
    return [row for row in raw if isinstance(row, dict)]


def safe_read_json(path: str, default: Any = None, *, ensure: bool = True) -> Any:
    """Safely read JSON returning ``default`` on errors or directories."""

    try:
        if not path:
            raise FileNotFoundError(path)
        if os.path.isdir(path):
            raise IsADirectoryError(path)
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        if ensure and path:
            try:
                _ensure_parent(path)
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(default, handle, indent=2, ensure_ascii=False)
                logger.warning(
                    "[AUTOJSON] Brak pliku %s – utworzono szablon (%s)",
                    path,
                    type(default).__name__,
                )
            except Exception as exc:
                logger.error("[JSON] Nie udało się utworzyć %s: %s", path, exc)
        return copy.deepcopy(default)
    except IsADirectoryError:
        logger.error("[JSON] Błąd czytania %s: wskazuje na katalog, nie plik.", path)
        return copy.deepcopy(default)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.error("[JSON] Błąd czytania %s: %s", path, exc)
        return copy.deepcopy(default)


def _is_tool_item_path(path: str) -> bool:
    """Rozpoznaj pojedynczy plik narzędzia, bez plików konfiguracyjnych/indexu."""

    try:
        target = Path(path)
        return (
            target.suffix.casefold() == ".json"
            and target.parent.name.casefold() == "narzedzia"
            and target.stem.isdigit()
        )
    except Exception:
        return False


def _write_json_atomic(path: str, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temp, target)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def safe_write_json(path: str, data: Any) -> bool:
    """Safely write JSON ensuring parent directories exist."""

    try:
        if os.path.isdir(path):
            logger.error("[JSON] Próba zapisu do katalogu (nie pliku): %s", path)
            return False
        _ensure_parent(path)
        if _is_tool_item_path(path):
            with file_write_lock(path, label="Narzędzi"):
                _write_json_atomic(path, data)
        else:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
        logger.info("[JSON] Zapisano %s", path)
        return True
    except Exception as exc:
        logger.error("[JSON] Błąd zapisu %s: %s", path, exc)
        return False


def normalize_doc_list_or_dict(
    data: Any, key: str, *, fallback_keys: Iterable[str] | None = None
) -> List[Dict]:
    """Return dictionaries from ``data`` stored either as a list or under ``key``.

    ``data`` may be a list of dictionaries or a dictionary containing the list
    under ``key``.  ``fallback_keys`` allows support for legacy layouts where the
    payload might be stored under one of several keys.  Only dictionaries are
    returned – other types are ignored.
    """

    if isinstance(data, list):
        raw_items = data
    elif isinstance(data, dict):
        keys: List[str] = [key]
        if fallback_keys:
            for extra in fallback_keys:
                if extra not in keys:
                    keys.append(extra)
        for candidate in keys:
            value = data.get(candidate)
            if isinstance(value, list):
                raw_items = value
                break
        else:
            raw_items = []
    else:
        raw_items = []
    return [row for row in raw_items if isinstance(row, dict)]


def normalize_tools_index(doc: Any) -> Dict[str, List[Dict]]:
    """Ujednolicenie indeksu narzędzi: dict z ``"items"``."""

    if isinstance(doc, dict):
        items = doc.get("items")
        doc["items"] = items if isinstance(items, list) else []
        doc["items"] = [item for item in doc["items"] if isinstance(item, dict)]
        return doc
    if isinstance(doc, list):
        return {"items": [item for item in doc if isinstance(item, dict)]}
    return {"items": []}


def normalize_tools_doc(doc: Any) -> dict:
    """Normalize narzędzia document structure to a dictionary."""

    if isinstance(doc, dict):
        return doc
    if isinstance(doc, list):
        if len(doc) == 1 and isinstance(doc[0], dict):
            return doc[0]
        return {"items": doc}
    return {}


def normalize_tools_index(doc: Any) -> Dict[str, Any]:
    """Return a normalized representation of a tools index document."""

    normalized: Dict[str, Any] = {"items": []}

    if isinstance(doc, list):
        normalized["items"] = [row for row in doc if isinstance(row, dict)]
        return normalized

    if isinstance(doc, dict):
        meta = {k: v for k, v in doc.items() if k not in {"items", "narzedzia", "narzędzia", "tools"}}
        normalized.update(meta)

        candidates = [
            doc.get("items"),
            doc.get("narzedzia"),
            doc.get("narzędzia"),
            doc.get("tools"),
        ]

        items: List[Dict] = []
        for candidate in candidates:
            if isinstance(candidate, list):
                items = [row for row in candidate if isinstance(row, dict)]
                if items:
                    break

        if not items:
            keys = ("nr", "numer", "id", "nazwa", "status", "typ", "zadania")
            if any(key in doc for key in keys):
                entry = {k: v for k, v in doc.items() if k not in {"items", "narzedzia", "narzędzia", "tools"}}
                items = [entry]

        normalized["items"] = items
        return normalized

    if doc is None:
        return normalized

    return normalized


_safe_read_json = safe_read_json
