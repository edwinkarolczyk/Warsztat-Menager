import json

import magazyn_io


def test_append_history_accepts_komentarz(tmp_path, monkeypatch):
    hist_path = tmp_path / "hist.json"
    monkeypatch.setattr(magazyn_io, "HISTORY_PATH", str(hist_path))

    items = {}
    entry = magazyn_io.append_history(
        items,
        "A",
        "user",
        "CREATE",
        1,
        komentarz="uwaga",
    )

    assert entry["comment"] == "uwaga"
    assert items["A"]["historia"][0]["comment"] == "uwaga"
    data = json.loads(hist_path.read_text(encoding="utf-8"))
    assert data[0]["comment"] == "uwaga"


def test_append_history_normalizes_none_comment(tmp_path, monkeypatch):
    hist_path = tmp_path / "hist.json"
    monkeypatch.setattr(magazyn_io, "HISTORY_PATH", str(hist_path))

    items = {}
    entry = magazyn_io.append_history(
        items,
        "A",
        "user",
        "CREATE",
        1,
        comment=None,
    )

    assert entry["comment"] == ""
    assert items["A"]["historia"][0]["comment"] == ""
    data = json.loads(hist_path.read_text(encoding="utf-8"))
    assert data[0]["comment"] == ""
