# WM 1.0.1 - read-only BOM completion proposal.
import planista_semi_progress_runtime as semi


def _order(made, stock=None, confirmed=0):
    return {
        "id": "000125",
        "produkt": "PRD-1",
        "ilosc": 6,
        "wykonano": confirmed,
        "sledzenie_polproduktow": True,
        "wykonano_polprodukty": made,
        "polprodukty_z_magazynu_baza": stock or {},
        "plan_polprodukty": {
            "A": {"potrzeba": 18},
            "B": {"potrzeba": 24},
        },
    }


def test_proposal_two_sets_without_confirming_product(monkeypatch):
    monkeypatch.setattr(semi, "_full_semi_targets", lambda order: {
        "A": {"potrzeba": 18}, "B": {"potrzeba": 24},
    })
    order = _order({"A": 6, "B": 8})
    proposal = semi.proposed_product_completion(order)
    assert proposal["complete_sets"] == 2
    assert proposal["additional"] == 2
    assert order["wykonano"] == 0
    assert order["wykonano_polprodukty"] == {"A": 6, "B": 8}


def test_proposal_respects_confirmed_and_allocated_stock(monkeypatch):
    monkeypatch.setattr(semi, "_full_semi_targets", lambda order: {
        "A": {"potrzeba": 18}, "B": {"potrzeba": 24},
    })
    proposal = semi.proposed_product_completion(
        _order({"A": 3, "B": 4}, stock={"A": 3, "B": 4}, confirmed=1)
    )
    assert proposal["complete_sets"] == 2
    assert proposal["additional"] == 1


def test_legacy_order_does_not_recalculate_existing_completion():
    order = {"ilosc": 6, "wykonano": 4}
    proposal = semi.proposed_product_completion(order)
    assert not proposal["available"]
    assert proposal["complete_sets"] == 4
    assert proposal["additional"] == 0


def test_missing_bom_does_not_mark_product_ready(monkeypatch):
    monkeypatch.setattr(semi, "_full_semi_targets", lambda order: {})
    proposal = semi.proposed_product_completion(_order({"A": 99}))
    assert not proposal["available"]
    assert proposal["additional"] == 0


def test_repeated_proposal_does_not_add_completion(monkeypatch):
    monkeypatch.setattr(semi, "_full_semi_targets", lambda order: {
        "A": {"potrzeba": 18}, "B": {"potrzeba": 24},
    })
    order = _order({"A": 6, "B": 8}, confirmed=2)
    assert semi.proposed_product_completion(order)["additional"] == 0
    assert semi.proposed_product_completion(order)["additional"] == 0
