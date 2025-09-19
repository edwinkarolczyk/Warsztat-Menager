# -*- coding: utf-8 -*-
"""Zakładka "Profile" w ustawieniach aplikacji."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk

USERS_PATH = os.path.join("data", "uzytkownicy.json")


def _load_users() -> list[dict[str, Any]]:
    """Return the list of users stored on disk."""

    if not os.path.exists(USERS_PATH):
        return []
    with open(USERS_PATH, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):  # pragma: no cover - defensive guard
        raise ValueError("Invalid users file structure")
    return [dict(item) for item in data if isinstance(item, dict)]


def _save_users(items: list[dict[str, Any]]) -> None:
    """Persist users to disk using UTF-8 JSON with two-space indent."""

    directory = os.path.dirname(USERS_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(USERS_PATH, "w", encoding="utf-8") as handle:
        json.dump(items, handle, ensure_ascii=False, indent=2)


class SettingsProfilesTab(ttk.Frame):
    """Simple manager for user profiles within the settings window."""

    COLUMNS: tuple[str, ...] = (
        "login",
        "rola",
        "zatrudniony_od",
        "status",
    )

    HEADERS: dict[str, str] = {
        "login": "LOGIN",
        "rola": "ROLA",
        "zatrudniony_od": "ZATRUDNIONY_OD",
        "status": "STATUS",
    }

    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.users: list[dict[str, Any]] = []
        self.tree = self._build_ui()
        self._load_from_storage()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _build_ui(self) -> ttk.Treeview:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=4)
        ttk.Button(toolbar, text="Dodaj profil", command=self._add_profile).pack(
            side="left"
        )
        ttk.Button(toolbar, text="Edytuj", command=self._edit_selected).pack(
            side="left", padx=6
        )
        ttk.Button(toolbar, text="Zapisz", command=self._save_now).pack(side="right")

        tree = ttk.Treeview(
            self,
            columns=self.COLUMNS,
            show="headings",
            height=12,
            selectmode="browse",
        )
        for column in self.COLUMNS:
            tree.heading(column, text=self.HEADERS[column])
            tree.column(column, width=140)
        tree.pack(fill="both", expand=True, pady=(4, 0))
        tree.bind("<Double-1>", lambda _event: self._edit_selected())
        return tree

    def _load_from_storage(self) -> None:
        self.users = [dict(user) for user in _load_users()]
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for user in self.users:
            self.tree.insert(
                "",
                "end",
                values=(
                    user.get("login", ""),
                    user.get("rola", "operator"),
                    user.get("zatrudniony_od", "—"),
                    user.get("status", "aktywny"),
                ),
            )

    def _select_login(self, login: str) -> None:
        for item in self.tree.get_children():
            values = self.tree.item(item).get("values", [])
            if values and values[0] == login:
                self.tree.selection_set(item)
                self.tree.focus(item)
                self.tree.see(item)
                break

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _get_selected_index(self) -> int | None:
        selected = self.tree.selection()
        if not selected:
            return None
        login = self.tree.item(selected[0]).get("values", [""])[0]
        for index, user in enumerate(self.users):
            if user.get("login") == login:
                return index
        return None

    def _login_exists(self, login: str, *, skip_index: int | None = None) -> bool:
        for index, user in enumerate(self.users):
            if skip_index is not None and index == skip_index:
                continue
            if user.get("login") == login:
                return True
        return False

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _add_profile(self) -> None:
        ProfileEditDialog(self, on_ok=self._on_added)

    def _on_added(self, item: dict[str, Any]) -> bool:
        login = item.get("login", "")
        if self._login_exists(login):
            messagebox.showerror("Profil", "Login już istnieje.")
            return False
        self.users.append(item)
        self._refresh_tree()
        self._select_login(login)
        return True

    def _edit_selected(self) -> None:
        index = self._get_selected_index()
        if index is None:
            messagebox.showinfo("Profil", "Wybierz profil do edycji.")
            return
        ProfileEditDialog(
            self,
            seed=self.users[index],
            on_ok=lambda item: self._on_edited(index, item),
        )

    def _on_edited(self, index: int, item: dict[str, Any]) -> bool:
        login = item.get("login", "")
        if self._login_exists(login, skip_index=index):
            messagebox.showerror("Profil", "Login już istnieje.")
            return False
        self.users[index] = item
        self._refresh_tree()
        self._select_login(login)
        return True

    def _save_now(self) -> None:
        _save_users([dict(user) for user in self.users])
        messagebox.showinfo("Profile", "Zapisano zmiany.")


class ProfileEditDialog(tk.Toplevel):
    """Dialog window for creating or editing a single profile entry."""

    ROLES = ["operator", "serwisant", "brygadzista", "admin"]
    STATUSES = ["aktywny", "zablokowany"]

    def __init__(
        self,
        master: tk.Misc,
        seed: dict[str, Any] | None = None,
        on_ok: Callable[[dict[str, Any]], bool | None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Profil użytkownika")
        self.resizable(False, False)
        self.on_ok = on_ok

        defaults = {
            "login": "",
            "rola": "operator",
            "zatrudniony_od": "",
            "status": "aktywny",
            "disabled_modules": [],
        }
        self.seed: dict[str, Any] = dict(defaults)
        if seed:
            self.seed.update(seed)

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build(self) -> None:
        self.geometry("420x220")
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Login:").grid(row=0, column=0, sticky="w")
        self.v_login = tk.StringVar(value=self.seed.get("login", ""))
        ttk.Entry(frame, textvariable=self.v_login).grid(row=0, column=1, sticky="ew")

        ttk.Label(frame, text="Rola:").grid(row=1, column=0, sticky="w")
        self.v_role = tk.StringVar(value=self.seed.get("rola", "operator"))
        ttk.Combobox(
            frame,
            textvariable=self.v_role,
            values=self.ROLES,
            state="readonly",
        ).grid(row=1, column=1, sticky="ew")

        ttk.Label(frame, text="Zatrudniony od (YYYY-MM-DD):").grid(
            row=2, column=0, sticky="w"
        )
        self.v_date = tk.StringVar(value=self.seed.get("zatrudniony_od", ""))
        ttk.Entry(frame, textvariable=self.v_date).grid(row=2, column=1, sticky="ew")

        ttk.Label(frame, text="Status:").grid(row=3, column=0, sticky="w")
        self.v_status = tk.StringVar(value=self.seed.get("status", "aktywny"))
        ttk.Combobox(
            frame,
            textvariable=self.v_status,
            values=self.STATUSES,
            state="readonly",
        ).grid(row=3, column=1, sticky="ew")

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="OK", command=self._ok).pack(side="left", padx=4)
        ttk.Button(buttons, text="Anuluj", command=self.destroy).pack(
            side="left", padx=4
        )

        frame.columnconfigure(1, weight=1)

    def _ok(self) -> None:
        item = dict(self.seed)
        item.update(
            {
                "login": self.v_login.get().strip(),
                "rola": self.v_role.get().strip() or "operator",
                "zatrudniony_od": self.v_date.get().strip(),
                "status": self.v_status.get().strip() or "aktywny",
            }
        )
        item.setdefault("disabled_modules", [])

        if not item["login"]:
            messagebox.showwarning("Profil", "Login jest wymagany.")
            return

        if self.on_ok and self.on_ok(item) is False:
            return
        self.destroy()


def make_tab(parent: tk.Misc, _role: str | None = None) -> SettingsProfilesTab:
    """Compatibility helper used by starsze testy/UI."""

    tab = SettingsProfilesTab(parent)
    tab.pack(fill="both", expand=True)
    return tab


__all__ = [
    "SettingsProfilesTab",
    "ProfileEditDialog",
    "_load_users",
    "_save_users",
    "make_tab",
]
