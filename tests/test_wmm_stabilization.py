from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest


def _prepare_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "wm-root"
    (root / "data").mkdir(parents=True)
    monkeypatch.setenv("WM_ROOT", str(root))
    monkeypatch.setenv("WM_DATA_ROOT", str(root / "data"))
    return root


def test_wmm_root_refuses_silent_cwd_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("WM_ROOT", raising=False)
    monkeypatch.delenv("WM_DATA_ROOT", raising=False)

    from core import root_paths
    from services import wmm_api

    monkeypatch.setattr(root_paths, "root_file_path", lambda: tmp_path / "missing.json")

    with pytest.raises(RuntimeError, match="Brak poprawnego WM_ROOT"):
        wmm_api._root_dir()


def test_wmm_media_route_accepts_stored_photo_url(tmp_path, monkeypatch):
    root = _prepare_root(tmp_path, monkeypatch)
    target = root / "data" / "maszyny" / "attachments" / "42" / "photo.jpg"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"photo")

    from services import wmm_api

    handler = object.__new__(wmm_api._WmmHandler)
    handler.path = "/api/v1/media/machines/42/photo.jpg"
    sent: list[Path] = []
    errors: list[tuple[int, dict]] = []
    handler._require_pairing_key = lambda: True
    handler._send_file = lambda path: sent.append(Path(path))
    handler._send = lambda status, payload: errors.append((status, payload))

    handler.do_GET()

    assert errors == []
    assert sent == [target]


def test_wmm_photo_for_missing_tool_does_not_create_orphan_file(tmp_path, monkeypatch):
    root = _prepare_root(tmp_path, monkeypatch)

    from services import wmm_api

    handler = object.__new__(wmm_api._WmmHandler)
    handler.path = "/api/v1/tools/missing/photos"
    handler._require_pairing_key = lambda: True
    handler._author = lambda: "Edwin"
    handler._request_id = lambda: ""
    handler._read_multipart_photo = lambda: ("photo.jpg", b"photo")
    responses = []
    handler._send = lambda status, payload: responses.append((status, payload))

    handler.do_POST()

    assert responses == [(400, {"ok": False, "error": "Nie znaleziono narzędzia."})]
    assert not (root / "data" / "narzedzia" / "attachments" / "missing").exists()


def test_wmm_photo_for_missing_machine_does_not_create_orphan_file(tmp_path, monkeypatch):
    root = _prepare_root(tmp_path, monkeypatch)
    machines = root / "data" / "maszyny"
    machines.mkdir()
    (machines / "maszyny.json").write_text("[]", encoding="utf-8")

    from services import wmm_api

    handler = object.__new__(wmm_api._WmmHandler)
    handler.path = "/api/v1/machines/missing/photos"
    handler._require_pairing_key = lambda: True
    handler._author = lambda: "Edwin"
    handler._request_id = lambda: ""
    handler._read_multipart_photo = lambda: ("photo.jpg", b"photo")
    responses = []
    handler._send = lambda status, payload: responses.append((status, payload))

    handler.do_POST()

    assert responses == [(400, {"ok": False, "error": "Nie znaleziono maszyny."})]
    assert not (machines / "attachments" / "missing").exists()


def test_wmm_concurrent_order_create_uses_distinct_ids(tmp_path, monkeypatch):
    root = _prepare_root(tmp_path, monkeypatch)
    products = root / "data" / "produkty"
    orders = root / "data" / "zlecenia"
    products.mkdir(parents=True)
    orders.mkdir(parents=True)
    (products / "P1.json").write_text(
        json.dumps({"kod": "P1", "nazwa": "Produkt testowy"}, ensure_ascii=False),
        encoding="utf-8",
    )

    from services import wmm_api

    results: list[str] = []
    errors: list[Exception] = []

    def worker() -> None:
        try:
            item = wmm_api._create_planista_order(
                {"product_code": "P1", "quantity": 1},
                "test",
            )
            results.append(str(item["id"]))
        except Exception as exc:  # pragma: no cover - diagnoza testu
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3.0)

    assert errors == []
    assert sorted(results) == ["000001", "000002"]
    assert (orders / "000001.json").is_file()
    assert (orders / "000002.json").is_file()


