import json
import re
from datetime import datetime

from magazyn_io_pz import (
    ensure_in_katalog,
    generate_pz_id,
    save_pz,
    update_stany_after_pz,
)


def test_generate_pz_id_format(tmp_path):
    seq_path = tmp_path / "_seq_pz.json"
    current_year = datetime.now().year
    seq_path.write_text(
        json.dumps({"year": current_year - 1, "seq": 5}), encoding="utf-8"
    )
    pz_id = generate_pz_id(seq_path=str(seq_path))
    assert pz_id == f"PZ/{current_year}/0001"
    assert re.match(r"^PZ/\d{4}/\d{4}$", pz_id)
    data = json.loads(seq_path.read_text(encoding="utf-8"))
    assert data == {"year": current_year, "seq": 1}


def test_save_pz_appends_entry(tmp_path):
    pz_path = tmp_path / "przyjecia.json"
    save_pz({"id": "PZ/2025/0001"}, path=str(pz_path))
    save_pz({"id": "PZ/2025/0002"}, path=str(pz_path))
    data = json.loads(pz_path.read_text(encoding="utf-8"))
    assert [e["id"] for e in data] == ["PZ/2025/0001", "PZ/2025/0002"]


def test_update_stany_after_pz_sums_quantities(tmp_path):
    stany_path = tmp_path / "stany.json"
    stany_path.write_text("{}", encoding="utf-8")
    entries = [
        {"item_id": "X", "qty": 2},
        {"item_id": "X", "qty": 3},
        {"item_id": "Y", "qty": 1},
    ]
    stany = update_stany_after_pz(entries, path=str(stany_path))
    assert stany["X"]["stan"] == 5
    assert stany["Y"]["stan"] == 1


def test_ensure_in_katalog_adds_new_position(tmp_path):
    katalog_path = tmp_path / "katalog.json"
    katalog_path.write_text('{"items": {}, "meta": {"order": []}}', encoding="utf-8")
    added = ensure_in_katalog({"id": "NEW", "nazwa": "Nowy"}, path=str(katalog_path))
    assert added
    data = json.loads(katalog_path.read_text(encoding="utf-8"))
    assert "NEW" in data["items"]
    assert "NEW" in data["meta"]["order"]
