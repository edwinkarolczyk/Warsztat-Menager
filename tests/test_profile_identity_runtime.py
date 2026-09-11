from __future__ import annotations

import json

import profile_identity_runtime as identity
from services import attendance_service, feedback_service, leave_workflow_service


def test_backfill_user_identity_preserves_legacy_login_records(tmp_path, monkeypatch):
    attendance_path = tmp_path / "ewidencja_obecnosci.json"
    attendance_audit = tmp_path / "ewidencja_obecnosci_audit.json"
    feedback_path = tmp_path / "opinie.json"
    leaves_path = tmp_path / "leaves.json"
    requests_path = tmp_path / "leave_requests.json"
    data_root = tmp_path / "data"
    data_root.mkdir()
    profile_audit = data_root / "profile_admin_audit.json"

    attendance_path.write_text(
        json.dumps(
            {
                "2026-09-01": {
                    "RANO": {
                        "jan": {
                            "planned": True,
                            "login_snapshot": "jan",
                        }
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    attendance_audit.write_text(
        json.dumps([{"login_snapshot": "jan", "action": "manual_day"}]),
        encoding="utf-8",
    )
    feedback_path.write_text(
        json.dumps([{"login": "jan", "message": "opinia"}]),
        encoding="utf-8",
    )
    leaves_path.write_text(
        json.dumps([{"login": "jan", "type": "l4", "date": "2026-09-01"}]),
        encoding="utf-8",
    )
    requests_path.write_text(
        json.dumps([{"login_snapshot": "jan", "status": "pending"}]),
        encoding="utf-8",
    )
    profile_audit.write_text(
        json.dumps([{"login": "jan", "action": "profil"}]),
        encoding="utf-8",
    )

    monkeypatch.setattr(attendance_service, "data_path", lambda: attendance_path)
    monkeypatch.setattr(attendance_service, "audit_path", lambda: attendance_audit)
    monkeypatch.setattr(feedback_service, "feedback_path", lambda: feedback_path)
    monkeypatch.setattr(leave_workflow_service, "leaves_path", lambda: leaves_path)
    monkeypatch.setattr(leave_workflow_service, "requests_path", lambda: requests_path)
    monkeypatch.setattr("core.root_paths.get_data_root", lambda: data_root)

    identity.backfill_user_identity("jan", "USR-0042")

    attendance = json.loads(attendance_path.read_text(encoding="utf-8"))
    rec = attendance["2026-09-01"]["RANO"]["jan"]
    assert rec["user_id"] == "USR-0042"
    assert rec["login_snapshot"] == "jan"

    attendance_history = json.loads(attendance_audit.read_text(encoding="utf-8"))
    assert attendance_history[0]["user_id"] == "USR-0042"

    feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
    assert feedback[0]["user_id"] == "USR-0042"
    assert feedback[0]["login"] == "jan"

    leaves = json.loads(leaves_path.read_text(encoding="utf-8"))
    assert leaves[0]["user_id"] == "USR-0042"

    requests = json.loads(requests_path.read_text(encoding="utf-8"))
    assert requests[0]["user_id"] == "USR-0042"

    admin_history = json.loads(profile_audit.read_text(encoding="utf-8"))
    assert admin_history[0]["user_id"] == "USR-0042"


def test_existing_user_id_is_never_overwritten():
    row = {"login": "jan", "user_id": "USR-9999"}
    changed = identity._stamp_row(row, "jan", "USR-0042")
    assert changed is False
    assert row["user_id"] == "USR-9999"
