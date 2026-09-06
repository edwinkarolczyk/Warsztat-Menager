from __future__ import annotations

import json
from datetime import datetime

import pytest

from services import attendance_service as attendance
from services import leave_workflow_service


def test_attendance_time_rules_without_lateness():
    assert attendance.classify_login("RANO", datetime(2026, 9, 4, 5, 30)) == attendance.STATUS_PRESENT
    assert attendance.classify_login("RANO", datetime(2026, 9, 4, 11, 59)) == attendance.STATUS_PRESENT
    assert attendance.classify_login("RANO", datetime(2026, 9, 4, 12, 0)) == attendance.STATUS_PRESENT
    assert attendance.classify_login("RANO", datetime(2026, 9, 4, 12, 1)) == attendance.STATUS_PENDING_LATE
    assert attendance.classify_login("POPO", datetime(2026, 9, 4, 13, 30)) == attendance.STATUS_PRESENT
    assert attendance.classify_login("POPO", datetime(2026, 9, 4, 19, 59)) == attendance.STATUS_PRESENT
    assert attendance.classify_login("POPO", datetime(2026, 9, 4, 20, 0)) == attendance.STATUS_PRESENT
    assert attendance.classify_login("POPO", datetime(2026, 9, 4, 20, 1)) == attendance.STATUS_PENDING_LATE


def test_first_login_is_preserved_and_second_login_is_not_second_day(tmp_path, monkeypatch):
    path = tmp_path / "ewidencja.json"
    audit = tmp_path / "audit.json"
    monkeypatch.setattr(attendance, "data_path", lambda: path)
    monkeypatch.setattr(attendance, "audit_path", lambda: audit)
    monkeypatch.setattr(attendance, "_is_guest", lambda _login: False)
    monkeypatch.setattr(attendance, "_scheduled_slot", lambda _login, _moment, slot: slot)
    monkeypatch.setattr(attendance, "user_id_for", lambda _login: "USR-0001")

    attendance.mark_login("2026-09-04", "RANO", "jan", "2026-09-04T05:55:00")
    attendance.mark_login("2026-09-04", "RANO", "jan", "2026-09-04T09:15:00")

    doc = json.loads(path.read_text(encoding="utf-8"))
    rec = doc["2026-09-04"]["RANO"]["USR-0001"]
    assert rec["first_login_ts"] == "2026-09-04T05:55:00"
    assert rec["logged_ts"] == "2026-09-04T05:55:00"
    assert rec["last_login_ts"] == "2026-09-04T09:15:00"
    assert rec["login_count"] == 2
    assert rec["day_value"] == 1.0
    assert rec["status"] == attendance.STATUS_PRESENT


def test_very_late_login_needs_foreman(tmp_path, monkeypatch):
    path = tmp_path / "ewidencja.json"
    audit = tmp_path / "audit.json"
    monkeypatch.setattr(attendance, "data_path", lambda: path)
    monkeypatch.setattr(attendance, "audit_path", lambda: audit)
    monkeypatch.setattr(attendance, "_is_guest", lambda _login: False)
    monkeypatch.setattr(attendance, "_scheduled_slot", lambda _login, _moment, slot: slot)
    monkeypatch.setattr(attendance, "user_id_for", lambda _login: "USR-0001")

    attendance.mark_login("2026-09-04", "RANO", "jan", "2026-09-04T12:15:00")
    doc = json.loads(path.read_text(encoding="utf-8"))
    rec = doc["2026-09-04"]["RANO"]["USR-0001"]
    assert rec["status"] == attendance.STATUS_PENDING_LATE
    assert rec["day_value"] == 0.0
    assert rec["approval_required"] is True
    assert "late" not in rec
    assert "spoznienie" not in rec


def test_saturday_is_separate_overtime_candidate(tmp_path, monkeypatch):
    path = tmp_path / "ewidencja.json"
    audit = tmp_path / "audit.json"
    monkeypatch.setattr(attendance, "data_path", lambda: path)
    monkeypatch.setattr(attendance, "audit_path", lambda: audit)
    monkeypatch.setattr(attendance, "_is_guest", lambda _login: False)
    monkeypatch.setattr(attendance, "_scheduled_slot", lambda _login, _moment, slot: slot)
    monkeypatch.setattr(attendance, "user_id_for", lambda _login: "USR-0001")

    # 2026-09-05 = sobota
    attendance.mark_login("2026-09-05", "RANO", "jan", "2026-09-05T06:10:00")
    doc = json.loads(path.read_text(encoding="utf-8"))
    rec = doc["2026-09-05"]["RANO"]["USR-0001"]
    assert rec["status"] == attendance.STATUS_SATURDAY
    assert rec["day_value"] == 0.0
    assert rec["overtime"]["type"] == "sobota"
    assert rec["overtime"]["status"] == "pending"


