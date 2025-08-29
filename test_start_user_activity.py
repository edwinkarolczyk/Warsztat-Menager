import pytest
import tkinter as tk

import start


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    r.withdraw()
    yield r
    r.destroy()


def test_monitor_triggers_logout(root):
    called = []

    def fake_logout():
        called.append(True)

    start.monitor_user_activity(root, timeout_sec=1, callback=fake_logout)
    root.after(1200, root.quit)
    root.mainloop()
    assert called


def test_monitor_resets_on_activity(root):
    called = []

    def fake_logout():
        called.append(True)

    start.monitor_user_activity(root, timeout_sec=1, callback=fake_logout)
    root.after(500, lambda: root.event_generate("<Motion>"))
    root.after(900, root.quit)
    root.mainloop()
    assert not called


def test_monitor_restart(root):
    called = []

    def fake_logout():
        called.append(True)

    start.monitor_user_activity(root, timeout_sec=5, callback=fake_logout)
    start.restart_user_activity_monitor(1)
    root.after(1200, root.quit)
    root.mainloop()
    assert called

