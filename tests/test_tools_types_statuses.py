import json
from collections import Counter
from pathlib import Path

def test_zadania_narzedzia_limits_and_structure():
    path = Path("data/zadania_narzedzia.json")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    types = data.get("types") or []
    assert len(types) <= 8
    for typ in types:
        assert {"id", "name", "statuses"} <= typ.keys()
        statuses = typ.get("statuses") or []
        assert len(statuses) <= 8
        for st in statuses:
            assert {"id", "name", "tasks"} <= st.keys()
            assert isinstance(st["tasks"], list)
