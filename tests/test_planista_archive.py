"""Regresje archiwizacji i trwałego pomijania pozycji Planisty."""
import json
from datetime import date
from types import SimpleNamespace

import planista_excel_orders as sync
import zlecenia_logika as orders
from planista_excel_match import STATUS_FOUND


def test_order_archive_preserves_production_and_history(tmp_path, monkeypatch):
    path = tmp_path / "0001.json"
    original = {
        "id": "0001", "status": "w trakcie", "ilosc": 100,
        "wykonano": 40, "rezerwacje_surowce": {"A": 50},
        "historia": [{"co": "utworzenie"}],
    }
    path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(orders, "_order_path", lambda _order_id: path)

    archived = orders.set_zlecenie_archived("0001", archived=True, kto="test")
    assert archived["status"] == "w trakcie"
    assert archived["wykonano"] == 40
    assert archived["rezerwacje_surowce"] == {"A": 50}
    assert archived["archiwum"]["kto"] == "test"
    assert archived["historia"][-1]["co"] == "archiwizacja"

    restored = orders.set_zlecenie_archived("0001", archived=False, kto="test")
    assert not restored.get("archiwum")
    assert restored["historia"][-1]["co"] == "przywrócenie z archiwum"
    assert restored["rezerwacje_surowce"] == {"A": 50}


def test_excel_archive_blocks_import_until_restored(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sync, "ConfigManager",
        lambda: SimpleNamespace(path_data=lambda: str(tmp_path)),
    )
    row = {
        "nr_zlec": "ZL-444", "wm_symbol": "P-1",
        "match_status": STATUS_FOUND, "ilosc": 10,
        "data_wysylki": "2026-04-23", "produkt": "P-1",
        "source_row": 7,
    }
    item = {
        "identity": "zl-444|p-1", "nr_zlec": "ZL-444",
        "wm_symbol": "P-1", "termin": "2026-04-23",
    }
    payload = {"rows": [row]}

    before = sync.build_order_sync_plan(payload, orders=[])
    assert before["items"][0]["action"] == sync.ACTION_CREATE

    sync.set_excel_archive(item, archived=True, kto="test")
    assert "zl-444|p-1" in sync.load_excel_archive()
    blocked = sync.build_order_sync_plan(payload, orders=[])
    assert blocked["items"][0]["action"] == sync.ACTION_ARCHIVED
    assert not blocked["can_write"]

    sync.set_excel_archive(item, archived=False, kto="test")
    assert "zl-444|p-1" not in sync.load_excel_archive()
    restored = sync.build_order_sync_plan(payload, orders=[])
    assert restored["items"][0]["action"] == sync.ACTION_CREATE


def test_archived_existing_order_is_not_updated(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sync, "ConfigManager",
        lambda: SimpleNamespace(path_data=lambda: str(tmp_path)),
    )
    row = {
        "nr_zlec": "ZL-451", "wm_symbol": "P-2",
        "match_status": STATUS_FOUND, "ilosc": 20,
        "data_wysylki": "2026-04-23", "produkt": "P-2",
        "source_row": 8,
    }
    existing = {
        "id": "0002", "produkt": "P-2", "ilosc": 10,
        "status": "nowe", "termin": "2026-04-23",
        "archiwum": {"kiedy": "2026-10-22T13:00:00"},
        "planista_excel": {
            "nr_zlec": "ZL-451", "wm_symbol": "P-2",
            "identity": "zl-451|p-2",
        },
    }
    plan = sync.build_order_sync_plan({"rows": [row]}, orders=[existing])
    assert plan["items"][0]["action"] == sync.ACTION_ARCHIVED
    assert not plan["can_write"]


def test_order_display_filters(monkeypatch):
    from gui_planista_panel import _planista_order_visible

    today = date(2026, 10, 22)
    pending = {"id": "0003", "status": "nowe", "ilosc": 10,
               "wykonano": 0, "termin": "2026-04-23"}
    finished = {**pending, "id": "0004", "status": "zakończone", "wykonano": 10}
    archived = {**pending, "id": "0005", "archiwum": {"kiedy": "now"}}
    assert _planista_order_visible(pending, "Aktywne", today=today)
    assert _planista_order_visible(pending, "Zaległe", today=today)
    assert not _planista_order_visible(finished, "Aktywne", today=today)
    assert _planista_order_visible(finished, "Zakończone", today=today)
    assert not _planista_order_visible(archived, "Zaległe", today=today)
    assert _planista_order_visible(archived, "Archiwum", today=today)
    assert _planista_order_visible(pending, "Wszystkie", search="0003", today=today)
    assert not _planista_order_visible(pending, "Wszystkie", search="inne", today=today)
