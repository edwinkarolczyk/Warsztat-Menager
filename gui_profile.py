# version: 1.8.0
"""Aktywny Profil WM z opcjonalną zakładką Brygadzista.

Dotychczasowy kod Profilu pozostaje w :mod:`gui_profile_core` bez zmian.
Ten moduł zachowuje jego publiczne i prywatne API, a rozszerza wyłącznie
aktywną klasę ``ProfileView`` o panel przeznaczony dla roli ``brygadzista``.
"""
from __future__ import annotations

import gui_profile_core as _core

# Zachowaj zgodność z kodem i testami importującymi także pomocnicze nazwy
# bezpośrednio z gui_profile.py.
for _name in dir(_core):
    if _name in {
        "__name__",
        "__package__",
        "__loader__",
        "__spec__",
        "__file__",
        "__cached__",
        "ProfileView",
    }:
        continue
    globals()[_name] = getattr(_core, _name)

_BaseProfileView = _core.ProfileView


class ProfileView(_BaseProfileView):
    """Profil użytkownika rozszerzony o panel brygadzisty."""

    def _render_profile_body(self, parent) -> None:
        """Pokaż zwykły Profil lub Profil + Brygadzista zależnie od roli."""
        if self._is_brygadzista():
            try:
                from gui_profile_foreman import build_profile_with_foreman_tabs

                build_profile_with_foreman_tabs(
                    parent,
                    self,
                    self._render_simple_profile,
                )
                return
            except Exception as exc:
                log_akcja(
                    f"[WM-ERR][FOREMAN] Nie udało się zbudować panelu brygadzisty: {exc}"
                )
        self._render_simple_profile(parent)

    def _build_simple_profile(self) -> None:
        body = ttk.Frame(self, style="WM.Container.TFrame")
        body.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self._simple_container = body
        self._render_profile_body(body)

    def _refresh_view(self) -> None:
        """Odśwież Profil bez gubienia karty Brygadzista."""
        self._reload_profile_data()
        if self._header_container is not None:
            for child in self._header_container.winfo_children():
                child.destroy()
            self._build_header(self._header_container)
        if self._simple_container is not None:
            for child in self._simple_container.winfo_children():
                child.destroy()
            self._render_profile_body(self._simple_container)


# Zachowaj semantykę dawnego `from gui_profile import *`.
_core_all = getattr(_core, "__all__", None)
if _core_all is not None:
    __all__ = list(_core_all)
    if "ProfileView" not in __all__:
        __all__.append("ProfileView")
else:
    __all__ = sorted(name for name in globals() if not name.startswith("_"))
