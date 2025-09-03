import json
from datetime import date

import pytest

import bom


def test_compute_bom_for_prd_ilosc_positive():
    with pytest.raises(ValueError, match="ilosc"):
        bom.compute_bom_for_prd("PRD001", 0)


def test_compute_sr_for_pp_ilosc_positive():
    with pytest.raises(ValueError, match="ilosc"):
        bom.compute_sr_for_pp("PP001", -1)


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


def test_revision_and_date_filters(tmp_path, monkeypatch):
    produkty = tmp_path / "produkty"
    polprodukty = tmp_path / "polprodukty"
    produkty.mkdir()
    polprodukty.mkdir()
    product_v1 = {
        "kod": "Z",
        "version": "1",
        "bom_revision": 1,
        "effective_from": "2024-01-01",
        "effective_to": "2024-12-31",
        "polprodukty": [
            {
                "kod": "PP1",
                "ilosc_na_szt": 1,
                "czynnosci": ["a"],
                "surowiec": {"typ": "T1", "dlugosc": 1},
            }
        ],
    }
    product_v2 = {
        "kod": "Z",
        "version": "2",
        "bom_revision": 2,
        "effective_from": "2025-01-01",
        "effective_to": None,
        "polprodukty": [
            {
                "kod": "PP2",
                "ilosc_na_szt": 1,
                "czynnosci": ["a"],
                "surowiec": {"typ": "T2", "dlugosc": 1},
            }
        ],
    }
    with open(produkty / "Z_v1.json", "w", encoding="utf-8") as f:
        json.dump(product_v1, f, ensure_ascii=False, indent=2)
    with open(produkty / "Z_v2.json", "w", encoding="utf-8") as f:
        json.dump(product_v2, f, ensure_ascii=False, indent=2)
    pp1 = {"kod": "PP1", "surowiec": {"kod": "SR1", "ilosc_na_szt": 2}}
    pp2 = {"kod": "PP2", "surowiec": {"kod": "SR2", "ilosc_na_szt": 3}}
    with open(polprodukty / "PP1.json", "w", encoding="utf-8") as f:
        json.dump(pp1, f, ensure_ascii=False, indent=2)
    with open(polprodukty / "PP2.json", "w", encoding="utf-8") as f:
        json.dump(pp2, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)

    bom1 = bom.compute_bom_for_prd(
        "Z", 1, bom_revision=1, at_date=date(2024, 6, 1)
    )
    assert set(bom1.keys()) == {"PP1"}

    bom2 = bom.compute_bom_for_prd(
        "Z", 1, bom_revision=2, at_date=date(2025, 2, 1)
    )
    assert set(bom2.keys()) == {"PP2"}

    with pytest.raises(FileNotFoundError):
        bom.compute_bom_for_prd("Z", 1, bom_revision=1, at_date=date(2025, 1, 1))

    sr_res = bom.compute_sr_for_prd(
        "Z", 2, bom_revision=2, at_date=date(2025, 5, 1)
    )
    assert sr_res == {"SR2": 6}
