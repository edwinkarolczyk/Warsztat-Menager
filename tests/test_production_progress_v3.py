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

    with pytest.raises(ValueError, match="stan magazynowy jest za mały"):
        zp.report_wykonano("000001", 50, kto="Edwin")

    assert calls == []


def test_partial_report_keeps_only_this_orders_remaining_reservation(monkeypatch):
    order = _base_order(
        ilosc=100.0,
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

    zp.report_wykonano("000001", 50, kto="Edwin")

    # Z 60 szt. rezerwacji dla tego zlecenia zuzyto 1/6 = 10.
    # Do przeliczenia moze zostac przekazane tylko pozostale 50, a nie stare 60.
    assert released_by_replan == [{"POL-OS": 50.0}]
    # Globalnie bylo 100 rezerwacji, wiec 40 nalezalo do innych zlecen.
    assert state["POL-OS"]["rezerwacje"] == 90.0
    assert state["POL-OS"]["stan"] == 90.0
