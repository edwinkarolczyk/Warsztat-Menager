# version: 1.9
"""Bezpieczny punkt wejścia modułu Maszyny z warstwowym rozszerzeniem hali.

Oryginalna, działająca implementacja Maszyn pozostaje bez zmian w
``gui_maszyny_legacy.py``. Poniżej instalujemy jedynie rozszerzenie
pomieszczeń/lokalizacji i eksportujemy ten sam interfejs modułu.
"""
from __future__ import annotations

import gui_maszyny_legacy as _legacy
from widok_hali.machine_rooms_patch import install_machine_rooms as _install_machine_rooms

_install_machine_rooms(_legacy)

_SKIP = {
    "__name__",
    "__file__",
    "__package__",
    "__loader__",
    "__spec__",
    "__builtins__",
}
for _name, _value in vars(_legacy).items():
    if _name not in _SKIP:
        globals()[_name] = _value

__all__ = getattr(
    _legacy,
    "__all__",
    [name for name in globals() if not name.startswith("_")],
)
