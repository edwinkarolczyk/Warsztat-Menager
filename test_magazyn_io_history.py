import magazyn_io as mio
from io_utils import read_json


def test_append_history_persists_global_logs(tmp_path, monkeypatch):
    hist_path = tmp_path / "magazyn_history.json"
    pz_path = tmp_path / "przyjecia.json"
    monkeypatch.setattr(mio, "MAGAZYN_HISTORY_PATH", str(hist_path))
    monkeypatch.setattr(mio, "PRZYJECIA_PATH", str(pz_path))

    items = {}
    mio.append_history("A", {"user": "u", "op": "ZW", "qty": 1, "comment": "c"}, items)
    assert hist_path.exists()
    hist = read_json(str(hist_path))
    assert hist and hist[-1]["item_id"] == "A"
    assert not pz_path.exists()

    mio.append_history("A", {"user": "u", "op": "PZ", "qty": 2, "comment": "d"}, items)
    hist = read_json(str(hist_path))
    pz = read_json(str(pz_path))
    assert hist and hist[-1]["item_id"] == "A" and hist[-1]["op"] == "PZ"
    assert pz and pz[-1]["op"] == "PZ"

