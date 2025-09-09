import pytest
import tkinter as tk
import gui_panel


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    r.withdraw()
    yield r
    r.destroy()


def test_disabled_modules_hide_buttons(root, monkeypatch):
    monkeypatch.setattr(
        gui_panel, "get_user", lambda login: {"login": login, "disabled_modules": ["narzedzia"]}
    )
    gui_panel.uruchom_panel(root, "demo", "user")
    side = root.winfo_children()[0]
    texts = [w.cget("text") for w in side.winfo_children() if hasattr(w, "cget")]
    assert "Narzędzia" not in texts
    assert "Zlecenia" in texts


def test_disabled_profile_module(root, monkeypatch):
    monkeypatch.setattr(
        gui_panel,
        "get_user",
        lambda login: {"login": login, "disabled_modules": ["profil"]},
    )
    gui_panel.uruchom_panel(root, "demo", "user")
    side = root.winfo_children()[0]
    texts = [w.cget("text") for w in side.winfo_children() if hasattr(w, "cget")]
    assert "Profil" not in texts
    assert "Zlecenia" in texts
