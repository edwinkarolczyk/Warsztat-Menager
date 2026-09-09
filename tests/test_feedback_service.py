from __future__ import annotations

import json

from services import feedback_service as feedback


def test_legacy_feedback_is_normalized_and_can_be_managed(tmp_path, monkeypatch):
    path = tmp_path / "opinie.json"
    path.write_text(
        json.dumps([
            {
                "login": "Edwin",
                "rola": "brygadzista",
                "ts": "2026-09-04T07:26:36",
                "message": "Test opinii",
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(feedback, "feedback_path", lambda: path)
    monkeypatch.setattr(feedback, "get_user", lambda _login: {"user_id": "USR-0001", "rola": "brygadzista"})

    rows = feedback.list_feedback()
    assert len(rows) == 1
    assert rows[0]["id"].startswith("OPN-")
    assert rows[0]["user_id"] == "USR-0001"
    assert rows[0]["status"] == "nowa"

    updated = feedback.update_feedback(
        rows[0]["id"],
        status="w_realizacji",
        module="Profile",
        actor="Edwin",
    )
    assert updated["status"] == "w_realizacji"
    assert updated["module"] == "Profile"
    assert updated["handled_by"] == "Edwin"

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored[0]["status"] == "w_realizacji"
    assert stored[0]["module"] == "Profile"
