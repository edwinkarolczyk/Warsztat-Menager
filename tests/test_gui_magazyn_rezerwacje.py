# WM-VERSION: 0.1
# Plik: tests/test_gui_magazyn_rezerwacje.py
# version: 1.0

from __future__ import annotations

from pathlib import Path


def test_release_dialog_uses_canonical_unreserve_flow():
    gui_source = Path("gui_magazyn_rezerwacje.py").read_text(encoding="utf-8")
    logic_source = Path("logika_magazyn.py").read_text(encoding="utf-8")

    assert "LM.zwolnij_rezerwacje(" in gui_source
    assert 'op="ZWOLNIJ"' not in gui_source
    assert '"UNRESERVE"' in logic_source