def test_wmm_concurrent_tool_updates_keep_both_changes(tmp_path, monkeypatch):
    root = _prepare_root(tmp_path, monkeypatch)
    tools = root / "data" / "narzedzia"
    tools.mkdir(parents=True)
    target = tools / "001.json"
    target.write_text(
        json.dumps({"id": "001", "status": "dostępne"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    from services import wmm_api

    first_started = threading.Event()

    def mutate_first(row: dict) -> None:
        first_started.set()
        time.sleep(0.15)
        row["uwagi_a"] = "A"

    def mutate_second(row: dict) -> None:
        row["uwagi_b"] = "B"

    first = threading.Thread(target=lambda: wmm_api._update_tool("001", mutate_first))

    def second_worker() -> None:
        assert first_started.wait(timeout=1.0)
        wmm_api._update_tool("001", mutate_second)

    second = threading.Thread(target=second_worker)
    first.start()
    second.start()
    first.join(timeout=3.0)
    second.join(timeout=3.0)

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["uwagi_a"] == "A"
    assert saved["uwagi_b"] == "B"


def test_wmm_idempotency_replays_success_without_second_write(tmp_path, monkeypatch):
    from services import wmm_api

    monkeypatch.setattr(wmm_api, "_idempotency_path", lambda: tmp_path / "ledger.json")
    monkeypatch.setattr(wmm_api, "_IDEMPOTENCY_LOADED_PATH", None)
    with wmm_api._IDEMPOTENCY_LOCK:
        wmm_api._IDEMPOTENCY_CACHE.clear()

    calls: list[int] = []

    def operation() -> dict:
        calls.append(1)
        return {"id": "001", "status": "Do naprawy"}

    first_replayed, first = wmm_api._run_idempotent(
        "wmm-test-request-001", "/api/v1/tools/001/status", operation
    )
    second_replayed, second = wmm_api._run_idempotent(
        "wmm-test-request-001", "/api/v1/tools/001/status", operation
    )

    assert first_replayed is False
    assert second_replayed is True
    assert first == second
    assert calls == [1]


def test_wmm_idempotency_same_request_id_is_scoped_by_endpoint(tmp_path, monkeypatch):
    from services import wmm_api

    monkeypatch.setattr(wmm_api, "_idempotency_path", lambda: tmp_path / "ledger.json")
    monkeypatch.setattr(wmm_api, "_IDEMPOTENCY_LOADED_PATH", None)
    with wmm_api._IDEMPOTENCY_LOCK:
        wmm_api._IDEMPOTENCY_CACHE.clear()

    calls: list[str] = []

    def first() -> dict:
        calls.append("tool")
        return {"id": "001"}

    def second() -> dict:
        calls.append("machine")
        return {"id": "42"}

    wmm_api._run_idempotent("wmm-shared-request", "/api/v1/tools/001/status", first)
    wmm_api._run_idempotent("wmm-shared-request", "/api/v1/machines/42/status", second)

    assert calls == ["tool", "machine"]


def test_wmm_idempotency_survives_api_restart(tmp_path, monkeypatch):
    from services import wmm_api as api

    monkeypatch.setattr(api, "_idempotency_path", lambda: tmp_path / "ledger.json")
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    api._IDEMPOTENCY_CACHE.clear()
    calls = []

    def operation():
        calls.append(1)
        return {"id": "001", "status": "Do naprawy"}

    first, row = api._run_idempotent(
        "restart-case-001", "/api/v1/tools/001/status", operation, "payload-a"
    )
    assert first is False
    assert row["status"] == "Do naprawy"
    assert (tmp_path / "ledger.json").is_file()

    # Symulacja nowego procesu API po utracie odpowiedzi HTTP.
    api._IDEMPOTENCY_CACHE.clear()
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    replayed, restored = api._run_idempotent(
        "restart-case-001", "/api/v1/tools/001/status", operation, "payload-a"
    )
    assert replayed is True
    assert restored == row
    assert calls == [1]


def test_wmm_pending_after_crash_is_not_reexecuted(tmp_path, monkeypatch):
    from services import wmm_api as api

    monkeypatch.setattr(api, "_idempotency_path", lambda: tmp_path / "ledger.json")
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    api._IDEMPOTENCY_CACHE.clear()
    calls = []

    def interrupted():
        calls.append(1)
        raise RuntimeError("Odpowiedź zgubiona po wykonaniu mutacji")

    with pytest.raises(RuntimeError, match="Odpowiedź"):
        api._run_idempotent("pending-case-001", "/api/v1/tools/001/photos",
                            interrupted, "photo-a")
    api._IDEMPOTENCY_CACHE.clear()
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    with pytest.raises(api.WmmIdempotencyPending, match="Niepewny"):
        api._run_idempotent("pending-case-001", "/api/v1/tools/001/photos",
                            interrupted, "photo-a")
    assert calls == [1]


def test_wmm_revision_rejects_stale_machine_and_tool_changes():
    from services import wmm_api as api

    original = {"status": "ok", "historia": []}
    snapshot = api._wmm_revision_item(original)["wmm_revision"]
    api._wmm_expect_revision(original, snapshot)
    original["status"] = "warn"
    with pytest.raises(api.WmmRevisionConflict, match="Odśwież"):
        api._wmm_expect_revision(original, snapshot)
    assert api._wmm_revision(original) == api._wmm_revision({**original, "photos": []})


def test_wmm_request_id_different_payload_does_not_replay(tmp_path, monkeypatch):
    from services import wmm_api as api

    monkeypatch.setattr(api, "_idempotency_path", lambda: tmp_path / "ledger.json")
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    api._IDEMPOTENCY_CACHE.clear()
    api._run_idempotent("payload-case-001", "/api/v1/tools/001/status",
                        lambda: {"id": "001"}, "payload-a")
    with pytest.raises(api.WmmIdempotencyConflict, match="innymi danymi"):
        api._run_idempotent("payload-case-001", "/api/v1/tools/001/status",
                            lambda: {"id": "001"}, "payload-b")


def test_wmm_two_phones_stale_machine_write_cannot_overwrite(tmp_path, monkeypatch):
    root = _prepare_root(tmp_path, monkeypatch)
    target = root / "data" / "maszyny" / "maszyny.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps([{"id": "42", "status": "ok", "historia": []}]),
                      encoding="utf-8")

    from services import wmm_api as api

    revision = api._wmm_revision(api._find_machine("42"))

    def first_phone(row):
        api._wmm_expect_revision(row, revision)
        row["status"] = "warn"
        row["historia"].append({"action": "status_changed", "by": "Marek"})

    api._update_machine("42", first_phone)

    def second_phone(row):
        api._wmm_expect_revision(row, revision)
        row["status"] = "alert"

    with pytest.raises(api.WmmRevisionConflict, match="Odśwież"):
        api._update_machine("42", second_phone)

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved[0]["status"] == "warn"
    assert len(saved[0]["historia"]) == 1


def test_wmm_two_phones_stale_machine_note_cannot_overwrite(tmp_path, monkeypatch):
    root = _prepare_root(tmp_path, monkeypatch)
    target = root / "data" / "maszyny" / "maszyny.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps([{"id": "42", "status": "ok", "uwagi": "", "historia": []}]),
        encoding="utf-8",
    )

    from services import wmm_api as api

    revision = api._wmm_revision(api._find_machine("42"))

    def send_note(note):
        handler = object.__new__(api._WmmHandler)
        handler.path = "/api/v1/machines/42/note"
        handler._read_json = lambda: {"note": note, "base_revision": revision}
        handler._require_pairing_key = lambda: True
        handler._author = lambda: "Edwin"
        handler._request_id = lambda: ""
        responses = []
        handler._send = lambda status, payload: responses.append((status, payload))
        handler.do_POST()
        return responses

    assert send_note("Pierwsza uwaga")[0][0] == 200
    stale_response = send_note("Nieaktualna uwaga")

    assert stale_response[0][0] == 409
    assert stale_response[0][1]["code"] == "WMM_REVISION_CONFLICT"
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved[0]["uwagi"] == "Pierwsza uwaga"
    assert len(saved[0]["historia"]) == 1


def test_wmm_two_phones_stale_tool_write_cannot_overwrite(tmp_path, monkeypatch):
    root = _prepare_root(tmp_path, monkeypatch)
    target = root / "data" / "narzedzia" / "001.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps({"id": "001", "status": "Dostępne", "historia": []}),
        encoding="utf-8",
    )

    from services import wmm_api as api

    revision = api._wmm_revision(api._find_tool("001"))

    def first_phone(row):
        api._wmm_expect_revision(row, revision)
        row["status"] = "Do naprawy"

    api._update_tool("001", first_phone)

    def second_phone(row):
        api._wmm_expect_revision(row, revision)
        row["status"] = "Do ostrzenia"

    with pytest.raises(api.WmmRevisionConflict, match="Odśwież"):
        api._update_tool("001", second_phone)

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["status"] == "Do naprawy"


