# version: 1.0
"""Regresja punktu wejścia Maszyn po dołożeniu pomieszczeń hali."""

import sys

import gui_maszyny
import gui_maszyny_legacy


def test_gui_maszyny_is_same_legacy_module_object():
    assert gui_maszyny is gui_maszyny_legacy
    assert sys.modules["gui_maszyny"] is gui_maszyny_legacy


def test_room_extension_is_installed_without_hiding_public_machine_panel():
    assert gui_maszyny._WM_ROOM_EXTENSION_INSTALLED is True
    assert callable(gui_maszyny.panel_maszyny)
    assert callable(gui_maszyny.open_machine_usage)
    assert hasattr(gui_maszyny.MachineHallRenderer, "_draw_rooms")
    assert hasattr(gui_maszyny.MachineHallRenderer, "_toggle_layout_edit")


def test_machine_status_helpers_still_use_same_module_globals(monkeypatch):
    monkeypatch.setattr(
        gui_maszyny,
        "_machine_now_iso",
        lambda: "2026-08-31T12:00:00",
    )
    machine = {"status": "sprawna"}

    changed = gui_maszyny._apply_machine_status_change(
        machine,
        "ok",
        actor="test",
        note="",
    )

    assert changed is False
    assert machine["status"] == "ok"
    assert machine["status_current"]["started_at"] == "2026-08-31T12:00:00"
