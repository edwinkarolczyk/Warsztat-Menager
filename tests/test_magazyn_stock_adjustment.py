import json

import pytest


def test_brygadzista_adjusts_actual_stock_with_audit_trail(tmp_path, monkeypatch):
    import magazyn_stock_adjustment as adjustment

    monkeypatch.setattr(adjustment, "get_data_root", lambda: tmp_path / "data")

    record = adjustment.adjust_actual_stock(
        "SUR-001",
        "12,5",
        current_stock=10,
        user="Edwin",
        reason="Inwentaryzacja",
        item={"nazwa": "Rura fi 20", "jednostka": "mb"},
    )

    assert record["stan_przed"] == 10
    assert record["stan_po"] == 12.5
    assert record["roznica"] == 2.5
    states = json.loads(
        (tmp_path / "data" / "magazyn" / "stany.json").read_text(encoding="utf-8")
    )
    assert states["SUR-001"]["stan"] == 12.5
    assert states["SUR-001"]["historia"][-1]["user"] == "Edwin"
    assert states["SUR-001"]["historia"][-1]["comment"] == "Inwentaryzacja"


def test_actual_stock_adjustment_requires_reason_and_non_negative_value(tmp_path, monkeypatch):
    import magazyn_stock_adjustment as adjustment

    monkeypatch.setattr(adjustment, "get_data_root", lambda: tmp_path / "data")

    with pytest.raises(ValueError, match="powód"):
        adjustment.adjust_actual_stock(
            "SUR-001", 5, current_stock=4, user="Edwin", reason=""
        )
    with pytest.raises(ValueError, match="nie może być ujemny"):
        adjustment.adjust_actual_stock(
            "SUR-001", -1, current_stock=4, user="Edwin", reason="Spis"
        )


def test_actual_state_overlay_wins_over_catalog_stock(tmp_path, monkeypatch):
    import magazyn_stock_adjustment as adjustment

    monkeypatch.setattr(adjustment, "get_data_root", lambda: tmp_path / "data")
    states_path = tmp_path / "data" / "magazyn" / "stany.json"
    states_path.parent.mkdir(parents=True)
    states_path.write_text(
        json.dumps({"SUR-001": {"stan": 7.0}}), encoding="utf-8"
    )
    items = {"SUR-001": {"stan": 99.0}}

    adjustment.overlay_actual_states(items)

    assert items["SUR-001"]["stan"] == 7.0
