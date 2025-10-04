import os
from datetime import date

from utils_json import normalize_rows, safe_read_json as _r, safe_write_json as _w


def _fix_if_dir(path: str, expected_rel: str) -> str:
    if not path or os.path.isdir(path):
        return os.path.normpath(os.path.join(path or "", expected_rel))
    return path


def load_orders_rows_with_fallback(cfg: dict, resolve_rel):
    primary = resolve_rel(cfg, r"zlecenia\zlecenia.json")
    primary = _fix_if_dir(primary, r"zlecenia\zlecenia.json")
    data = _r(primary, default={"zlecenia": []})
    rows = normalize_rows(data, "zlecenia") or normalize_rows(data, None)
    if rows:
        return rows, primary

    legacy = resolve_rel(cfg, r"zlecenia.json")
    legacy = _fix_if_dir(legacy, r"zlecenia\zlecenia.json")
    data2 = _r(legacy, default=[])
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
    _w(primary_path, {"zlecenia": sample})
    return sample
