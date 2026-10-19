"""Regresje automatycznego rozliczania braków surowca po PZ."""

import dyspozycje_magazyn as dm
import dyspozycje_store as DS
import logika_magazyn as LM
import zlecenia_logika as ZL


def _row(identifier, order_id, *, status="nowa", source="zlecenia"):
    return {
        "id": identifier,
        "typ_dyspozycji": "magazyn",
        "modul_zrodlowy": source,
        "obiekt_id": f"zlecenie:{order_id}:surowiec:SUR-001",
        "status": status,
        "meta": {"zlecenie_id": order_id, "surowiec": "SUR-001", "brakuje": 10},
    }


def _arrange(monkeypatch, *, quantity, reservations=0, rows=None, orders=None):
    stock = {"stan": quantity, "rezerwacje": reservations}
    records = rows if rows is not None else [_row("D-1", "Z-1")]
    orders = orders or {
        "Z-1": {
            "zapotrzebowanie_surowce": {"SUR-001": {"ilosc": 10}},
            "rezerwacje_surowce": {},
        }
    }
    history = []
    monkeypatch.setattr(LM, "get_item", lambda code: stock if code == "SUR-001" else None)
    monkeypatch.setattr(DS, "load_dyspozycje", lambda: records)
    monkeypatch.setattr(ZL, "_order_path", lambda order_id: order_id)
    monkeypatch.setattr(ZL, "_read_json", lambda order_id: orders[order_id])

    def transition(identifier, target, **kwargs):
        row = next(r for r in records if r["id"] == identifier)
        history.append((identifier, row["status"], target))
        row["status"] = target
        return dict(row)

    monkeypatch.setattr(DS, "set_dyspozycja_status", transition)
    return history, stock, records


def test_full_receipt_closes_only_linked_shortage_once(monkeypatch):
    rows = [
        _row("D-1", "Z-1"),
        _row("D-MANUAL", "Z-1", source="magazyn"),
        _row("D-HOLD", "Z-1", status="wstrzymana"),
    ]
    history, _stock, records = _arrange(monkeypatch, quantity=13, rows=rows)
    assert dm.close_fulfilled_material_dispositions("SUR-001") == ["D-1"]
    assert history == [
        ("D-1", "nowa", "w_toku"),
        ("D-1", "w_toku", "zamknieta"),
    ]
    assert records[1]["status"] == "nowa"
    assert records[2]["status"] == "wstrzymana"
    assert dm.close_fulfilled_material_dispositions("SUR-001") == []


def test_partial_receipt_does_not_close(monkeypatch):
    history, _stock, _rows = _arrange(monkeypatch, quantity=8)
    assert dm.close_fulfilled_material_dispositions("SUR-001") == []
    assert history == []


def test_two_orders_must_not_double_count_same_warehouse_stock(monkeypatch):
    rows = [_row("D-1", "Z-1"), _row("D-2", "Z-2")]
    orders = {
        key: {
            "zapotrzebowanie_surowce": {"SUR-001": {"ilosc": 10}},
            "rezerwacje_surowce": {},
        }
        for key in ("Z-1", "Z-2")
    }
    history, stock, _rows = _arrange(
        monkeypatch, quantity=13, rows=rows, orders=orders
    )
    assert dm.close_fulfilled_material_dispositions("SUR-001") == []
    stock["stan"] = 20
    assert dm.close_fulfilled_material_dispositions("SUR-001") == ["D-1", "D-2"]
    assert len(history) == 4


def test_order_reservation_counts_towards_its_own_requirement(monkeypatch):
    orders = {
        "Z-1": {
            "zapotrzebowanie_surowce": {"SUR-001": {"ilosc": 10}},
            "rezerwacje_surowce": {"SUR-001": 5},
        }
    }
    history, _stock, _rows = _arrange(
        monkeypatch, quantity=10, reservations=5, orders=orders
    )
    assert dm.close_fulfilled_material_dispositions("SUR-001") == ["D-1"]
    assert len(history) == 2
