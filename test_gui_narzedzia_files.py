import os
import types

import gui_narzedzia


def test_is_allowed_file(tmp_path):
    good = tmp_path / "ok.png"
    good.write_bytes(b"x")
    assert gui_narzedzia._is_allowed_file(str(good))

    bad_ext = tmp_path / "bad.txt"
    bad_ext.write_bytes(b"x")
    assert not gui_narzedzia._is_allowed_file(str(bad_ext))

    big = tmp_path / "big.png"
    big.write_bytes(b"x" * (gui_narzedzia.MAX_FILE_SIZE + 1))
    assert not gui_narzedzia._is_allowed_file(str(big))


def test_remove_task_deletes_files(tmp_path):
    media = tmp_path / "m.png"
    thumb = tmp_path / "t.jpg"
    media.write_bytes(b"1")
    thumb.write_bytes(b"1")
    tasks = [{"tytul": "a", "done": False, "media": str(media), "miniatura": str(thumb)}]
    gui_narzedzia._remove_task(tasks, 0)
    assert tasks == []
    assert not media.exists()
    assert not thumb.exists()


def test_panel_handles_return(monkeypatch):
    created = []

    class DummyTree:
        def __init__(self, *args, **kwargs):
            created.append(self)
            self.bindings = {}

        def heading(self, *args, **kwargs):
            pass

        def column(self, *args, **kwargs):
            pass

        def pack(self, *args, **kwargs):
            pass

        def tag_configure(self, *args, **kwargs):
            pass

        def delete(self, *args, **kwargs):
            pass

        def get_children(self):
            return []

        def bind(self, seq, func):
            self.bindings[seq] = func

        def identify_row(self, _y):
            return ""

    class DummyVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, val):
            self.value = val

        def trace_add(self, *_):
            pass

    class DummyWidget:
        def __init__(self, *args, **kwargs):
            pass

        def pack(self, *args, **kwargs):
            pass

        def bind(self, *args, **kwargs):
            pass

        def config(self, *args, **kwargs):
            pass

        configure = config

    dummy_tk = types.SimpleNamespace(StringVar=DummyVar)
    dummy_ttk = types.SimpleNamespace(
        Frame=DummyWidget,
        Label=DummyWidget,
        Entry=DummyWidget,
        Button=DummyWidget,
        Treeview=DummyTree,
    )

    monkeypatch.setattr(gui_narzedzia, "tk", dummy_tk)
    monkeypatch.setattr(gui_narzedzia, "ttk", dummy_ttk)
    monkeypatch.setattr(gui_narzedzia, "apply_theme", lambda *a, **k: None)
    monkeypatch.setattr(gui_narzedzia, "clear_frame", lambda *a, **k: None)
    monkeypatch.setattr(gui_narzedzia, "_load_all_tools", lambda: [])
    monkeypatch.setattr(
        gui_narzedzia.ui_hover, "bind_treeview_row_hover", lambda *a, **k: None
    )

    gui_narzedzia.panel_narzedzia(DummyWidget(), DummyWidget())
    tree = created[0]

    assert "<Return>" in tree.bindings
    assert tree.bindings["<Return>"] is tree.bindings["<Double-1>"]
