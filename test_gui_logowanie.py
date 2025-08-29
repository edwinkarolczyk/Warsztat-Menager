import json
import types
import subprocess
import pytest
from config_manager import ConfigManager
import gui_logowanie


class DummyWidget:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
    def pack(self, *args, **kwargs):
        pass
    def place(self, *args, **kwargs):
        pass
    def config(self, **kwargs):
        self.kwargs.update(kwargs)
    configure = config
    def bind(self, *args, **kwargs):
        pass
    def destroy(self):
        pass
    def winfo_exists(self):
        return True
    def winfo_children(self):
        return []
    def delete(self, *args, **kwargs):
        pass
    def create_rectangle(self, *args, **kwargs):
        pass


class DummyRoot(DummyWidget):
    def title(self, *args, **kwargs):
        pass
    def attributes(self, *args, **kwargs):
        pass
    def winfo_screenwidth(self):
        return 800
    def winfo_screenheight(self):
        return 600
    def after(self, *args, **kwargs):
        return 1
    def after_cancel(self, *args, **kwargs):
        pass
    def keys(self):
        return []
    def __getitem__(self, key):
        raise KeyError


class DummyLabel(DummyWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial_text = kwargs.get("text")


@pytest.fixture
def dummy_gui(monkeypatch):
    labels = []

    def fake_label(master=None, **kwargs):
        lbl = DummyLabel(**kwargs)
        labels.append(lbl)
        return lbl

    fake_ttk = types.SimpleNamespace(
        Frame=DummyWidget,
        Label=fake_label,
        Entry=DummyWidget,
        Button=DummyWidget,
        Style=DummyWidget,
    )
    fake_tk = types.SimpleNamespace(Canvas=DummyWidget, Label=DummyLabel)

    monkeypatch.setattr(gui_logowanie, "ttk", fake_ttk)
    monkeypatch.setattr(gui_logowanie, "tk", fake_tk)
    monkeypatch.setattr(gui_logowanie, "apply_theme", lambda root: None)
    monkeypatch.setattr(gui_logowanie.gui_panel, "_shift_progress", lambda now: (0, False))
    monkeypatch.setattr(gui_logowanie.gui_panel, "_shift_bounds", lambda now: (now, now))
    return labels


def test_load_last_update_info_json(tmp_path, monkeypatch):
    data = [{"data": "2024-01-02", "wersje": {"app": "1.0"}}]
    (tmp_path / "logi_wersji.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert gui_logowanie.load_last_update_info() == (
        "Ostatnia aktualizacja: 2024-01-02",
        "1.0",
    )


def test_load_last_update_info_fallback(tmp_path, monkeypatch):
    content = "# Info\nData: 2023-10-15 12:00\n"
    (tmp_path / "CHANGES_PROFILES_UPDATE.txt").write_text(content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert gui_logowanie.load_last_update_info() == (
        "Ostatnia aktualizacja: 2023-10-15 12:00",
        None,
    )


# brak informacji przy niepoprawnym lub brakującym pliku
@pytest.mark.parametrize("json_content", [None, "[{"])
def test_load_last_update_info_missing_or_malformed(tmp_path, monkeypatch, json_content):
    if json_content is not None:
        (tmp_path / "logi_wersji.json").write_text(json_content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def fake_check_output(cmd, text=True, stderr=None):
        assert cmd == ["git", "log", "-1", "--format=%ci"]
        return "2024-06-01 10:00:00 +0000"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    assert gui_logowanie.load_last_update_info() == (
        "Ostatnia aktualizacja: 2024-06-01 10:00:00",
        None,
    )


def test_load_last_update_info_git_show_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def fake_check_output(cmd, text=True, stderr=None):
        if cmd[:3] == ["git", "log", "-1"]:
            raise subprocess.CalledProcessError(1, cmd)
        assert cmd == ["git", "show", "-s", "--format=%ci", "HEAD"]
        return "2024-06-02 11:00:00 +0000"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    assert gui_logowanie.load_last_update_info() == (
        "Ostatnia aktualizacja: 2024-06-02 11:00:00",
        None,
    )


def test_label_color_current(monkeypatch, dummy_gui):
    cfg = ConfigManager()
    remote = cfg.get("updates.remote")
    branch = cfg.get("updates.branch")

    def fake_run(cmd, *args, **kwargs):
        if cmd == ["git", "fetch", remote, branch]:
            return subprocess.CompletedProcess(cmd, 0)
        raise AssertionError(cmd)

    def fake_check_output(cmd, *args, **kwargs):
        if cmd == ["git", "rev-parse", f"{remote}/{branch}"]:
            return "abc\n"
        if cmd == ["git", "rev-parse", "HEAD"]:
            return "abc\n"
        raise AssertionError(cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(gui_logowanie, "load_last_update_info", lambda: ("init", None))
    root = DummyRoot()
    gui_logowanie.ekran_logowania(root=root)
    lbl = next(l for l in dummy_gui if l.initial_text == "init")
    assert lbl.kwargs["text"] == "init – Aktualna"
    assert lbl.kwargs["foreground"] == "green"


def test_label_color_outdated(monkeypatch, dummy_gui):
    cfg = ConfigManager()
    remote = cfg.get("updates.remote")
    branch = cfg.get("updates.branch")

    def fake_run(cmd, *args, **kwargs):
        if cmd == ["git", "fetch", remote, branch]:
            return subprocess.CompletedProcess(cmd, 0)
        raise AssertionError(cmd)

    def fake_check_output(cmd, *args, **kwargs):
        if cmd == ["git", "rev-parse", f"{remote}/{branch}"]:
            return "def\n"
        if cmd == ["git", "rev-parse", "HEAD"]:
            return "abc\n"
        raise AssertionError(cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(gui_logowanie, "load_last_update_info", lambda: ("init", None))
    root = DummyRoot()
    gui_logowanie.ekran_logowania(root=root)
    lbl = next(l for l in dummy_gui if l.initial_text == "init")
    assert lbl.kwargs["text"] == "init – Nieaktualna"
    assert lbl.kwargs["foreground"] == "red"


def test_logowanie_success(tmp_path, monkeypatch):
    users = [{"login": "user", "pin": "1234", "rola": "admin"}]
    (tmp_path / "uzytkownicy.json").write_text(
        json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gui_logowanie, "__file__", str(tmp_path / "gui_logowanie.py"))
    monkeypatch.setattr(gui_logowanie, "entry_login", types.SimpleNamespace(get=lambda: "user"))
    monkeypatch.setattr(gui_logowanie, "entry_pin", types.SimpleNamespace(get=lambda: "1234"))
    logged = {}

    def fake_cb(login, rola, extra):
        logged["login"] = login
        logged["rola"] = rola

    monkeypatch.setattr(gui_logowanie, "_on_login_cb", fake_cb)
    monkeypatch.setattr(gui_logowanie, "root_global", DummyRoot())
    gui_logowanie.logowanie()
    assert logged == {"login": "user", "rola": "admin"}


def test_logowanie_invalid_pair(tmp_path, monkeypatch):
    users = [{"login": "user", "pin": "1234"}]
    (tmp_path / "uzytkownicy.json").write_text(
        json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gui_logowanie, "__file__", str(tmp_path / "gui_logowanie.py"))
    monkeypatch.setattr(gui_logowanie, "entry_login", types.SimpleNamespace(get=lambda: "user"))
    monkeypatch.setattr(gui_logowanie, "entry_pin", types.SimpleNamespace(get=lambda: "0000"))
    errors = []

    def fake_error(title, msg):
        errors.append(msg)

    monkeypatch.setattr(gui_logowanie, "messagebox", types.SimpleNamespace(showerror=fake_error))
    logged = []
    monkeypatch.setattr(gui_logowanie, "_on_login_cb", lambda *args: logged.append(args))
    monkeypatch.setattr(gui_logowanie, "root_global", DummyRoot())
    gui_logowanie.logowanie()
    assert errors and errors[0] == "Nieprawidłowy login lub PIN"
    assert not logged


@pytest.mark.parametrize("attempt_login", ["Edwin", "EDWIN"])
def test_logowanie_case_insensitive(tmp_path, monkeypatch, attempt_login):
    users = [{"login": "edwin", "pin": "1234", "rola": "pracownik"}]
    (tmp_path / "uzytkownicy.json").write_text(
        json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gui_logowanie, "__file__", str(tmp_path / "gui_logowanie.py"))
    monkeypatch.setattr(
        gui_logowanie, "entry_login", types.SimpleNamespace(get=lambda: attempt_login)
    )
    monkeypatch.setattr(
        gui_logowanie, "entry_pin", types.SimpleNamespace(get=lambda: "1234")
    )
    logged = {}

    def fake_cb(login, rola, extra):
        logged["login"] = login
        logged["rola"] = rola

    monkeypatch.setattr(gui_logowanie, "_on_login_cb", fake_cb)
    monkeypatch.setattr(gui_logowanie, "root_global", DummyRoot())
    gui_logowanie.logowanie()
    assert logged == {"login": "edwin", "rola": "pracownik"}


def test_logowanie_callback_error(tmp_path, monkeypatch):
    users = [{"login": "user", "pin": "1234", "rola": "admin"}]
    (tmp_path / "uzytkownicy.json").write_text(
        json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        gui_logowanie, "entry_login", types.SimpleNamespace(get=lambda: "user")
    )
    monkeypatch.setattr(
        gui_logowanie, "entry_pin", types.SimpleNamespace(get=lambda: "1234")
    )

    errors = []

    def fake_error(title, msg):
        errors.append(msg)

    monkeypatch.setattr(
        gui_logowanie, "messagebox", types.SimpleNamespace(showerror=fake_error)
    )

    logged = []
    monkeypatch.setattr(
        gui_logowanie, "logging", types.SimpleNamespace(exception=lambda msg: logged.append(msg))
    )

    def failing_cb(login, rola, extra):
        raise RuntimeError("boom")

    monkeypatch.setattr(gui_logowanie, "_on_login_cb", failing_cb)
    monkeypatch.setattr(gui_logowanie, "root_global", DummyRoot())

    gui_logowanie.logowanie()
    assert errors and "boom" in errors[0]
    assert logged and logged[0] == "Error in login callback"
