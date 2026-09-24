"""WM window/tray and WMM API lifetime; no Windows session needed."""
from pathlib import Path

from services.wm_tray_runtime import WmTrayRuntime


class FakeRoot:
    def __init__(self):
        self.jobs = {}
        self.protocols = {}
        self.withdrawn = False
        self.destroyed = False
        self.restored = False

    def protocol(self, name, callback):
        self.protocols[name] = callback

    def after(self, delay, callback):
        ident = f"job-{len(self.jobs) + 1}"
        self.jobs[ident] = (delay, callback)
        return ident

    def after_cancel(self, ident):
        self.jobs.pop(ident, None)

    def withdraw(self):
        self.withdrawn = True

    def deiconify(self):
        self.withdrawn = False
        self.restored = True

    def lift(self):
        pass

    def focus_force(self):
        pass

    def destroy(self):
        self.destroyed = True


class FakeIcon:
    def __init__(self, on_show, on_exit):
        self.on_show = on_show
        self.on_exit = on_exit
        self.started = False
        self.stopped = False
        self.notices = []

    def run_detached(self):
        self.started = True

    def notify(self, body, title):
        self.notices.append((body, title))

    def stop(self):
        self.stopped = True


def make_runtime(root, users=None, *, api_ok=True):
    users = users if users is not None else []
    events = []
    icons = []

    def factory(show, exit_app):
        icon = FakeIcon(show, exit_app)
        icons.append(icon)
        return icon

    runtime = WmTrayRuntime(
        root, api_start=lambda: events.append("start") or api_ok,
        api_stop=lambda: events.append("stop"),
        status_provider=lambda: {"users": list(users)},
        icon_factory=factory,
        on_exit=lambda: events.append("extra"),
    )
    return runtime, events, icons


def test_close_hides_without_stopping_wmm_and_tray_exit_stops_once():
    root = FakeRoot()
    runtime, events, icons = make_runtime(root)
    runtime.install()
    assert events == ["start"]
    assert icons[0].started
    root.protocols["WM_DELETE_WINDOW"]()
    assert root.withdrawn
    assert not root.destroyed
    assert events == ["start"]

    icons[0].on_show()
    runtime._tick()
    assert root.restored and not root.withdrawn
    root.protocols["WM_DELETE_WINDOW"]()
    icons[0].on_exit()
    runtime._tick()
    assert events == ["start", "stop", "extra"]
    assert root.destroyed and icons[0].stopped
    runtime.shutdown()
    assert events == ["start", "stop", "extra"]


def test_notify_only_on_new_named_connection_and_after_reconnection():
    root = FakeRoot()
    users = []
    runtime, _events, icons = make_runtime(root, users)
    runtime.install()
    runtime._presence_tick()
    users[:] = [{"user_id": "wmm-mobile", "name": "WMM Mobile BETA"}]
    runtime._presence_tick()
    assert not icons[0].notices

    users[:] = [{"user_id": "USR-1", "login": "Marek", "name": "Marek Kowalski"}]
    runtime._presence_tick()
    runtime._presence_tick()
    assert sum("Marek Kowalski" in notice[0] for notice in icons[0].notices) == 1
    users[:] = []
    runtime._presence_tick()
    users[:] = [{"user_id": "USR-1", "login": "Marek", "name": "Marek Kowalski"}]
    runtime._presence_tick()
    assert sum("Marek Kowalski" in notice[0] for notice in icons[0].notices) == 2
    runtime.shutdown()


def test_missing_tray_never_leaves_invisible_window_running():
    root = FakeRoot()
    runtime = WmTrayRuntime(
        root,
        api_start=lambda: True,
        api_stop=lambda: None,
        status_provider=lambda: {"users": []},
        icon_factory=lambda *_args: (_ for _ in ()).throw(RuntimeError("brak ikony")),
    )
    runtime.install()
    assert runtime.icon is None
    root.protocols["WM_DELETE_WINDOW"]()
    assert not root.withdrawn
    assert root.destroyed


def test_failed_api_is_not_misreported_as_started_or_stopped():
    root = FakeRoot()
    runtime, events, _icons = make_runtime(root, api_ok=False)
    runtime.install()
    assert not runtime.api_started
    runtime.exit_app()
    assert events == ["start", "extra"]


def test_start_and_footer_use_separate_hide_and_explicit_exit_paths():
    start = Path("start.py").read_text(encoding="utf-8")
    panel = Path("gui_panel.py").read_text(encoding="utf-8")
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    assert "install_wm_background(root)" in start
    assert "wm_background.shutdown()" in start
    assert 'getattr(root, "_wm_exit_app", root.quit)()' in panel
    assert "pystray" in requirements
