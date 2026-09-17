from __future__ import annotations

import pytest

from services import wmm_api_impl as api


def _definitions():
    return {
        "collections": {
            "SN": {
                "types": [
                    {
                        "id": "POST",
                        "name": "Postępowe",
                        "statuses": [
                            {"id": "READY", "name": "Dostępne"},
                            {"id": "SHARPEN", "name": "Do ostrzenia"},
                        ],
                    }
                ]
            }
        }
    }


def test_tool_statuses_come_from_matching_wm_tool_type(monkeypatch):
    import tools_config_loader

    monkeypatch.setattr(tools_config_loader, "load_config", lambda path=None: _definitions())
    tool = {"numer": "507", "tryb": "STARE", "typ": "Postępowe"}

    assert api._tool_status_options(tool) == [
        {"id": "READY", "name": "Dostępne"},
        {"id": "SHARPEN", "name": "Do ostrzenia"},
    ]
    assert api._canonical_tool_status(tool, "sharpen") == "Do ostrzenia"


def test_tool_status_rejects_value_not_configured_in_wm(monkeypatch):
    import tools_config_loader

    monkeypatch.setattr(tools_config_loader, "load_config", lambda path=None: _definitions())

    with pytest.raises(RuntimeError, match="nie jest przypisany"):
        api._canonical_tool_status(
            {"numer": "507", "tryb": "STARE", "typ": "Postępowe"},
            "Do naprawy",
        )


def test_tool_status_adds_one_canonical_history_entry(monkeypatch):
    monkeypatch.setattr(
        api,
        "_canonical_tool_status",
        lambda tool, requested: "W ostrzeniu",
    )
    tool = {
        "status": "Przegląd",
        "opis": "Stały opis techniczny narzędzia",
        "historia": [],
    }

    changed = api._apply_tool_status_from_wmm(
        tool,
        "SHARPEN",
        actor="Edwin",
        note="Do ostrzenia",
    )

    assert changed is True
    assert tool["status"] == "W ostrzeniu"
    assert tool["opis"] == "Stały opis techniczny narzędzia"
    assert len(tool["historia"]) == 1
    assert tool["historia"][0]["action"] == "status_changed"
    assert tool["historia"][0]["z"] == "Przegląd"
    assert tool["historia"][0]["na"] == "W ostrzeniu"
    assert tool["historia"][0]["source"] == "WMM"
    assert "Przegląd → W ostrzeniu" in tool["historia"][0]["details"]
    assert "Do ostrzenia" in tool["historia"][0]["details"]


def test_selecting_current_tool_status_is_noop(monkeypatch):
    monkeypatch.setattr(
        api,
        "_canonical_tool_status",
        lambda tool, requested: "W ostrzeniu",
    )
    tool = {"status": "W ostrzeniu", "historia": []}

    changed = api._apply_tool_status_from_wmm(
        tool,
        "SHARPEN",
        actor="Edwin",
        note="",
    )

    assert changed is False
    assert tool["historia"] == []


def test_machine_status_uses_desktop_wm_change_mechanism(monkeypatch):
    import gui_maszyny_legacy

    calls = []
    monkeypatch.setattr(
        gui_maszyny_legacy,
        "_apply_machine_status_change",
        lambda machine, status, **kwargs: calls.append((status, kwargs)),
    )
    machine = {"status": "ok"}

    api._apply_machine_status_from_wmm(
        machine, "Awaria", actor="edwin", note="Silnik"
    )

    assert calls == [("warn", {"actor": "edwin", "note": "Silnik"})]
    assert machine["uwagi"] == "Silnik"


def test_machine_status_rejects_unknown_value():
    with pytest.raises(RuntimeError, match="Nieprawidłowy status"):
        api._apply_machine_status_from_wmm(
            {"status": "ok"}, "własny status", actor="edwin", note=""
        )
