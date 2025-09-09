import json

import gui_narzedzia_qr
import narzedzia_history


def test_handle_action_appends_history(tmp_path, monkeypatch):
    tools_dir = tmp_path / "narzedzia"
    tools_dir.mkdir()
    tool_file = tools_dir / "001.json"
    tool_file.write_text(
        json.dumps(
            {"numer": "001", "status": "", "pracownik": "", "historia": []},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(gui_narzedzia_qr, "_resolve_tools_dir", lambda: str(tools_dir))
    hist_dir = tmp_path / "hist"
    monkeypatch.setattr(narzedzia_history, "TOOL_HISTORY_DIR", hist_dir)
    monkeypatch.setattr(gui_narzedzia_qr, "_info", lambda *a, **k: None)
    monkeypatch.setattr(gui_narzedzia_qr, "_error", lambda *a, **k: None)

    assert gui_narzedzia_qr.handle_action("001", "issue", "adam", None)

    log_path = hist_dir / "001.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["user"] == "adam"
    assert record["action"] == "qr_issue"

    data = json.loads(tool_file.read_text(encoding="utf-8"))
    assert "historia" not in data
    assert data["pracownik"] == "adam"
