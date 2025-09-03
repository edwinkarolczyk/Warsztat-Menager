import json

import pytest

import bom


def test_compute_bom_for_prd_ilosc_positive():
    with pytest.raises(ValueError, match="ilosc"):
        bom.compute_bom_for_prd("PRD001", 0)


def test_compute_sr_for_pp_ilosc_positive():
    with pytest.raises(ValueError, match="ilosc"):
        bom.compute_sr_for_pp("PP001", -1)


def test_compute_sr_for_prd_ilosc_positive():
    with pytest.raises(ValueError, match="ilosc"):
        bom.compute_sr_for_prd("PRD001", 0)


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
    pp = {"kod": "X", "surowiec": {"kod": "SR"}}
    with open(polprodukty / "X.json", "w", encoding="utf-8") as f:
        json.dump(pp, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)
    with pytest.raises(KeyError, match="ilosc_na_szt"):
        bom.compute_sr_for_pp("X", 1)


def test_compute_sr_for_prd_aggregates_and_units(tmp_path, monkeypatch):
    produkty = tmp_path / "produkty"
    produkty.mkdir()
    polprodukty = tmp_path / "polprodukty"
    polprodukty.mkdir()

    pp1 = {
        "kod": "PP1",
        "surowiec": {"kod": "SR1", "ilosc_na_szt": 1, "jednostka": "kg"},
    }
    pp2 = {
        "kod": "PP2",
        "surowiec": {"kod": "SR1", "ilosc_na_szt": 2, "jednostka": "kg"},
    }
    with open(polprodukty / "PP1.json", "w", encoding="utf-8") as f:
        json.dump(pp1, f, ensure_ascii=False, indent=2)
    with open(polprodukty / "PP2.json", "w", encoding="utf-8") as f:
        json.dump(pp2, f, ensure_ascii=False, indent=2)

    prd = {
        "kod": "X",
        "polprodukty": [
            {
                "kod": "PP1",
                "ilosc_na_szt": 1,
                "czynnosci": ["a"],
                "surowiec": {"typ": "T", "dlugosc": 1},
            },
            {
                "kod": "PP2",
                "ilosc_na_szt": 1,
                "czynnosci": ["b"],
                "surowiec": {"typ": "T", "dlugosc": 1},
            },
        ],
    }
    with open(produkty / "X.json", "w", encoding="utf-8") as f:
        json.dump(prd, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)

    res = bom.compute_sr_for_prd("X", 1)
    assert res["SR1"]["ilosc"] == pytest.approx(3.0)
    assert res["SR1"]["jednostka"] == "kg"


def test_compute_bom_for_prd_returns_extra_fields(tmp_path, monkeypatch):
    product = {
        "kod": "X",
        "polprodukty": [
            {
                "kod": "PP1",
                "ilosc_na_szt": 1,
                "czynnosci": ["ciecie", "spawanie"],
                "surowiec": {"typ": "SR1", "dlugosc": 2},
            }
        ],
    }
    produkty = tmp_path / "produkty"
    produkty.mkdir()
    with open(produkty / "X.json", "w", encoding="utf-8") as f:
        json.dump(product, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)
    res = bom.compute_bom_for_prd("X", 2)
    assert res["PP1"]["ilosc"] == 2
    assert res["PP1"]["czynnosci"] == ["ciecie", "spawanie"]
    assert res["PP1"]["surowiec"]["typ"] == "SR1"


def test_compute_bom_for_prd_requires_czynnosci(tmp_path, monkeypatch):
    product = {
        "kod": "X",
        "polprodukty": [
            {
                "kod": "PP1",
                "ilosc_na_szt": 1,
                "surowiec": {"typ": "SR1", "dlugosc": 1},
            }
        ],
    }
    produkty = tmp_path / "produkty"
    produkty.mkdir()
    with open(produkty / "X.json", "w", encoding="utf-8") as f:
        json.dump(product, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)
    with pytest.raises(KeyError, match="czynnosci"):
        bom.compute_bom_for_prd("X", 1)


def test_compute_bom_for_prd_requires_surowiec_fields(tmp_path, monkeypatch):
    product = {
        "kod": "X",
        "polprodukty": [
            {
                "kod": "PP1",
                "ilosc_na_szt": 1,
                "czynnosci": ["a"],
                "surowiec": {"typ": "SR1"},
            }
        ],
    }
    produkty = tmp_path / "produkty"
    produkty.mkdir()
    with open(produkty / "X.json", "w", encoding="utf-8") as f:
        json.dump(product, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)
    with pytest.raises(KeyError, match="surowiec"):
        bom.compute_bom_for_prd("X", 1)
