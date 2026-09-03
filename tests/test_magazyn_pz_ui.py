# version: 1.1
from pathlib import Path

import pytest

from gui_magazyn_pz import _bars_to_mm, _display_unit


SOURCE = Path("gui_magazyn_pz.py").read_text(encoding="utf-8")
EDIT_SOURCE = Path("gui_magazyn_edit.py").read_text(encoding="utf-8")


def test_pz_display_unit_comes_from_warehouse_item():
    assert _display_unit({"jednostka": "mm"}) == "mm"
    assert _display_unit({"jednostka": "mb"}) == "mb"
    assert _display_unit({"jednostka": "szt"}) == "szt"
    assert _display_unit({}) == "—"


def test_pz_quantity_label_shows_selected_unit_for_non_mm_items():
    assert 'f"Ilość [{unit}]:"' in SOURCE


def test_pz_mm_receipt_uses_bar_count_times_bar_length():
    assert _bars_to_mm("50", "3000") == 150000.0
    assert _bars_to_mm("2", "6000,5") == 12001.0
    assert '"Liczba sztang:"' in SOURCE
    assert '"Długość sztangi [mm]:"' in SOURCE
    assert 'unit.casefold() == "mm"' in SOURCE


def test_pz_bar_count_must_be_positive_integer():
    with pytest.raises(ValueError):
        _bars_to_mm("0", "3000")
    with pytest.raises(ValueError):
        _bars_to_mm("1.5", "3000")
    with pytest.raises(ValueError):
        _bars_to_mm("2", "0")


def test_existing_item_edit_hides_technology_tasks_and_preserves_them():
    edit_form = EDIT_SOURCE.split("def _build_edit_form", 1)[1].split("def _open_pz", 1)[0]
    assert "Zadania tech." not in edit_form
    assert "var_zad" not in edit_form
    assert 'self.item["zadania"] = zadania' not in EDIT_SOURCE


def test_pz_uses_global_context_help_for_form_rows():
    assert "from ui_context_help import add_help_button" in SOURCE
    assert "for row, (label, variable, help_text) in enumerate(rows):" in SOURCE
    assert "add_help_button(" in SOURCE
    assert '"Dostawca:"' in SOURCE
    assert '"Numer dokumentu:"' in SOURCE
    assert '"Komentarz (opcjonalnie):"' in SOURCE
