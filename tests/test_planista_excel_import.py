# WM-VERSION: 0.2
# Plik: tests/test_planista_excel_import.py
# version: 1.1
# 1.1: regresje dopasowania pozycji Excel do Produktów WM po oznaczeniu.

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from planista_excel_import import PlanExcelError, load_production_plan
from planista_excel_match import (
    STATUS_AMBIGUOUS,
    STATUS_FOUND,
    STATUS_MISSING,
    extract_product_designation,
    excel_mapping_key,
    match_excel_product,
    match_production_plan,
)


def _fixture_xlsx(path: Path, sheet_name: str = "PLAN 2026") -> Path:
    shared = [
        "Nr zlec.",
        " ",
        "Ilość",
        "Data wysyłki",
        "Proces",
        "1.327.50 NW – RAL 5003",
        "1.620.165 NW – RAL 5003",
        "1.435.135 BH – RAL 3000",
        "zgrzane",
        "x",
    ]
    shared_xml = "".join(f"<si><t>{value}</t></si>" for value in shared)
    workbook_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="{sheet_name}" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''
    sheet_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
 <sheetData>
  <row r="1">
   <c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c>
   <c r="D1" t="s"><v>3</v></c><c r="E1" t="s"><v>4</v></c>
  </row>
  <row r="4">
   <c r="A4"><v>659</v></c><c r="B4" t="s"><v>5</v></c><c r="C4"><v>640</v></c>
   <c r="D4"><v>46279</v></c><c r="E4" t="s"><v>8</v></c>
  </row>
  <row r="5">
   <c r="B5" t="s"><v>6</v></c><c r="C5"><v>84</v></c><c r="E5" t="s"><v>8</v></c>
  </row>
  <row r="6">
   <c r="A6"><v>593</v></c><c r="B6" t="s"><v>7</v></c><c r="C6"><v>420</v></c>
   <c r="D6"><v>46281</v></c><c r="E6" t="s"><v>9</v></c>
  </row>
 </sheetData>
</worksheet>'''
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        archive.writestr(
            "xl/sharedStrings.xml",
            f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared)}" uniqueCount="{len(shared)}">{shared_xml}</sst>''',
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return path


def test_import_reads_plan_groups_and_does_not_modify_source(tmp_path):
    path = _fixture_xlsx(tmp_path / "Plan.xlsx")
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    payload = load_production_plan(path)

    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after
    assert payload["sheet"] == "PLAN 2026"
    assert payload["header_row"] == 1
    assert len(payload["rows"]) == 3

    first, second, third = payload["rows"]
    assert first == {
        "source_row": 4,
        "nr_zlec": "659",
        "produkt": "1.327.50 NW – RAL 5003",
        "ilosc": 640.0,
        "data_wysylki": "2026-09-14",
        "proces": "zgrzane",
    }
    assert second["nr_zlec"] == "659"
    assert second["data_wysylki"] == "2026-09-14"
    assert second["produkt"] == "1.620.165 NW – RAL 5003"
    assert third["nr_zlec"] == "593"
    assert third["data_wysylki"] == "2026-09-16"


def test_import_requires_expected_sheet(tmp_path):
    path = _fixture_xlsx(tmp_path / "Plan.xlsx", sheet_name="INNY ARKUSZ")
    with pytest.raises(PlanExcelError, match="PLAN 2026"):
        load_production_plan(path)


def test_gui_planowanie_installs_excel_runtime():
    source = Path("gui_planowanie.py").read_text(encoding="utf-8")
    assert "from planista_excel_runtime import install_planista_excel_runtime" in source
    assert "install_planista_excel_runtime()" in source


def test_extracts_leading_product_designation_without_guessing_name():
    assert extract_product_designation("1.560.450 SITI - RAL 7001GS") == "1.560.450"
    assert extract_product_designation("5.WN10 TESAM - RAL 6016") == "5.WN10"
    assert extract_product_designation("HP14 Tatra") == "HP14"


