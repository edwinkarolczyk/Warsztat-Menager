import importlib
import json
from config_manager import ConfigManager


def test_foreman_role_case_insensitive():
    mod = importlib.import_module("gui_profile")
    order = {"nr": 1}
    tool = {"id": "NARZ-1-1"}
    roles = ["brygadzista", "BRYGADZISTA", "Brygadzista", "BrYgAdZiStA"]
    for r in roles:
        assert mod._order_visible_for(order, "user", r)
        assert mod._tool_visible_for(tool, "user", r)


def test_read_tasks_foreman_role_case_insensitive(monkeypatch, tmp_path):
    mod = importlib.import_module("gui_profile")

    cfg = ConfigManager()
    assert isinstance(cfg.get("updates.remote"), str)
    assert isinstance(cfg.get("updates.branch"), str)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "zlecenia.json").write_text(json.dumps([{"nr": 1}]), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    sample_order = {"nr": 1, "login": "other", "status": "Nowe"}

    def fake_load_json(path, default):
        if str(path).endswith("zlecenia.json"):
            return [sample_order]
        return []

    monkeypatch.setattr(mod, "_load_json", fake_load_json)
    monkeypatch.setattr(mod, "_load_status_overrides", lambda login: {})
    monkeypatch.setattr(mod, "_load_assign_orders", lambda: {})
    monkeypatch.setattr(mod, "_load_assign_tools", lambda: {})
    monkeypatch.setattr(mod.glob, "glob", lambda pattern: [])

    roles = ["brygadzista", "BRYGADZISTA", "Brygadzista", "BrYgAdZiStA"]
    for r in roles:
        tasks = mod._read_tasks("user", r)
        assert any(t.get("id") == "ZLEC-1" for t in tasks)