def test_schedule_without_saved_record_becomes_missing_and_decision(tmp_path, monkeypatch):
    path = tmp_path / "ewidencja.json"
    audit = tmp_path / "audit.json"
    monkeypatch.setattr(attendance, "data_path", lambda: path)
    monkeypatch.setattr(attendance, "audit_path", lambda: audit)
    monkeypatch.setattr(attendance, "user_id_for", lambda _login: "USR-0001")
    monkeypatch.setattr(
        attendance,
        "_planned_slot_for_day",
        lambda _login, day: attendance.RANO if day.weekday() < 5 else None,
    )

    # Do 4 września są cztery zaplanowane dni robocze i nie ma żadnego zapisu
    # ewidencji. Po 12:00 każdy z nich ma być widoczny jako brak.
    now = datetime(2026, 9, 4, 12, 1)
    rows = attendance.month_records("jan", 2026, 9, now=now)
    missing = [row for row in rows if row["status"] == attendance.STATUS_MISSING]
    assert [row["date"] for row in missing] == [
        "2026-09-01",
        "2026-09-02",
        "2026-09-03",
        "2026-09-04",
    ]

    decisions = attendance.decision_records("jan", 2026, 9, now=now)
    assert [row["date"] for row in decisions] == [
        "2026-09-01",
        "2026-09-02",
        "2026-09-03",
        "2026-09-04",
    ]
    assert all(row["decision_label"] == "Brak logowania" for row in decisions)

    summary = attendance.summary_for_month("jan", 2026, 9, now=now)
    assert summary["missing"] == 4.0
    assert summary["pending"] == 4.0


def test_today_exactly_at_auto_boundary_is_not_missing_yet(tmp_path, monkeypatch):
    path = tmp_path / "ewidencja.json"
    monkeypatch.setattr(attendance, "data_path", lambda: path)
    monkeypatch.setattr(attendance, "user_id_for", lambda _login: "USR-0001")
    monkeypatch.setattr(
        attendance,
        "_planned_slot_for_day",
        lambda _login, day: attendance.RANO if day.weekday() < 5 else None,
    )

    now = datetime(2026, 9, 4, 12, 0)
    rows = attendance.month_records("jan", 2026, 9, now=now)
    today = next(row for row in rows if row["date"] == "2026-09-04")
    assert today["status"] == attendance.STATUS_PLANNED

    decisions = attendance.decision_records("jan", 2026, 9, now=now)
    assert "2026-09-04" not in {row["date"] for row in decisions}


def test_manual_day_accepts_zero_half_and_full_day(tmp_path, monkeypatch):
    path = tmp_path / "ewidencja.json"
    audit = tmp_path / "audit.json"
    monkeypatch.setattr(attendance, "data_path", lambda: path)
    monkeypatch.setattr(attendance, "audit_path", lambda: audit)
    monkeypatch.setattr(attendance, "user_id_for", lambda _login: "USR-0001")
    monkeypatch.setattr(
        attendance,
        "absence_conflict",
        lambda _date, _login: {"has_conflict": False, "reasons": [], "slot": ""},
    )

    for day, value in (("2026-09-07", 0.0), ("2026-09-08", 0.5), ("2026-09-09", 1.0)):
        rec = attendance.set_manual_day(day, "RANO", "jan", value, "brygadzista")
        assert rec["day_value"] == value
        assert rec["approval_required"] is False
        assert rec["status"] == (attendance.STATUS_PRESENT if value > 0 else attendance.STATUS_MISSING)


