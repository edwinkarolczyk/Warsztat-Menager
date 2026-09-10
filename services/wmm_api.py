# version: 1.0
"""Bezpieczny punkt wejścia WMM z blokadą zapisu danych Maszyn."""

from __future__ import annotations

import sys

from machine_file_guard import machine_file_lock as _machine_file_lock
from services import wmm_api_impl as _impl


if not getattr(_impl, "_WM10_MACHINE_FILE_GUARD", False):
    _original_update_machine = _impl._update_machine

    def _guarded_update_machine(machine_id: str, mutator):
        with _machine_file_lock(_impl._machines_path()):
            return _original_update_machine(machine_id, mutator)

    _impl._update_machine = _guarded_update_machine
    _impl._WM10_MACHINE_FILE_GUARD = True

# Zachowaj dotychczasowy publiczny moduł i wszystkie jego symbole.
sys.modules[__name__] = _impl