def test_matching_uses_designation_as_primary_key_and_name_as_confirmation():
    products = {
        "1.560.450": {"symbol": "1.560.450", "nazwa": "SITI"},
    }
    result = match_excel_product("1.560.450 SITI - RAL 7001GS", products)

    assert result["match_status"] == STATUS_FOUND
    assert result["excel_oznaczenie"] == "1.560.450"
    assert result["wm_symbol"] == "1.560.450"
    assert result["wm_nazwa"] == "SITI"
    assert "potwierdzone" in result["match_note"]


def test_same_name_with_different_designation_is_not_fuzzy_matched():
    products = {
        "1.327.50": {"symbol": "1.327.50", "nazwa": "NW"},
    }
    result = match_excel_product("99.999 NW - RAL 5003", products)

    assert result["match_status"] == STATUS_MISSING
    assert result["wm_symbol"] == ""


def test_unknown_product_is_explicitly_missing():
    products = {
        "1.327.50": {"symbol": "1.327.50", "nazwa": "NW"},
    }
    result = match_excel_product("8.888.888 NIEZNANY", products)

    assert result["match_status"] == STATUS_MISSING
    assert result["excel_oznaczenie"] == "8.888.888"
    assert "Brak produktu" in result["match_note"]


def test_duplicate_designation_is_ambiguous_when_name_cannot_resolve_it():
    products = {
        "A": {"symbol": "1.327.50", "nazwa": "NW"},
        "B": {"symbol": "1.327.50", "nazwa": "BH"},
    }
    result = match_excel_product("1.327.50 INNY - RAL 5003", products)

    assert result["match_status"] == STATUS_AMBIGUOUS
    assert result["wm_symbol"] == ""
    assert len(result["candidate_symbols"]) == 2


def test_name_can_resolve_duplicate_designation_but_never_replace_code():
    products = {
        "A": {"symbol": "1.327.50", "nazwa": "NW"},
        "B": {"symbol": "1.327.50", "nazwa": "BH"},
    }
    result = match_excel_product("1.327.50 NW - RAL 5003", products)

    assert result["match_status"] == STATUS_FOUND
    assert result["wm_symbol"] == "1.327.50"
    assert result["wm_nazwa"] == "NW"
    assert "jednoznacznie" in result["match_note"]


def test_whole_import_is_matched_row_by_row_without_losing_order_groups(tmp_path):
    payload = load_production_plan(_fixture_xlsx(tmp_path / "Plan.xlsx"))
    products = {
        "1.327.50": {"symbol": "1.327.50", "nazwa": "NW"},
        "1.620.165": {"symbol": "1.620.165", "nazwa": "NW"},
    }

    matched = match_production_plan(payload, products)

    assert [row["nr_zlec"] for row in matched["rows"]] == ["659", "659", "593"]
    assert [row["match_status"] for row in matched["rows"]] == [
        STATUS_FOUND,
        STATUS_FOUND,
        STATUS_MISSING,
    ]
    assert matched["match_summary"] == {
        STATUS_FOUND: 2,
        STATUS_MISSING: 1,
        STATUS_AMBIGUOUS: 0,
    }



def test_loto_product_matches_exact_normalized_name_and_dimensions_without_code():
    products = {
        "L-1": {"symbol": "L-1", "nazwa": "Szafka loto"},
        "L-2": {"symbol": "L-2", "nazwa": "Szafka loto 270x100x170"},
        "L-3": {"symbol": "L-3", "nazwa": "Szafka loto 260x100x300"},
    }
    expected = [
        ("Szafka LOTO – RAL 1023", "L-1"),
        ("Szafka LOTO 270×100×170 – RAL 1023", "L-2"),
        ("Szafka LOTO 260x100x300 – RAL 1023", "L-3"),
    ]
    for text, symbol in expected:
        result = match_excel_product(text, products)
        assert result["match_status"] == STATUS_FOUND, text
        assert result["wm_symbol"] == symbol, text
        assert result["match_method"] == "name"


