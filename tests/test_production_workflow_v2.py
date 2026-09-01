# WM-VERSION: 0.1
# Plik: tests/test_production_workflow_v2.py
# version: 1.0


def test_gui_planowanie_is_compatibility_wrapper():
    text = open("gui_planowanie.py", encoding="utf-8").read()
    assert "open_planista" in text
    assert "Planista" in text
    assert "PlanowanieUI" not in text


def test_zlecenia_uses_configured_data_root():
    text = open("zlecenia_logika.py", encoding="utf-8").read()
    assert "ConfigManager().path_data()" in text
    assert 'DATA_DIR = Path("data")' not in text


def test_cut_is_added_per_piece_only_for_mm(monkeypatch):
    import zlecenia_logika as zl

    monkeypatch.setattr(
        zl.bom,
        "get_polprodukt",
        lambda _code: {
            "surowiec": {"kod": "SUR-1", "ilosc_na_szt": 369, "jednostka": "mm"},
            "norma_strat_procent": 0,
        },
    )
    result = zl._raw_need_for_pp("OSKA", 100, 2)
    assert result["SUR-1"]["ilosc"] == 37100


def test_plan_subtracts_available_semis(monkeypatch):
    import zlecenia_logika as zl

    monkeypatch.setattr(
        zl.bom,
        "compute_bom_for_prd",
        lambda *_a, **_k: {
            "OSKA": {
                "ilosc": 40,
                "nazwa": "Oś Banaszak",
                "czynnosci": ["Cięcie"],
                "surowiec": {"kod": "SUR-1", "ilosc_na_szt": 369, "jednostka": "mm"},
            }
        },
    )
    monkeypatch.setattr(zl, "_semi_stock", lambda _code: {"stan": 10.0, "rezerwacje": 0.0, "dostepne": 10.0})
    monkeypatch.setattr(zl, "_raw_need_for_pp", lambda _code, qty, _cut: {"SUR-1": {"ilosc": qty * 371, "jednostka": "mm"}})
    plan, raw = zl.build_production_plan("1.775.250", 20, cut_mm=2)
    assert plan["OSKA"]["potrzeba"] == 40
    assert plan["OSKA"]["z_magazynu"] == 10
    assert plan["OSKA"]["do_wykonania"] == 30
    assert raw["SUR-1"]["ilosc"] == 11130
