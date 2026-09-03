# WM-VERSION: 0.1

from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "gui_planista_panel.py"


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_planista_orders_table_has_required_start_and_bom_version():
    source = _source()
    assert '"zlec_wew",\n            "id",\n            "produkt",\n            "ilosc",\n            "version",' in source
    assert '"zlec_wew": "Zlecenie wew"' in source
    assert '"id": "Zlecenie warsztatowe"' in source
    assert '"produkt": "Produkt"' in source
    assert '"ilosc": "Zamówienie"' in source
    assert '"version": "Wersja BOM"' in source


def test_planista_orders_table_keeps_existing_progress_columns():
    source = _source()
    for column in ("wykonano", "pozostalo", "termin", "status"):
        assert f'"{column}"' in source


def test_planista_order_sources_remain_independent():
    source = _source()
    assert 'order.get("zlec_wew", "")' in source
    assert '# Numer warsztatowy pochodzi wyłącznie z kanonicznego ID zlecenia.\n                    oid,' in source
    assert 'str(order.get("version") or "")' in source
