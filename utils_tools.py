import os

from utils_json import normalize_rows, safe_read_json as _r, safe_write_json as _w


def _fix_if_dir(path: str, expected_rel: str) -> str:
    if not path or os.path.isdir(path):
        return os.path.normpath(os.path.join(path or "", expected_rel))
    return path


def load_tools_rows_with_fallback(cfg: dict, resolve_rel):
    primary = resolve_rel(cfg, r"narzedzia\narzedzia.json")
    primary = _fix_if_dir(primary, r"narzedzia\narzedzia.json")
    data = _r(primary, default={"narzedzia": []})
    rows = normalize_rows(data, "narzedzia") or normalize_rows(data, None)
    if rows:
        return rows, primary

    legacy = resolve_rel(cfg, r"narzedzia.json")
    legacy = _fix_if_dir(legacy, r"narzedzia\narzedzia.json")
    data2 = _r(legacy, default=[])
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
    _w(primary_path, {"narzedzia": sample})
    return sample
