# Testy regresyjne: jednostka „oczek” i wyszukiwanie w dostępnych modułach.
import json

import zlecenia_logika as ZL
import bom
from gui_planista import _work_order_html
from wm_global_search import search_wm


def test_chain_quantity_and_unit_follow_active_material_catalog(monkeypatch):
    monkeypatch.setattr(
        bom, "get_polprodukt",
        lambda _code: {"surowiec": {"kod": "SUR-003", "ilosc_na_szt": 16, "jednostka": "szt"}},
    )
    monkeypatch.setattr(
        ZL, "_raw_definitions",
        lambda: {"SUR-003": {
            "nazwa": "Łańcuszek - 13", "jednostka": "oczek", "dlugosc_sztangi_mm": 0
        }},
    )
    need = ZL._raw_need_for_pp("POL-024", 500, 2)
    assert need == {"SUR-003": {"ilosc": 8000.0, "jednostka": "oczek"}}

    order = {
        "id": "0030", "produkt": "1.147.35", "ilosc": 500, "wykonano": 0,
        "plan_polprodukty": {
            "POL-024": {
                "nazwa": "Łańcuszek do zbijaka",
                "potrzeba": 500, "z_magazynu": 0, "do_wykonania": 500,
                "surowiec": {
                    "kod": "SUR-003", "nazwa": "Łańcuszek - 13",
                    "ilosc_na_szt": 16, "jednostka": "szt",
                },
            },
        },
        "zapotrzebowanie_surowce": {
            "SUR-003": {"ilosc": 8000, "jednostka": "szt"},
        },
        "braki": [
            {"kod": "SUR-003", "nazwa": "Łańcuszek - 13", "brakuje": 8000, "jednostka": "szt"}
        ],
    }
    rendered = _work_order_html(order)
    assert "16 oczek" in rendered
    assert "Ilość na półprodukt: 16 oczek" in rendered
    assert "8000 oczek" in rendered
    assert "Długość detalu: 16" not in rendered


def test_global_search_uses_root_data_and_obeys_module_permissions(tmp_path):
    data = tmp_path / "data"
    (data / "produkty").mkdir(parents=True)
    (data / "magazyn").mkdir(parents=True)
    (data / "zlecenia").mkdir(parents=True)
    (data / "produkty" / "1.147.35.json").write_text(
        json.dumps({"kod": "1.147.35", "nazwa": "Zbijak"}), encoding="utf-8"
    )
    (data / "magazyn" / "surowce.json").write_text(
        json.dumps([{"kod": "SUR-003", "nazwa": "Łańcuszek - 13"}]), encoding="utf-8"
    )
    (data / "zlecenia" / "0030.json").write_text(
        json.dumps({"id": "0030", "produkt": "1.147.35"}), encoding="utf-8"
    )

    assert [row["code"] for row in search_wm("lancuszek", {"magazyn"}, data_dir=data)] == ["SUR-003"]
    assert not search_wm("Łańcuszek", {"planowanie"}, data_dir=data)
    assert [row["code"] for row in search_wm("0030", {"planowanie"}, data_dir=data)] == ["0030"]
    assert not search_wm("0030", {"magazyn"}, data_dir=data)