def test_loto_dimensions_must_not_match_different_size():
    products = {
        "L-3": {"symbol": "L-3", "nazwa": "Szafka loto 260x100x300"},
    }
    result = match_excel_product("Szafka LOTO 270×100×170 – RAL 1023", products)
    assert result["match_status"] != STATUS_FOUND
    assert result["wm_symbol"] == ""


def test_ambiguous_product_name_requires_manual_selection():
    products = {
        "L-2A": {"symbol": "L-2A", "nazwa": "Szafka loto 270x100x170"},
        "L-2B": {"symbol": "L-2B", "nazwa": "Szafka LOTO 270×100×170"},
    }
    result = match_excel_product("Szafka LOTO 270×100×170 – RAL 1023", products)
    assert result["match_status"] == STATUS_AMBIGUOUS
    assert set(result["candidate_symbols"]) == {"L-2A", "L-2B"}


def test_manual_mapping_is_specific_to_exact_excel_description_including_ral():
    products = {
        "L-2A": {"symbol": "L-2A", "nazwa": "Szafka loto 270x100x170"},
        "L-2B": {"symbol": "L-2B", "nazwa": "Szafka loto 270x100x170"},
    }
    original = "Szafka LOTO 270×100×170 – RAL 1023"
    mappings = {excel_mapping_key(original): {"wm_symbol": "L-2B"}}
    result = match_excel_product(original, products, manual_mappings=mappings)
    assert result["match_status"] == STATUS_FOUND
    assert result["wm_symbol"] == "L-2B"
    assert result["match_method"] == "manual"

    other_color = match_excel_product(
        "Szafka LOTO 270x100x170 – RAL 9011",
        products,
        manual_mappings=mappings,
    )
    assert other_color["match_status"] == STATUS_AMBIGUOUS


def test_stale_manual_mapping_does_not_match_missing_product():
    products = {"L-2A": {"symbol": "L-2A", "nazwa": "Szafka loto 270x100x170"}}
    value = "Szafka LOTO 270×100×170 – RAL 1023"
    stale = {excel_mapping_key(value): {"wm_symbol": "DELETED"}}
    result = match_excel_product(value, products, manual_mappings=stale)
    assert result["match_status"] == STATUS_FOUND
    assert result["wm_symbol"] == "L-2A"
    assert result.get("match_method") != "manual"


def test_manual_mappings_are_atomic_and_persist_across_imports(tmp_path, monkeypatch):
    import json
    import planista_excel_mappings as mappings

    destination = tmp_path / "planista" / "excel_product_mappings.json"
    monkeypatch.setattr(mappings, "mapping_path", lambda: destination)
    mappings.remember_manual_mapping("Szafka LOTO – RAL 1023", "L-1")
    mappings.remember_manual_mapping("Szafka LOTO 270×100×170 – RAL 1023", "L-2")

    saved = mappings.load_manual_mappings()
    assert len(saved) == 2
    assert saved[excel_mapping_key("Szafka LOTO – RAL 1023")]["wm_symbol"] == "L-1"
    assert saved[excel_mapping_key("Szafka LOTO 270x100x170 – RAL 1023")]["wm_symbol"] == "L-2"
    assert json.loads(destination.read_text(encoding="utf-8"))["schema"] == 1


def test_analysis_preview_has_manual_mapping_button_and_refreshes_working_payload():
    source = Path("planista_excel_runtime.py").read_text(encoding="utf-8")
    assert 'text="Przypisz Produkt WM…"' in source
    assert "remember_manual_mapping(excel_text, symbol)" in source
    assert 'payload["match_summary"] = matched["match_summary"]' in source
    assert "owner._excel_plan_import = payload" in source
    assert "dims_excel != dims_wm" in source


