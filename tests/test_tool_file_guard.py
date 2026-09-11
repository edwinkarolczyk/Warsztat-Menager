from concurrent.futures import ThreadPoolExecutor
import json
import threading
import time

from machine_file_guard import file_write_lock
import utils_json


def _tool_path(tmp_path, nr="001"):
    path = tmp_path / "data" / "narzedzia" / f"{nr}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_desktop_tool_write_waits_for_shared_file_lock(tmp_path):
    path = _tool_path(tmp_path)
    assert utils_json.safe_write_json(str(path), {"id": "001", "status": "sprawne"})

    started = threading.Event()

    def writer():
        started.set()
        return utils_json.safe_write_json(
            str(path), {"id": "001", "status": "do naprawy"}
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        with file_write_lock(path, label="Narzędzi"):
            future = pool.submit(writer)
            assert started.wait(timeout=2)
            time.sleep(0.1)
            assert not future.done()
        assert future.result(timeout=2) is True

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["status"] == "do naprawy"


def test_failed_atomic_tool_replace_keeps_previous_json(monkeypatch, tmp_path):
    path = _tool_path(tmp_path, "002")
    original = {"id": "002", "status": "sprawne"}
    assert utils_json.safe_write_json(str(path), original)

    def fail_replace(_src, _dst):
        raise OSError("symulowany błąd replace")

    monkeypatch.setattr(utils_json.os, "replace", fail_replace)
    assert not utils_json.safe_write_json(
        str(path), {"id": "002", "status": "uszkodzone"}
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == original
    assert not list(path.parent.glob(".002.json.*.tmp"))


def test_wmm_tool_update_uses_same_file_lock(monkeypatch, tmp_path):
    root = tmp_path / "wm"
    path = root / "data" / "narzedzia" / "003.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"id": "003", "nr": "003", "status": "sprawne"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("WM_ROOT", str(root))
    monkeypatch.setenv("WM_DATA_ROOT", str(root / "data"))

    from services import wmm_api as api

    started = threading.Event()

    def update_from_wmm():
        started.set()

        def mutate(row):
            row["status"] = "do ostrzenia"

        return api._update_tool("003", mutate)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with file_write_lock(path, label="Narzędzi"):
            future = pool.submit(update_from_wmm)
            assert started.wait(timeout=2)
            time.sleep(0.1)
            assert not future.done()
        result = future.result(timeout=2)

    assert result["status"] == "do ostrzenia"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["status"] == "do ostrzenia"
