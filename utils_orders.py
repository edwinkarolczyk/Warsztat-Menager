import os
from datetime import date

from utils_json import (
    normalize_rows,
    safe_read_json as _safe_read_json,
    safe_write_json as _safe_write_json,
)


def load_orders_rows_with_fallback(cfg: dict, resolve_rel):
    r"""
    1) <root>\zlecenia\zlecenia.json  (dict{'zlecenia':list} lub list)
    2) fallback: <root>\zlecenia.json (legacy: list)
    """

    primary = resolve_rel(cfg, r"zlecenia\zlecenia.json")
    if not primary:
        primary = resolve_rel({}, r"zlecenia\zlecenia.json")
    data = _safe_read_json(primary, default={"zlecenia": []})
    rows = normalize_rows(data, "zlecenia")
    if not rows and isinstance(data, list):
        rows = normalize_rows(data, None)
    if rows:
        return rows, primary

    legacy = resolve_rel(cfg, r"zlecenia.json")
    if not legacy:
        legacy = resolve_rel({}, r"zlecenia.json")
    data2 = _safe_read_json(legacy, default=[])
    rows2 = normalize_rows(data2, None)
    if rows2:
        return rows2, primary
    return [], primary


def ensure_orders_sample_if_empty(rows: list[dict], primary_path: str):
    if rows:
        return rows
    sample = [
        {"id": "Z-2025-001", "klient": "ACME", "status": "otwarte", "data": str(date.today())},
        {"id": "Z-2025-002", "klient": "BRAVO", "status": "w toku", "data": str(date.today())},
    ]
    os.makedirs(os.path.dirname(primary_path) or ".", exist_ok=True)
    _safe_write_json(primary_path, {"zlecenia": sample})
    return sample
