# version: 1.2
# Moduł: settings_users_runtime
# Jednolity układ Ustawienia → Użytkownicy: Użytkownicy | Profile | Rangi.

from __future__ import annotations

from typing import Any

from profile_admin_ui import ProfileAdminNotebook


def _register_tabs(panel: Any, admin: ProfileAdminNotebook) -> None:
    register = getattr(panel, "_register_nested_tab", None)
    top = getattr(panel, "tab_users", None)
    if not callable(register) or top is None:
        return
    for name, widget in (
        ("Użytkownicy", admin.users_tab),
        ("Profile", admin.profile_tab),
        ("Rangi", admin.roles_tab),
    ):
        try:
            register(name, top, admin.nb, widget)
        except Exception:
            pass
    # Zachowaj starszy alias używany przez część nawigacji.
    try:
        register("Profil", top, admin.nb, admin.profile_tab)
    except Exception:
        pass


def _rebuild_profile_admin(panel: Any) -> ProfileAdminNotebook | None:
    """Zastąp wielopoziomowy układ jednym wspólnym notebookiem."""
    root = getattr(panel, "_users_container", None)
    if root is None:
        return None

    current = getattr(panel, "_wm_profile_admin", None)
    try:
        if current is not None and bool(current.winfo_exists()):
            _register_tabs(panel, current)
            return current
    except Exception:
        pass

    for child in list(root.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass

    admin = ProfileAdminNotebook(root, settings_owner=panel)
    admin.pack(fill="both", expand=True, padx=4, pady=4)
    panel._wm_profile_admin = admin
    panel._users_notebook = admin.nb
    _register_tabs(panel, admin)
    return admin


def _open_requested_profile_tab(panel: Any) -> None:
    """Obsłuż przejście Profil → Ustawienia → Profile."""
    try:
        root = panel.winfo_toplevel()
    except Exception:
        return
    target = str(getattr(root, "_wm_settings_target_tab", "") or "").strip().casefold()
    if target not in {"profil", "profile", "profiles"}:
        return

    admin = getattr(panel, "_wm_profile_admin", None)
    if admin is not None:
        try:
            admin.select("Profile")
        except Exception:
            pass
    else:
        opener = getattr(panel, "open_tab", None)
        if callable(opener):
            try:
                opener("Profile")
            except Exception:
                pass
    try:
        delattr(root, "_wm_settings_target_tab")
    except Exception:
        pass


def _decorate(panel: Any) -> None:
    try:
        _rebuild_profile_admin(panel)
    finally:
        _open_requested_profile_tab(panel)


# Nazwy zachowane dla testów/wtyczek starszej wersji runtime.
def _rename_tabs(panel: Any) -> None:
    _rebuild_profile_admin(panel)


def _cleanup_embedded_profile_manager(panel: Any) -> None:
    _rebuild_profile_admin(panel)


def _rebuild_profile_settings(panel: Any) -> None:
    _rebuild_profile_admin(panel)


def install_settings_users_runtime(settings_panel_cls: type) -> None:
    if getattr(settings_panel_cls, "_wm_settings_users_runtime", False):
        return
    original = getattr(settings_panel_cls, "_build_ui", None)
    if not callable(original):
        return

    def _build_ui_with_users(self, *args: Any, **kwargs: Any):
        result = original(self, *args, **kwargs)
        _decorate(self)
        return result

    settings_panel_cls._build_ui = _build_ui_with_users
    settings_panel_cls._wm_settings_users_runtime = True


__all__ = [
    "_cleanup_embedded_profile_manager",
    "_open_requested_profile_tab",
    "_rebuild_profile_admin",
    "_rebuild_profile_settings",
    "_rename_tabs",
    "install_settings_users_runtime",
]
