import json

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


def test_compute_sr_for_pp_missing_surowce_file_uses_pp_unit(
    tmp_path, monkeypatch
):
    polprodukty = tmp_path / "polprodukty"
    polprodukty.mkdir()
    pp = {
        "kod": "X",
        "surowiec": {"kod": "SR", "ilosc_na_szt": 2, "jednostka": "kg"},
    }
    with open(polprodukty / "X.json", "w", encoding="utf-8") as f:
        json.dump(pp, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)
    res = bom.compute_sr_for_pp("X", 3)
    assert res["SR"]["stan"] == 6
    assert res["SR"]["jednostka"] == "kg"


def test_compute_sr_for_pp_missing_jednostka(tmp_path, monkeypatch):
    polprodukty = tmp_path / "polprodukty"
    polprodukty.mkdir()
    pp = {"kod": "X", "surowiec": {"kod": "SR", "ilosc_na_szt": 1}}
    with open(polprodukty / "X.json", "w", encoding="utf-8") as f:
        json.dump(pp, f, ensure_ascii=False, indent=2)
    magazyn = tmp_path / "magazyn"
    magazyn.mkdir()
    surowce = {"SR": {}}
    with open(magazyn / "surowce.json", "w", encoding="utf-8") as f:
        json.dump(surowce, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)
    with pytest.raises(KeyError, match="SR"):
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
    assert res["PP1"]["stan"] == 2
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


def test_get_produkt_warns_on_multiple_defaults(tmp_path, monkeypatch, caplog):
    produkty = tmp_path / "produkty"
    produkty.mkdir()
    prod1 = {"kod": "X", "version": "1", "is_default": True}
    prod2 = {"kod": "X", "version": "2", "is_default": True}
    with open(produkty / "p1.json", "w", encoding="utf-8") as f:
        json.dump(prod1, f, ensure_ascii=False, indent=2)
    with open(produkty / "p2.json", "w", encoding="utf-8") as f:
        json.dump(prod2, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)
    with caplog.at_level("WARNING"):
        res = bom.get_produkt("X")
    assert res["version"] == "1"
    assert any("wiele domyślnych" in r.message for r in caplog.records)


def test_get_produkt_prefers_numeric_version(tmp_path, monkeypatch, caplog):
    produkty = tmp_path / "produkty"
    produkty.mkdir()
    prod_old = {"kod": "X", "version": "10", "is_default": True}
    prod_new = {"kod": "X", "version": "2", "is_default": True}
    with open(produkty / "p10.json", "w", encoding="utf-8") as f:
        json.dump(prod_old, f, ensure_ascii=False, indent=2)
    with open(produkty / "p2.json", "w", encoding="utf-8") as f:
        json.dump(prod_new, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)
    with caplog.at_level("WARNING"):
        res = bom.get_produkt("X")
    assert res["version"] == "2"
    assert any("wiele domyślnych" in r.message for r in caplog.records)