@pytest.mark.parametrize(
    "route,folder,filename,initial,mutation",
    [
        ("/api/v1/machines/42/note", "maszyny", "maszyny.json",
         [{"id": "42", "status": "ok", "uwagi": "Pierwsza", "historia": []}],
         {"note": "Druga"}),
        ("/api/v1/machines/42/status", "maszyny", "maszyny.json",
         [{"id": "42", "status": "ok", "historia": []}],
         {"status": "warn"}),
        ("/api/v1/tools/001/status", "narzedzia", "001.json",
         {"id": "001", "status": "Dostępne", "historia": []},
         {"status": "Do naprawy"}),
    ],
)
def test_wmm_mutation_without_revision_cannot_write(
    tmp_path, monkeypatch, route, folder, filename, initial, mutation
):
    root = _prepare_root(tmp_path, monkeypatch)
    target = root / "data" / folder / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(initial, ensure_ascii=False), encoding="utf-8")
    before = target.read_bytes()

    from services import wmm_api as api

    handler = object.__new__(api._WmmHandler)
    handler.path = route
    handler._read_json = lambda: mutation
    handler._require_pairing_key = lambda: True
    handler._author = lambda: "Edwin"
    handler._request_id = lambda: ""
    responses = []
    handler._send = lambda status, payload: responses.append((status, payload))
    handler.do_POST()

    assert responses[0][0] == 409
    assert responses[0][1]["code"] == "WMM_REVISION_CONFLICT"
    assert "Odśwież" in responses[0][1]["error"]
    assert target.read_bytes() == before


