import json

import magazyn_catalog as mc


def test_load_and_save_catalog(tmp_path, monkeypatch):
    path = tmp_path / "katalog.json"
    monkeypatch.setattr(mc, "CATALOG_PATH", str(path))
    data = {"A": {"nazwa": "Rurka"}}
    mc.save_catalog(data)
    assert mc.load_catalog() == data


def test_build_code_variants():
    profil = {
        "kategoria": "profil",
        "rodzaj": "kwadrat",
        "wymiar": "20x20",
        "typ": "s235",
    }
    assert mc.build_code(profil) == "PRF_KWADRAT_20x20_S235"

    rura = {"kategoria": "rura", "fi": 20, "scianka": 2, "typ": "kwas"}
    assert mc.build_code(rura) == "RUR_FI20x2_KWAS"

    polprodukt = {"kategoria": "półprodukt", "nazwa": "Półka stalowa"}
    assert mc.build_code(polprodukt) == "PP_POLKA_STALOWA"


def test_suggest_names_for_category(tmp_path, monkeypatch):
    cat_path = tmp_path / "katalog.json"
    stany_path = tmp_path / "stany.json"
    katalog = {
        "A": {"nazwa": "Kwadrat 20x20", "kategoria": "profil"},
        "B": {"nazwa": "Rurka 20", "kategoria": "rura"},
        "C": {"nazwa": "Kwadrat 30x30", "kategoria": "profil"},
    }
    stany = {
        "A": {"nazwa": "Kwadrat 20x20"},
        "C": {"nazwa": "Kwadrat 30x30"},
        "D": {"nazwa": "Inna"},
    }
    cat_path.write_text(json.dumps(katalog, ensure_ascii=False, indent=2), "utf-8")
    stany_path.write_text(json.dumps(stany, ensure_ascii=False, indent=2), "utf-8")
    monkeypatch.setattr(mc, "CATALOG_PATH", str(cat_path))
    monkeypatch.setattr(mc, "STANY_PATH", str(stany_path))

    assert mc.suggest_names_for_category("profil", "Kwa") == [
        "Kwadrat 20x20",
        "Kwadrat 30x30",
    ]
