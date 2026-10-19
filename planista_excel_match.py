# WM-VERSION: 0.1
# Plik: planista_excel_match.py
# version: 1.1
# 1.1: bezpieczne dopasowanie po pełnej nazwie/wymiarach i ręczne mapowania.
"""Dopasowanie pozycji zewnętrznego planu Excel do Produktów WM.

Oznaczenie produktu ma pierwszeństwo. Dla opisów bez kodu można
jednoznacznie dopasować pełną nazwę i wymiary (bez wariantu RAL).
Podobne nazwy wymagają ręcznego zatwierdzenia.
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



def excel_mapping_key(product_text) -> str:
    """Stabilny klucz zapamiętanego wyboru: zachowuje wariant RAL i wymiary."""
    return _normalize_text(_dimension_spacing(str(product_text or "")))


def _dimension_spacing(text: str) -> str:
    return re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", " x ", text, flags=re.I)


def _name_key(value) -> str:
    """Do porównania nazw ignoruj wyłącznie końcowy opis koloru RAL."""
    text = re.sub(
        r"(?:\s*[-–—]\s*)?\bRAL\s*\d{3,4}[A-Za-z]{0,3}(?:\b|$).*$",
        "",
        str(value or ""),
        flags=re.I,
    )
    return _normalize_text(_dimension_spacing(text))


def product_dimensions(value) -> tuple[float, ...]:
    """Rozpoznawaj konkretne wymiary, np. 270×100×170 lub 270x100x170."""
    text = str(value or "")
    found = re.search(
        r"(?<!\d)(\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+(?:[.,]\d+)?){1,3})(?!\d)",
        text,
        flags=re.I,
    )
    if not found:
        return ()
    return tuple(
        float(part.replace(",", "."))
        for part in re.split(r"\s*[x×]\s*", found.group(1), flags=re.I)
    )


def _dimension_conflict(excel_text: str, name: str) -> bool:
    excel_dims = product_dimensions(excel_text)
    wm_dims = product_dimensions(name)
    return bool(excel_dims and wm_dims and excel_dims != wm_dims)


def _name_candidates(products: dict, excel_text: str) -> tuple[list[dict], bool]:
    """Zwróć zgodne nazwy albo propozycje do jawnego wyboru; nigdy nie zgaduj wymiarów."""
    key = _name_key(excel_text)
    if not key or not isinstance(products, dict):
        return [], False
    candidates = []
    for ident, record in products.items():
        if not isinstance(record, dict):
            continue
        name = str(record.get("nazwa") or record.get("name") or "").strip()
        symbol = str(record.get("symbol") or record.get("kod") or ident).strip()
        if not name or not symbol or _dimension_conflict(excel_text, name):
            continue
        candidates.append({"symbol": symbol, "nazwa": name, "key": str(ident)})
    exact = [candidate for candidate in candidates if _name_key(candidate["nazwa"]) == key]
    if exact:
        return exact, True

    # Podobna nazwa jest tylko propozycją; wymaga decyzji człowieka.
    tokens = key.split()
    if len(tokens) < 2:
        return [], False
    prefix = " ".join(tokens[:2])
    proposed = [
        candidate for candidate in candidates
        if _name_key(candidate["nazwa"]).startswith(prefix + " ")
        or _name_key(candidate["nazwa"]) == prefix
    ]
    return proposed, False


def _candidate_match(designation: str, candidate: dict, note: str, *, method: str) -> dict:
    return {
        "excel_oznaczenie": designation,
        "match_status": STATUS_FOUND,
        "wm_symbol": candidate["symbol"],
        "wm_nazwa": candidate["nazwa"],
        "match_note": note,
        "candidate_symbols": [candidate["symbol"]],
        "match_method": method,
    }


def _manual_candidate(products: dict, symbol: str) -> dict | None:
    if not symbol or not isinstance(products, dict):
        return None
    matches = [
        {
            "symbol": str(record.get("symbol") or record.get("kod") or ident).strip(),
            "nazwa": str(record.get("nazwa") or record.get("name") or "").strip(),
        }
        for ident, record in products.items()
        if isinstance(record, dict)
        and normalize_designation(record.get("symbol") or record.get("kod") or ident)
        == normalize_designation(symbol)
    ]
    return matches[0] if len(matches) == 1 else None


def match_excel_product(product_text, products: dict, manual_mappings: dict | None = None) -> dict:
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
    mapping = (manual_mappings or {}).get(excel_mapping_key(excel_text))
    manual_symbol = (
        str(mapping.get("wm_symbol") or "").strip()
        if isinstance(mapping, dict)
        else str(mapping or "").strip()
    )
    confirmed = _manual_candidate(products, manual_symbol)
    if confirmed:
        return _candidate_match(
            designation, confirmed,
            "Ręcznie zatwierdzone powiązanie Excel → Produkt WM (zapamiętane).",
            method="manual",
        )

    if not candidates:
        # Kod jawny (np. 1.327.50 lub HP14) nie może być zastąpiony
        # podobną nazwą produktu o innym oznaczeniu.
        explicit_code = bool(
            re.search(r"\d", designation)
            or any(char in designation for char in ".-/_")
        )
        if not explicit_code:
            named, exact = _name_candidates(products, excel_text)
            if exact and len(named) == 1:
                return _candidate_match(
                    designation, named[0],
                    "Zgodność pełnej nazwy i wymiarów (pominięto wariant RAL).",
                    method="name",
                )
            if named:
                return {
                    "excel_oznaczenie": designation,
                    "match_status": STATUS_AMBIGUOUS,
                    "wm_symbol": "",
                    "wm_nazwa": "",
                    "match_note": (
                        "Podobne nazwy lub kilka Produktów WM; wybierz produkt ręcznie."
                    ),
                    "candidate_symbols": list(dict.fromkeys(
                        candidate["symbol"] for candidate in named
                    )),
                }
        return {
            "excel_oznaczenie": designation,
            "match_status": STATUS_MISSING,
            "wm_symbol": "",
            "wm_nazwa": "",
            "match_note": "Brak jednoznacznego Produktu WM. Możesz wskazać go ręcznie.",
            "candidate_symbols": [],
        }

    if len(candidates) == 1:
        candidate = candidates[0]
        if _dimension_conflict(excel_text, candidate["nazwa"]):
            return {
                "excel_oznaczenie": designation,
                "match_status": STATUS_AMBIGUOUS,
                "wm_symbol": "",
                "wm_nazwa": "",
                "match_note": "Oznaczenie zgodne, ale wymiary w Excelu i WM są różne. Wymaga decyzji.",
                "candidate_symbols": [candidate["symbol"]],
            }
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

    confirmed = [
        item for item in candidates
        if not _dimension_conflict(excel_text, item["nazwa"])
        and _name_confirms(excel_text, item["nazwa"])
    ]
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


def match_production_plan(payload: dict, products: dict, manual_mappings: dict | None = None) -> dict:
    """Dodaj wynik dopasowania do każdej pozycji planu, nie mutując wejścia."""
    matched_rows = []
    counts = {
        STATUS_FOUND: 0,
        STATUS_MISSING: 0,
        STATUS_AMBIGUOUS: 0,
    }
    for raw_row in list(payload.get("rows") or []):
        row = dict(raw_row) if isinstance(raw_row, dict) else {}
        match = match_excel_product(row.get("produkt"), products, manual_mappings=manual_mappings)
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
