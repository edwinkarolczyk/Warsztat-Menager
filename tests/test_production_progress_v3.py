# WM-VERSION: 0.1
# Plik: tests/test_production_progress_v3.py
# version: 1.0

import types

import pytest

import zlecenia_progress as zp


def _base_order(**extra):
    order = {
        "id": "000001",
        "produkt": "1.775.250",
        "ilosc": 100.0,
        "wykonano": 40.0,
        "rzaz_mm": 2.0,
        "status": "w trakcie",
        "rezerwacje_polprodukty": {},
        "rezerwacje_surowce": {},
        "zapotrzebowanie_surowce": {},
        "historia": [],
    }
    order.update(extra)
    return order


def test_replan_uses_only_remaining_product_quantity(monkeypatch):
    order = _base_order(ilosc=120.0, wykonano=40.0)
    seen = {}

    monkeypatch.setattr(zp.ZL, "_release_reservations", lambda *_a, **_k: None)

    def fake_build(product, qty, **kwargs):
        seen["product"] = product
        seen["qty"] = qty
        return {"POL-OS": {"potrzeba": qty * 2, "z_magazynu": 0, "do_wykonania": qty * 2}}, {}

    monkeypatch.setattr(zp.ZL, "build_production_plan", fake_build)
    monkeypatch.setattr(zp.ZL, "check_materials", lambda *_a, **_k: [])
    monkeypatch.setattr(zp.ZL, "_reserve_semis", lambda *_a, **_k: {})
    monkeypatch.setattr(zp.ZL, "reserve_materials", lambda *_a, **_k: ({}, {}))

    result = zp._replan_remaining(order, "Edwin")

    assert seen["qty"] == 80.0
    assert result["pozostalo"] == 80.0
    assert result["plan_polprodukty"]["POL-OS"]["potrzeba"] == 160.0


def test_reducing_below_done_credits_surplus_semis_once(monkeypatch):
    order = _base_order(ilosc=100.0, wykonano=40.0)
    stock = {}
    returns = []

    monkeypatch.setattr(
        zp.bom,
        "compute_bom_for_prd",
        lambda _product, qty, **_k: {
            "POL-OS": {"ilosc": qty * 2, "nazwa": "Oś Banaszak"},
            "POL-ZAW": {"ilosc": qty, "nazwa": "Zawleczka"},
        },
    )
    monkeypatch.setattr(zp.LM, "get_item", lambda code: stock.get(code))

    def fake_upsert(item):
        stock[item["id"]] = dict(item)
        return stock[item["id"]]

    def fake_return(code, qty, user, kontekst=None):
        returns.append((code, qty, user, kontekst))
        stock[code]["stan"] = float(stock[code].get("stan", 0)) + float(qty)

    monkeypatch.setattr(zp.LM, "upsert_item", fake_upsert)
    monkeypatch.setattr(zp.LM, "zwrot", fake_return)
    monkeypatch.setattr(zp.bom, "get_polprodukt", lambda code: {"nazwa": code})

    first = zp._credit_new_surplus(order, 100, 30, "Edwin")
    second = zp._credit_new_surplus(order, 30, 30, "Edwin")

    assert first == {"POL-OS": 20.0, "POL-ZAW": 10.0}
    assert second == {}
    assert stock["POL-OS"]["stan"] == 20.0
    assert stock["POL-ZAW"]["stan"] == 10.0
    assert order["nadprodukcja_zaksiegowana_prod"] == 10.0
    assert len(returns) == 2


def test_report_done_rejects_value_above_order_quantity(monkeypatch):
    order = _base_order(ilosc=30.0, wykonano=30.0)
    monkeypatch.setattr(zp.ZL, "_order_path", lambda _id: "dummy")
    monkeypatch.setattr(zp.ZL, "_read_json", lambda _p: order)

    with pytest.raises(ValueError, match="Najpierw zwiększ ilość"):
        zp.report_wykonano("000001", 31, kto="Edwin")


