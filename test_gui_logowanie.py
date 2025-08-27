import json
import types
import subprocess
import pytest

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


def test_load_last_update_info_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert gui_logowanie.load_last_update_info() is None


def test_label_color_current(monkeypatch, dummy_gui):
    def fake_run(cmd, *args, **kwargs):
        if cmd == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="abc\n")
        if cmd == ["git", "rev-parse", "@{upstream}"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="abc\n")
        raise AssertionError(cmd)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(gui_logowanie, "load_last_update_info", lambda: ("init", None))
    root = DummyRoot()
    gui_logowanie.ekran_logowania(root=root)
    lbl = next(l for l in dummy_gui if l.initial_text == "init")
    assert lbl.kwargs["text"] == "Aktualna"
    assert lbl.kwargs["foreground"] == "green"


def test_label_color_outdated(monkeypatch, dummy_gui):
    def fake_run(cmd, *args, **kwargs):
        if cmd == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="abc\n")
        if cmd == ["git", "rev-parse", "@{upstream}"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="def\n")
        raise AssertionError(cmd)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(gui_logowanie, "load_last_update_info", lambda: ("init", None))
    root = DummyRoot()
    gui_logowanie.ekran_logowania(root=root)
    lbl = next(l for l in dummy_gui if l.initial_text == "init")
    assert lbl.kwargs["text"] == "Nieaktualna"
    assert lbl.kwargs["foreground"] == "red"
