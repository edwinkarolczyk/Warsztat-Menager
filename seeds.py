"""Minimalne dane startowe dla podstawowych modułów GUI."""

from __future__ import annotations

SEEDS = {
    "maszyny": [
        {
            "id": "M001",
            "name": "Maszyna testowa",
            "nr": "MX-001",
            "status": "OK",
            "lokalizacja": "Hala A",
        }
    ],
    "narzedzia": [
        {
            "id": "T001",
            "name": "Młotek testowy",
            "typ": "NN",
            "status": "sprawne",
            "SN": False,
            "NN": True,
        }
    ],
    "zlecenia": [
        {
            "id": "Z001",
            "nazwa": "Zlecenie testowe",
            "opis": "Pierwsze zlecenie demo",
            "status": "nowe",
        }
    ],
    "magazyn": [
        {
            "id": "MAT001",
            "nazwa": "Materiał testowy",
            "jm": "szt",
            "qty": 10,
        }
    ],
    "profiles": [
        {
            "login": "admin",
            "rola": "admin",
            "imie": "Admin",
            "aktywne": True,
        }
    ],
}
