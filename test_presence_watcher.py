import presence
import presence_watcher


class DummyRoot:
    def __init__(self, exc=None):
        self.after_calls = []
        self.exc = exc

    def after(self, ms, func):
        self.after_calls.append(ms)
        if self.exc:
            raise self.exc


def test_start_heartbeat_success(monkeypatch):
    root = DummyRoot()
    called = []
    monkeypatch.setattr(presence, "heartbeat", lambda *a, **k: called.append(True))
    monkeypatch.setattr(presence.atexit, "register", lambda f: None)
    logs = []
    monkeypatch.setattr(presence, "log_akcja", lambda m: logs.append(m))

    presence.start_heartbeat(root, "jan")

    assert called and called[0]
    assert root.after_calls
    assert not logs


def test_start_heartbeat_failure_logs(monkeypatch):
    root = DummyRoot()

    def fail(*a, **k):
        raise OSError("disk error")

    monkeypatch.setattr(presence, "heartbeat", fail)
    monkeypatch.setattr(presence.atexit, "register", lambda f: None)
    logs = []
    monkeypatch.setattr(presence, "log_akcja", lambda m: logs.append(m))

    presence.start_heartbeat(root, "jan")

    assert any("heartbeat error" in m for m in logs)
    assert root.after_calls


def test_schedule_watcher_success(monkeypatch):
    root = DummyRoot()
    monkeypatch.setattr(presence_watcher, "run_check", lambda: 0)
    logs = []
    monkeypatch.setattr(presence_watcher, "log_akcja", lambda m: logs.append(m))

    presence_watcher.schedule_watcher(root)

    assert root.after_calls
    assert not logs


def test_schedule_watcher_failure_logs(monkeypatch):
    root = DummyRoot()

    def fail():
        raise ValueError("bad value")

    monkeypatch.setattr(presence_watcher, "run_check", fail)
    logs = []
    monkeypatch.setattr(presence_watcher, "log_akcja", lambda m: logs.append(m))

    presence_watcher.schedule_watcher(root)

    assert any("watcher error" in m for m in logs)
    assert root.after_calls
