# WM-VERSION: 0.1
# Plik: planista_excel_mappings.py
# version: 1.0
"""Zapamiętane, ręcznie zatwierdzone powiązania opisów Excel z Produktami WM.

Plik jest częścią aktywnego data root WM. Nie modyfikuje oryginalnego Excela
ani kartotek produktów.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from config_manager import ConfigManager
from machine_file_guard import file_write_lock
from planista_excel_match import excel_mapping_key


_MAPPING_FILE = "excel_product_mappings.json"


def mapping_path() -> Path:
    return Path(ConfigManager().path_data()) / "planista" / _MAPPING_FILE


def load_manual_mappings() -> dict:
    path = mapping_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Nie można odczytać zapisanych powiązań produktów: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("mappings"), dict):
        raise RuntimeError(f"Nieprawidłowy format powiązań produktów: {path}")
    return dict(payload["mappings"])


def remember_manual_mapping(excel_description: str, wm_symbol: str) -> dict:
    """Zapisz potwierdzony wybór atomowo, nie kasując poprzednich powiązań."""
    key = excel_mapping_key(excel_description)
    symbol = str(wm_symbol or "").strip()
    if not key or not symbol:
        raise ValueError("Opis Excel i kod produktu WM są wymagane.")
    path = mapping_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_write_lock(path, label="mapowania produktów Excel"):
        mappings = load_manual_mappings()
        record = {
            "wm_symbol": symbol,
            "excel_opis": str(excel_description or "").strip(),
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        mappings[key] = record
        tmp = path.with_name(path.name + ".tmp")
        try:
            tmp.write_text(
                json.dumps({"schema": 1, "mappings": mappings}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()
    return record
