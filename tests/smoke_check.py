from pathlib import Path

import bom


def test_surowce_file_exists() -> None:
    assert Path("data/magazyn/surowce.json").is_file()


def test_load_polprodukt_and_produkt() -> None:
    pp = bom.get_polprodukt("DRUT_10")
    assert pp["kod"] == "DRUT_10"
    prd = bom.get_produkt("SKRZYNKA_001")
    assert prd["kod"] == "SKRZYNKA_001"


def test_compute_sr_for_pp_sample() -> None:
    res = bom.compute_sr_for_pp("DRUT_10", 3)
    assert res == {"SR_DRUT10": {"ilosc": 6.0, "jednostka": "m"}}
