import json
import re
from datetime import datetime

import magazyn_io as mio


def test_generate_pz_id_format(tmp_path, monkeypatch):
    seq_path = tmp_path / "_seq_pz.json"
    monkeypatch.setattr(mio, "SEQ_PZ_PATH", str(seq_path))
    pz_id = mio.generate_pz_id(datetime(2025, 1, 1))
    assert re.match(r"^PZ-\d{4}-\d{2}-\d{2}-\d{4}$", pz_id)


def test_save_pz_appends_entry(tmp_path, monkeypatch):
    pz_path = tmp_path / "przyjecia.json"
    monkeypatch.setattr(mio, "PRZYJECIA_PATH", str(pz_path))
    mio.save_pz({"id": "PZ-2025-01-01-0001"})
    mio.save_pz({"id": "PZ-2025-01-01-0002"})
    data = json.loads(pz_path.read_text(encoding="utf-8"))
    assert [e["id"] for e in data] == ["PZ-2025-01-01-0001", "PZ-2025-01-01-0002"]


def test_update_stany_after_pz_sums_quantities(tmp_path, monkeypatch):
    stany_path = tmp_path / "stany.json"
    monkeypatch.setattr(mio, "STANY_PATH", str(stany_path))
    stany_path.write_text("{}", encoding="utf-8")
    entries = [
        {"item_id": "X", "qty": 2, "nazwa": "X"},
        {"item_id": "X", "qty": 3, "nazwa": "X"},
        {"item_id": "Y", "qty": 1, "nazwa": "Y"},
    ]
    for entry in entries:
        mio.update_stany_after_pz(entry)
    stany = json.loads(stany_path.read_text(encoding="utf-8"))
    assert stany["X"]["stan"] == 5
    assert stany["Y"]["stan"] == 1


def test_ensure_in_katalog_adds_new_position(tmp_path, monkeypatch):
    katalog_path = tmp_path / "katalog.json"
    katalog_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mio, "KATALOG_PATH", str(katalog_path))
    mio.ensure_in_katalog({"item_id": "NEW", "nazwa": "Nowy", "jednostka": ""})
    data = json.loads(katalog_path.read_text(encoding="utf-8"))
    assert "NEW" in data
