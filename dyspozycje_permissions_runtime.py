# version: 1.0
"""Stabilizuje rozpoznawanie roli i ładowanie kreatora Dyspozycji."""
from __future__ import annotations

import logging

_INSTALLED = False
logger = logging.getLogger(__name__)


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    import gui_zlecenia as dysp

    cls = dysp.ZleceniaView
    if getattr(cls, "_wm_permissions_runtime_installed", False):
        _INSTALLED = True
        return

    original_resolve_role = cls._resolve_login_role

    def _resolve_login_role(self) -> str:
        role = str(original_resolve_role(self) or "").strip().lower()
        if role:
            return role

        login = str(getattr(self, "_login_user", "") or "").strip().lower()
        if not login:
            return ""
        try:
            profiles = dysp.ProfileService.list_profiles()
        except Exception:
            profiles = []
        for profile in profiles or []:
            if not isinstance(profile, dict):
                continue
            if str(profile.get("login") or "").strip().lower() != login:
                continue
            return str(profile.get("rola") or profile.get("role") or "").strip().lower()
        return ""

    cls._resolve_login_role = _resolve_login_role

    # Kreator jest zwracany jako funkcja leniwa. Dzięki temu chwilowy problem
    # kolejności importów przy starcie nie wyłącza na stałe Dodaj/Edytuj.
    # Rzeczywisty błąd importu jest logowany i zostanie pokazany przez istniejący
    # handler _on_add/_on_edit.
    def _resolve_creator():
        def _open(*args, **kwargs):
            try:
                from gui_dyspozycje_creator import open_dyspozycje_creator
            except Exception as exc:
                dysp.logger.exception(
                    "[DYSP] Nie udało się załadować kreatora Dyspozycji: %s",
                    exc,
                )
                raise
            return open_dyspozycje_creator(*args, **kwargs)

        return _open

    dysp._resolve_creator = _resolve_creator
    cls._wm_permissions_runtime_installed = True
    _INSTALLED = True


__all__ = ["install"]
