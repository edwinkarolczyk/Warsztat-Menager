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
