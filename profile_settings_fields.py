# version: 1.0
"""Wspólna definicja pól edytowalnych własnego Profilu WM."""
from __future__ import annotations

import re
from typing import Any

EDITABLE_PROFILE_FIELDS: tuple[tuple[str, str], ...] = (
    ("imie", "Imię"),
    ("nazwisko", "Nazwisko"),
    ("zatrudniony_od", "Data zatrudnienia"),
    ("telefon", "Telefon"),
    ("email", "E-mail"),
)

_FIELD_KEYS = {key for key, _label in EDITABLE_PROFILE_FIELDS}
_FIELD_ALIASES = {
    "staz": "zatrudniony_od",
    "staż": "zatrudniony_od",
    "zatrudnienie": "zatrudniony_od",
    "data_zatrudnienia": "zatrudniony_od",
}


def normalize_editable_fields(raw: Any) -> list[str]:
    """Zwróć poprawną, unikalną listę pól Profilu.

    Obsługuje stare listy oraz CSV. Legacy ``staz`` mapuje na realne pole
    ``zatrudniony_od``. Nieznane/uszkodzone wpisy (np. ``im``) są odrzucane.
    Kolejność zawsze odpowiada kolejności pól w interfejsie.
    """

    tokens: list[str] = []

    def add(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            for token in re.split(r"[,;\n]+", value):
                text = token.strip().casefold()
                if text:
                    tokens.append(text)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                add(item)
            return
        text = str(value).strip().casefold()
        if text:
            tokens.append(text)

    add(raw)
    selected: set[str] = set()
    for token in tokens:
        canonical = _FIELD_ALIASES.get(token, token)
        if canonical in _FIELD_KEYS:
            selected.add(canonical)

    return [key for key, _label in EDITABLE_PROFILE_FIELDS if key in selected]


def editable_fields_csv(raw: Any) -> str:
    """Tekst pomocniczy dla istniejącego StringVar w Ustawieniach."""

    return ", ".join(normalize_editable_fields(raw))


__all__ = [
    "EDITABLE_PROFILE_FIELDS",
    "editable_fields_csv",
    "normalize_editable_fields",
]
