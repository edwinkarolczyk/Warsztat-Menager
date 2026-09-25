# WM-VERSION: 0.1

from pathlib import Path

import gui_magazyn_bom as GMB


def test_unassigned_filter_means_product_without_assigned_semiproducts():
    empty = {"symbol": "P-001", "nazwa": "Produkt bez BOM", "BOM": []}
    assigned = {
        "symbol": "P-002",
        "nazwa": "Produkt z BOM",
        "BOM": [{"typ": "polprodukt", "kod": "POL-001", "ilosc_na_sztuke": 1}],
    }

    assert GMB._product_matches_filter("P-001", empty, unassigned_only=True)
    assert not GMB._product_matches_filter("P-002", assigned, unassigned_only=True)
    assert GMB._product_matches_filter("P-002", assigned, unassigned_only=False)


def test_product_search_uses_symbol_name_and_bom_component_name():
    record = {
        "symbol": "1.775.250",
        "nazwa": "Banaszak",
        "BOM": [{"typ": "polprodukt", "kod": "POL-007", "ilosc_na_sztuke": 2}],
    }
    semis = {"POL-007": {"kod": "POL-007", "nazwa": "Hak prosty"}}

    assert GMB._product_matches_filter("1.775.250", record, query="775")
    assert GMB._product_matches_filter("1.775.250", record, query="banaszak")
    assert GMB._product_matches_filter(
        "1.775.250", record, query="hak prosty", polprodukty=semis
    )
    assert not GMB._product_matches_filter(
        "1.775.250", record, query="nieistniejacy", polprodukty=semis
    )


def test_new_raw_material_default_bar_length_is_6000_mm():
    assert GMB.DEFAULT_BAR_LENGTH_MM == 6000.0

    source = Path("planista_stock_runtime.py").read_text(encoding="utf-8")
    assert 'getattr(GMB, "DEFAULT_BAR_LENGTH_MM", 6000)' in source


def test_products_ui_has_search_and_unassigned_controls():
    source = Path("gui_magazyn_bom.py").read_text(encoding="utf-8")
    assert 'text="Szukaj:"' in source
    assert 'text="Tylko nieprzypisane"' in source
    assert "self.pr_search_var.trace_add" in source
