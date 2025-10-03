import os

from utils_json import (
    normalize_rows,
    safe_read_json as _safe_read_json,
    safe_write_json as _safe_write_json,
)


def load_tools_rows_with_fallback(cfg: dict, resolve_rel):
    r"""
    1) <root>\narzedzia\narzedzia.json  (dict{'narzedzia':list} lub list)
    2) fallback: <root>\narzedzia.json (legacy: list)
    """

    primary = resolve_rel(cfg, r"narzedzia\narzedzia.json")
    if not primary:
        primary = resolve_rel({}, r"narzedzia\narzedzia.json")
    data = _safe_read_json(primary, default={"narzedzia": []})
    rows = normalize_rows(data, "narzedzia")
    if not rows and isinstance(data, list):
        rows = normalize_rows(data, None)
    if rows:
        return rows, primary

    legacy = resolve_rel(cfg, r"narzedzia.json")
    if not legacy:
        legacy = resolve_rel({}, r"narzedzia.json")
    data2 = _safe_read_json(legacy, default=[])
    rows2 = normalize_rows(data2, None)
    if rows2:
        return rows2, primary
    return [], primary


def ensure_tools_sample_if_empty(rows: list[dict], primary_path: str):
    if rows:
        return rows
    sample = [
        {"id": "T-001", "nazwa": "Klucz dynamometryczny", "status": "OK"},
        {"id": "T-002", "nazwa": "Suwmiarka 150 mm", "status": "OK"},
        {"id": "T-003", "nazwa": "Wiertło Ø8 HSS", "status": "zużyte"},
    ]
    os.makedirs(os.path.dirname(primary_path) or ".", exist_ok=True)
    _safe_write_json(primary_path, {"narzedzia": sample})
    return sample