def test_report_done_validates_all_stock_before_any_mutation(monkeypatch):
    order = _base_order(
        ilosc=100.0,
        wykonano=40.0,
        rezerwacje_polprodukty={"POL-OS": 60.0},
        rezerwacje_surowce={"SUR-1": 1000.0},
        zapotrzebowanie_surowce={"SUR-1": {"ilosc": 6000.0, "jednostka": "mm"}},
    )
    calls = []
    states = {
        "POL-OS": {"stan": 100.0, "rezerwacje": 60.0},
        "SUR-1": {"stan": 10.0, "rezerwacje": 10.0},
    }
    monkeypatch.setattr(zp.ZL, "_order_path", lambda _id: "dummy")
    monkeypatch.setattr(zp.ZL, "_read_json", lambda _p: order)
    monkeypatch.setattr(zp.LM, "get_item", lambda code: states.get(code))
    monkeypatch.setattr(zp.LM, "zwolnij_rezerwacje", lambda *a, **k: calls.append(("release", a)))
    monkeypatch.setattr(zp.LM, "zuzyj", lambda *a, **k: calls.append(("consume", a)))

    order["wykonano"] = 50.0
    order["materialy_rozliczono_do"] = 40.0
    with pytest.raises(ValueError, match="stan magazynowy jest za mały"):
        zp.rozlicz_material("000001", kto="Edwin")

    assert calls == []


def test_partial_report_keeps_only_this_orders_remaining_reservation(monkeypatch):
    order = _base_order(
        ilosc=100.0,
        pozostalo=60.0,
        wykonano=40.0,
        rezerwacje_polprodukty={"POL-OS": 60.0},
        rezerwacje_surowce={},
        zapotrzebowanie_surowce={},
    )
    state = {"POL-OS": {"stan": 100.0, "rezerwacje": 100.0}}
    released_by_replan = []

    monkeypatch.setattr(zp.ZL, "_order_path", lambda _id: "dummy")
    monkeypatch.setattr(zp.ZL, "_read_json", lambda _p: order)
    monkeypatch.setattr(zp.ZL, "_write_json", lambda *_a, **_k: None)
    monkeypatch.setattr(zp.ZL, "_sync_execution_disposition", lambda *_a, **_k: None)
    monkeypatch.setattr(zp, "_sync_material_dispositions", lambda *_a, **_k: None)
    monkeypatch.setattr(zp.LM, "get_item", lambda code: state.get(code))

    def release(code, qty, *_a, **_k):
        state[code]["rezerwacje"] -= qty

    def consume(code, qty, *_a, **_k):
        state[code]["stan"] -= qty

    monkeypatch.setattr(zp.LM, "zwolnij_rezerwacje", release)
    monkeypatch.setattr(zp.LM, "zuzyj", consume)

    def fake_replan(obj, kto="system"):
        released_by_replan.append(dict(obj.get("rezerwacje_polprodukty") or {}))
        return obj

    monkeypatch.setattr(zp, "_replan_remaining", fake_replan)

    order["wykonano"] = 50.0
    order["materialy_rozliczono_do"] = 40.0
    zp.rozlicz_material("000001", kto="Edwin")

    # Z 60 szt. rezerwacji dla tego zlecenia zuzyto 1/6 = 10.
    # Do przeliczenia moze zostac przekazane tylko pozostale 50, a nie stare 60.
    assert released_by_replan == [{"POL-OS": 50.0}]
    # Globalnie bylo 100 rezerwacji, wiec 40 nalezalo do innych zlecen.
    assert state["POL-OS"]["rezerwacje"] == 90.0
    assert state["POL-OS"]["stan"] == 90.0


