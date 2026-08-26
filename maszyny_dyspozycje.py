# version: 1.5
# Zmiany 1.5:
# - Zapis historii DOCX używa trybu zgodnego z dyskami sieciowymi/SMB.
# Zmiany 1.4:
# - Historia DOCX korzysta z bezpośredniego zapisu po wykonaniu przeglądu/naprawy.
# - Dodano integrację wydruku planu przeglądów maszyn.
# Zmiany 1.3:
# - Podłączenie dodatkowej karty historii DOCX do modułu Maszyny.
# - Właściwa logika Dyspozycji maszyn pozostaje bez zmian w module core.
"""Adapter modułu Dyspozycji maszyn z integracją historii DOCX."""

from __future__ import annotations

import sys
import types
from importlib import import_module

import machine_history_runtime as _history_runtime
from machine_history_docx_io import append_history_entry as _append_history_entry

# Runtime zapisuje zdarzenia bezpośrednio po wykonaniu przeglądu/naprawy.
# Podmieniamy wyłącznie warstwę fizycznego zapisu DOCX, aby działała także
# na udziałach sieciowych Windows/SMB, bez zmiany logiki Maszyn i Dyspozycji.
_history_runtime.append_history_entry = _append_history_entry
install_gui_integration = _history_runtime.install_gui_integration

_core = import_module("_maszyny_dyspozycje_core")
__all__ = [name for name in vars(_core) if not name.startswith("_")]


def _ensure_gui_integration() -> None:
    gui_module = sys.modules.get("gui_maszyny")
    if gui_module is not None:
        install_gui_integration(gui_module)


class _IntegratedModule(types.ModuleType):
    """Deleguje API do core i podłącza GUI dokładnie przy użyciu modułu Maszyn."""

    def __getattribute__(self, name: str):
        if name not in {
            "_ensure_gui_integration",
            "_core",
            "_IntegratedModule",
            "__class__",
            "__dict__",
            "__name__",
            "__spec__",
            "__loader__",
            "__package__",
            "__file__",
            "__cached__",
            "__all__",
        }:
            _ensure_gui_integration()
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return getattr(_core, name)

    def __setattr__(self, name: str, value) -> None:
        if not name.startswith("__") and hasattr(_core, name):
            setattr(_core, name, value)
            return
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if not name.startswith("__") and hasattr(_core, name):
            delattr(_core, name)
            return
        super().__delattr__(name)


def __getattr__(name: str):
    _ensure_gui_integration()
    return getattr(_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_core)))


sys.modules[__name__].__class__ = _IntegratedModule
_ensure_gui_integration()
