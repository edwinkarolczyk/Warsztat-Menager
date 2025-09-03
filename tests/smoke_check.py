from pathlib import Path
import json

import pytest

from bom import compute_sr_for_pp
import logika_magazyn as lm
import logika_zakupy as lz



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


def test_zlecenie_zakupu_powstaje(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "MAGAZYN_PATH", str(tmp_path / "magazyn.json"))
    monkeypatch.setattr(lz, "ZAMOWIENIA_DIR", tmp_path / "zamowienia")
    lm.load_magazyn()
    lm.upsert_item(
        {
            "id": "MAT-C",
            "nazwa": "C",
            "typ": "materiał",
            "jednostka": "szt",
            "stan": 1,
            "min_poziom": 0,
        }
    )
    bom = {"MAT-C": {"ilosc": 5}}
    ok, braki, zlec = lm.rezerwuj_materialy(bom, 1)
    assert ok is False
    assert zlec is not None
    zam_file = tmp_path / "zamowienia" / f"{zlec['nr']}.json"
    assert zam_file.exists()
