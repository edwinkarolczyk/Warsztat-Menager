import json
from collections import Counter
from pathlib import Path

def test_zadania_narzedzia_limits_and_structure():
    path = Path("data/zadania_narzedzia.json")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) <= 64, "Limit 8x8 przekroczony"
    required = {"id", "login", "tytul", "status", "termin", "opis", "zlecenie"}
    allowed_statuses = {"Nowe", "W toku", "Pilne", "Zrobione"}
    counts = Counter()
    for item in data:
        assert required <= item.keys()
        assert item["status"] in allowed_statuses
        counts[item["login"]] += 1
    assert len(counts) <= 8
    assert all(c <= 8 for c in counts.values())
