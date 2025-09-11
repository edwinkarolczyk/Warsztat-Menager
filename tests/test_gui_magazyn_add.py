import json
import gui_magazyn_add as gma


def test_load_jednostki_valid(tmp_path, monkeypatch):
    path = tmp_path / "slowniki.json"
    data = {"jednostki": ["szt", "kg", "mb", "KG", "  L "]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    monkeypatch.setattr(gma, "SLOWNIKI_PATH", str(path))

    result = gma._load_jednostki()
    assert result == ["szt", "kg", "mb", "L"]


def test_load_jednostki_missing_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(gma, "SLOWNIKI_PATH", str(tmp_path / "missing.json"))
    assert gma._load_jednostki() == gma.FALLBACK_JM


def test_load_jednostki_invalid_json_fallback(tmp_path, monkeypatch):
    path = tmp_path / "slowniki.json"
    path.write_text("{invalid}", encoding="utf-8")
    monkeypatch.setattr(gma, "SLOWNIKI_PATH", str(path))
    assert gma._load_jednostki() == gma.FALLBACK_JM
