"""WM 1.0: WMM uses the same order/closure business rules as desktop WM."""
from pathlib import Path

import pytest

import zlecenia_logika as ZL
import dyspozycje_store as DS
import dyspozycje_access as DA
import planista_dispatch_runtime as PD
from services import wmm_api as API


def test_wmm_creates_canonical_bom_order(monkeypatch, tmp_path):
    data = tmp_path / "data"
    monkeypatch.setattr(ZL, "_data_dir", lambda: data)
    monkeypatch.setattr(API, "_data_dir", lambda: data)
    monkeypatch.setattr(API, "_planista_products", lambda: [
        {"kod": "P1", "version": 7}
    ])
    captured = {}

    def create(product, qty, **kwargs):
        captured.update({"product": product, "qty": qty, **kwargs})
        return {"id": "000125", "plan_polprodukty": {"A": {"potrzeba": 18}}},
               []

    create._wm_full_transaction = True
    monkeypatch.setattr(ZL, "create_zlecenie", create)
    result = API._create_planista_order({
        "product_code": "P1", "quantity": 6, "external_no": "INT-1"
    }, "Edwin")
    assert result["id"] == "000125"
    assert result["plan_polprodukty"]["A"]["potrzeba"] == 18
    assert captured["reserve"] is True
    assert captured["auto_dyspozycje"] is True
    assert captured["version"] == 7
    assert captured["zlec_wew"] == "INT-1"


def test_wmm_product_disposition_closure_checks_planista(monkeypatch):
    monkeypatch.setattr(DS, "get_dyspozycja", lambda _id: {
        "id": "D1", "typ_dyspozycji": "zlecenie_wykonania",
        "status": "w_toku", "obiekt_id": "zlecenie:000125",
    })
    monkeypatch.setattr(DA, "resolve_role_for_login", lambda _name: "brygadzista")
    calls = []
    monkeypatch.setattr(PD, "close_completed_planista_dispatch",
        lambda order, **kwargs: (
            calls.append((order, kwargs["who"], kwargs["role"]))
            or {"id": "D1", "status": "zamknieta"}
        ))
    saved = API._set_disposition_status("D1", "zamknieta", "Edwin")
    assert saved["status"] == "zamknieta"
    assert calls == [("000125", "Edwin", "brygadzista")]


def test_wmm_refuses_unlinked_production_close(monkeypatch):
    monkeypatch.setattr(DS, "get_dyspozycja", lambda _id: {
        "id": "D1", "typ_dyspozycji": "zlecenie_wykonania",
        "status": "w_toku", "obiekt_id": "zlec-elsewhere",
    })
    with pytest.raises(RuntimeError, match="bez powiązanego"):
        API._set_disposition_status("D1", "zamknieta", "Edwin")
