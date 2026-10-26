# WM-VERSION: 0.1

from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "gui_planista_panel.py"


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_planista_orders_table_has_required_start_and_semi_progress():
    source = _source()
    assert '"zlec_wew",\n            "id",\n            "produkt",\n            "ilosc",\n            "polprodukty",' in source
    assert '"zlec_wew": "Zlecenie wew"' in source
    assert '"id": "Zlecenie warsztatowe"' in source
    assert '"produkt": "Produkt"' in source
    assert '"ilosc": "Zamówienie"' in source
    assert '"polprodukty": "Półprodukty"' in source


def test_planista_orders_table_keeps_existing_progress_columns():
    source = _source()
    for column in ("wykonano", "pozostalo", "termin", "status"):
        assert f'"{column}"' in source


def test_planista_order_sources_remain_independent():
    source = _source()
    assert 'order.get("zlec_wew", "")' in source
    assert '# Numer warsztatowy pochodzi wyłącznie z kanonicznego ID zlecenia.\n                    oid,' in source
    assert '_semi_progress_display(order)' in source


def test_planista_semi_progress_display_uses_requested_traffic_light(monkeypatch):
    import gui_planista_panel as panel
    import planista_semi_progress_runtime as semi

    monkeypatch.setattr(
        semi,
        "proposed_product_completion",
        lambda _order: {
            "available": True,
            "planned": 50,
            "complete_sets": 0,
        },
    )
    assert panel._semi_progress_display({}) == "🔴 0/50"

    monkeypatch.setattr(
        semi,
        "proposed_product_completion",
        lambda _order: {
            "available": True,
            "planned": 50,
            "complete_sets": 1,
        },
    )
    assert panel._semi_progress_display({}) == "🟡 1/50"

    monkeypatch.setattr(
        semi,
        "proposed_product_completion",
        lambda _order: {
            "available": True,
            "planned": 50,
            "complete_sets": 50,
        },
    )
    assert panel._semi_progress_display({}) == "🟢 50/50"

def test_planista_view_filter_is_independent_from_print_filter():
    source = _source()
    assert 'order_mode = self._order_filter_var.get()' in source
    assert 'print_mode = (' in source
    assert '_planista_order_visible(order, order_mode, search)' in source
    assert 'if print_mode == "Do wydrukowania":' in source
    assert 'elif print_mode != "Wszystkie" and state != print_mode:' in source
    assert 'if _planista_order_visible(order, mode, search):' not in source

