# WM-VERSION: 0.1

import tkinter as tk

from narzedzia_ui.editor_media_guard_runtime import _logged_wm_actor
from services.profile_service import ProfileService


def test_information_author_uses_active_wm_profile(monkeypatch):
    monkeypatch.setattr(tk, "_default_root", None)
    monkeypatch.setattr(
        ProfileService,
        "ensure_active_user_or_none",
        staticmethod(lambda: "Edwin"),
    )
    assert _logged_wm_actor() == "Edwin"


def test_information_author_never_falls_back_to_windows_username(monkeypatch):
    monkeypatch.setattr(tk, "_default_root", None)
    monkeypatch.setenv("USERNAME", "Metalbox_Warsztat")
    monkeypatch.setenv("USER", "Metalbox_Warsztat")
    monkeypatch.setattr(
        ProfileService,
        "ensure_active_user_or_none",
        staticmethod(lambda: None),
    )
    assert _logged_wm_actor() == "—"
