# version: 1.7
"""Ujednolica Profile brygadzisty i podpina aktywne rozszerzenia Profilu."""
from __future__ import annotations

_INSTALLED = False


def _install_workforce_extensions() -> None:
    """Ładuj rozszerzenia po bazowych patchach, żeby nie zmieniać layoutu Profilu."""
    try:
        from profile_workforce_runtime import install as install_workforce
        install_workforce()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] workforce runtime install failed: {exc!r}")
    try:
        from profile_leave_card_runtime import install as install_leave_card
        install_leave_card()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] leave card runtime install failed: {exc!r}")
    try:
        from leave_ui_runtime import install as install_leave_ui
        install_leave_ui()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] leave UI runtime install failed: {exc!r}")

    # Ta warstwa daje Brygadziście realną edycję, ale nie przebudowuje
    # głównej karty Profilu.
    try:
        from profile_foreman_edit_runtime import install as install_foreman_edit
        install_foreman_edit()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] foreman edit runtime install failed: {exc!r}")

    # Wcześniejszy runtime montuje pełny notebook Użytkownicy | Profile | Rangi.
    # Najpierw spłaszczamy go do jednej karty Użytkownicy, bez dublowania nawigacji.
    try:
        from profile_foreman_flat_users_runtime import install as install_flat_users
        install_flat_users()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] flat users runtime install failed: {exc!r}")

    # Końcowa warstwa semantyczna: musi wejść po wszystkich wcześniejszych
    # runtime'ach, bo to ona rozdziela Ruch WM od Obecności i buduje kolejkę
    # decyzji na podstawie Grafiku.
    try:
        from profile_attendance_finalize_runtime import install as install_attendance_finalize
        install_attendance_finalize()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] attendance finalize runtime install failed: {exc!r}")


def install() -> None:
    global _INSTALLED

    # Ta warstwa jest ładowana przez gui_profile przed zdefiniowaniem końcowej
    # klasy ProfileView. Patchujemy klasę bazową, więc obecny wygląd pozostaje.
    try:
        import gui_profile_core as profile_core
        from profile_user_actions_runtime import install as install_user_actions
        install_user_actions(profile_core.ProfileView)
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] user actions runtime install failed: {exc!r}")

    try:
        from dyspozycje_permissions_runtime import install as install_dysp_permissions
        install_dysp_permissions()
    except Exception as exc:
        print(f"[WM-DBG][DYSP][WARN] permissions runtime install failed: {exc!r}")

    if _INSTALLED:
        _install_workforce_extensions()
        return

    import gui_profile_foreman as foreman

    cls = foreman.ForemanProfilePanel
    if not getattr(cls, "_wm_profile_admin_unified", False):
        original_build = cls._build

        def _build(self, *args, **kwargs):
            result = original_build(self, *args, **kwargs)

            # Zadania i Sprzęt pozostają źródłem danych Pulpitu/statystyk,
            # lecz nadal są ukryte jako osobne zakładki.
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

            # Administracja ma być tylko w Użytkownicy. Stara zakładka
            # "Profile" może istnieć po starszym runtime; końcowa warstwa ją
            # ukryje, zamiast dublować ten sam panel w dwóch miejscach.
            profile_tab = tabs.get("Profile")
            if profile_tab is not None:
                try:
                    notebook.hide(profile_tab)
                except Exception:
                    pass
            return result

        cls._build = _build
        cls._wm_profile_admin_unified = True

    _INSTALLED = True
    _install_workforce_extensions()


__all__ = ["install"]
