"""Helpers for warehouse catalogue."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import List

KATALOG_PATH = "data/magazyn/katalog.json"
STANY_PATH = "data/magazyn/stany.json"


def _strip_accents(text: str) -> str:
    """Return ``text`` converted to ASCII by removing diacritics."""

    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c))


def build_code(name: str) -> str:
    """Build a material code from ``name``.

    The algorithm removes diacritics, uppercases the name and joins the
    first word, the first numeric token and remaining words truncated to
    five characters, using underscores. Examples::

        >>> build_code("Plaskownik 40mm")
        'PLASK_40'
        >>> build_code("Rura 30mm")
        'RURA_30'
        >>> build_code("Drut gwintowany 30mm")
        'DRUT_30_GWINT'
    """

    clean = _strip_accents(name).upper()
    tokens = re.split(r"[\s\-/]+", clean)
    num_token = None
    num_index = None
    for idx, tok in enumerate(tokens):
        m = re.search(r"\d+", tok)
        if m:
            num_token = m.group(0)
            num_index = idx
            break
    parts: List[str] = []
    if tokens:
        parts.append(tokens[0][:5])
    if num_token:
        parts.append(num_token)
    for idx, tok in enumerate(tokens[1:], start=1):
        if idx == num_index or re.search(r"\d", tok):
            continue
        parts.append(tok[:5])
    return "_".join(parts)


def suggest_names_for_category(
    category: str,
    prefix: str,
    katalog_path: str = KATALOG_PATH,
    stany_path: str = STANY_PATH,
) -> List[str]:
    """Return names for ``category`` starting with ``prefix``.

    The function reads ``katalog.json`` and ``stany.json`` and merges
    matching names from both files, removing duplicates while preserving
    order.
    """

    cat_norm = (category or "").lower()
    pref_norm = (prefix or "").lower()
    suggestions: List[str] = []

    try:
        with open(katalog_path, encoding="utf-8") as fh:
            katalog = json.load(fh)
    except FileNotFoundError:  # pragma: no cover - optional file
        katalog = {}
    items = katalog.get("items", katalog)
    for data in items.values():
        typ = str(data.get("typ") or data.get("kategoria") or "").lower()
        name = data.get("nazwa", "")
        if typ == cat_norm and name.lower().startswith(pref_norm):
            suggestions.append(name)

    try:
        with open(stany_path, encoding="utf-8") as fh:
            stany = json.load(fh)
    except FileNotFoundError:  # pragma: no cover - optional file
        stany = {}
    for iid, data in stany.items():
        name = data.get("nazwa", "")
        if not name.lower().startswith(pref_norm):
            continue
        typ = str(items.get(iid, {}).get("typ") or items.get(iid, {}).get("kategoria") or "").lower()
        if typ and typ != cat_norm:
            continue
        suggestions.append(name)

    seen = set()
    result: List[str] = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result
