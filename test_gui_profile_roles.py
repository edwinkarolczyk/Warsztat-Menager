import importlib
import json
import tkinter as tk
from tkinter import ttk

import pytest

from config_manager import ConfigManager
import ustawienia_uzytkownicy


def test_foreman_role_case_insensitive():
    mod = importlib.import_module("gui.profile")
    order = {"nr": 1}
    tool = {"id": "NARZ-1-1"}
    roles = ["brygadzista", "BRYGADZISTA", "Brygadzista", "BrYgAdZiStA"]
    for r in roles:
        assert mod._order_visible_for(order, "user", r)
        assert mod._tool_visible_for(tool, "user", r)


def test_read_tasks_foreman_role_case_insensitive(monkeypatch, tmp_path):
    mod = importlib.import_module("gui.profile")

    cfg = ConfigManager()
    assert isinstance(cfg.get("updates.remote"), str)
    assert isinstance(cfg.get("updates.branch"), str)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "zlecenia.json").write_text(
        json.dumps([{"nr": 1}]), encoding="utf-8"
    )
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


def test_widok_startowy_persistence(tmp_path, monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()

    users_file = tmp_path / "uzytkownicy.json"
    presence_file = tmp_path / "presence.json"
    users_file.write_text("[]", encoding="utf-8")
    presence_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        ustawienia_uzytkownicy, "_USERS_FILE", str(users_file)
    )
    monkeypatch.setattr(
        ustawienia_uzytkownicy, "_PRESENCE_FILE", str(presence_file)
    )

    frame = ustawienia_uzytkownicy.make_tab(root, "admin")
    form = [w for w in frame.winfo_children() if isinstance(w, ttk.Frame)][0]

    entry_login = [
        w
        for w in form.winfo_children()
        if w.winfo_class() == "TEntry"
        and w.grid_info().get("row") == 0
    ][0]
    root.setvar(entry_login.cget("textvariable"), "jan")

    combo = [
        w
        for w in form.winfo_children()
        if w.winfo_class() == "TCombobox"
    ][0]
    root.setvar(combo.cget("textvariable"), "dashboard")

    btn_save = [
        w
        for w in form.winfo_children()
        if w.winfo_class() == "TButton" and w.cget("text") == "Zapisz"
    ][0]
    btn_save.invoke()
    root.destroy()

    saved = json.loads(users_file.read_text(encoding="utf-8"))
    assert saved[0]["preferencje"]["widok_startowy"] == "dashboard"

