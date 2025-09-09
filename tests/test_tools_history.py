import json
from pathlib import Path

import tools_history


def test_append_tool_history_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "hist.jsonl"
    entry1 = {"tool": "a", "action": "add"}
    entry2 = {"tool": "b", "action": "remove"}
    tools_history.append_tool_history(path, entry1)
    tools_history.append_tool_history(path, entry2)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0]) == entry1
    assert json.loads(lines[1]) == entry2