def test_supported_absence_reasons_are_persisted(tmp_path, monkeypatch):
    path = tmp_path / "ewidencja.json"
    audit = tmp_path / "audit.json"
    monkeypatch.setattr(attendance, "data_path", lambda: path)
    monkeypatch.setattr(attendance, "audit_path", lambda: audit)
    monkeypatch.setattr(attendance, "user_id_for", lambda _login: "USR-0001")

    cases = (
        ("2026-09-10", "L4", "L4"),
        ("2026-09-11", "NN", "NN"),
        ("2026-09-12", "UR", "UR"),
        ("2026-09-13", "UŻ", "UŻ"),
        ("2026-09-14", "SW", "ŚW"),
    )
    for day, entered, expected in cases:
        attendance.set_reason(day, "RANO", "jan", "brygadzista", entered, f"{day}T08:00:00")

    doc = json.loads(path.read_text(encoding="utf-8"))
    for day, _entered, expected in cases:
        rec = doc[day]["RANO"]["USR-0001"]
        assert rec["reason"] == expected
        assert rec["status"] == attendance.STATUS_EXCUSED
        assert rec["day_value"] == 0.0


def test_canonical_force_majeure_can_coexist_with_present_day(tmp_path, monkeypatch):
    path = tmp_path / "ewidencja.json"
    audit = tmp_path / "audit.json"
    monkeypatch.setattr(attendance, "data_path", lambda: path)
    monkeypatch.setattr(attendance, "audit_path", lambda: audit)
    monkeypatch.setattr(attendance, "user_id_for", lambda _login: "USR-0001")
    monkeypatch.setattr(
        leave_workflow_service,
        "active_absences_for_day",
        lambda _login, _day: [{"type": "ŚW"}],
    )

    cancelled = []
    monkeypatch.setattr(
        leave_workflow_service,
        "cancel_absences_for_day",
        lambda *args, **kwargs: cancelled.append((args, kwargs)),
    )

    conflict = attendance.absence_conflict("2026-09-15", "jan")
    assert conflict["has_conflict"] is False

    rec = attendance.set_manual_day("2026-09-15", "RANO", "jan", 1.0, "brygadzista")
    assert rec["day_value"] == 1.0
    assert rec["reason"] == ""
    assert cancelled == []


def test_l4_still_requires_explicit_replacement(tmp_path, monkeypatch):
    path = tmp_path / "ewidencja.json"
    audit = tmp_path / "audit.json"
    monkeypatch.setattr(attendance, "data_path", lambda: path)
    monkeypatch.setattr(attendance, "audit_path", lambda: audit)
    monkeypatch.setattr(attendance, "user_id_for", lambda _login: "USR-0001")
    monkeypatch.setattr(
        leave_workflow_service,
        "active_absences_for_day",
        lambda _login, _day: [{"type": "L4"}],
    )

    cancelled = []
    monkeypatch.setattr(
        leave_workflow_service,
        "cancel_absences_for_day",
        lambda *args, **kwargs: cancelled.append((args, kwargs)),
    )

    with pytest.raises(ValueError, match="potwierdź zastąpienie"):
        attendance.set_manual_day("2026-09-16", "RANO", "jan", 1.0, "brygadzista")

    rec = attendance.set_manual_day(
        "2026-09-16",
        "RANO",
        "jan",
        1.0,
        "brygadzista",
        replace_absence=True,
    )
    assert rec["day_value"] == 1.0
    assert rec["reason"] == ""
    assert len(cancelled) == 1


def test_manual_day_can_move_between_shifts_without_duplicate(tmp_path, monkeypatch):
    path = tmp_path / "ewidencja.json"
    audit = tmp_path / "audit.json"
    monkeypatch.setattr(attendance, "data_path", lambda: path)
    monkeypatch.setattr(attendance, "audit_path", lambda: audit)
    monkeypatch.setattr(attendance, "user_id_for", lambda _login: "USR-0001")
    monkeypatch.setattr(
        attendance,
        "absence_conflict",
        lambda _date, _login: {"has_conflict": False, "reasons": [], "slot": ""},
    )

    attendance.set_manual_day("2026-09-17", "RANO", "jan", 1.0, "brygadzista")
    moved = attendance.set_manual_day(
        "2026-09-17",
        "POPO",
        "jan",
        0.5,
        "brygadzista",
        original_slot="RANO",
    )

    doc = json.loads(path.read_text(encoding="utf-8"))
    assert "USR-0001" not in doc["2026-09-17"].get("RANO", {})
    assert doc["2026-09-17"]["POPO"]["USR-0001"]["day_value"] == 0.5
    assert moved["day_value"] == 0.5

    audit_rows = json.loads(audit.read_text(encoding="utf-8"))
    assert audit_rows[-1]["action"] == "manual_day_move"
    assert "RANO → POPO" in audit_rows[-1]["note"]
