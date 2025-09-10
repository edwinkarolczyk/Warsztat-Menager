import types
import pytest
import gui_magazyn as gm


def test_btn_do_zam_attaches_tooltip(monkeypatch):
    recorded: list[str] = []

    def fake_attach(widget, text):  # noqa: ANN001 - test helper
        recorded.append(text)
        return {}

    monkeypatch.setattr(gm, "_attach_tooltip", fake_attach)

    class DummyWidget:
        def __init__(self, *_, **__):
            pass

        def grid(self, *_, **__):
            pass

        def columnconfigure(self, *_args, **_kwargs):
            pass

        def rowconfigure(self, *_args, **_kwargs):
            pass

        def bind(self, *_, **__):
            pass

        def bind_all(self, *_, **__):
            pass

    class DummyNotebook:
        def __init__(self, *_, **__):
            raise RuntimeError

    fake_ttk = types.SimpleNamespace(
        Frame=DummyWidget,
        Label=DummyWidget,
        Entry=DummyWidget,
        Button=DummyWidget,
        Notebook=DummyNotebook,
        Treeview=DummyWidget,
    )

    fake_tk = types.SimpleNamespace(StringVar=lambda: object())

    monkeypatch.setattr(gm, "ttk", fake_ttk)
    monkeypatch.setattr(gm, "tk", fake_tk)
    monkeypatch.setattr(gm, "apply_theme", lambda *_a, **_k: None)

    panel = object.__new__(gm.PanelMagazyn)
    panel.master = DummyWidget()
    panel.master.tab = lambda *a, **k: None
    panel.columnconfigure = lambda *a, **k: None
    panel.rowconfigure = lambda *a, **k: None
    panel.grid = lambda *a, **k: None
    panel.bind_all = lambda *a, **k: None

    with pytest.raises(RuntimeError):
        panel._build_ui()

    assert "Dodaj pozycję do listy zamówień." in recorded

