import importlib
import json
import sqlite3
import types

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


def test_panel_fallback_when_table_missing(monkeypatch):
    mod = importlib.import_module("gui_profile")

    class DummyRoot:
        def winfo_toplevel(self):
            return self

    class DummyFrame:
        def configure(self, **kwargs):
            pass

        def winfo_children(self):
            return []

    class DummyWidget:
        def __init__(self, *args, **kwargs):
            pass

        def pack(self, *args, **kwargs):
            pass

        def destroy(self):
            pass

        def configure(self, *args, **kwargs):
            pass

        def winfo_children(self):
            return []

    class DummyNotebook(DummyWidget):
        def add(self, *args, **kwargs):
            pass

    monkeypatch.setattr(mod, "apply_theme", lambda *a, **k: None)
    monkeypatch.setattr(
        mod,
        "ttk",
        types.SimpleNamespace(
            Frame=DummyWidget, Label=DummyWidget, Notebook=DummyNotebook
        ),
    )
    monkeypatch.setattr(
        mod, "tk", types.SimpleNamespace(Label=DummyWidget, Text=DummyWidget)
    )
    monkeypatch.setattr(mod, "_load_avatar", lambda parent, login: DummyWidget())
    monkeypatch.setattr(mod, "_read_tasks", lambda *a, **k: [])
    monkeypatch.setattr(mod, "_build_basic_tab", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_build_skills_tab", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_build_tasks_tab", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_build_stats_tab", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_build_simple_list_tab", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_build_preferences_tab", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_build_description_tab", lambda *a, **k: None)

    def raise_error(login):
        raise sqlite3.OperationalError("no such table")

    monkeypatch.setattr(mod, "get_user", raise_error)
    monkeypatch.setattr(mod, "read_users", lambda: [{"login": "abc"}])

    called = {}

    def fake_info(title, msg):
        called["msg"] = msg

    monkeypatch.setattr(mod.messagebox, "showinfo", fake_info)

    root = DummyRoot()
    frame = DummyFrame()
    mod.uruchom_panel(root, frame, login="abc", rola="operator")
    assert "msg" in called

