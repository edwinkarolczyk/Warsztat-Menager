"""UI-only regression for the guided Planista order editor.

Do not replace the production callbacks or order format while improving layout.
"""
import ast
from pathlib import Path


SOURCE = Path("planista_editor_runtime.py").read_text(encoding="utf-8")


def test_editor_is_valid_python():
    ast.parse(SOURCE)


def test_summary_and_three_step_workflow_are_visible():
    for label in (
        "PLAN PRODUKTU", "WYKONANO", "POZOSTAŁO",
        "1. Wybierz półprodukt",
        "2. Zgłoś wykonanie",
        "3. Gotowy produkt",
        "Przejdź do potwierdzenia produktu",
    ):
        assert label in SOURCE


def test_manual_correction_is_separate_from_primary_operation():
    assert 'text="Zapisz wykonanie operacji"' in SOURCE
    assert 'command=save_operation' in SOURCE
    assert 'text="Zapisz plan"' in SOURCE
    assert 'command=save_semi_target' in SOURCE
    assert 'text="Zapisz wykonanie półproduktu"' in SOURCE
    assert 'command=save_semi_done' in SOURCE
    assert 'else "Korekta planu / zapis ręczny' in SOURCE
    assert 'semi_edit.pack_forget()' in SOURCE
    assert 'operation_frame.pack_forget()' in SOURCE


def test_surplus_is_only_shown_when_pending_and_uses_existing_callback():
    assert "pending > 1e-9" in SOURCE
    assert "surplus_button.pack_forget()" in SOURCE
    assert "command=transfer_pending_semi" in SOURCE


def test_selection_survives_refresh_and_plan_data_save_is_unambiguous():
    assert "old_selection = semi_tree.selection()" in SOURCE
    assert "semi_tree.selection_set(picked)" in SOURCE
    assert "on_semi_select()" in SOURCE
    assert 'text="Zapisz dane zlecenia"' in SOURCE
    assert "command=save_basic" in SOURCE
    assert "command=save_done" in SOURCE
    assert "command=settle_material" in SOURCE
