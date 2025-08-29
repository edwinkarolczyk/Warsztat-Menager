"""Package aggregating GUI submodules.

Submodules are exposed as attributes so they can be imported like::
    from gui import logowanie

A simple registry keeps track of loaded submodules which makes it easy
for future extensions to plug in additional GUI modules.
"""

from importlib import import_module
from types import ModuleType
from typing import Dict

__all__ = [
    "logowanie",
    "magazyn",
    "maszyny",
    "narzedzia",
    "panel",
    "produkty",
    "profile",
    "settings_shifts",
    "uzytkownicy",
    "zlecenia",
]

_registry: Dict[str, ModuleType] = {}


def _load(name: str) -> ModuleType:
    module = import_module(f"{__name__}.{name}")
    _registry[name] = module
    return module


def __getattr__(name: str) -> ModuleType:  # pragma: no cover - simple proxy
    if name in __all__:
        return _registry.get(name) or _load(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_registered() -> Dict[str, ModuleType]:
    """Return a mapping of already loaded GUI submodules."""
    return dict(_registry)
