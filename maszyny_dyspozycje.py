# version: 1.3
# Zmiany 1.3:
# - Podłączenie dodatkowej karty historii DOCX do modułu Maszyny.
# - Właściwa logika Dyspozycji maszyn pozostaje bez zmian w module core.
"""Adapter modułu Dyspozycji maszyn z integracją historii DOCX."""

from __future__ import annotations

import sys
from importlib import import_module

from machine_history_doc import install_gui_integration

_core = import_module("_maszyny_dyspozycje_core")
__all__ = [name for name in vars(_core) if not name.startswith("_")]


def _ensure_gui_integration() -> None:
    gui_module = sys.modules.get("gui_maszyny")
    if gui_module is not None:
        install_gui_integration(gui_module)


def __getattr__(name: str):
    _ensure_gui_integration()
    return getattr(_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_core)))