def test_saved_mapping_does_not_ignore_changed_dimensions():
    products = {
        "L-2": {"symbol": "L-2", "nazwa": "Szafka loto 260x100x300"},
    }
    excel_text = "Szafka LOTO 270×100×170 – RAL 1023"
    mappings = {excel_mapping_key(excel_text): {"wm_symbol": "L-2"}}

    match = match_excel_product(excel_text, products, manual_mappings=mappings)

    assert match["match_status"] != STATUS_FOUND
    assert match["wm_symbol"] == ""


def test_real_catalog_loto_uses_designation_dimensions_not_generic_names():
    # W rzeczywistej kartotece wszystkie trzy nazwy są "Szafka loto".
    # Rozmiary są zapisane tylko w oznaczeniach produktu.
    products = {
        "Szafka loto": {"symbol": "Szafka loto", "nazwa": "Szafka loto"},
        "270x100x170": {"symbol": "270x100x170", "nazwa": "Szafka loto"},
        "260x100x300": {"symbol": "260x100x300", "nazwa": "Szafka loto"},
    }
    cases = [
        ("Szafka LOTO – RAL 1023", "Szafka loto"),
        ("Szafka LOTO 270×100×170 – RAL 1023", "270x100x170"),
        ("Szafka LOTO 260x100x300 – RAL 1023", "260x100x300"),
    ]
    for excel_text, wm_symbol in cases:
        matched = match_excel_product(excel_text, products)
        assert matched["match_status"] == STATUS_FOUND, excel_text
        assert matched["wm_symbol"] == wm_symbol, excel_text
        assert matched["match_method"] == "name"


def test_real_catalog_does_not_guess_size_without_matching_catalog_dimensions():
    products = {
        "Szafka loto": {"symbol": "Szafka loto", "nazwa": "Szafka loto"},
        "260x100x300": {"symbol": "260x100x300", "nazwa": "Szafka loto"},
    }
    matched = match_excel_product("Szafka LOTO 270x100x170 – RAL 1023", products)
    assert matched["match_status"] == STATUS_AMBIGUOUS
    assert matched["wm_symbol"] == ""
    assert "260x100x300" not in matched["candidate_symbols"]


def test_manual_mapping_does_not_override_different_dimensions_from_catalog_symbol():
    products = {
        "260x100x300": {"symbol": "260x100x300", "nazwa": "Szafka loto"},
    }
    excel_text = "Szafka LOTO 270×100×170 – RAL 1023"
    manual = {excel_mapping_key(excel_text): {"wm_symbol": "260x100x300"}}
    matched = match_excel_product(excel_text, products, manual_mappings=manual)
    assert matched["match_status"] != STATUS_FOUND


def test_variant_without_dimensions_never_infers_specific_size_from_name_alone():
    products = {
        "270x100x170": {"symbol": "270x100x170", "nazwa": "Szafka loto"},
    }
    matched = match_excel_product("Szafka LOTO – RAL 1023", products)
    assert matched["match_status"] == STATUS_AMBIGUOUS


def test_manual_picker_checks_dimensions_from_catalog_symbol():
    source = Path("planista_excel_runtime.py").read_text(encoding="utf-8")
    assert "dims_symbol = product_dimensions(symbol)" in source
    assert "dims_wm = catalog_product_dimensions(wm_name, symbol)" in source


def test_composite_att_designations_are_distinct_and_normalized():
    products = {
        "ATT 507.360": {"symbol": "ATT 507.360", "nazwa": "ATT"},
        "ATT 1267.260": {"symbol": "ATT 1267.260", "nazwa": "ATT"},
    }
    assert extract_product_designation("ATT 507.360 – RAL 5010") == "ATT 507.360"
    assert extract_product_designation("ATT 1267.260 – RAL 5010") == "ATT 1267.260"
    first = match_excel_product("ATT 507.360 – RAL 5010", products)
    second = match_excel_product("ATT 1267.260 – RAL 5010", products)
    assert first["match_status"] == STATUS_FOUND
    assert second["match_status"] == STATUS_FOUND
    assert first["wm_symbol"] != second["wm_symbol"]


