# version: 1.0
"""Ujednolica Brygadzista → Profile z Ustawienia → Użytkownicy."""
from __future__ import annotations

from profile_admin_ui import ProfileAdminNotebook

_INSTALLED = False


def install() -> None:
    global _INSTALLED
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
        profile_tab = getattr(self, "_tabs", {}).get("Profile")
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
