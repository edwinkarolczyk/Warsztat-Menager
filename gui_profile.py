# version: 1.9.5
"""Aktywny Profil WM z Kalendarzem i panelem Brygadzisty."""
from __future__ import annotations

try:
    from calendar_ui_runtime import install as _install_calendar_ui_runtime

    _install_calendar_ui_runtime()
except Exception as _calendar_runtime_exc:
    print(f"[WM-DBG][CALENDAR][WARN] runtime install failed: {_calendar_runtime_exc}")

try:
    from machine_review_ui_runtime import install as _install_machine_review_ui_runtime

    _install_machine_review_ui_runtime()
except Exception as _machine_review_runtime_exc:
    print(
        "[WM-DBG][MASZYNY][WARN] review runtime install failed: "
        f"{_machine_review_runtime_exc}"
    )

try:
    from foreman_shift_profiles_runtime import install as _install_foreman_shift_profiles_runtime

    _install_foreman_shift_profiles_runtime()
except Exception as _foreman_shift_runtime_exc:
    print(
        "[WM-DBG][FOREMAN][WARN] shift/profile runtime install failed: "
        f"{_foreman_shift_runtime_exc}"
    )

try:
    from profile_admin_foreman_runtime import install as _install_profile_admin_foreman_runtime

    _install_profile_admin_foreman_runtime()
except Exception as _profile_admin_runtime_exc:
    print(
        "[WM-DBG][PROFILE][WARN] unified admin runtime install failed: "
        f"{_profile_admin_runtime_exc}"
    )

import gui_profile_core as _core
from profile_settings_fields import normalize_editable_fields

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
    """Profil użytkownika z jedną konfiguracją pól i administracji."""

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
        return self._is_brygadzista()

    @staticmethod
    def _cfg_bool(key: str, fallback_key: str, default: bool) -> bool:
        try:
            cfg = ConfigManager()
            value = cfg.get(key, None)
            if value is None:
                value = cfg.get(fallback_key, default)
            return bool(value)
        except Exception:
            return default

    def _profile_card_enabled(self) -> bool:
        return self._cfg_bool(
            "profiles.ui.enable_profile_card",
            "ui.profile.enabled",
            True,
        )

    def _show_name_in_header(self) -> bool:
        return self._cfg_bool(
            "profiles.ui.show_name_in_header",
            "ui.profile.show_name_header",
            True,
        )

    def _avatar_enabled(self) -> bool:
        return self._cfg_bool(
            "profiles.avatar.enabled",
            "ui.profile.avatar_enabled",
            False,
        )

    def _build_header(self, parent) -> None:
        """Nagłówek aktywnego ProfileView respektujący ustawienie imienia."""
        wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrap.pack(fill="x")
        user = get_user(self.login) or {}
        display = (
            user.get("display_name")
            or self.display_name
            or " ".join(
                part
                for part in (
                    str(user.get("imie") or "").strip(),
                    str(user.get("nazwisko") or "").strip(),
                )
                if part
            )
            or self.login
            or "—"
        )
        role = user.get("rola") or self.rola or "—"
        login_label = f"@{self.login}" if self.login else "@—"

        if self._show_name_in_header():
            ttk.Label(wrap, text=str(display), style="WM.H1.TLabel").pack(anchor="w")
            ttk.Label(wrap, text=login_label, style="WM.Muted.TLabel").pack(
                anchor="w", pady=(2, 0)
            )
        else:
            ttk.Label(wrap, text=str(self.login or "—"), style="WM.H1.TLabel").pack(anchor="w")
        ttk.Label(wrap, text=f"Rola: {role}", style="WM.Muted.TLabel").pack(
            anchor="w", pady=(2, 0)
        )

    def _make_avatar(self, parent):
        """Wyłączony avatar daje placeholder zamiast ignorowania ustawienia."""
        if not self._avatar_enabled():
            return self._avatar_placeholder(parent)
        return super()._make_avatar(parent)

    def _user_editable_fields(self) -> tuple[list[str], bool, int]:
        """Czytaj dokładnie pola wybrane w Ustawienia → Profile."""
        cfg = ConfigManager()
        raw_fields = cfg.get("profiles.editable_fields", None)
        if raw_fields is None:
            raw_fields = cfg.get(
                "profiles.fields_editable_by_user",
                ["telefon", "email"],
            )
        fields = normalize_editable_fields(raw_fields)
        allow_pin = bool(
            cfg.get(
                "profiles.pin.change_allowed",
                cfg.get("profiles.allow_pin_change", False),
            )
        )
        pin_cfg = cfg.get("profiles.pin", {}) or {}
        pin_min_length = max(1, int(pin_cfg.get("min_length", 4) or 4))
        return fields, allow_pin, pin_min_length

    def _open_edit_profile(self) -> None:
        """Edycja własnego profilu działa tak samo dla każdej rangi."""
        return super()._open_edit_profile()

    def _open_profile_settings(self) -> None:
        """Administracyjny skrót brygadzisty do Ustawienia → Profile."""
        if not self._logged_user_is_brygadzista():
            return
        try:
            root = self.winfo_toplevel()
            container = self.master
            active_login = str(
                ProfileService.ensure_active_user_or_none() or self.login or ""
            ).strip()
            active_user = get_user(active_login) or {}
            active_role = str(
                active_user.get("rola") or active_user.get("role") or "brygadzista"
            ).strip() or "brygadzista"
            setattr(root, "_wm_settings_target_tab", "Profile")
            from ustawienia_systemu import panel_ustawien

            panel_ustawien(
                root,
                container,
                login=active_login,
                rola=active_role,
            )
        except Exception as exc:
            try:
                root = self.winfo_toplevel()
                if hasattr(root, "_wm_settings_target_tab"):
                    delattr(root, "_wm_settings_target_tab")
            except Exception:
                pass
            try:
                log_akcja(
                    f"[WM-ERR][PROFILE] Nie udało się otworzyć Ustawienia → Profile: {exc}"
                )
            except Exception:
                pass

    def _render_simple_profile(self, parent) -> None:
        """Zwykły Profil zawsze daje dostęp do edycji własnych danych."""
        account = ttk.LabelFrame(
            parent,
            text="Mój profil",
            style="WM.Section.TLabelframe",
            padding=10,
        )
        account.pack(fill="x", pady=(0, 10))
        ttk.Label(
            account,
            text="Dane własnego profilu i pola udostępnione do samodzielnej edycji.",
            style="WM.Muted.TLabel",
        ).pack(side="left")
        ttk.Button(
            account,
            text="Edytuj mój profil",
            command=self._open_edit_profile,
            style="WM.Button.TButton",
        ).pack(side="right")
        super()._render_simple_profile(parent)

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

        if self._profile_card_enabled():
            self._render_simple_profile(profile_tab)
        else:
            box = ttk.LabelFrame(
                profile_tab,
                text="Profil",
                style="WM.Section.TLabelframe",
                padding=12,
            )
            box.pack(fill="x", padx=12, pady=12)
            ttk.Label(
                box,
                text="Karta Profil jest wyłączona w Ustawienia → Profile.",
                style="WM.Muted.TLabel",
            ).pack(side="left")
            ttk.Button(
                box,
                text="Edytuj mój profil",
                command=self._open_edit_profile,
                style="WM.Button.TButton",
            ).pack(side="right")

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
