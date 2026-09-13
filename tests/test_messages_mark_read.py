from __future__ import annotations

import json

from services import messages_service


def _write_mailbox(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_mark_read_writes_only_when_value_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(messages_service, "BASE_DIR", str(tmp_path))
    mailbox = tmp_path / "edwin.jsonl"
    _write_mailbox(
        mailbox,
        [{"id": "msg-1", "folder": "inbox", "read": False}],
    )
    replacements = []
    original_replace = messages_service.os.replace

    def replace(source, target):
        replacements.append((source, target))
        original_replace(source, target)

    monkeypatch.setattr(messages_service.os, "replace", replace)

    assert messages_service.mark_read("edwin", "msg-1") is True
    assert len(replacements) == 1
    assert json.loads(mailbox.read_text(encoding="utf-8"))["read"] is True

    assert messages_service.mark_read("edwin", "msg-1") is False
    assert len(replacements) == 1


def test_mark_read_does_not_create_mailbox_for_unknown_message(tmp_path, monkeypatch):
    monkeypatch.setattr(messages_service, "BASE_DIR", str(tmp_path))

    assert messages_service.mark_read("edwin", "missing") is False
    assert not (tmp_path / "edwin.jsonl").exists()
