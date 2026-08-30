# version: 1.9.0
"""Aktywny Profil WM z Kalendarzem dla każdego i panelem Brygadzisty."""
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
    """Profil użytkownika z kalendarzem oraz panelem brygadzisty."""

    def _logged_user_is_brygadzista(self) -> bool:
        """Uprawnienie wynika z roli zalogowanej osoby, nie oglądanego profilu."""
        try:
            active_login = str(ProfileService.ensure_active_user_or_none() or "").strip()
        except Exception:
            active_login = ""
        if active_login:
            try:
                active_user = get_user(active_login) or {}
            except Exception:
                active_user = {}
            role = str(
                active_user.get("rola") or active_user.get("role") or ""
            ).strip().lower()
            return role == "brygadzista"
        # Zachowaj działanie podglądu/testów bez aktywnej sesji.
        return self._is_brygadzista()

    def _render_profile_body(self, parent) -> None:
        """Pokaż Profil + Kalendarz oraz opcjonalnie Brygadzistę."""
        try:
            from gui_profile_calendar import (
                ProfileCalendarPanel,
                install_foreman_leave_workflow,
            )
        except Exception as exc:
            log_akcja(f"[WM-ERR][PROFILE_CAL] Nie udało się załadować kalendarza: {exc}")
            self._render_simple_profile(parent)
            return

        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)

        profile_tab = ttk.Frame(notebook, style="WM.Container.TFrame")
        calendar_tab = ttk.Frame(notebook, style="WM.Container.TFrame")
        notebook.add(profile_tab, text="Profil")
        notebook.add(calendar_tab, text="Kalendarz")
        self._render_simple_profile(profile_tab)

        foreman_tab = None
        is_foreman = self._logged_user_is_brygadzista()
        if is_foreman:
            foreman_tab = ttk.Frame(notebook, style="WM.Container.TFrame")
            notebook.add(foreman_tab, text="Brygadzista")

        state = {"calendar": False, "foreman": False}

        def ensure_calendar() -> None:
            if state["calendar"]:
                return
            state["calendar"] = True
            panel = ProfileCalendarPanel(calendar_tab, login=self.login, owner=self)
            panel.pack(fill="both", expand=True)
            self._wm_profile_calendar = panel

        def ensure_foreman() -> None:
            if not is_foreman or foreman_tab is None or state["foreman"]:
                return
            state["foreman"] = True
            try:
                from gui_profile_foreman import ForemanProfilePanel

                install_foreman_leave_workflow(ForemanProfilePanel)
                panel = ForemanProfilePanel(foreman_tab, owner=self)
                panel.pack(fill="both", expand=True)
                self._wm_foreman_panel = panel
            except Exception as exc:
                log_akcja(
                    f"[WM-ERR][FOREMAN] Nie udało się zbudować panelu brygadzisty: {exc}"
                )
                ttk.Label(
                    foreman_tab,
                    text=f"Panel brygadzisty jest niedostępny:\n{exc}",
                    style="WM.Muted.TLabel",
                ).pack(anchor="w", padx=12, pady=12)

        def on_tab_changed(_event=None) -> None:
            try:
                selected = str(notebook.tab(notebook.select(), "text"))
            except Exception:
                return
            self._wm_profile_main_tab = selected
            if selected == "Kalendarz":
                ensure_calendar()
            elif selected == "Brygadzista":
                ensure_foreman()

        notebook.bind("<<NotebookTabChanged>>", on_tab_changed, add="+")
        previous = str(getattr(self, "_wm_profile_main_tab", "Profil") or "Profil")
        if previous == "Kalendarz":
            notebook.select(calendar_tab)
            ensure_calendar()
        elif previous == "Brygadzista" and foreman_tab is not None:
            notebook.select(foreman_tab)
            ensure_foreman()
        else:
            notebook.select(profile_tab)

    def _build_simple_profile(self) -> None:
        body = ttk.Frame(self, style="WM.Container.TFrame")
        body.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self._simple_container = body
        self._render_profile_body(body)

    def _refresh_view(self) -> None:
        """Odśwież Profil bez gubienia aktywnej zakładki."""
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
