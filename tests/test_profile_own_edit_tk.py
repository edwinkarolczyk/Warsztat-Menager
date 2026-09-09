# version: 1.0
import tkinter as tk
from tkinter import ttk

import gui_profile


def _texts(widget):
    out = []
    try:
        text = str(widget.cget("text") or "")
    except Exception:
        text = ""
    if text:
        out.append(text)
    for child in widget.winfo_children():
        out.extend(_texts(child))
    return out


def test_regular_profile_shows_own_edit_and_no_admin_banner(monkeypatch):
    monkeypatch.setattr(
        gui_profile._BaseProfileView,
        "_render_simple_profile",
        lambda _self, _parent: None,
    )
    calls = []
    monkeypatch.setattr(
        gui_profile.ProfileView,
        "_open_edit_profile",
        lambda _self: calls.append("edit"),
    )

    root = tk.Tk()
    try:
        parent = ttk.Frame(root)
        parent.pack(fill="both", expand=True)
        view = gui_profile.ProfileView.__new__(gui_profile.ProfileView)
        gui_profile.ProfileView._render_simple_profile(view, parent)
        root.update_idletasks()

        texts = _texts(parent)
        assert "Mój profil" in texts
        assert "Edytuj mój profil" in texts
        assert "Administracja profili" not in texts
        assert "Ustawienia profili" not in texts

        button = next(
            child
            for frame in parent.winfo_children()
            for child in frame.winfo_children()
            if isinstance(child, ttk.Button)
            and str(child.cget("text")) == "Edytuj mój profil"
        )
        button.invoke()
        assert calls == ["edit"]
    finally:
        root.destroy()