def test_wmm_pending_note_after_crash_reconciles_without_duplicate(tmp_path, monkeypatch):
    root = _prepare_root(tmp_path, monkeypatch)
    target = root / "data" / "maszyny" / "maszyny.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps([{"id": "42", "status": "ok", "uwagi": "", "historia": []}]),
        encoding="utf-8",
    )
    from services import wmm_api as api

    monkeypatch.setattr(api, "_idempotency_path", lambda: tmp_path / "ledger.json")
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    api._IDEMPOTENCY_CACHE.clear()
    request_id = "wmm-note-reconcile-001"
    path = "/api/v1/machines/42/note"
    calls = []

    def operation():
        calls.append(1)

        def mutate(row):
            row["uwagi"] = "Test po restarcie"
            api._append_history(row, "uwaga", "Edwin", "Test po restarcie")
            api._wmm_mark_applied(row, request_id, path)

        updated = api._update_machine("42", mutate)
        if len(calls) == 1:
            raise RuntimeError("Awaria po zapisaniu karty WM, przed done")
        return updated

    with pytest.raises(RuntimeError, match="Awaria"):
        api._run_idempotent(request_id, path, operation, "note-fingerprint")
    api._IDEMPOTENCY_CACHE.clear()
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    replayed, result = api._run_idempotent(
        request_id, path, operation, "note-fingerprint"
    )

    assert replayed is True
    assert len(calls) == 1
    assert result["uwagi"] == "Test po restarcie"
    persisted = json.loads(target.read_text(encoding="utf-8"))[0]
    assert len(persisted["historia"]) == 1


