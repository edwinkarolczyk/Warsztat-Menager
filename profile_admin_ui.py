# version: 1.1
"""Wspólny interfejs administracji profilami dla Ustawień i panelu brygadzisty."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from config_manager import ConfigManager
from profile_settings_fields import EDITABLE_PROFILE_FIELDS, editable_fields_csv, normalize_editable_fields
from services.profile_service import ProfileService
from wm_access import get_role_modules, normalize_module_name, normalize_role_name, set_role_modules


def _legacy_profiles_module():
    import ustawienia_uzytkownicy as legacy

    return legacy


def _invalidate_profile_cache() -> None:
    try:
        ProfileService._profiles_cache = None
    except Exception:
        pass


def _is_active_user(user: dict[str, Any]) -> bool:
    """Czy konto jest aktywne; obsługuje nowe i starsze nazwy pola."""
    if "active" in user:
        return bool(user.get("active"))
    if "aktywny" in user:
        return bool(user.get("aktywny"))
    status = str(user.get("status") or "").strip().casefold()
    if status in {"archiwalny", "nieaktywny", "dezaktywowany", "inactive"}:
        return False
    return True


class UsersAdminPanel(ttk.Frame):
    """Płaski menedżer kont użytkowników bez dodatkowego Notebooka."""

    COLUMNS = ("login", "pin", "rola", "zatrudniony_od", "status")
    HEADERS = {
        "login": "LOGIN",
        "pin": "PIN",
        "rola": "ROLA",
        "zatrudniony_od": "ZATRUDNIONY OD",
        "status": "STATUS",
    }

    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.users: list[dict[str, Any]] = []
        self._build()
        self.reload()

    def _build(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(toolbar, text="Dodaj profil", command=self._add_profile).pack(side="left")
        ttk.Button(toolbar, text="Edytuj", command=self._edit_selected).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Dezaktywuj profil", command=self._deactivate_selected).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Zapisz", command=self._save_now).pack(side="right")

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            wrap,
            columns=self.COLUMNS,
            show="headings",
            selectmode="browse",
            height=14,
        )
        for column in self.COLUMNS:
            self.tree.heading(column, text=self.HEADERS[column])
            width = 85 if column == "pin" else 150
            self.tree.column(column, width=width, stretch=True)
        y = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=y.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda _event: self._edit_selected())

    def reload(self) -> None:
        legacy = _legacy_profiles_module()
        try:
            self.users = [dict(user) for user in legacy._load_users()]
        except Exception as exc:
            messagebox.showerror("Profile", f"Nie udało się wczytać profili:\n{exc}", parent=self)
            self.users = []
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for user in self.users:
            pin_state = "Ustawiony" if str(user.get("pin") or "").strip() else "—"
            status = "aktywny" if _is_active_user(user) else "archiwalny"
            self.tree.insert(
                "",
                "end",
                values=(
                    user.get("login", ""),
                    pin_state,
                    user.get("rola", "operator"),
                    user.get("zatrudniony_od", "—"),
                    status,
                ),
            )

    def _selected_index(self) -> int | None:
        selected = self.tree.selection()
        if not selected:
            return None
        values = self.tree.item(selected[0]).get("values", [])
        login = str(values[0]) if values else ""
        for index, user in enumerate(self.users):
            if str(user.get("login") or "") == login:
                return index
        return None

    def _select_login(self, login: str) -> None:
        for item in self.tree.get_children():
            values = self.tree.item(item).get("values", [])
            if values and str(values[0]) == str(login):
                self.tree.selection_set(item)
                self.tree.focus(item)
                self.tree.see(item)
                return

    def _login_exists(self, login: str, skip_index: int | None = None) -> bool:
        key = str(login or "").strip().casefold()
        for index, user in enumerate(self.users):
            if skip_index is not None and index == skip_index:
                continue
            if str(user.get("login") or "").strip().casefold() == key:
                return True
        return False

    def _add_profile(self) -> None:
        legacy = _legacy_profiles_module()
        legacy.ProfileEditDialog(self, on_ok=self._on_added)

    def _on_added(self, item: dict[str, Any]) -> bool:
        login = str(item.get("login") or "").strip()
        if self._login_exists(login):
            messagebox.showerror("Profil", "Login już istnieje.", parent=self)
            return False
        prepared = dict(item)
        prepared.setdefault("active", True)
        prepared.setdefault("aktywny", True)
        prepared.setdefault("status", "aktywny")
        self.users.append(prepared)
        self._refresh_tree()
        self._select_login(login)
        return True

    def _edit_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Profil", "Wybierz profil do edycji.", parent=self)
            return
        legacy = _legacy_profiles_module()
        legacy.ProfileEditDialog(
            self,
            seed=self.users[index],
            on_ok=lambda item: self._on_edited(index, item),
        )

    def _on_edited(self, index: int, item: dict[str, Any]) -> bool:
        login = str(item.get("login") or "").strip()
        if self._login_exists(login, skip_index=index):
            messagebox.showerror("Profil", "Login już istnieje.", parent=self)
            return False
        previous = dict(self.users[index])
        updated = dict(item)
        # Edycja profilu nie może przypadkiem reaktywować zarchiwizowanego konta.
        if not _is_active_user(previous):
            updated["active"] = False
            updated["aktywny"] = False
            updated["status"] = "archiwalny"
        self.users[index] = updated
        self._refresh_tree()
        self._select_login(login)
        return True

    def _save_now(self) -> None:
        legacy = _legacy_profiles_module()
        legacy._save_users([dict(user) for user in self.users])
        _invalidate_profile_cache()
        messagebox.showinfo("Profile", "Zapisano zmiany.", parent=self)

    def _deactivate_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Dezaktywuj profil", "Zaznacz użytkownika do dezaktywacji.", parent=self)
            return
        user = self.users[index]
        login = str(user.get("login") or "").strip()
        if not _is_active_user(user):
            messagebox.showinfo("Dezaktywuj profil", "Ten profil jest już zarchiwizowany.", parent=self)
            return
        try:
            active_login = str(ProfileService.ensure_active_user_or_none() or "").strip()
        except Exception:
            active_login = ""
        if active_login and active_login.casefold() == login.casefold():
            messagebox.showerror(
                "Dezaktywuj profil",
                "Nie można dezaktywować aktualnie zalogowanego użytkownika.",
                parent=self,
            )
            return
        active_admins = sum(
            1
            for item in self.users
            if _is_active_user(item)
            and normalize_role_name(item.get("rola", "")) == "administrator"
        )
        if normalize_role_name(user.get("rola", "")) == "administrator" and active_admins <= 1:
            messagebox.showerror(
                "Dezaktywuj profil",
                "Nie można dezaktywować ostatniego aktywnego administratora.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Dezaktywuj profil",
            f"Zarchiwizować profil '{login}'? Historia i user_id pozostaną zachowane.",
            parent=self,
        ):
            return

        user["active"] = False
        user["aktywny"] = False
        user["status"] = "archiwalny"
        user["deactivated_at"] = __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")
        legacy = _legacy_profiles_module()
        legacy._save_users([dict(entry) for entry in self.users])
        _invalidate_profile_cache()
        self._refresh_tree()
        self._select_login(login)


class RolesAdminPanel(ttk.Frame):
    """Płaski edytor uprawnień rang."""

    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        legacy = _legacy_profiles_module()
        self.role_labels = list(legacy.ROLE_LABELS)
        self.module_labels = list(legacy.MODULE_LABELS)
        self._vars: dict[str, tk.BooleanVar] = {}
        self._build()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="ns", padx=(10, 12), pady=10)
        ttk.Label(left, text="Rangi / role").pack(anchor="w", pady=(0, 6))
        self.roles = tk.Listbox(left, height=12, exportselection=False)
        self.roles.pack(fill="y", expand=True)
        for _role_key, role_label in self.role_labels:
            self.roles.insert("end", role_label)

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        right.columnconfigure(0, weight=1)
        self.title_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.title_var).grid(row=0, column=0, sticky="w", pady=(0, 8))
        checks = ttk.Frame(right)
        checks.grid(row=1, column=0, sticky="nsew")
        for idx, (module_key, module_label) in enumerate(self.module_labels):
            var = tk.BooleanVar(value=False)
            self._vars[module_key] = var
            ttk.Checkbutton(checks, text=module_label, variable=var).grid(
                row=idx, column=0, sticky="w", pady=2
            )
        self.roles.bind("<<ListboxSelect>>", self._load_role)
        ttk.Button(right, text="Zapisz rangę", command=self._save_role).grid(
            row=2, column=0, sticky="e", pady=(12, 0)
        )
        if self.role_labels:
            self.roles.selection_set(0)
            self._load_role()

    def _selected_role_key(self) -> str:
        selected = self.roles.curselection()
        return self.role_labels[int(selected[0])][0] if selected else ""

    def _load_role(self, _event=None) -> None:
        role_key = self._selected_role_key()
        if not role_key:
            return
        self.title_var.set(f"Uprawnienia rangi: {dict(self.role_labels).get(role_key, role_key)}")
        modules = get_role_modules(role_key)
        for module_key, var in self._vars.items():
            var.set(bool(modules.get(normalize_module_name(module_key), False)))

    def _save_role(self) -> None:
        role_key = self._selected_role_key()
        if not role_key:
            messagebox.showwarning("Rangi", "Wybierz rangę do zapisania.", parent=self)
            return
        modules_map = {module_key: bool(var.get()) for module_key, var in self._vars.items()}
        set_role_modules(normalize_role_name(role_key), modules_map)
        messagebox.showinfo("Rangi", "Zapisano uprawnienia rangi.", parent=self)


class ProfileSettingsPanel(ttk.Frame):
    """Ustawienia wyglądu i samodzielnej edycji Profilu."""

    def __init__(self, master: tk.Misc, *, settings_owner: Any | None = None, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.settings_owner = settings_owner
        self.cfg = getattr(settings_owner, "cfg", None) or ConfigManager()
        self._standalone = settings_owner is None
        self._prepare_vars()
        self._build()

    def _cfg_bool(self, key: str, fallback_key: str, default: bool) -> bool:
        value = self.cfg.get(key, None)
        if value is None:
            value = self.cfg.get(fallback_key, default)
        return bool(value)

    def _prepare_vars(self) -> None:
        owner = self.settings_owner
        if owner is not None:
            self.var_enabled = owner.var_profile_enabled
            self.var_header = owner.var_profile_header
            self.var_avatar = owner.var_profile_avatar
            self.var_pin = owner.var_profile_pin_change
            self.var_fields = owner.var_profile_editable_fields
            self.var_fields.set(editable_fields_csv(self.var_fields.get()))
            return
        self.var_enabled = tk.BooleanVar(
            master=self,
            value=self._cfg_bool("profiles.ui.enable_profile_card", "ui.profile.enabled", True),
        )
        self.var_header = tk.BooleanVar(
            master=self,
            value=self._cfg_bool("profiles.ui.show_name_in_header", "ui.profile.show_name_header", True),
        )
        self.var_avatar = tk.BooleanVar(
            master=self,
            value=self._cfg_bool("profiles.avatar.enabled", "ui.profile.avatar_enabled", False),
        )
        self.var_pin = tk.BooleanVar(
            master=self,
            value=self._cfg_bool("profiles.pin.change_allowed", "profiles.allow_pin_change", False),
        )
        raw = self.cfg.get("profiles.editable_fields", None)
        if raw is None:
            raw = self.cfg.get("profiles.fields_editable_by_user", ["telefon", "email"])
        self.var_fields = tk.StringVar(master=self, value=editable_fields_csv(raw))

    def _changed(self) -> None:
        owner = self.settings_owner
        if owner is None:
            return
        marker = getattr(owner, "_mark_dirty", None)
        if callable(marker):
            try:
                marker()
            except Exception:
                pass
        else:
            try:
                owner._dirty = True
                owner._unsaved = True
            except Exception:
                pass
        status = getattr(owner, "_mark_save_dirty", None)
        if callable(status):
            try:
                status()
            except Exception:
                pass

    def _build(self) -> None:
        intro = ttk.Label(
            self,
            text="Jedno źródło ustawień Profilu. Zmiany pól poniżej określają dokładnie, co użytkownik może zmienić w „Edytuj mój profil”.",
            wraplength=900,
            justify="left",
        )
        intro.pack(anchor="w", padx=12, pady=(10, 8))

        groups = ttk.Frame(self)
        groups.pack(fill="x", padx=10, pady=(0, 8))
        groups.columnconfigure(0, weight=1)
        groups.columnconfigure(1, weight=1)

        visibility = ttk.LabelFrame(groups, text="Widoczność profilu")
        visibility.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ttk.Checkbutton(
            visibility, text="Włącz kartę Profil", variable=self.var_enabled, command=self._changed
        ).pack(anchor="w", padx=10, pady=(8, 4))
        ttk.Checkbutton(
            visibility, text="Pokazuj imię w nagłówku", variable=self.var_header, command=self._changed
        ).pack(anchor="w", padx=10, pady=4)
        ttk.Checkbutton(
            visibility, text="Włącz avatar", variable=self.var_avatar, command=self._changed
        ).pack(anchor="w", padx=10, pady=(4, 8))

        edit = ttk.LabelFrame(groups, text="Edycja własnego profilu")
        edit.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ttk.Checkbutton(
            edit,
            text="Zezwól użytkownikowi na zmianę PIN",
            variable=self.var_pin,
            command=self._changed,
        ).pack(anchor="w", padx=10, pady=(8, 6))
        ttk.Label(edit, text="Pola, które użytkownik może edytować:").pack(
            anchor="w", padx=10, pady=(2, 4)
        )
        fields_frame = ttk.Frame(edit)
        fields_frame.pack(fill="x", padx=8, pady=(0, 8))

        selected = set(normalize_editable_fields(self.var_fields.get()))
        self.field_vars: dict[str, tk.BooleanVar] = {}

        def sync_fields() -> None:
            values = [key for key, _label in EDITABLE_PROFILE_FIELDS if self.field_vars[key].get()]
            self.var_fields.set(", ".join(values))
            self._changed()

        for idx, (key, label) in enumerate(EDITABLE_PROFILE_FIELDS):
            var = tk.BooleanVar(master=fields_frame, value=key in selected)
            self.field_vars[key] = var
            ttk.Checkbutton(fields_frame, text=label, variable=var, command=sync_fields).grid(
                row=idx // 2,
                column=idx % 2,
                sticky="w",
                padx=(2, 18),
                pady=3,
            )

        note = ttk.Label(
            self,
            text="Konta użytkowników są w zakładce Użytkownicy, a uprawnienia rang w zakładce Rangi.",
        )
        note.pack(anchor="w", padx=12, pady=(0, 8))

        if self._standalone:
            ttk.Button(self, text="Zapisz ustawienia profilu", command=self.save).pack(
                anchor="e", padx=12, pady=(0, 10)
            )

    def save(self) -> None:
        values = normalize_editable_fields(self.var_fields.get())
        self.var_fields.set(", ".join(values))
        self.cfg.set("profiles.ui.enable_profile_card", bool(self.var_enabled.get()))
        self.cfg.set("profiles.ui.show_name_in_header", bool(self.var_header.get()))
        self.cfg.set("profiles.avatar.enabled", bool(self.var_avatar.get()))
        self.cfg.set("profiles.pin.change_allowed", bool(self.var_pin.get()))
        self.cfg.set("profiles.editable_fields", values)
        self.cfg.save_all()
        messagebox.showinfo("Profile", "Zapisano ustawienia profilu.", parent=self)


class ProfileAdminNotebook(ttk.Frame):
    """Jednolity układ: Użytkownicy | Profile | Rangi."""

    def __init__(self, master: tk.Misc, *, settings_owner: Any | None = None, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.users_tab = ttk.Frame(self.nb)
        self.profile_tab = ttk.Frame(self.nb)
        self.roles_tab = ttk.Frame(self.nb)
        self.nb.add(self.users_tab, text="Użytkownicy")
        self.nb.add(self.profile_tab, text="Profile")
        self.nb.add(self.roles_tab, text="Rangi")

        self.users_panel = UsersAdminPanel(self.users_tab)
        self.users_panel.pack(fill="both", expand=True)
        self.profile_panel = ProfileSettingsPanel(
            self.profile_tab,
            settings_owner=settings_owner,
        )
        self.profile_panel.pack(fill="both", expand=True)
        self.roles_panel = RolesAdminPanel(self.roles_tab)
        self.roles_panel.pack(fill="both", expand=True)

    def select(self, name: str) -> bool:
        wanted = str(name or "").strip().casefold()
        for tab in self.nb.tabs():
            text = str(self.nb.tab(tab, "text") or "").strip().casefold()
            if text == wanted:
                self.nb.select(tab)
                return True
        return False


__all__ = [
    "ProfileAdminNotebook",
    "ProfileSettingsPanel",
    "RolesAdminPanel",
    "UsersAdminPanel",
]
