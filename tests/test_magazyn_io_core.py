import json
import logging
import re
from datetime import datetime, timezone

import magazyn_io


def test_generate_pz_id_resets_each_year(tmp_path, monkeypatch):
    seq_path = tmp_path / "_seq_pz.json"
    monkeypatch.setattr(magazyn_io, "SEQ_PZ_PATH", str(seq_path))
    now_2024 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    now_2025 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    pz1 = magazyn_io.generate_pz_id(now=now_2024)
    pz2 = magazyn_io.generate_pz_id(now=now_2024)
    pz3 = magazyn_io.generate_pz_id(now=now_2025)
    data = json.loads(seq_path.read_text(encoding="utf-8"))
    regex = r"^PZ/\d{4}/\d{4}$"
    assert re.match(regex, pz1)
    assert re.match(regex, pz2)
    assert re.match(regex, pz3)
    assert pz1 == "PZ/2024/0001"
    assert pz2 == "PZ/2024/0002"
    assert pz3 == "PZ/2025/0001"
    assert data == {"2024": 2, "2025": 1}


def test_ensure_in_katalog_unit_conflict(tmp_path, monkeypatch):
    katalog_path = tmp_path / "katalog.json"
    monkeypatch.setattr(magazyn_io, "KATALOG_PATH", str(katalog_path))
    magazyn_io.ensure_in_katalog({"item_id": "A", "nazwa": "A", "jednostka": "szt"})
    warning = magazyn_io.ensure_in_katalog({"item_id": "A", "jednostka": "kg"})
    assert warning == {"warning": "Jednostka różni się: katalog=szt, PZ=kg"}


def test_logging_messages(tmp_path, monkeypatch, caplog):
    seq_path = tmp_path / "_seq_pz.json"
    pz_path = tmp_path / "przyjecia.json"
    stany_path = tmp_path / "stany.json"
    monkeypatch.setattr(magazyn_io, "SEQ_PZ_PATH", str(seq_path))
    monkeypatch.setattr(magazyn_io, "PRZYJECIA_PATH", str(pz_path))
    monkeypatch.setattr(magazyn_io, "STANY_PATH", str(stany_path))
    caplog.set_level(logging.INFO)
    pz_id = magazyn_io.save_pz({"item_id": "X", "qty": 1})
    magazyn_io.update_stany_after_pz({"item_id": "X", "qty": 1, "nazwa": "X"})
    assert f"[INFO] Zapisano PZ {pz_id}" in caplog.text
    assert "[INFO] Zaktualizowano stan X: 1.0" in caplog.text