def test_wmm_pending_photo_reconciles_and_orphan_uses_same_path(tmp_path, monkeypatch):
    root = _prepare_root(tmp_path, monkeypatch)
    target = root / "data" / "maszyny" / "maszyny.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps([{"id": "42", "status": "ok", "photos": [], "historia": []}]),
        encoding="utf-8",
    )
    from services import wmm_api as api
    import hashlib

    monkeypatch.setattr(api, "_idempotency_path", lambda: tmp_path / "ledger.json")
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    api._IDEMPOTENCY_CACHE.clear()
    request_id = "wmm-photo-reconcile-001"
    path = "/api/v1/machines/42/photos"
    data = b"fake photo bytes"
    photo_sha = hashlib.sha256(data).hexdigest()
    calls = []

    def operation():
        calls.append(1)

        def mutate(row):
            photo = api._store_photo(
                "machines", "42", "photo.jpg", data, "Edwin",
                request_id=request_id, photo_sha256=photo_sha,
            )
            row["photos"].append(photo)
            api._append_history(row, "zdjęcie", "Edwin", photo["name"])
            api._wmm_mark_applied(row, request_id, path)

        updated = api._update_machine("42", mutate)
        if len(calls) == 1:
            raise RuntimeError("Awaria przed done")
        return updated

    with pytest.raises(RuntimeError, match="Awaria"):
        api._run_idempotent(request_id, path, operation, photo_sha)
    api._IDEMPOTENCY_CACHE.clear()
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    replayed, row = api._run_idempotent(request_id, path, operation, photo_sha)
    assert replayed is True
    assert len(calls) == 1
    assert len(row["photos"]) == 1
    assert len(row["historia"]) == 1
    assert row["photos"][0]["sha256"] == photo_sha
    assert len(list((root / "data" / "maszyny" / "attachments" / "42").glob("*.jpg"))) == 1


def test_wmm_pending_photo_before_card_write_can_retry_without_orphan(tmp_path, monkeypatch):
    root = _prepare_root(tmp_path, monkeypatch)
    target = root / "data" / "narzedzia" / "001.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"id": "001", "photos": [], "historia": []}),
                      encoding="utf-8")
    from services import wmm_api as api

    monkeypatch.setattr(api, "_idempotency_path", lambda: tmp_path / "ledger.json")
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    api._IDEMPOTENCY_CACHE.clear()
    request_id = "wmm-tool-orphan-001"
    path = "/api/v1/tools/001/photos"
    calls = []

    def operation():
        calls.append(1)
        if len(calls) == 1:
            api._store_photo(
                "tools", "001", "photo.jpg", b"photo bytes", "Edwin",
                request_id=request_id,
            )
            raise RuntimeError("Awaria przed zapisaniem metadanych")

        def mutate(row):
            photo = api._store_photo(
                "tools", "001", "photo.jpg", b"photo bytes", "Edwin",
                request_id=request_id,
            )
            row["photos"].append(photo)
            api._wmm_mark_applied(row, request_id, path)

        return api._update_tool("001", mutate)

    with pytest.raises(RuntimeError, match="Awaria"):
        api._run_idempotent(request_id, path, operation, "same-file")
    api._IDEMPOTENCY_CACHE.clear()
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    replayed, row = api._run_idempotent(request_id, path, operation, "same-file")
    assert replayed is False
    assert len(calls) == 2
    assert len(row["photos"]) == 1
    assert len(list((root / "data" / "narzedzia" / "attachments" / "001").glob("*.jpg"))) == 1
