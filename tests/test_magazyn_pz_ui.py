# version: 1.0
from pathlib import Path

from gui_magazyn_pz import _display_unit


SOURCE = Path("gui_magazyn_pz.py").read_text(encoding="utf-8")


def test_pz_display_unit_comes_from_warehouse_item():
    assert _display_unit({"jednostka": "mm"}) == "mm"
    assert _display_unit({"jednostka": "mb"}) == "mb"
    assert _display_unit({"jednostka": "szt"}) == "szt"
    assert _display_unit({}) == "—"


def test_pz_quantity_label_shows_selected_unit():
    assert 'f"Ilość [{unit}]:"' in SOURCE


def test_pz_uses_global_context_help_for_form_rows():
    assert "from ui_context_help import add_help_button" in SOURCE
    assert "for row, label, variable, help_text in rows:" in SOURCE
    assert "add_help_button(" in SOURCE
    assert '"Dostawca:"' in SOURCE
    assert '"Numer dokumentu:"' in SOURCE
    assert '"Komentarz (opcjonalnie):"' in SOURCE
