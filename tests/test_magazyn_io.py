import json
import re
from datetime import datetime, timezone

import magazyn_io


def test_generate_pz_id_format(tmp_path, monkeypatch):
    seq_path = tmp_path / "_seq_pz.json"
    seq_path.write_text('{"year": 2025, "seq": 0}', encoding="utf-8")
    monkeypatch.setattr(magazyn_io, "SEQ_PZ_PATH", str(seq_path))
    pz_id = magazyn_io.generate_pz_id(now=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert re.match(r"^PZ/\d{4}/\d{4}$", pz_id)
    assert pz_id == "PZ/2025/0001"


def test_save_pz_appends_entry(tmp_path, monkeypatch):
    pz_path = tmp_path / "przyjecia.json"
    monkeypatch.setattr(magazyn_io, "PRZYJECIA_PATH", str(pz_path))
    magazyn_io.save_pz({"id": "PZ/2025/0001"})
    magazyn_io.save_pz({"id": "PZ/2025/0002"})
    data = json.loads(pz_path.read_text(encoding="utf-8"))
    assert [e["id"] for e in data] == ["PZ/2025/0001", "PZ/2025/0002"]


def test_update_stany_after_pz_sums_quantities(tmp_path, monkeypatch):
    stany_path = tmp_path / "stany.json"
    stany_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(magazyn_io, "STANY_PATH", str(stany_path))
    entries = [
        {"item_id": "X", "qty": 2},
        {"item_id": "X", "qty": 3},
        {"item_id": "Y", "qty": 1},
    ]
    stany = magazyn_io.update_stany_after_pz(entries)
    assert stany["X"]["stan"] == 5
    assert stany["Y"]["stan"] == 1


def test_ensure_in_katalog_adds_new_position(tmp_path, monkeypatch):
    katalog_path = tmp_path / "katalog.json"
    katalog_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(magazyn_io, "KATALOG_PATH", str(katalog_path))
    magazyn_io.ensure_in_katalog({"item_id": "NEW", "nazwa": "Nowy"})
    data = json.loads(katalog_path.read_text(encoding="utf-8"))
    assert "NEW" in data
