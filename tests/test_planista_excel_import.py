# WM-VERSION: 0.1
# Plik: tests/test_planista_excel_import.py
# version: 1.0

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from planista_excel_import import PlanExcelError, load_production_plan


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
