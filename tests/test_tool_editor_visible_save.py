from __future__ import annotations

from narzedzia_ui import editor_polish_runtime as runtime


class _FakeTk:
    def __init__(self):
        self.calls = []

    def call(self, command):
        self.calls.append(command)


class _FakeButton:
    def __init__(self, command="save-command"):
        self.command = command
        self.tk = _FakeTk()

    def cget(self, key):
        assert key == "command"
        return self.command


def test_dashboard_save_invokes_existing_editor_save(monkeypatch):
    button = _FakeButton()
    monkeypatch.setattr(runtime, "_find_save_button", lambda window: button)

    assert runtime._invoke_editor_save(object()) is True
    assert button.tk.calls == ["save-command"]


def test_dashboard_save_returns_false_without_editor_action(monkeypatch):
    monkeypatch.setattr(runtime, "_find_save_button", lambda window: None)

    assert runtime._invoke_editor_save(object()) is False