def test_report_done_does_not_touch_warehouse_or_reservations(monkeypatch):
    order = _base_order(
        ilosc=100.0,
        wykonano=40.0,
        rezerwacje_polprodukty={"POL-OS": 60.0},
        rezerwacje_surowce={"SUR-1": 6000.0},
        zapotrzebowanie_surowce={"SUR-1": {"ilosc": 6000.0, "jednostka": "mm"}},
    )
    before_pp = dict(order["rezerwacje_polprodukty"])
    before_raw = dict(order["rezerwacje_surowce"])
    warehouse_calls = []

    monkeypatch.setattr(zp.ZL, "_order_path", lambda _id: "dummy")
    monkeypatch.setattr(zp.ZL, "_read_json", lambda _p: order)
    monkeypatch.setattr(zp.ZL, "_write_json", lambda *_a, **_k: None)
    monkeypatch.setattr(zp.ZL, "_sync_execution_disposition", lambda *_a, **_k: None)
    monkeypatch.setattr(zp.LM, "zwolnij_rezerwacje", lambda *a, **k: warehouse_calls.append(("release", a)))
    monkeypatch.setattr(zp.LM, "zuzyj", lambda *a, **k: warehouse_calls.append(("consume", a)))

    result = zp.report_wykonano("000001", 100, kto="Edwin")

    assert result["wykonano"] == 100.0
    assert result["status"] == "zakończone"
    assert result["rezerwacje_polprodukty"] == before_pp
    assert result["rezerwacje_surowce"] == before_raw
    assert warehouse_calls == []


def test_settlement_uses_replanned_quantity_after_order_increase(monkeypatch):
    # 100 szt. -> 50 wykonanych -> zamówienie zwiększone do 120.
    # Nowy plan obejmuje 70 szt., ale trzeba rozliczyć 50 wykonanych.
    order = _base_order(
        ilosc=120.0,
        wykonano=50.0,
        pozostalo=70.0,
        materialy_rozliczono_do=0.0,
        rezerwacje_polprodukty={"POL-OS": 70.0},
        zapotrzebowanie_surowce={},
    )
    state = {"POL-OS": {"stan": 120.0, "rezerwacje": 70.0}}
    consumed = []

    monkeypatch.setattr(zp.ZL, "_order_path", lambda _id: "dummy")
    monkeypatch.setattr(zp.ZL, "_read_json", lambda _p: order)
    monkeypatch.setattr(zp.ZL, "_write_json", lambda *_a, **_k: None)
    monkeypatch.setattr(zp.ZL, "_sync_execution_disposition", lambda *_a, **_k: None)
    monkeypatch.setattr(zp, "_sync_material_dispositions", lambda *_a, **_k: None)
    monkeypatch.setattr(zp, "_replan_remaining", lambda obj, *_a: obj)
    monkeypatch.setattr(zp.LM, "get_item", lambda code: state.get(code))
    monkeypatch.setattr(
        zp.LM,
        "zwolnij_rezerwacje",
        lambda code, amount, *_a, **_k: state[code].__setitem__(
            "rezerwacje", state[code]["rezerwacje"] - amount
        ),
    )

    def consume(code, amount, *_a, **_k):
        consumed.append((code, amount))
        state[code]["stan"] -= amount

    monkeypatch.setattr(zp.LM, "zuzyj", consume)

    result = zp.rozlicz_material("000001", kto="Edwin")

    assert consumed == [("POL-OS", pytest.approx(50.0))]
    assert state["POL-OS"]["stan"] == pytest.approx(70.0)
    assert state["POL-OS"]["rezerwacje"] == pytest.approx(20.0)
    assert result["materialy_rozliczono_do"] == 50.0
    zp.rozlicz_material("000001", kto="Edwin")
    assert len(consumed) == 1


def test_settlement_refuses_plan_not_covering_unsettled_work(monkeypatch):
    order = _base_order(
        ilosc=120.0, wykonano=50.0, pozostalo=20.0,
        rezerwacje_polprodukty={"POL-OS": 20.0},
    )
    monkeypatch.setattr(zp.ZL, "_order_path", lambda _id: "dummy")
    monkeypatch.setattr(zp.ZL, "_read_json", lambda _p: order)
    with pytest.raises(ValueError, match="Plan materiałowy nie obejmuje"):
        zp.rozlicz_material("000001", kto="Edwin")


