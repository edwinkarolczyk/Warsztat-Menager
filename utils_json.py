import os
import json
import logging

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

