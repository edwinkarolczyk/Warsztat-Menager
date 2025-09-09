import json
from pathlib import Path


def test_zadania_narzedzia_limits_and_structure():
    path = Path("data/zadania_narzedzia.json")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    types = data.get("types")
    assert isinstance(types, list)
    assert len(types) <= 8, "Limit typów przekroczony"
    for typ in types:
        assert {"id", "name", "statuses"} <= typ.keys()
        statuses = typ.get("statuses") or []
        assert len(statuses) <= 8, f"Za dużo statusów dla typu {typ.get('id')}"
        for st in statuses:
            assert {"id", "name", "tasks"} <= st.keys()
            tasks = st.get("tasks") or []
            assert isinstance(tasks, list)
