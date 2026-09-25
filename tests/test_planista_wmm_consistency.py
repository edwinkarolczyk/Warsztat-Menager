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
        return ({"id": "000125", "plan_polprodukty": {"A": {"potrzeba": 18}}}, [])

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


def test_headless_wmm_creation_rolls_back_partial_order(monkeypatch, tmp_path):
    import logika_magazyn as LM
    import planista_audit_runtime as PAR

    data = tmp_path / "data"
    orders = data / "zlecenia"
    orders.mkdir(parents=True)
    monkeypatch.setattr(ZL, "_data_dir", lambda: data)
    monkeypatch.setattr(API, "_data_dir", lambda: data)
    monkeypatch.setattr(API, "_planista_products", lambda: [
        {"kod": "P1", "version": 1}
    ])
    monkeypatch.setattr(LM, "_warehouse_path", lambda: data / "magazyn.json")
    stock = {"RAW": 20}
    monkeypatch.setattr(PAR, "_canonical_warehouse_snapshot", lambda: dict(stock))
    monkeypatch.setattr(PAR, "_restore_canonical_warehouse",
                        lambda original: stock.update(original))
    monkeypatch.setattr(PAR, "_disposition_snapshot", lambda: (None, None))
    monkeypatch.setattr(PAR, "_restore_disposition_snapshot", lambda *_: None)

    def fail_after_first_write(*_args, **_kwargs):
        (orders / "000125.json").write_text('{"id":"000125"}', encoding="utf-8")
        stock["RAW"] -= 5
        raise RuntimeError("przerwany zapis")

    monkeypatch.setattr(ZL, "create_zlecenie", fail_after_first_write)
    with pytest.raises(RuntimeError, match="przerwany zapis"):
        API._create_planista_order({"product_code": "P1", "quantity": 6}, "Edwin")
    assert stock["RAW"] == 20
    assert not (orders / "000125.json").exists()



def test_wmm_planista_detail_exposes_semiproducts_and_operations(monkeypatch):
    import planista_semi_progress_runtime as PS

    order = {
        "id": "000125",
        "produkt": "P1",
        "ilosc": 6,
        "wykonano": 0,
        "status": "nowe",
        "historia": [],
        "wykonano_polprodukty": {"A": 0},
        "postep_operacji_polproduktow": {"A": {"Cięcie": 6}},
    }
    monkeypatch.setattr(
        PS,
        "_full_semi_targets",
        lambda _order: {
            "A": {
                "nazwa": "Rama",
                "potrzeba": 6,
                "czynnosci": ["Cięcie", "Spawanie"],
            }
        },
    )
    monkeypatch.setattr(
        PS,
        "semi_progress_rows",
        lambda _order: [
            {
                "kod": "A",
                "nazwa": "Rama",
                "potrzeba": 6,
                "z_magazynu": 0,
                "do_wykonania": 6,
                "wykonano": 0,
                "pozostalo": 6,
            }
        ],
    )

    detail = API._planista_mobile_order(order)

    assert detail["id"] == "000125"
    assert detail["wmm_revision"]
    semi = detail["wmm_polprodukty"][0]
    assert semi["kod"] == "A"
    assert semi["nazwa"] == "Rama"
    assert semi["do_wykonania"] == 6
    assert [op["nazwa"] for op in semi["operacje"]] == ["Cięcie", "Spawanie"]
    assert semi["operacje"][0]["wykonana"] is True
    assert semi["operacje"][1]["wykonana"] is False
    assert semi["operacje"][1]["dostepna"] is True
