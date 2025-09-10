import types
import gui_magazyn as gm


class DummyToplevel:
    def __init__(self, master):
        self.master = master
        self.label = None

    def wm_overrideredirect(self, _):
        pass

    def wm_geometry(self, _):
        pass

    def destroy(self):
        self.label = None


class DummyLabel:
    def __init__(self, master, **kwargs):
        self.master = master
        self.text = kwargs.get("text", "")
        master.label = self

    def pack(self, **_):
        pass


class DummyWidget:
    def __init__(self):
        self.bindings = {}

    def bind(self, seq, func, add=None):  # noqa: A003 - mimic tk interface
        self.bindings[seq] = func

    def winfo_rootx(self):
        return 0

    def winfo_rooty(self):
        return 0

    def trigger(self, seq):
        self.bindings[seq]()


def setup_dummy(monkeypatch):
    dummy_tk = types.SimpleNamespace(Toplevel=DummyToplevel, Label=DummyLabel)
    monkeypatch.setattr(gm, "tk", dummy_tk)
    monkeypatch.setattr(gm, "_ensure_topmost", lambda *_: None)
    return dummy_tk


def test_attach_tooltip_shows_text(monkeypatch):
    setup_dummy(monkeypatch)
    widget = DummyWidget()
    tip = gm._attach_tooltip(widget, "tekst")
    widget.trigger("<Enter>")
    assert tip["w"] is not None
    assert tip["w"].label.text == "tekst"
    widget.trigger("<Leave>")
    assert tip["w"] is None
