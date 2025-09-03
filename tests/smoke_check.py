from pathlib import Path
import json

import pytest

from bom import compute_sr_for_pp



def test_smoke_check():
    surowce_path = Path("data/magazyn/surowce.json")
    assert surowce_path.exists()

    pp = json.loads(Path("data/polprodukty/PP001.json").read_text(encoding="utf-8"))
    assert pp["kod"] == "PP001"

    prd = json.loads(Path("data/produkty/PRD001.json").read_text(encoding="utf-8"))
    assert prd["kod"] == "PRD001"

    result = compute_sr_for_pp("PP001", 1)
    expected_qty = 0.2 * 1 * (1 + 0.02)
    assert result["SR001"]["ilosc"] == pytest.approx(expected_qty)
    assert result["SR001"]["jednostka"] == "mb"


def test_surowiec_delivery_and_delete(tmp_path, monkeypatch):
    import gui_magazyn_bom as gmb

    monkeypatch.setattr(gmb, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(gmb, "LOG_FILE", tmp_path / "log.txt")

    model = gmb.WarehouseModel()
    rec = {
        "kod": "SRX",
        "nazwa": "Stal",
        "rodzaj": "metal",
        "rozmiar": "10",
        "dlugosc": 1.0,
        "jednostka": "m",
        "stan": 0,
    }
    model.add_or_update_surowiec(rec)

    model.register_delivery("SRX", 5)
    data = json.loads(
        (tmp_path / "data" / "magazyn" / "surowce.json").read_text(
            encoding="utf-8"
        )
    )
    assert any(r["kod"] == "SRX" and r["stan"] == 5 for r in data)

    model.delete_surowiec("SRX")
    data = json.loads(
        (tmp_path / "data" / "magazyn" / "surowce.json").read_text(
            encoding="utf-8"
        )
    )
    assert all(r["kod"] != "SRX" for r in data)
