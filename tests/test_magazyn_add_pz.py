from gui_magazyn_edit import _build_new_item_payload
from gui_magazyn_pz import _apply_pz_to_item


def test_build_new_item_payload_full_fields():
    item_id, item = _build_new_item_payload(
        {
            "id": "PROFIL-30X30X2",
            "sekcja": "Surowce",
            "nazwa": "Profil 30x30x2",
            "rozmiar": "30x30x2",
            "stan": "120,5",
            "jednostka": "m",
            "lokalizacja": "Regał A2",
            "stan_min": "20",
            "zadania": "cięcie, wiercenie",
        }
    )

    assert item_id == "PROFIL-30X30X2"
    assert item["typ"] == "surowiec"
    assert item["stan"] == 120.5
    assert item["rezerwacje"] == 0.0
    assert item["jednostka"] == "m"
    assert item["lokalizacja"] == "Regał A2"
    assert item["stan_min"] == 20.0
    assert item["zadania"] == ["cięcie", "wiercenie"]


def test_build_new_item_payload_rejects_missing_required_and_negative_stock():
    try:
        _build_new_item_payload(
            {
                "id": "X",
                "sekcja": "Surowce",
                "nazwa": "",
                "jednostka": "szt",
                "stan": "0",
            }
        )
    except ValueError as exc:
        assert "nazw" in str(exc).lower()
    else:
        raise AssertionError("Brak nazwy powinien być odrzucony")

    try:
        _build_new_item_payload(
            {
                "id": "X",
                "sekcja": "Surowce",
                "nazwa": "Test",
                "jednostka": "szt",
                "stan": "-1",
            }
        )
    except ValueError as exc:
        assert "ujem" in str(exc).lower()
    else:
        raise AssertionError("Ujemny stan powinien być odrzucony")


def test_apply_pz_increases_stock_and_rejects_non_positive_qty():
    item = {"stan": 10}
    assert _apply_pz_to_item(item, 2.5) == 12.5
    assert item["stan"] == 12.5

    for qty in (0, -1):
        try:
            _apply_pz_to_item(item, qty)
        except ValueError:
            pass
        else:
            raise AssertionError("PZ <= 0 powinno być odrzucone")
