import json
from pathlib import Path


def test_zadania_narzedzia_limits_and_structure():
    path = Path("data/zadania_narzedzia.json")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    types = data.get("types") or []
    assert len(types) <= 8, "Limit typów przekroczony"
    seen_types = set()
    for typ in types:
        tid = typ.get("id")
        assert tid and tid not in seen_types
        seen_types.add(tid)
        statuses = typ.get("statuses") or []
        assert len(statuses) <= 8, f"Za dużo statusów dla {tid}"
        seen_statuses = set()
        for st in statuses:
            sid = st.get("id")
            assert sid and sid not in seen_statuses
            seen_statuses.add(sid)
            tasks = st.get("tasks") or []
            assert len(tasks) <= 8, f"Za dużo zadań dla {sid}"
            assert isinstance(st.get("auto_check_on_entry", False), bool)
