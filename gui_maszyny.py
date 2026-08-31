# version: 1.9
"""Bezpieczny punkt wejścia modułu Maszyny z warstwowym rozszerzeniem hali.

Oryginalna, działająca implementacja Maszyn pozostaje bez zmian w
``gui_maszyny_legacy.py``. Po instalacji rozszerzenia ten import zwraca
bezpośrednio oryginalny obiekt modułu, dzięki czemu nie powstaje drugi zestaw
globali i zachowują się dotychczasowe testy/monkeypatch oraz importy.
"""
from __future__ import annotations

import sys

import gui_maszyny_legacy as _legacy
from widok_hali.machine_rooms_patch import install_machine_rooms as _install_machine_rooms
from widok_hali.machine_rooms_persistence import (
    install_machine_room_persistence as _install_machine_room_persistence,
)

_install_machine_rooms(_legacy)
_install_machine_room_persistence(_legacy)

# Kluczowe dla zgodności: użytkownik ``import gui_maszyny`` dostaje dokładnie
# moduł z dotychczasową implementacją, a nie proxy z kopiami jego symboli.
sys.modules[__name__] = _legacy