def test_finish_after_replan_preserves_unsettled_material(monkeypatch):
    # 100 -> wykonano 50 -> zamówiono 120 -> wykonano 120 -> rozlicz.
    order = _base_order(
        ilosc=100.0, wykonano=50.0, materialy_rozliczono_do=0.0,
        rezerwacje_polprodukty={"POL-OS": 100.0},
        zapotrzebowanie_surowce={"SUR-1": {"ilosc": 100.0, "jednostka": "szt"}},
    )
    state = {
        "POL-OS": {"stan": 200.0, "rezerwacje": 100.0},
        "SUR-1": {"stan": 200.0, "rezerwacje": 100.0},
    }
    consumed = []
    monkeypatch.setattr(zp.ZL, "_order_path", lambda _id: "dummy")
    monkeypatch.setattr(zp.ZL, "_read_json", lambda _p: order)
    monkeypatch.setattr(zp.ZL, "_write_json", lambda *_a, **_k: None)
    monkeypatch.setattr(zp.ZL, "_sync_execution_disposition", lambda *_a, **_k: None)
    monkeypatch.setattr(zp, "_sync_material_dispositions", lambda *_a, **_k: None)
    monkeypatch.setattr(zp.ZL, "_release_reservations", lambda *_a, **_k: None)
    monkeypatch.setattr(zp.ZL, "build_production_plan", lambda _p, qty, **_k: (
        {"POL-OS": {"potrzeba": qty}}, {"SUR-1": {"ilosc": qty, "jednostka": "szt"}}
    ))
    monkeypatch.setattr(zp.ZL, "check_materials", lambda *_a: [])
    monkeypatch.setattr(zp.ZL, "_reserve_semis", lambda plan, *_a: {
        code: rec["potrzeba"] for code, rec in plan.items()
    })
    monkeypatch.setattr(zp.ZL, "reserve_materials", lambda raw, *_a, **_k: (
        {}, {code: rec["ilosc"] for code, rec in raw.items()}
    ))
    monkeypatch.setattr(zp.LM, "get_item", lambda code: state.get(code))
    monkeypatch.setattr(
        zp.LM, "zwolnij_rezerwacje",
        lambda code, amount, *_a, **_k: state[code].__setitem__(
            "rezerwacje", state[code]["rezerwacje"] - amount
        ),
    )

    def consume(code, amount, *_a, **_k):
        consumed.append((code, amount))
        state[code]["stan"] -= amount

    monkeypatch.setattr(zp.LM, "zuzyj", consume)
    monkeypatch.setattr(zp, "_credit_new_surplus", lambda *_a, **_k: {})
    zp.update_zlecenie("000001", ilosc=120.0, kto="Edwin")
    assert order["materialy_oczekujace"]["ilosc"] == 50.0
    assert order["materialy_oczekujace"]["polprodukty"]["POL-OS"] == pytest.approx(50.0)
    assert order["materialy_oczekujace"]["surowce"]["SUR-1"] == pytest.approx(50.0)
    assert order["pozostalo"] == 70.0
    zp.report_wykonano("000001", 120.0, kto="Edwin")
    assert consumed == []
    zp.rozlicz_material("000001", kto="Edwin")
    assert consumed == [("POL-OS", pytest.approx(120.0)), ("SUR-1", pytest.approx(120.0))]
    assert order["materialy_rozliczono_do"] == 120.0
    assert "materialy_oczekujace" not in order
    zp.rozlicz_material("000001", kto="Edwin")
    assert len(consumed) == 2


def test_repeated_replan_does_not_duplicate_pending_material(monkeypatch):
    order = _base_order(
        ilosc=120.0, wykonano=50.0, pozostalo=70.0,
        materialy_oczekujace={
            "ilosc": 50.0, "polprodukty": {"POL-OS": 50.0}, "surowce": {},
        },
        rezerwacje_polprodukty={"POL-OS": 70.0},
    )
    monkeypatch.setattr(zp.ZL, "_release_reservations", lambda *_a, **_k: None)
    monkeypatch.setattr(zp.ZL, "build_production_plan", lambda _p, qty, **_k: (
        {"POL-OS": {"potrzeba": qty}}, {}
    ))
    monkeypatch.setattr(zp.ZL, "check_materials", lambda *_a: [])
    monkeypatch.setattr(zp.ZL, "_reserve_semis", lambda *_a: {})
    monkeypatch.setattr(zp.ZL, "reserve_materials", lambda *_a, **_k: ({}, {}))
    zp._replan_remaining(order, "Edwin")
    assert order["materialy_oczekujace"]["ilosc"] == 50.0
    assert order["materialy_oczekujace"]["polprodukty"] == {"POL-OS": 50.0}
