# WM-VERSION: 0.1
# Plik: planista_excel_matching.py
# version: 1.0
"""Dopasowanie pozycji zewnętrznego planu Excel do kartoteki Produktów WM.

Zasada bezpieczeństwa: oznaczenie/kod produktu jest kluczem głównym. Nazwa
może jedynie rozstrzygnąć konflikt kilku rekordów z tym samym oznaczeniem;
nie jest używana do wyszukiwania produktu, gdy kodu brak w WM.
"""

from __future__ import annotations

import re
import unicodedata


MATCH_FOUND = "Znaleziony w WM"
MATCH_MISSING = "Brak produktu w WM"
MATCH_AMBIGUOUS = "Niejednoznaczny"
# Status wykorzystywany dopiero przez zadanie 10 (porównanie ze snapshotem).
MATCH_CHANGED = "Zmieniony w Excelu"

_CODE_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._/\-]*)")
_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-"})


def _normalize_code(value) -> str:
    text = str(value or "").strip().translate(_DASHES)
    return re.sub(r"\s+", "", text).casefold()


def _normalize_text(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.translate(_DASHES)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def extract_excel_product_code(value) -> str:
    """Zwróć wiodące oznaczenie produktu z tekstu pozycji Excel."""
    text = str(value or "").strip().translate(_DASHES)
    match = _CODE_RE.match(text)
    return match.group(1).strip() if match else ""


def _excel_description_without_code(value, code: str) -> str:
    text = str(value or "").strip()
    if not code:
        return text
    prefix = re.compile(rf"^\s*{re.escape(code)}(?:\s+|\s*[-–—:]\s*)?", re.IGNORECASE)
    return prefix.sub("", text, count=1).strip(" -–—:")


def _catalog_candidates(products) -> dict[str, list[dict]]:
    by_code: dict[str, list[dict]] = {}
    if not isinstance(products, dict):
        return by_code

    for key, raw in products.items():
        if not isinstance(raw, dict):
            continue
        symbol = str(raw.get("symbol") or raw.get("kod") or key or "").strip()
        normalized = _normalize_code(symbol)
        if not normalized:
            continue
        rec = dict(raw)
        rec["symbol"] = symbol
        rec.setdefault("nazwa", raw.get("name") or "")
        by_code.setdefault(normalized, []).append(rec)
    return by_code


def _name_resolves_candidate(excel_text: str, code: str, candidates: list[dict]) -> dict | None:
    """Rozstrzygnij duplikat kodu nazwą, ale nigdy nie wyszukuj po samej nazwie."""
    excel_desc = _normalize_text(_excel_description_without_code(excel_text, code))
    if not excel_desc:
        return None

    exact = [
        rec
        for rec in candidates
        if _normalize_text(rec.get("nazwa")) and _normalize_text(rec.get("nazwa")) == excel_desc
    ]
    if len(exact) == 1:
        return exact[0]

    starts = []
    for rec in candidates:
        name = _normalize_text(rec.get("nazwa"))
        if not name:
            continue
        if excel_desc == name or excel_desc.startswith(name + " "):
            starts.append(rec)
    return starts[0] if len(starts) == 1 else None


def match_plan_rows(rows, products) -> list[dict]:
    """Dodaj do pozycji Excel wynik dopasowania do aktualnej kartoteki Produktów WM."""
    catalog = _catalog_candidates(products)
    matched = []

    for raw_row in rows or []:
        row = dict(raw_row) if isinstance(raw_row, dict) else {}
        excel_text = str(row.get("produkt") or "").strip()
        code = extract_excel_product_code(excel_text)
        candidates = list(catalog.get(_normalize_code(code), [])) if code else []

        selected = None
        status = MATCH_MISSING
        if len(candidates) == 1:
            selected = candidates[0]
            status = MATCH_FOUND
        elif len(candidates) > 1:
            selected = _name_resolves_candidate(excel_text, code, candidates)
            status = MATCH_FOUND if selected is not None else MATCH_AMBIGUOUS

        row["excel_oznaczenie"] = code
        row["status_dopasowania"] = status
        row["produkt_wm_symbol"] = str(selected.get("symbol") or "") if selected else ""
        row["produkt_wm_nazwa"] = str(selected.get("nazwa") or "") if selected else ""
        row["kandydaci_wm"] = [
            {
                "symbol": str(rec.get("symbol") or ""),
                "nazwa": str(rec.get("nazwa") or ""),
            }
            for rec in candidates
        ]
        matched.append(row)

    return matched
