import types
import start


def test_show_startup_error_restores_and_copies_log(tmp_path, monkeypatch):
    log_file = tmp_path / "log.txt"
    log_file.write_text("example log", encoding="utf-8")
    monkeypatch.setattr(start, "_log_path", lambda: str(log_file))

    restored = []
    monkeypatch.setattr(start.updater, "_list_backups", lambda: ["old", "new"])

    def fake_restore(stamp):
        restored.append(stamp)

    monkeypatch.setattr(start.updater, "_restore_backup", fake_restore)

    roots = []

    class FakeRoot:
        def __init__(self):
            roots.append(self)
            self.clipboard = ""
            self.buttons = []

        def title(self, t):
            pass

        def clipboard_clear(self):
            self.clipboard = ""

        def clipboard_append(self, text):
            self.clipboard += text

        def destroy(self):
            pass

        def mainloop(self):
            for btn in self.buttons:
                btn.command()

    class FakeButton:
        def __init__(self, master, text="", command=None):
            self.command = command
            master.buttons.append(self)

        def pack(self, *a, **kw):
            pass

    class FakeLabel:
        def __init__(self, *a, **kw):
            pass

        def pack(self, *a, **kw):
            pass

    class FakeText:
        def __init__(self, *a, **kw):
            self.text = ""

        def insert(self, index, text):
            self.text += text

        def config(self, *a, **kw):
            pass

        def pack(self, *a, **kw):
            pass

    class FakeFrame:
        def __init__(self, master):
            self.buttons = master.buttons

        def pack(self, *a, **kw):
            pass

    monkeypatch.setattr(start.tk, "Tk", FakeRoot)
    monkeypatch.setattr(start.tk, "Button", FakeButton)
    monkeypatch.setattr(start.tk, "Label", FakeLabel)
    monkeypatch.setattr(start.tk, "Text", FakeText)
    monkeypatch.setattr(start.tk, "Frame", FakeFrame)

    mb = types.SimpleNamespace(
        showinfo=lambda *a, **kw: None,
        showwarning=lambda *a, **kw: None,
        showerror=lambda *a, **kw: None,
    )
    monkeypatch.setattr(start, "messagebox", mb)

    start.show_startup_error(Exception("boom"))

    root = roots[0]
    assert root.clipboard == "example log"
    assert restored == ["new"]


def test_auto_update_on_start_conflict(monkeypatch):
    msgs = []

    class DummyCfg:
        def __init__(self):
            pass

        def get(self, key, default=None):
            return True

    monkeypatch.setattr(start, "ConfigManager", DummyCfg)

    def fake_pull(cwd, stamp):
        raise RuntimeError(
            "W repozytorium istnieją lokalne zmiany. "
            "Zapisz lub odrzuć je przed aktualizacją."
        )

    monkeypatch.setattr(start, "_run_git_pull", fake_pull)

    def fake_showerror(title, message, suggestion=None):
        msgs.append(message)

    monkeypatch.setattr(start.error_dialogs, "show_error_dialog", fake_showerror)

    class FakeRoot:
        def withdraw(self):
            pass

        def destroy(self):
            pass

    monkeypatch.setattr(start.tk, "Tk", lambda: FakeRoot())
    monkeypatch.setattr(start, "_error", lambda msg: None)

    start.auto_update_on_start()
    assert any("Zapisz lub odrzuć" in m for m in msgs)
