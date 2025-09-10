import json
import tkinter as tk
from pathlib import Path

import pytest

import gui_panel
import ustawienia_uzytkownicy
from services import profile_service


def _make_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    return root


@pytest.fixture
def temp_users(tmp_path, monkeypatch):
    src = Path("uzytkownicy.json").read_text(encoding="utf-8")
    users_path = tmp_path / "uzytkownicy.json"
    users_path.write_text(src, encoding="utf-8")
    monkeypatch.setattr(ustawienia_uzytkownicy, "_USERS_FILE", str(users_path))
    monkeypatch.setattr(ustawienia_uzytkownicy, "_PRESENCE_FILE", str(tmp_path / "presence.json"))
    monkeypatch.setattr(ustawienia_uzytkownicy, "_sync_presence", lambda users: None)
    return users_path


def test_toggle_modules_persist_and_affect_gui(temp_users, monkeypatch):
    root = _make_root()
    tab = ustawienia_uzytkownicy.make_tab(root, "admin")
    lb = tab.lb
    lb.selection_set(0)
    lb.event_generate("<<ListboxSelect>>")
    tab.module_vars["narzedzia"].set(True)
    tab.btn_save.invoke()
    root.destroy()

    data = json.loads(temp_users.read_text(encoding="utf-8"))
    edwin = next(u for u in data if u["login"] == "edwin")
    assert "narzedzia" in edwin["disabled_modules"]

    root2 = _make_root()
    monkeypatch.setattr(
        gui_panel,
        "get_user",
        lambda login: profile_service.get_user(login, file_path=str(temp_users)),
    )
    gui_panel.uruchom_panel(root2, "edwin", "brygadzista")
    side = root2.winfo_children()[0]
    texts = [w.cget("text") for w in side.winfo_children() if hasattr(w, "cget")]
    assert "Narzędzia" not in texts
    root2.destroy()
