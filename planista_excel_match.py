# WM-VERSION: 0.1
# Plik: planista_excel_match.py
# version: 1.0
"""Dopasowanie pozycji zewnętrznego planu Excel do Produktów WM.

Oznaczenie produktu jest kluczem głównym. Nazwa/wariant może jedynie
potwierdzić albo rozstrzygnąć konflikt kandydatów o tym samym oznaczeniu;
nigdy nie zastępuje niezgodnego kodu produktu.
"""

from __future__ import annotations

import re
import unicodedata


STATUS_FOUND = "Znaleziony w WM"
STATUS_MISSING = "Brak produktu w WM"
STATUS_AMBIGUOUS = "Niejednoznaczny"
# Status jest zarezerwowany dla zadania 10 (porównanie z poprzednim snapshotem).
STATUS_CHANGED = "Zmieniony w Excelu"

_CODE_RE = re.compile(r"^\s*([A-Za-z0-9]+(?:[.\-/_][A-Za-z0-9]+)*)")


def _normalize_text(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def normalize_designation(value) -> str:
    """Normalizuj zapis kodu bez zgadywania innych oznaczeń."""
    text = str(value or "").strip().upper()
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    return re.sub(r"\s+", "", text)


def extract_product_designation(product_text) -> str:
    """Pobierz prowadzące oznaczenie z opisu typu `1.560.450 SITI - RAL...`."""
    match = _CODE_RE.match(str(product_text or ""))
    return match.group(1).strip() if match else ""


def _catalog_candidates(products: dict, designation: str) -> list[dict]:
    target = normalize_designation(designation)
    candidates = []
    if not target or not isinstance(products, dict):
        return candidates

    for key, raw in products.items():
        if not isinstance(raw, dict):
            continue
        symbol = str(raw.get("symbol") or raw.get("kod") or key).strip()
        if not symbol or normalize_designation(symbol) != target:
            continue
        candidates.append(
            {
                "key": str(key),
                "symbol": symbol,
                "nazwa": str(raw.get("nazwa") or raw.get("name") or "").strip(),
                "record": raw,
            }
        )
    return candidates


def _name_confirms(product_text: str, name: str) -> bool:
    normalized_name = _normalize_text(name)
    if not normalized_name:
        return False
    normalized_excel = _normalize_text(product_text)
    if not normalized_excel:
        return False
    # Porównanie całych tokenów/zwrotu po normalizacji, nie fuzzy similarity.
    return f" {normalized_name} " in f" {normalized_excel} "


def match_excel_product(product_text, products: dict) -> dict:
    """Dopasuj jedną linię Excel do Produktu WM bez zapisu danych."""
    excel_text = str(product_text or "").strip()
    designation = extract_product_designation(excel_text)
    if not designation:
        return {
            "excel_oznaczenie": "",
            "match_status": STATUS_MISSING,
            "wm_symbol": "",
            "wm_nazwa": "",
            "match_note": "Nie udało się odczytać oznaczenia produktu z początku opisu Excel.",
            "candidate_symbols": [],
        }

    candidates = _catalog_candidates(products, designation)
    if not candidates:
        return {
            "excel_oznaczenie": designation,
            "match_status": STATUS_MISSING,
            "wm_symbol": "",
            "wm_nazwa": "",
            "match_note": "Brak produktu o tym oznaczeniu w aktualnej kartotece Produktów WM.",
            "candidate_symbols": [],
        }

    if len(candidates) == 1:
        candidate = candidates[0]
        confirmed = _name_confirms(excel_text, candidate["nazwa"])
        note = "Oznaczenie zgodne."
        if candidate["nazwa"]:
            note = (
                "Oznaczenie i nazwa/wariant potwierdzone."
                if confirmed
                else "Oznaczenie zgodne; nazwa/wariant z Excel nie potwierdza nazwy WM."
            )
        return {
            "excel_oznaczenie": designation,
            "match_status": STATUS_FOUND,
            "wm_symbol": candidate["symbol"],
            "wm_nazwa": candidate["nazwa"],
            "match_note": note,
            "candidate_symbols": [candidate["symbol"]],
        }

    confirmed = [item for item in candidates if _name_confirms(excel_text, item["nazwa"])]
    if len(confirmed) == 1:
        candidate = confirmed[0]
        return {
            "excel_oznaczenie": designation,
            "match_status": STATUS_FOUND,
            "wm_symbol": candidate["symbol"],
            "wm_nazwa": candidate["nazwa"],
            "match_note": "Kilka rekordów miało to oznaczenie; nazwa/wariant jednoznacznie wskazały Produkt WM.",
            "candidate_symbols": [item["symbol"] for item in candidates],
        }

    return {
        "excel_oznaczenie": designation,
        "match_status": STATUS_AMBIGUOUS,
        "wm_symbol": "",
        "wm_nazwa": "",
        "match_note": "Więcej niż jeden Produkt WM pasuje do oznaczenia i nazwa/wariant nie rozstrzygają wyboru.",
        "candidate_symbols": [item["symbol"] for item in candidates],
    }


def match_production_plan(payload: dict, products: dict) -> dict:
    """Dodaj wynik dopasowania do każdej pozycji planu, nie mutując wejścia."""
    matched_rows = []
    counts = {
        STATUS_FOUND: 0,
        STATUS_MISSING: 0,
        STATUS_AMBIGUOUS: 0,
    }
    for raw_row in list(payload.get("rows") or []):
        row = dict(raw_row) if isinstance(raw_row, dict) else {}
        match = match_excel_product(row.get("produkt"), products)
        row.update(match)
        matched_rows.append(row)
        status = match["match_status"]
        if status in counts:
            counts[status] += 1

    result = dict(payload)
    result["rows"] = matched_rows
    result["match_summary"] = counts
    result["product_catalog_size"] = len(products) if isinstance(products, dict) else 0
    return result
