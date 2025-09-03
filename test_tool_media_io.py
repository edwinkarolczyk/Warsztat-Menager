import types

import gui_narzedzia


def test_save_and_read_media(monkeypatch, tmp_path):
    monkeypatch.setattr(gui_narzedzia, "_resolve_tools_dir", lambda: str(tmp_path))
    data = {
        "numer": "010",
        "nazwa": "N",
        "typ": "T",
        "status": "sprawne",
        "zadania": [],
        "obraz": "media/010_img.png",
        "dxf": "media/010.dxf",
        "dxf_png": "media/010_dxf.png",
    }
    gui_narzedzia._save_tool(data)
    read = gui_narzedzia._read_tool("010")
    assert read["obraz"] == data["obraz"]
    assert read["dxf"] == data["dxf"]
    assert read["dxf_png"] == data["dxf_png"]
    items = gui_narzedzia._iter_folder_items()
    assert items[0]["obraz"] == data["obraz"]
    assert items[0]["dxf"] == data["dxf"]
    assert items[0]["dxf_png"] == data["dxf_png"]


def test_refresh_list_prefers_dxf_png(monkeypatch, tmp_path):
    monkeypatch.setattr(gui_narzedzia, "_resolve_tools_dir", lambda: str(tmp_path))

    media_dir = tmp_path / "media"
    media_dir.mkdir()
    dxf_png = media_dir / "tool_dxf.png"
    obraz = media_dir / "tool_img.png"
    dxf_png.write_bytes(b"1")
    obraz.write_bytes(b"1")

    tool = {
        "nr": "001",
        "nazwa": "n",
        "typ": "t",
        "status": "s",
        "data": "d",
        "postep": 0,
        "obraz": f"media/{obraz.name}",
        "dxf_png": f"media/{dxf_png.name}",
    }
    monkeypatch.setattr(gui_narzedzia, "_load_all_tools", lambda: [tool])

    class DummyVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def trace_add(self, *_):
            pass

    class DummyWidget:
        def __init__(self, *_, **__):
            pass

        def pack(self, *_, **__):
            pass

        def grid(self, *_, **__):
            pass

        def config(self, *_, **__):
            pass

        configure = config

        def bind(self, *_, **__):
            pass

        def delete(self, *_, **__):
            pass

        def get_children(self):
            return []

        def heading(self, *_, **__):
            pass

        def column(self, *_, **__):
            pass

        def insert(self, *_, **__):
            pass

        def tag_configure(self, *_, **__):
            pass

    dummy_tk = types.SimpleNamespace(StringVar=DummyVar)
    dummy_ttk = types.SimpleNamespace(
        Frame=DummyWidget,
        Label=DummyWidget,
        Entry=DummyWidget,
        Button=DummyWidget,
        Treeview=DummyWidget,
    )

    monkeypatch.setattr(gui_narzedzia, "tk", dummy_tk)
    monkeypatch.setattr(gui_narzedzia, "ttk", dummy_ttk)
    monkeypatch.setattr(gui_narzedzia, "apply_theme", lambda *a, **k: None)
    monkeypatch.setattr(gui_narzedzia, "clear_frame", lambda *a, **k: None)

    captured = {}

    def fake_bind(_tree, _iid, paths):
        captured["paths"] = paths

    monkeypatch.setattr(
        gui_narzedzia.ui_hover,
        "bind_treeview_row_hover",
        fake_bind,
    )

    gui_narzedzia.panel_narzedzia(DummyWidget(), DummyWidget())

    assert captured["paths"] == [str(dxf_png)]
