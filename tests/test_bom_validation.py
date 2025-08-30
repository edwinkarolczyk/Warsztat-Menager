import json

import pytest

import bom


def test_compute_bom_for_prd_ilosc_positive():
    with pytest.raises(ValueError, match="ilosc"):
        bom.compute_bom_for_prd("PRD001", 0)


def test_compute_sr_for_pp_ilosc_positive():
    with pytest.raises(ValueError, match="ilosc"):
        bom.compute_sr_for_pp("PP001", -1)


def test_compute_bom_for_prd_aggregates_fields():
    res = bom.compute_bom_for_prd("PRD001", 1)
    assert res["polprodukty"] == {"PP001": 2.0, "PP002": 1.0}
    assert res["operacje"] == {"ciecie": 3.0, "giecie": 1.0}
    assert res["surowce"] == {"SR001": 0.4, "SR002": 0.5}


def test_compute_bom_for_prd_missing_ilosc_na_szt(tmp_path, monkeypatch):
    product = {"kod": "X", "polprodukty": [{"kod": "PPX"}]}
    produkty = tmp_path / "produkty"
    produkty.mkdir()
    with open(produkty / "X.json", "w", encoding="utf-8") as f:
        json.dump(product, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)
    with pytest.raises(KeyError, match="ilosc_na_szt"):
        bom.compute_bom_for_prd("X", 1)


def test_compute_sr_for_pp_missing_surowiec(tmp_path, monkeypatch):
    polprodukty = tmp_path / "polprodukty"
    polprodukty.mkdir()
    with open(polprodukty / "X.json", "w", encoding="utf-8") as f:
        json.dump({"kod": "X"}, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)
    with pytest.raises(KeyError, match="surowiec"):
        bom.compute_sr_for_pp("X", 1)


def test_compute_sr_for_pp_missing_ilosc_na_szt(tmp_path, monkeypatch):
    polprodukty = tmp_path / "polprodukty"
    polprodukty.mkdir()
    pp = {"kod": "X", "surowiec": {"typ": "SR"}}
    with open(polprodukty / "X.json", "w", encoding="utf-8") as f:
        json.dump(pp, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)
    with pytest.raises(KeyError, match="dlugosc"):
        bom.compute_sr_for_pp("X", 1)
