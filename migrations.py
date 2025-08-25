"""
Migracje konfiguracji MW
Wersja: 1.0.1

Cel:
- Utrzymywać zgodność konfiguracji między wersjami aplikacji.
- W razie zmian kluczy lub struktur – przenosić/renamować pola.

Na dziś (v1.0.1) brak aktywnych migracji – zostawiamy szkielet.
"""
from __future__ import annotations
from typing import Dict, Any

LATEST_VERSION = 1


def migrate(config: Dict[str, Any]) -> Dict[str, Any]:
    """Zaktualizuj przekazany słownik config do najnowszej wersji schematu.

    Przykład dodawania migracji (odkomentuj i dostosuj, gdy podbijesz wersję):

    version = int(config.get("config_version", 1) or 1)
    if version < 2:
        # 1) Przeniesienie ui.color -> ui.accent, jeśli istnieje i brak docelowego klucza
        ui = config.get("ui", {})
        if isinstance(ui, dict) and "color" in ui and "accent" not in ui:
            ui["accent"] = ui.pop("color")
        version = 2

    if version < 3:
        # 2) Zmiana typu/zakresów – np. pin_length clamp do [4,8]
        auth = config.get("auth", {})
        if isinstance(auth, dict):
            pin = auth.get("pin_length")
            if isinstance(pin, int):
                auth["pin_length"] = max(4, min(8, pin))
        version = 3

    """
    # Aktualnie brak realnych kroków – tylko ustawienie wersji
    config["config_version"] = LATEST_VERSION
    return config


def needs_migration(config: Dict[str, Any]) -> bool:
    """Czy wymagana jest migracja configu?"""
    try:
        return int(config.get("config_version", 1) or 1) < LATEST_VERSION
    except Exception:
        return True