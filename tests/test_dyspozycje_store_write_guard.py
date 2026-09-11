from concurrent.futures import ThreadPoolExecutor
import json
import threading

import pytest

import dyspozycje_store as store


def _use_test_path(monkeypatch, tmp_path):
    path = tmp_path / "dyspozycje.json"
    monkeypatch.setattr(store, "_active_dyspozycje_path", lambda: path)
    monkeypatch.setattr(
        store,
        "_migrate_legacy_if_needed",
        lambda _path: None,
    )
    return path


def test_concurrent_additions_do_not_lose_records(monkeypatch, tmp_path):
    path = _use_test_path(monkeypatch, tmp_path)
    workers = 16
    start = threading.Barrier(workers)

    def add_one(index):
        record = store.make_dyspozycja(
            typ_dyspozycji="narzedzie",
            tytul=f"Równoległa {index}",
            autor="test",
        )
        start.wait(timeout=5)
        return store.add_dyspozycja(record)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(add_one, range(workers)))

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert len(raw["items"]) == workers
    assert {row["id"] for row in raw["items"]} == {
        row["id"] for row in results
    }


def test_failed_atomic_replace_keeps_previous_json(monkeypatch, tmp_path):
    path = _use_test_path(monkeypatch, tmp_path)
    first = store.make_dyspozycja(
        typ_dyspozycji="maszyna",
        tytul="Pierwsza",
    )
    second = store.make_dyspozycja(
        typ_dyspozycji="maszyna",
        tytul="Druga",
    )
    store.save_dyspozycje([first])

    original = json.loads(path.read_text(encoding="utf-8"))

    def fail_replace(_src, _dst):
        raise OSError("symulowany błąd replace")

    monkeypatch.setattr(store.os, "replace", fail_replace)
    with pytest.raises(OSError, match="symulowany błąd replace"):
        store.save_dyspozycje([second])

    after = json.loads(path.read_text(encoding="utf-8"))
    assert after == original
    assert not list(tmp_path.glob(".dyspozycje.json.*.tmp"))
