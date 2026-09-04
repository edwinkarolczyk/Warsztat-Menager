# WM-VERSION: 0.1
# Plik: tests/test_planista_excel_sync_e2e.py
# version: 1.0
"""Końcowa regresja E2E: Excel -> analiza -> synchronizacja -> ponowny import."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from planista_excel_changes import (
    CHANGE_CHANGED,
    CHANGE_NEW_ORDER,
    CHANGE_NONE,
    CHANGE_REMOVED,
    analyze_and_store_plan_changes,
)
from planista_excel_import import PlanExcelError, load_production_plan
from planista_excel_match import STATUS_AMBIGUOUS, STATUS_FOUND, STATUS_MISSING, match_production_plan
import planista_excel_orders as sync


PRODUCTS = {
    "1.327.50": {"symbol": "1.327.50", "nazwa": "NW"},
    "1.620.165": {"symbol": "1.620.165", "nazwa": "NW"},
    "5.300.600": {"symbol": "5.300.600", "nazwa": "Szafka"},
    "2.100.100": {"symbol": "2.100.100", "nazwa": "Stary"},
    "2.200.200": {"symbol": "2.200.200", "nazwa": "Nowy"},
    "dup-a": {"symbol": "7.777", "nazwa": "Wariant A"},
    "dup-b": {"symbol": "7.777", "nazwa": "Wariant B"},
}


def _write_plan_xlsx(path: Path, records: list[dict], *, start_row: int = 4) -> Path:
    """Zbuduj minimalny, prawdziwy XLSX obsługiwany przez produkcyjny parser WM."""
    shared = ["Nr zlec.", " ", "Ilość", "Data wysyłki", "Proces"]
    for record in records:
        shared.extend([str(record["product"]), str(record.get("process") or "")])

    unique: list[str] = []
    for value in shared:
        if value not in unique:
            unique.append(value)
    indexes = {value: idx for idx, value in enumerate(unique)}

    workbook_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="PLAN 2026" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''

    row_xml = [
        '<row r="1">'
        f'<c r="A1" t="s"><v>{indexes["Nr zlec."]}</v></c>'
        f'<c r="B1" t="s"><v>{indexes[" "]}</v></c>'
        f'<c r="C1" t="s"><v>{indexes["Ilość"]}</v></c>'
        f'<c r="D1" t="s"><v>{indexes["Data wysyłki"]}</v></c>'
        f'<c r="E1" t="s"><v>{indexes["Proces"]}</v></c>'
        '</row>'
    ]
    for offset, record in enumerate(records):
        row_no = start_row + offset
        cells = []
        if record.get("order") not in (None, ""):
            cells.append(f'<c r="A{row_no}"><v>{record["order"]}</v></c>')
        cells.append(
            f'<c r="B{row_no}" t="s"><v>{indexes[str(record["product"])]}</v></c>'
        )
        cells.append(f'<c r="C{row_no}"><v>{record["qty"]}</v></c>')
        if record.get("date_serial") not in (None, ""):
            cells.append(f'<c r="D{row_no}"><v>{record["date_serial"]}</v></c>')
        process = str(record.get("process") or "")
        cells.append(f'<c r="E{row_no}" t="s"><v>{indexes[process]}</v></c>')
        row_xml.append(f'<row r="{row_no}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData></worksheet>'
    )
    shared_xml = "".join(f"<si><t>{escape(value)}</t></si>" for value in unique)

    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        archive.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            f'count="{len(unique)}" uniqueCount="{len(unique)}">{shared_xml}</sst>',
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return path


class _TempOrders:
    """Minimalny backend zleceń zapisujący realne JSON-y wyłącznie w tmp WM_ROOT."""

    def __init__(self, root: Path):
        self.root = root
        self.data = root / "data"
        self.orders = self.data / "zlecenia"
        self.orders.mkdir(parents=True, exist_ok=True)
        self._next = 1

    def _path(self, order_id: str) -> Path:
        return self.orders / f"{order_id}.json"

    def list(self) -> list[dict]:
        result = []
        for path in sorted(self.orders.glob("*.json")):
            result.append(json.loads(path.read_text(encoding="utf-8")))
        return result

    def create(self, product, qty, **kwargs):
        order_id = f"{self._next:06d}"
        self._next += 1
        record = {
            "id": order_id,
            "produkt": str(product),
            "ilosc": float(qty),
            "wykonano": 0.0,
            "status": "nowe",
            "termin": str(kwargs.get("termin") or ""),
            "zlec_wew": str(kwargs.get("zlec_wew") or ""),
            "version": f"BOM-{product}",
            "historia": [],
        }
        self._path(order_id).write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return dict(record), []

    def update(self, order_id, **kwargs):
        path = self._path(str(order_id))
        record = json.loads(path.read_text(encoding="utf-8"))
        if "ilosc" in kwargs:
            record["ilosc"] = float(kwargs["ilosc"])
        if "termin" in kwargs:
            record["termin"] = str(kwargs["termin"] or "")
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def by_product(self, product: str) -> dict:
        return next(item for item in self.list() if item.get("produkt") == product)


class _TmpConfig:
    def __init__(self, data: Path):
        self.data = data

    def path_data(self):
        return str(self.data)


def _install_temp_backend(monkeypatch, root: Path) -> _TempOrders:
    backend = _TempOrders(root)
    monkeypatch.setattr(sync.ZL, "list_zlecenia", backend.list)
    monkeypatch.setattr(sync.ZL, "create_zlecenie", backend.create)
    monkeypatch.setattr(sync.ZL, "update_zlecenie", backend.update)
    monkeypatch.setattr(sync, "ConfigManager", lambda: _TmpConfig(backend.data))
    return backend


def _analyze(path: Path, root: Path, products: dict = PRODUCTS) -> dict:
    parsed = load_production_plan(path)
    matched = match_production_plan(parsed, products)
    return analyze_and_store_plan_changes(matched, root=root)


def _approved(plan: dict) -> set[str]:
    return {
        item["identity"]
        for item in plan.get("items", [])
        if item.get("action") in {sync.ACTION_CREATE, sync.ACTION_UPDATE}
    }


def test_full_excel_sync_flow_is_idempotent_and_preserves_order_identity(monkeypatch, tmp_path):
    root = tmp_path / "WM_ROOT"
    backend = _install_temp_backend(monkeypatch, root)
    source = tmp_path / "Plan.xlsx"

    initial_records = [
        {"order": 659, "product": "1.327.50 NW – RAL 5003", "qty": 640, "date_serial": 46279, "process": "zgrzane"},
        {"order": None, "product": "1.620.165 NW – RAL 5003", "qty": 84, "date_serial": None, "process": "zgrzane"},
        {"order": 700, "product": "8.888.888 NIEZNANY", "qty": 10, "date_serial": 46281, "process": "zgrzane"},
        {"order": 701, "product": "7.777 INNY", "qty": 5, "date_serial": 46281, "process": "zgrzane"},
    ]
    _write_plan_xlsx(source, initial_records)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    first = _analyze(source, root)
    assert first["baseline_created"] is True
    assert first["match_summary"][STATUS_FOUND] == 2
    assert first["match_summary"][STATUS_MISSING] == 1
    assert first["match_summary"][STATUS_AMBIGUOUS] == 1
    assert Path(first["snapshot_path"]) == root / "data" / "planista" / "excel_plan_snapshot.json"

    create_plan = sync.build_order_sync_plan(first, orders=backend.list())
    assert [item["action"] for item in create_plan["items"]].count(sync.ACTION_CREATE) == 2
    assert [item["action"] for item in create_plan["items"]].count(sync.ACTION_SKIP) == 2
    applied = sync.apply_order_sync(
        first,
        create_plan,
        approved_identities=_approved(create_plan),
        autor="e2e",
    )
    assert applied["written"] == 2
    assert len(backend.list()) == 2
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash

    first_a = backend.by_product("1.327.50")
    first_b = backend.by_product("1.620.165")
    a_workshop_id = first_a["id"]
    b_workshop_id = first_b["id"]
    assert a_workshop_id != "659"
    assert b_workshop_id != "659"
    assert first_a["zlec_wew"] == "659"
    assert first_b["zlec_wew"] == "659"
    assert first_a["version"] == "BOM-1.327.50"
    assert first_a["planista_excel"]["identity"] == "659|1.327.50"
    assert "source_row" not in first_a["planista_excel"]
    assert sync._orders_dir() == root / "data" / "zlecenia"

    # Ten sam biznesowy plan przeniesiony w inne wiersze Excela nie może tworzyć duplikatów.
    _write_plan_xlsx(source, initial_records, start_row=20)
    second = _analyze(source, root)
    assert all(row["excel_change_status"] == CHANGE_NONE for row in second["rows"])
    repeat_plan = sync.build_order_sync_plan(second, orders=backend.list())
    assert repeat_plan["can_write"] is False
    assert [item["action"] for item in repeat_plan["items"]].count(sync.ACTION_NONE) == 2
    assert len(backend.list()) == 2

    # Zmieniamy ilość, termin i proces A, usuwamy B oraz dodajemy nowe zlecenie C.
    changed_records = [
        {"order": 659, "product": "1.327.50 NW – RAL 5003", "qty": 700, "date_serial": 46283, "process": "malowane"},
        {"order": 900, "product": "5.300.600 Szafka", "qty": 12, "date_serial": 46284, "process": "zgrzane"},
        {"order": 700, "product": "8.888.888 NIEZNANY", "qty": 10, "date_serial": 46281, "process": "zgrzane"},
        {"order": 701, "product": "7.777 INNY", "qty": 5, "date_serial": 46281, "process": "zgrzane"},
    ]
    _write_plan_xlsx(source, changed_records, start_row=30)
    changed = _analyze(source, root)
    changed_a = next(row for row in changed["rows"] if row.get("wm_symbol") == "1.327.50")
    assert changed_a["excel_change_status"] == CHANGE_CHANGED
    assert changed_a["excel_change_fields"] == ["Ilość", "Data wysyłki", "Proces"]
    assert any(row["excel_change_status"] == CHANGE_NEW_ORDER for row in changed["rows"])
    assert any(
        row.get("wm_symbol") == "1.620.165" and row["excel_change_status"] == CHANGE_REMOVED
        for row in changed["removed_rows"]
    )

    update_plan = sync.build_order_sync_plan(changed, orders=backend.list())
    actions = [item["action"] for item in update_plan["items"]]
    assert sync.ACTION_UPDATE in actions
    assert sync.ACTION_CREATE in actions
    assert sync.ACTION_REMOVED in actions
    assert actions.count(sync.ACTION_SKIP) == 2

    applied = sync.apply_order_sync(
        changed,
        update_plan,
        approved_identities=_approved(update_plan),
        autor="e2e",
    )
    assert applied["written"] == 2
    assert len(backend.list()) == 3

    updated_a = backend.by_product("1.327.50")
    untouched_b = backend.by_product("1.620.165")
    created_c = backend.by_product("5.300.600")
    assert updated_a["id"] == a_workshop_id
    assert updated_a["zlec_wew"] == "659"
    assert updated_a["ilosc"] == 700.0
    assert updated_a["termin"] == "2026-09-18"
    assert updated_a["planista_excel"]["proces"] == "malowane"
    assert updated_a["version"] == "BOM-1.327.50"
    assert untouched_b["id"] == b_workshop_id
    assert untouched_b["zlec_wew"] == "659"
    assert created_c["zlec_wew"] == "900"
    assert created_c["id"] not in {"659", "900"}


def test_product_replacement_is_detected_but_never_applied_automatically(monkeypatch, tmp_path):
    root = tmp_path / "WM_ROOT"
    backend = _install_temp_backend(monkeypatch, root)
    source = tmp_path / "Replacement.xlsx"

    _write_plan_xlsx(
        source,
        [{"order": 800, "product": "2.100.100 Stary", "qty": 20, "date_serial": 46279, "process": "zgrzane"}],
    )
    baseline = _analyze(source, root)
    plan = sync.build_order_sync_plan(baseline, orders=[])
    sync.apply_order_sync(baseline, plan, approved_identities=_approved(plan), autor="e2e")
    old_id = backend.by_product("2.100.100")["id"]

    _write_plan_xlsx(
        source,
        [{"order": 800, "product": "2.200.200 Nowy", "qty": 20, "date_serial": 46279, "process": "zgrzane"}],
        start_row=12,
    )
    changed = _analyze(source, root)
    row = changed["rows"][0]
    assert row["excel_change_status"] == CHANGE_CHANGED
    assert "Produkt" in row["excel_change_fields"]

    replacement_plan = sync.build_order_sync_plan(changed, orders=backend.list())
    assert replacement_plan["items"][0]["action"] == sync.ACTION_CONFLICT
    assert replacement_plan["can_write"] is False
    assert len(backend.list()) == 1
    assert backend.list()[0]["id"] == old_id
    assert backend.list()[0]["produkt"] == "2.100.100"


def test_malformed_xlsx_fails_safely_before_any_sync(tmp_path):
    path = tmp_path / "Broken.xlsx"
    path.write_bytes(b"to nie jest plik xlsx")

    with pytest.raises(PlanExcelError, match="Nie można odczytać pliku Excel"):
        load_production_plan(path)
