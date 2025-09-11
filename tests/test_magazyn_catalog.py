import json

import magazyn_catalog as mc


def test_build_code_profile():
    assert mc.build_code("Plaskownik 40mm") == "PLASK_40"


def test_build_code_pipe():
    assert mc.build_code("Rura 30mm") == "RURA_30"


def test_build_code_semiproduct():
    assert mc.build_code("Drut gwintowany 30mm") == "DRUT_30_GWINT"


def test_suggest_names_for_category(tmp_path, monkeypatch):
    katalog = {
        "items": {
            "RURA_30": {"nazwa": "Rura 30mm", "typ": "rura"},
            "RURKA_40": {"nazwa": "Rurka 40mm", "typ": "rura"},
            "PLASK_40": {"nazwa": "Plaskownik 40mm", "typ": "profil"},
        }
    }
    stany = {
        "RURA_30": {"nazwa": "Rura 30mm"},
        "RURA_50": {"nazwa": "Rura 50mm"},
        "PLASK_40": {"nazwa": "Plaskownik 40mm"},
    }
    katalog_path = tmp_path / "katalog.json"
    katalog_path.write_text(
        json.dumps(katalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    stany_path = tmp_path / "stany.json"
    stany_path.write_text(
        json.dumps(stany, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result = mc.suggest_names_for_category(
        "rura", "Ru", katalog_path=str(katalog_path), stany_path=str(stany_path)
    )
    assert result == ["Rura 30mm", "Rurka 40mm", "Rura 50mm"]
