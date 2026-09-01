# version: 1.2
"""Ujednolica Profile brygadzisty i podpina drobne akcje aktywnego Profilu."""
from __future__ import annotations

from profile_admin_ui import ProfileAdminNotebook

_INSTALLED = False


def install() -> None:
    global _INSTALLED

    # Ta warstwa jest ładowana przez gui_profile przed zdefiniowaniem końcowej
    # klasy ProfileView. Patchujemy więc klasę bazową: końcowy widok nadal
    # dziedziczy poprawione "Edytuj mój profil" i obsługę zamykania Dyspozycji.
    try:
        import gui_profile_core as profile_core
        from profile_user_actions_runtime import install as install_user_actions

        install_user_actions(profile_core.ProfileView)
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] user actions runtime install failed: {exc!r}")

    if _INSTALLED:
        return

    import gui_profile_foreman as foreman

    cls = foreman.ForemanProfilePanel
    if getattr(cls, "_wm_profile_admin_unified", False):
        _INSTALLED = True
        return

    original_build = cls._build

    def _build(self, *args, **kwargs):
        result = original_build(self, *args, **kwargs)

        # Zadania i Sprzęt pozostają w kodzie i nadal mogą zasilać Pulpit/
        # statystyki, ale nie są pokazywane jako osobne zakładki brygadzisty.
        notebook = getattr(self, "notebook", None)
        tabs = getattr(self, "_tabs", {})
        if notebook is not None:
            for tab_name in ("Zadania", "Sprzęt"):
                tab = tabs.get(tab_name)
                if tab is None:
                    continue
                try:
                    notebook.hide(tab)
                except Exception:
                    pass

        profile_tab = tabs.get("Profile")
        if profile_tab is None:
            return result

        for child in list(profile_tab.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        admin = ProfileAdminNotebook(profile_tab)
        admin.pack(fill="both", expand=True)
        self._wm_profile_admin = admin
        return result

    cls._build = _build
    cls._wm_profile_admin_unified = True
    _INSTALLED = True


__all__ = ["install"]
