import json

import magazyn_io as mio


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def test_suggest_and_get_code(tmp_path, monkeypatch):
    katalog_path = tmp_path / "katalog.json"
    stany_path = tmp_path / "stany.json"
    write_json(
        katalog_path,
        {
            "rurka": {"R1": "Rurka 30mm", "R2": "Rurka 40mm"},
            "plaskownik": {"P1": "Płaskownik 40mm"},
        },
    )
    write_json(stany_path, {"X": {"nazwa": "Rurka 50mm", "stan": 0, "prog_alert": 0}})
    monkeypatch.setattr(mio, "KATALOG_PATH", str(katalog_path))
    monkeypatch.setattr(mio, "STANY_PATH", str(stany_path))

    names = mio.suggest_names_for_category("rurka", "Rur")
    assert names == ["Rurka 30mm", "Rurka 40mm", "Rurka 50mm"]

    code = mio.get_or_build_code({"kategoria": "rurka", "nazwa": "Rurka 40mm"})
    assert code == "R2"

    new_code = mio.get_or_build_code({"kategoria": "rurka", "nazwa": "Rurka 60mm"})
    assert new_code not in {"R1", "R2"}
    with open(katalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert any(n == "Rurka 60mm" for n in data["rurka"].values())


def test_append_history_updates_stany(tmp_path, monkeypatch):
    stany_path = tmp_path / "stany.json"
    hist_path = tmp_path / "hist.json"
    pz_path = tmp_path / "pz.json"
    monkeypatch.setattr(mio, "STANY_PATH", str(stany_path))
    monkeypatch.setattr(mio, "HISTORY_PATH", str(hist_path))
    monkeypatch.setattr(mio, "PRZYJECIA_PATH", str(pz_path))

    items = {"NEW": {"nazwa": "Nowy"}}
    mio.append_history(items, "NEW", user="t", op="PZ", qty=5)
    mio.append_history(items, "NEW", user="t", op="PZ", qty=2)
    with open(stany_path, "r", encoding="utf-8") as f:
        stany = json.load(f)
    assert stany["NEW"]["stan"] == 7
    assert stany["NEW"]["nazwa"] == "Nowy"
