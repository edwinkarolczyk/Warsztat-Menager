import json

from narzedzia_history import append_tool_history


def test_append_tool_history(tmp_path, monkeypatch):
    hist_dir = tmp_path / "hist"
    monkeypatch.setattr("narzedzia_history.TOOL_HISTORY_DIR", hist_dir)
    append_tool_history("T001", "adam", "create", info="x")

    file_path = hist_dir / "T001.jsonl"
    assert file_path.exists()

    lines = file_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["user"] == "adam"
    assert data["action"] == "create"
    assert data["info"] == "x"
    assert data["ts"].endswith("+00:00")
