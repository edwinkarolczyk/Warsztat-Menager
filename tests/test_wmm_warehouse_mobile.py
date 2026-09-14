from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.wmm_warehouse_mobile import receive_existing_material


class _FakeImpl:
    def __init__(self, data_dir: Path):
        self._data = data_dir

    def _data_dir(self) -> Path:
        return self._data

    @staticmethod
    def _read_json(path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json_atomic(path: Path, value) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".test.tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)


def _prepare(tmp_path: Path):
    data = tmp_path / "data"
    magazyn = data / "magazyn"
    magazyn.mkdir(parents=True)
    master = [
        {
            "kod": "SR001",
            "nazwa": "Pręt fi8",
            "rodzaj": "pręt",
            "rozmiar": "fi8",
            "jednostka": "kg",
            "lokalizacja": "Regał A1",
        }
    ]
    master_path = magazyn / "surowce.json"
    master_path.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
    (magazyn / "stany.json").write_text(
        json.dumps({"SR001": {"stan": 10.0}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    impl = _FakeImpl(data)

    def loader():
        rows = json.loads(master_path.read_text(encoding="utf-8"))
        states = json.loads((magazyn / "stany.json").read_text(encoding="utf-8"))
        out = []
        for source in rows:
            row = dict(source)
            row["id"] = row["kod"]
            state = states.get(row["id"], {})
            row["stan"] = state.get("stan", 0.0)
            out.append(row)
        return out

    return impl, loader, master_path, magazyn


def test_receive_increases_stock_and_does_not_touch_material_master(tmp_path):
    impl, loader, master_path, magazyn = _prepare(tmp_path)
    master_before = master_path.read_bytes()

    item, receipt = receive_existing_material(
        impl,
        loader,
        "SR001",
        {
            "qty": "2,5",
            "document": "WZ 123/2026",
            "supplier": "Hurtownia Test",
            "note": "Dostawa poranna",
        },
        "edwin",
    )

    assert master_path.read_bytes() == master_before
    states = json.loads((magazyn / "stany.json").read_text(encoding="utf-8"))
    assert states["SR001"]["stan"] == 12.5
    assert item["stan"] == 12.5
    assert item["jednostka"] == "kg"
    assert receipt["qty"] == 2.5
    assert receipt["user"] == "edwin"
    assert receipt["stan_przed"] == 10.0
    assert receipt["stan_po"] == 12.5
    assert receipt["source"] == "WMM"

    receipts = json.loads((magazyn / "przyjecia.json").read_text(encoding="utf-8"))
    history = json.loads((magazyn / "magazyn_history.json").read_text(encoding="utf-8"))
    assert receipts[-1]["item_id"] == "SR001"
    assert history[-1]["op"] == "PZ"


def test_receive_rejects_new_material_and_non_positive_qty(tmp_path):
    impl, loader, master_path, magazyn = _prepare(tmp_path)
    master_before = master_path.read_bytes()
    states_before = (magazyn / "stany.json").read_bytes()

    with pytest.raises(RuntimeError, match="Nie znaleziono surowca"):
        receive_existing_material(impl, loader, "NOWY", {"qty": 4}, "edwin")

    with pytest.raises(RuntimeError, match="większa od zera"):
        receive_existing_material(impl, loader, "SR001", {"qty": 0}, "edwin")

    assert master_path.read_bytes() == master_before
    assert (magazyn / "stany.json").read_bytes() == states_before
    assert not (magazyn / "przyjecia.json").exists()
