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
