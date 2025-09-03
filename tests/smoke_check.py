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
    assert result["SR001"]["stan"] == pytest.approx(expected_qty)
    assert result["SR001"]["jednostka"] == "mb"