def test_name_with_producer_and_dimensions_is_only_suggested():
    from planista_excel_match import MATCH_CATEGORY_POSSIBLE
    products = {
        "670x210x1245": {
            "symbol": "670x210x1245",
            "nazwa": "Szafa na akcesoria ppoż",
        },
    }
    result = match_excel_product(
        "Szafa na akcesoria ppoż KORUS 670×210×1245 – RAL 3000", products
    )
    assert result["match_status"] == STATUS_AMBIGUOUS
    assert result["match_category"] == MATCH_CATEGORY_POSSIBLE
    assert result["candidate_symbols"] == ["670x210x1245"]
    assert result["wm_symbol"] == ""


def test_product_dimension_conflict_is_distinguished_from_absent_product():
    from planista_excel_match import MATCH_CATEGORY_DIMENSIONS, MATCH_CATEGORY_MISSING
    products = {
        "260x100x300": {"symbol": "260x100x300", "nazwa": "Szafka LOTO"},
    }
    conflict = match_excel_product("Szafka LOTO 270×100×170 – RAL 1023", products)
    absent = match_excel_product("99.999.999 NIEZNANY", products)
    assert conflict["match_status"] != STATUS_FOUND
    assert conflict["match_category"] == MATCH_CATEGORY_DIMENSIONS
    assert absent["match_status"] == STATUS_MISSING
    assert absent["match_category"] == MATCH_CATEGORY_MISSING


def test_xlsx_parser_reports_skipped_rows_and_invalid_qty_date(tmp_path):
    path = _fixture_xlsx(tmp_path / "Plan.xlsx")
    with ZipFile(path, "r") as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    xml = files["xl/worksheets/sheet1.xml"].decode("utf-8")
    xml = xml.replace(
        '<c r="B5" t="s"><v>6</v></c>',
        '<c r="B5" t="s"><v>1</v></c>',
    )
    xml = xml.replace(
        '<c r="C6"><v>420</v></c>',
        '<c r="C6" t="str"><v>nieprawidlowe</v></c>',
    )
    xml = xml.replace(
        '<c r="D4"><v>46279</v></c>',
        '<c r="D4" t="str"><v>31 lutego</v></c>',
    )
    files["xl/worksheets/sheet1.xml"] = xml.encode("utf-8")
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)

    before = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = load_production_plan(path)
    diag = payload["import_diagnostics"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert diag["source_rows"] == 3
    assert diag["imported_rows"] == 2
    assert diag["skipped_rows"][0]["source_row"] == 5
    assert diag["row_warnings"][0]["source_row"] == 4
    assert "data" in " ".join(diag["row_warnings"][0]["reasons"])
    assert diag["row_warnings"][1]["source_row"] == 6
    assert "ilości" in " ".join(diag["row_warnings"][1]["reasons"])


def test_blank_product_row_still_carries_next_order_and_date(tmp_path):
    path = _fixture_xlsx(tmp_path / "Plan.xlsx")
    with ZipFile(path, "r") as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    xml = files["xl/worksheets/sheet1.xml"].decode("utf-8")
    xml = xml.replace(
        '<c r="B5" t="s"><v>6</v></c>',
        '<c r="A5"><v>750</v></c><c r="B5" t="s"><v>1</v></c><c r="D5"><v>46279</v></c>',
    )
    xml = xml.replace('<c r="A6"><v>593</v></c>', "")
    xml = xml.replace('<c r="D6"><v>46281</v></c>', "")
    files["xl/worksheets/sheet1.xml"] = xml.encode("utf-8")
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)

    payload = load_production_plan(path)
    assert len(payload["rows"]) == 2
    assert payload["import_diagnostics"]["skipped_rows"][0]["source_row"] == 5
    assert payload["rows"][1]["nr_zlec"] == "750"
    assert payload["rows"][1]["data_wysylki"] == "2026-09-14"
