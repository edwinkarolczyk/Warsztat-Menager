# WM-VERSION: 0.1
"""Regresje rejestru drukowania kart A4 zleceń Planisty."""

from pathlib import Path

import planista_print_history as PRINT


def _order(oid="0028", *, qty=5):
    return {
        "id": oid, "produkt": "Szafka loto", "ilosc": qty,
        "wykonano": 0, "termin": "2026-10-09",
        "plan_polprodukty": {"POL-032": {"ilosc": qty}},
        "rzaz_mm": 2,
    }


def test_legacy_orders_are_unknown_and_new_orders_unprinted(monkeypatch, tmp_path):
    dest = tmp_path / "planista" / "zlecenia_wydruki.json"
    monkeypatch.setattr(PRINT, "print_history_path", lambda: dest)

    PRINT.ensure_print_registry([_order("0028")])
    data = PRINT.load_print_history()
    assert PRINT.print_status(_order("0028"), data) == PRINT.PRINT_UNKNOWN
    assert PRINT.print_status(_order("0029"), data) == PRINT.PRINT_NEW

    # Ponowny start nie może zmienić nowego zlecenia w historyczne.
    PRINT.ensure_print_registry([_order("0028"), _order("0029")])
    assert PRINT.print_status(_order("0029")) == PRINT.PRINT_NEW
    assert dest.is_file()


def test_sent_order_becomes_changed_when_card_data_changes(monkeypatch, tmp_path):
    monkeypatch.setattr(
        PRINT, "print_history_path", lambda: tmp_path / "registry.json",
    )
    old = _order()
    PRINT.ensure_print_registry([old])
    PRINT.record_print_event(old, PRINT.PRINT_PENDING, user="Edwin")
    assert PRINT.print_status(old) == PRINT.PRINT_PENDING

    PRINT.record_print_event(old, PRINT.PRINT_SENT, user="Edwin", source="WM")
    assert PRINT.print_status(old) == PRINT.PRINT_SENT
    assert PRINT.print_status(_order(qty=10)) == PRINT.PRINT_CHANGED

    history = PRINT.print_events("0028")
    assert len(history) == 2
    assert history[1]["uzytkownik"] == "Edwin"
    assert history[1]["czas"]
    assert history[1]["wersja"] == PRINT.order_print_fingerprint(old)


def test_second_print_is_recorded_and_failures_remain_visible(monkeypatch, tmp_path):
    monkeypatch.setattr(
        PRINT, "print_history_path", lambda: tmp_path / "registry.json",
    )
    record = _order()
    PRINT.ensure_print_registry([record])
    PRINT.record_print_event(record, PRINT.PRINT_SENT, source="WM")
    PRINT.record_print_event(record, PRINT.PRINT_PENDING, source="WM")
    PRINT.record_print_event(record, PRINT.PRINT_ERROR, details="Brak drukarki")
    assert PRINT.print_status(record) == PRINT.PRINT_ERROR
    PRINT.record_print_event(record, PRINT.PRINT_SENT, source="ponowienie")
    assert PRINT.print_status(record) == PRINT.PRINT_SENT
    assert len(PRINT.print_events("0028")) == 4


def test_history_registry_uses_active_data_and_is_not_saved_inside_order(monkeypatch, tmp_path):
    monkeypatch.setattr(
        PRINT, "print_history_path", lambda: tmp_path / "planista" / "zlecenia_wydruki.json",
    )
    PRINT.ensure_print_registry([_order()])
    PRINT.record_print_event(_order(), PRINT.PRINT_SENT)
    path = PRINT.print_history_path()
    assert "planista" in str(path)
    assert "zlecenia_wydruki.json" == path.name
    assert "0028" in path.read_text(encoding="utf-8")


def test_print_controls_have_extended_selection_and_safe_status_distinctions():
    source = (Path(__file__).resolve().parents[1] / "gui_planista_panel.py").read_text(
        encoding="utf-8"
    )
    assert '"wydruk": "Wydruk"' in source
    assert '"wybor": "✓"' in source
    assert "selectmode=" in source
    assert "Drukuj zaznaczone" in source
    assert "Drukuj niewydrukowane" in source
    assert "Historia wydruków" in source
    assert "only_unprinted=True" in source
    assert "print_status(self._orders[oid], registry) == PRINT_NEW" in source
    assert "str(order.get(" in source
    assert "Wysłano ≠ potwierdzenie wydruku na papierze." in source


def test_existing_editor_preserves_print_controls_and_double_click_history():
    panel = (Path(__file__).resolve().parents[1] / "gui_planista_panel.py").read_text(
        encoding="utf-8"
    )
    editor = (Path(__file__).resolve().parents[1] / "planista_editor_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "self._orders_action_bar = buttons" in panel
    assert 'bar = getattr(self, "_orders_action_bar", frames[-1])' in editor
    assert "_open_print_history_on_double_click(event)" in panel
    assert "_open_print_history_on_double_click(event)" in editor
    assert 'text="Drukuj A4"' in panel
    assert 'self.tree.set(oid, "wydruk", "… W kolejce")' in panel


def test_unaccepted_excel_print_does_not_mark_workshop_order_as_sent(monkeypatch, tmp_path):
    monkeypatch.setattr(
        PRINT, "print_history_path", lambda: tmp_path / "registry.json",
    )
    original_order = _order("747")
    PRINT.ensure_print_registry([original_order])
    external = {"id": "747", "produkt": "Szafka LOTO", "ilosc": 5}
    PRINT.record_print_event(
        external, PRINT.PRINT_SENT, source="Excel przed akceptacją",
    )

    data = PRINT.load_print_history()
    assert PRINT.print_status(original_order, data) == PRINT.PRINT_UNKNOWN
    assert not PRINT.print_events("747", data)
    assert len(data["orders"]["excel:747"]) == 1
