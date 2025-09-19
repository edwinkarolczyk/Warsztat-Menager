import tkinter as tk
from typing import Any

import pytest

import ustawienia_uzytkownicy


def _make_root() -> tk.Tk:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    return root


def _sample_user(login: str, **extra: Any) -> dict[str, Any]:
    data = {
        "login": login,
        "rola": "operator",
        "zatrudniony_od": "2024-01-01",
        "status": "aktywny",
    }
    data.update(extra)
    return data


def test_load_and_save_users_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "users.json"
    monkeypatch.setattr(ustawienia_uzytkownicy, "USERS_PATH", str(path))

    assert ustawienia_uzytkownicy._load_users() == []

    users = [_sample_user("anna"), _sample_user("piotr", status="zablokowany")]
    ustawienia_uzytkownicy._save_users(users)

    loaded = ustawienia_uzytkownicy._load_users()
    assert loaded == users


def test_profiles_tab_populates_tree(monkeypatch):
    root = _make_root()
    users = [_sample_user("anna"), _sample_user("piotr", rola="admin")]
    monkeypatch.setattr(ustawienia_uzytkownicy, "_load_users", lambda: users)

    tab = ustawienia_uzytkownicy.SettingsProfilesTab(root)

    rows = [tab.tree.item(item)["values"] for item in tab.tree.get_children()]
    assert rows == [
        ["anna", "operator", "2024-01-01", "aktywny"],
        ["piotr", "admin", "2024-01-01", "aktywny"],
    ]

    root.destroy()


def test_add_duplicate_login_shows_error(monkeypatch):
    root = _make_root()
    users = [_sample_user("anna"), _sample_user("piotr")]
    monkeypatch.setattr(ustawienia_uzytkownicy, "_load_users", lambda: users.copy())

    errors: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        ustawienia_uzytkownicy.messagebox,
        "showerror",
        lambda *args: errors.append(args),
    )

    tab = ustawienia_uzytkownicy.SettingsProfilesTab(root)
    result = tab._on_added(_sample_user("anna"))

    assert result is False
    assert len(tab.users) == len(users)
    assert errors

    root.destroy()


def test_edit_profile_updates_tree(monkeypatch):
    root = _make_root()
    users = [_sample_user("anna"), _sample_user("piotr")]
    monkeypatch.setattr(ustawienia_uzytkownicy, "_load_users", lambda: users.copy())

    tab = ustawienia_uzytkownicy.SettingsProfilesTab(root)
    updated = _sample_user("anna", rola="admin", status="zablokowany")
    result = tab._on_edited(0, updated)

    assert result is True
    first_row = tab.tree.item(tab.tree.get_children()[0])["values"]
    assert first_row == ["anna", "admin", "2024-01-01", "zablokowany"]

    root.destroy()


def test_save_now_invokes_persistence(monkeypatch):
    root = _make_root()
    users = [_sample_user("anna"), _sample_user("piotr")]
    monkeypatch.setattr(ustawienia_uzytkownicy, "_load_users", lambda: users.copy())

    saved: dict[str, Any] = {}
    monkeypatch.setattr(
        ustawienia_uzytkownicy,
        "_save_users",
        lambda items: saved.setdefault("items", items.copy()),
    )
    infos: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        ustawienia_uzytkownicy.messagebox,
        "showinfo",
        lambda *args: infos.append(args),
    )

    tab = ustawienia_uzytkownicy.SettingsProfilesTab(root)
    tab.users[0]["status"] = "zablokowany"
    tab._save_now()

    assert saved["items"][0]["status"] == "zablokowany"
    assert infos

    root.destroy()


def test_profile_edit_dialog_requires_login(monkeypatch):
    root = _make_root()
    warnings: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        ustawienia_uzytkownicy.messagebox,
        "showwarning",
        lambda *args: warnings.append(args),
    )

    dialog = ustawienia_uzytkownicy.ProfileEditDialog(root, on_ok=lambda item: True)
    dialog.v_login.set("   ")
    dialog._ok()

    assert warnings
    assert dialog.winfo_exists()

    dialog.destroy()
    root.destroy()


def test_profile_edit_dialog_preserves_additional_fields(monkeypatch):
    root = _make_root()

    captured: list[dict[str, Any]] = []

    def on_ok(item: dict[str, Any]) -> bool:
        captured.append(item)
        return True

    seed = _sample_user("anna", disabled_modules=["narzedzia"], extra="value")
    dialog = ustawienia_uzytkownicy.ProfileEditDialog(root, seed=seed, on_ok=on_ok)
    dialog.v_login.set(" anna ")
    dialog.v_role.set("")
    dialog.v_date.set("2025-02-02")
    dialog.v_status.set("")
    dialog._ok()

    assert captured
    item = captured[0]
    assert item["login"] == "anna"
    assert item["rola"] == "operator"
    assert item["zatrudniony_od"] == "2025-02-02"
    assert item["disabled_modules"] == ["narzedzia"]
    assert item["extra"] == "value"
    assert not dialog.winfo_exists()

    root.destroy()
