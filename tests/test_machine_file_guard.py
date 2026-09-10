from __future__ import annotations

import json
import threading
import time

from machine_file_guard import machine_file_lock


def test_machine_file_lock_serializes_threads(tmp_path):
    target = tmp_path / "data" / "maszyny" / "maszyny.json"
    entered: list[str] = []

    def worker() -> None:
        with machine_file_lock(target, timeout=2.0, poll_interval=0.01):
            entered.append("worker")

    with machine_file_lock(target):
        thread = threading.Thread(target=worker)
        thread.start()
        time.sleep(0.1)
        assert entered == []

    thread.join(timeout=2.0)
    assert entered == ["worker"]
    assert target.with_name("maszyny.json.lock").is_file()


def test_wmm_machine_update_keeps_existing_document_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("WM_ROOT", str(tmp_path))
    target = tmp_path / "data" / "maszyny" / "maszyny.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "maszyny": [
                    {"id": "42", "nazwa": "Prasa", "status": "ok"},
                    {"id": "43", "nazwa": "Zgrzewarka", "status": "ok"},
                ],
                "meta": {"source": "test"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    from services import wmm_api

    result = wmm_api._update_machine(
        "42", lambda row: row.__setitem__("status", "warn")
    )

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert result["status"] == "warn"
    assert saved["meta"] == {"source": "test"}
    assert saved["maszyny"][0]["status"] == "warn"
    assert saved["maszyny"][1]["status"] == "ok"
