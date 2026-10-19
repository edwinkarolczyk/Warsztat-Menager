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


def test_stale_snapshot_does_not_override_newer_catalog_stock(tmp_path, monkeypatch):
    import magazyn_stock_adjustment as adjustment

    monkeypatch.setattr(adjustment, "get_data_root", lambda: tmp_path / "data")
    states_path = tmp_path / "data" / "magazyn" / "stany.json"
    states_path.parent.mkdir(parents=True)
    states_path.write_text(
        json.dumps({"SUR-001": {"stan": 7.0}}), encoding="utf-8"
    )
    items = {"SUR-001": {"stan": 99.0}}

    adjustment.overlay_actual_states(items)

    assert items["SUR-001"]["stan"] == 99.0


def test_corrected_stock_keeps_manual_audit_and_syncs_main_card(tmp_path, monkeypatch):
    import logika_magazyn as LM
    import magazyn_stock_adjustment as adjustment

    monkeypatch.setattr(adjustment, "get_data_root", lambda: tmp_path / "data")
    canonical = {"items": {"SUR-001": {"id": "SUR-001", "nazwa": "Profil", "stan": 13.0}}}
    monkeypatch.setattr(LM, "load_magazyn", lambda **_kw: canonical)
    monkeypatch.setattr(LM, "save_magazyn", lambda obj: None)

    adjustment.adjust_actual_stock(
        "SUR-001", "11", current_stock=13, user="Edwin",
        reason="Przeliczenie", item={"nazwa": "Profil", "jednostka": "m"},
    )
    assert canonical["items"]["SUR-001"]["stan"] == 11.0

    # Kolejne PZ aktualizuje tylko jedną migawkę, nie kasuje historii innych.
    path = tmp_path / "data" / "magazyn" / "stany.json"
    states = json.loads(path.read_text(encoding="utf-8"))
    states["SUR-999"] = {"stan": 2.0, "historia": [{"typ": "KOREKTA_STANU"}]}
    path.write_text(json.dumps(states), encoding="utf-8")
    adjustment.synchronize_stock_snapshot("SUR-001", 24, {"nazwa": "Profil"})
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["SUR-001"]["stan"] == 24
    assert after["SUR-001"]["historia"][-1]["comment"] == "Przeliczenie"
    assert after["SUR-999"]["historia"] == [{"typ": "KOREKTA_STANU"}]


def test_newer_pz_wins_over_old_manual_stock_adjustment(tmp_path, monkeypatch):
    import magazyn_stock_adjustment as adjustment

    monkeypatch.setattr(adjustment, "get_data_root", lambda: tmp_path / "data")
    path = tmp_path / "data" / "magazyn" / "stany.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "SUR-001": {
            "stan": 0,
            "historia": [{"typ": "KOREKTA_STANU", "ts": "2026-10-18T12:00:00+02:00"}],
        }
    }), encoding="utf-8")
    item = {
        "stan": 13, "historia": [
            {"op": "PZ", "ts": "2026-10-19T04:00:00+00:00"},
        ],
    }
    adjustment.overlay_actual_states({"SUR-001": item})
    assert item["stan"] == 13
