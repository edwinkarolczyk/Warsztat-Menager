import json
import gui_settings


def test_slowniki_save_does_not_touch_config(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps({"a": 1}, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    sl_path = tmp_path / "data/magazyn/slowniki.json"
    monkeypatch.setattr(gui_settings, "MAG_DICT_PATH", str(sl_path))

    panel = gui_settings.SettingsPanel.__new__(gui_settings.SettingsPanel)

    original = cfg_path.read_text(encoding="utf-8")
    panel._save_magazyn_dicts({
        "kategorie": ["x"],
        "typy_materialu": [],
        "jednostki": [],
    })
    assert cfg_path.read_text(encoding="utf-8") == original

    with open(sl_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["kategorie"] == ["x"]
