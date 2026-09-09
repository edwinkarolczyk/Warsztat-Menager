# version: 1.0
import datetime as dt

import planista_dispatch_runtime as PDR


def test_priority_boundaries():
    today = dt.date(2026, 9, 3)
    assert PDR.priority_for_deadline("2026-09-02", today=today) == "krytyczny"
    assert PDR.priority_for_deadline("2026-09-06", today=today) == "krytyczny"
    assert PDR.priority_for_deadline("2026-09-07", today=today) == "wysoki"
    assert PDR.priority_for_deadline("2026-09-10", today=today) == "wysoki"
    assert PDR.priority_for_deadline("2026-09-11", today=today) == "normalny"
    assert PDR.priority_for_deadline("2026-09-24", today=today) == "normalny"
    assert PDR.priority_for_deadline("2026-09-25", today=today) == "niski"
    assert PDR.priority_for_deadline("", today=today) == "normalny"
    assert PDR.priority_for_deadline("abc", today=today) == "normalny"


def test_magazyn_hidden_only_for_new_creator():
    values = ["Narzędzie", "Maszyna", "Magazyn", "Zlecenie produkcyjne"]
    assert "Magazyn" not in PDR.creator_type_values(values, edit_mode=False)
    assert "Magazyn" in PDR.creator_type_values(values, edit_mode=True)


def test_planista_choices_and_context_use_real_orders(monkeypatch):
    orders = [
        {
            "id": "000002",
            "produkt": "5.FAM",
            "ilosc": 82,
            "termin": "2026-09-10",
        }
    ]
    monkeypatch.setattr(PDR, "_planista_orders", lambda: orders)
    assert PDR.planista_order_choices() == [
        ("zlecenie:000002", "000002 — 5.FAM — 82 szt.")
    ]
    ctx = PDR.planista_order_context("zlecenie:000002")
    assert ctx["nr_zlecenia"] == "000002"
    assert ctx["ilosc_domyslna"] == 82
    assert ctx["termin"] == "2026-09-10"


def test_active_duplicate_is_blocked_but_closed_is_not():
    active = {
        "id": "DYSP-1",
        "typ_dyspozycji": "zlecenie_wykonania",
        "status": "w_toku",
        "obiekt_id": "zlecenie:000002",
        "meta": {"nr_zlecenia": "000002"},
    }
    closed = dict(active, id="DYSP-2", status="zamknieta")
    assert PDR.find_active_planista_dispatch("000002", rows=[active]) == active
    assert PDR.find_active_planista_dispatch("000002", rows=[closed]) is None


def test_print_has_need_done_box():
    source = (
        "<div class='meta'>"
        "<div><b>Ilość:</b> 80</div>\n"
        "<div><b>Wykonano:</b> 0</div>"
        "</div>"
    )
    result = PDR.enhance_work_order_html({"ilosc": 80}, source)
    assert "Potrzeba / wykonane:" in result
    assert "80 /" in result
    assert "[&nbsp;&nbsp;&nbsp;]" in result
    assert "<b>Ilość:</b>" not in result
    assert "<b>Wykonano:</b>" not in result
