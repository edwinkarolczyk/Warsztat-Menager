from __future__ import annotations

import gui_zlecenia as GZ
import zlecenia_logika as ZL


def _planista_row(status="nowa"):
    return {
        "id": "DYSP-OLD-001",
        "typ_dyspozycji": "zlecenie_wykonania",
        "obiekt_id": "zlecenie:000012",
        "tytul": "1. Wykonanie produktu 1.300.300 — zlecenie 000012",
        "status": status,
        "meta": {"legacy_flag": "zostaje"},
    }


def test_existing_open_planista_disposition_uses_live_source_without_migration(monkeypatch):
    monkeypatch.setattr(
        GZ,
        "_DYSP_ORDER_INFO_CACHE",
        {
            "000012": {
                "id": "000012",
                "produkt": "1.300.300",
                "ilosc": 10,
                "wykonano": 5,
                "status": "w trakcie",
            }
        },
    )
    row = _planista_row()

    assert GZ._is_linked_source_disposition(row) is True
    assert GZ._source_object_label(row) == "Planista • 000012"
    assert GZ._task_label(row) == "Wykonanie produktu 1.300.300"
    assert GZ._live_object_state_label(row) == "5/10 szt. • w trakcie"
    assert row["id"] == "DYSP-OLD-001"
    assert row["meta"]["legacy_flag"] == "zostaje"


def test_existing_machine_and_tool_rows_show_live_name_and_state(monkeypatch):
    monkeypatch.setattr(
        GZ,
        "_DYSP_MACHINE_INFO_CACHE",
        {"75": {"id": "75", "name": "Filtry laser", "status": "Sprawna"}},
    )
    monkeypatch.setattr(
        GZ,
        "_DYSP_TOOL_INFO_CACHE",
        {"507": {"id": "507", "name": "Frez", "status": "W ostrzeniu"}},
    )

    machine = {
        "typ_dyspozycji": "maszyna",
        "obiekt_id": "75",
        "tytul": "Przegląd cykliczny",
        "status": "nowa",
    }
    tool = {
        "typ_dyspozycji": "narzedzie",
        "obiekt_id": "507",
        "tytul": "Ostrzenie",
        "status": "w_toku",
    }

    assert GZ._source_object_label(machine) == "Maszyna • 75 Filtry laser"
    assert GZ._live_object_state_label(machine) == "Sprawna"
    assert GZ._source_object_label(tool) == "Narzędzie • 507 Frez"
    assert GZ._live_object_state_label(tool) == "W ostrzeniu"


def test_legacy_unlinked_disposition_keeps_normal_mode(monkeypatch):
    monkeypatch.setattr(GZ, "_DYSP_TOOL_INFO_CACHE", {})
    row = {
        "id": "DYSP-LEGACY",
        "typ_dyspozycji": "narzedzie",
        "tytul": "Stare zadanie bez obiektu",
        "status": "nowa",
        "obiekt_id": "",
    }
    assert GZ._is_linked_source_disposition(row) is False
    assert GZ._source_object_label(row) == "—"
    assert GZ._task_label(row) == "Stare zadanie bez obiektu"


class _FakeButton:
    def __init__(self):
        self.disabled = None
        self.text = ""

    def state(self, values):
        self.disabled = "disabled" in values

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]


def test_linked_source_disables_duplicate_dyspozycja_actions(monkeypatch):
    monkeypatch.setattr(
        GZ,
        "_DYSP_ORDER_INFO_CACHE",
        {"000012": {"id": "000012", "ilosc": 10, "wykonano": 0, "status": "nowe"}},
    )
    view = object.__new__(GZ.ZleceniaView)
    row = _planista_row(status="nowa")
    view._selected_row = lambda: row
    view.btn_start = _FakeButton()
    view.btn_pause = _FakeButton()
    view.btn_resume = _FakeButton()
    view.btn_close = _FakeButton()
    view.btn_edit = _FakeButton()
    view.btn_open_source = _FakeButton()

    view._update_status_actions()

    assert view.btn_start.disabled is True
    assert view.btn_pause.disabled is True
    assert view.btn_resume.disabled is True
    assert view.btn_close.disabled is True
    assert view.btn_edit.disabled is True
    assert view.btn_open_source.disabled is False
    assert view.btn_open_source.text == "Otwórz w Planista"


def test_planista_status_mapping_waits_for_material_before_close():
    assert ZL._execution_dispatch_target_status(
        {"status": "w trakcie", "ilosc": 10, "wykonano": 5, "materialy_rozliczono_do": 5}
    ) == "w_toku"
    assert ZL._execution_dispatch_target_status(
        {"status": "zakończone", "ilosc": 10, "wykonano": 10, "materialy_rozliczono_do": 9}
    ) == "w_toku"
    assert ZL._execution_dispatch_target_status(
        {"status": "zakończone", "ilosc": 10, "wykonano": 10, "materialy_rozliczono_do": 10}
    ) == "zamknieta"


def test_planista_automatic_close_records_actor_and_source_note():
    calls = []

    class FakeStore:
        @staticmethod
        def set_dyspozycja_status(dysp_id, status, **kwargs):
            calls.append((dysp_id, status, kwargs))
            return {
                "id": dysp_id,
                "status": status,
                "zamkniete_przez": kwargs.get("changed_by", "") if status == "zamknieta" else "",
            }

    result = ZL._apply_execution_dispatch_status(
        FakeStore,
        {"id": "DYSP-OLD-001", "status": "w_toku"},
        "zamknieta",
        actor="Edwin",
    )

    assert result["status"] == "zamknieta"
    assert calls == [
        (
            "DYSP-OLD-001",
            "zamknieta",
            {
                "changed_by": "Edwin",
                "uwagi": "Zamknięto automatycznie ze źródła: Planista.",
            },
        )
    ]


def test_actor_falls_back_to_last_real_planista_history_user():
    order = {
        "historia": [
            {"kto": "system", "co": "utworzenie"},
            {"kto": "Marek", "co": "rozliczono materiał"},
        ]
    }
    assert ZL._execution_dispatch_actor(order, "system") == "Marek"
