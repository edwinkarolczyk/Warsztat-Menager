# version: 1.9.7
"""Aktywny Profil WM z Kalendarzem i panelem Brygadzisty.

Diagnostyka wydajności Profilu korzysta z ``wm_perf`` i wypisuje do konsoli
czas każdego ważnego etapu budowy, odświeżenia oraz leniwego ładowania zakładek.
Od 1.9.7 powtórne ``load_by_login`` dla już zbudowanego tego samego profilu nie
niszczy i nie buduje całego widoku drugi raz.
"""
from __future__ import annotations

from contextlib import contextmanager

from wm_perf import PerfFlow, perf, perf_span


with perf_span("PROFILE_IMPORT:calendar_ui_runtime.install"):
    try:
        from calendar_ui_runtime import install as _install_calendar_ui_runtime

        _install_calendar_ui_runtime()
    except Exception as _calendar_runtime_exc:
        print(f"[WM-DBG][CALENDAR][WARN] runtime install failed: {_calendar_runtime_exc}")

with perf_span("PROFILE_IMPORT:machine_review_ui_runtime.install"):
    try:
        from machine_review_ui_runtime import install as _install_machine_review_ui_runtime

        _install_machine_review_ui_runtime()
    except Exception as _machine_review_runtime_exc:
        print(
            "[WM-DBG][MASZYNY][WARN] review runtime install failed: "
            f"{_machine_review_runtime_exc}"
        )

with perf_span("PROFILE_IMPORT:foreman_shift_profiles_runtime.install"):
    try:
        from foreman_shift_profiles_runtime import install as _install_foreman_shift_profiles_runtime

        _install_foreman_shift_profiles_runtime()
    except Exception as _foreman_shift_runtime_exc:
        print(
            "[WM-DBG][FOREMAN][WARN] shift/profile runtime install failed: "
            f"{_foreman_shift_runtime_exc}"
        )

with perf_span("PROFILE_IMPORT:profile_admin_foreman_runtime.install"):
    try:
        from profile_admin_foreman_runtime import install as _install_profile_admin_foreman_runtime

        _install_profile_admin_foreman_runtime()
    except Exception as _profile_admin_runtime_exc:
        print(
            "[WM-DBG][PROFILE][WARN] unified admin runtime install failed: "
            f"{_profile_admin_runtime_exc}"
        )

with perf_span("PROFILE_IMPORT:gui_profile_core"):
    import gui_profile_core as _core

from profile_settings_fields import normalize_editable_fields


@contextmanager
def _timed_core_calls(*names: str):
    """Tymczasowo mierz wybrane wywołania używane przez bazowy ProfileView."""
    originals: dict[str, object] = {}
    try:
        for name in names:
            original = getattr(_core, name, None)
            if not callable(original):
                continue
            originals[name] = original

            def wrapped(*args, __name=name, __fn=original, **kwargs):
                with perf_span(f"PROFILE_DATA:{__name}"):
                    result = __fn(*args, **kwargs)
                try:
                    if isinstance(result, (list, tuple, set, dict)):
                        perf(f"PROFILE_DATA:{__name} RESULT count={len(result)}")
                    elif result is not None:
                        perf(f"PROFILE_DATA:{__name} RESULT type={type(result).__name__}")
                except Exception:
                    pass
                return result

            setattr(_core, name, wrapped)
        yield
    finally:
        for name, original in originals.items():
            try:
                setattr(_core, name, original)
            except Exception:
                pass


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

    def __init__(self, *args, **kwargs) -> None:
        login_arg = kwargs.get("login")
        flow = PerfFlow("PROFILE_VIEW_INIT")
        perf(f"PROFILE_VIEW_INIT login_arg={login_arg!r}")
        try:
            with perf_span("PROFILE_VIEW_INIT:base_constructor"):
                super().__init__(*args, **kwargs)
            flow.mark("base_constructor_done")
            try:
                perf(
                    "PROFILE_VIEW_INIT RESULT "
                    f"login={self.login!r} dysp={len(self._dysp_cache)} "
                    f"widgets={len(self.winfo_children())}"
                )
            except Exception:
                pass
        finally:
            flow.end()

    def load_by_login(self, login: str) -> None:
        flow = PerfFlow("PROFILE_LOAD_BY_LOGIN")
        perf(f"PROFILE_LOAD_BY_LOGIN login={login!r}")
        try:
            wanted = str(login or "").strip().casefold()
            current = str(getattr(self, "login", "") or "").strip().casefold()
            container = getattr(self, "_simple_container", None)
            already_built = False
            if container is not None:
                try:
                    already_built = bool(container.winfo_exists() and container.winfo_children())
                except Exception:
                    already_built = False
            if wanted and wanted == current and already_built:
                try:
                    self.forced_login = str(getattr(self, "login", "") or login).strip()
                except Exception:
                    pass
                perf("PROFILE_LOAD_BY_LOGIN SKIP already_loaded=True same_login=True")
                flow.mark("already_loaded")
                return

            with perf_span("PROFILE_LOAD_BY_LOGIN:base"):
                super().load_by_login(login)
            flow.mark("base_done")
        finally:
            flow.end()

    def _reload_profile_data(self) -> None:
        flow = PerfFlow("PROFILE_DATA_RELOAD")
        try:
            with _timed_core_calls(
                "get_user",
                "visible_for_login",
                "staz_days_for_login",
                "staz_years_floor_for_login",
            ):
                with perf_span("PROFILE_DATA_RELOAD:base"):
                    result = super()._reload_profile_data()
            try:
                perf(
                    "PROFILE_DATA_RELOAD RESULT "
                    f"login={self.login!r} user_fields={len(self._user_data)} "
                    f"dysp={len(self._dysp_cache)} tasks={len(self._tasks_cache)} "
                    f"inbox={len(self._inbox_cache)} sent={len(self._sent_cache)}"
                )
            except Exception:
                pass
            flow.mark("data_ready")
            return result
        finally:
            flow.end()

    def _logged_user_is_brygadzista(self) -> bool:
        """Uprawnienie wynika z roli zalogowanej osoby, nie oglądanego profilu."""
        flow = PerfFlow("PROFILE_ROLE_CHECK")
        try:
            try:
                with perf_span("PROFILE_ROLE_CHECK:active_login"):
                    active_login = str(ProfileService.ensure_active_user_or_none() or "").strip()
            except Exception:
                active_login = ""
            if active_login:
                try:
                    with perf_span("PROFILE_ROLE_CHECK:get_user"):
                        active_user = get_user(active_login) or {}
                except Exception:
                    active_user = {}
                role = str(
                    active_user.get("rola") or active_user.get("role") or ""
                ).strip().lower()
                result = role == "brygadzista"
                perf(
                    f"PROFILE_ROLE_CHECK RESULT login={active_login!r} role={role!r} "
                    f"is_foreman={result}"
                )
                return result
            with perf_span("PROFILE_ROLE_CHECK:fallback"):
                result = self._is_brygadzista()
            perf(f"PROFILE_ROLE_CHECK RESULT fallback={result}")
            return result
        finally:
            flow.end()

    @staticmethod
    def _cfg_bool(key: str, fallback_key: str, default: bool) -> bool:
        with perf_span(f"PROFILE_CFG_BOOL:{key}"):
            try:
                cfg = ConfigManager()
                value = cfg.get(key, None)
                if value is None:
                    value = cfg.get(fallback_key, default)
                result = bool(value)
            except Exception:
                result = default
        perf(f"PROFILE_CFG_BOOL RESULT key={key} value={result}")
        return result

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
        flow = PerfFlow("PROFILE_HEADER")
        try:
            with perf_span("PROFILE_HEADER:create_widgets"):
                wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
                wrap.pack(fill="x")
            with perf_span("PROFILE_HEADER:get_user"):
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

            with perf_span("PROFILE_HEADER:show_name_config"):
                show_name = self._show_name_in_header()
            with perf_span("PROFILE_HEADER:labels"):
                if show_name:
                    ttk.Label(wrap, text=str(display), style="WM.H1.TLabel").pack(anchor="w")
                    ttk.Label(wrap, text=login_label, style="WM.Muted.TLabel").pack(
                        anchor="w", pady=(2, 0)
                    )
                else:
                    ttk.Label(wrap, text=str(self.login or "—"), style="WM.H1.TLabel").pack(anchor="w")
                ttk.Label(wrap, text=f"Rola: {role}", style="WM.Muted.TLabel").pack(
                    anchor="w", pady=(2, 0)
                )
            flow.mark("header_ready")
        finally:
            flow.end()

    def _make_avatar(self, parent):
        """Wyłączony avatar daje placeholder zamiast ignorowania ustawienia."""
        with perf_span("PROFILE_AVATAR:total"):
            with perf_span("PROFILE_AVATAR:config"):
                enabled = self._avatar_enabled()
            if not enabled:
                perf("PROFILE_AVATAR RESULT placeholder=config_disabled")
                return self._avatar_placeholder(parent)
            with perf_span("PROFILE_AVATAR:base_load"):
                return super()._make_avatar(parent)

    def _profile_shift_text(self) -> str:
        with perf_span("PROFILE_RENDER:shift_text"):
            return super()._profile_shift_text()

    def _user_editable_fields(self) -> tuple[list[str], bool, int]:
        """Czytaj dokładnie pola wybrane w Ustawienia → Profile."""
        flow = PerfFlow("PROFILE_EDITABLE_FIELDS")
        try:
            with perf_span("PROFILE_EDITABLE_FIELDS:ConfigManager"):
                cfg = ConfigManager()
            with perf_span("PROFILE_EDITABLE_FIELDS:read_fields"):
                raw_fields = cfg.get("profiles.editable_fields", None)
                if raw_fields is None:
                    raw_fields = cfg.get(
                        "profiles.fields_editable_by_user",
                        ["telefon", "email"],
                    )
                fields = normalize_editable_fields(raw_fields)
            with perf_span("PROFILE_EDITABLE_FIELDS:read_pin"):
                allow_pin = bool(
                    cfg.get(
                        "profiles.pin.change_allowed",
                        cfg.get("profiles.allow_pin_change", False),
                    )
                )
                pin_cfg = cfg.get("profiles.pin", {}) or {}
                pin_min_length = max(1, int(pin_cfg.get("min_length", 4) or 4))
            perf(
                "PROFILE_EDITABLE_FIELDS RESULT "
                f"fields={fields!r} allow_pin={allow_pin} pin_min={pin_min_length}"
            )
            return fields, allow_pin, pin_min_length
        finally:
            flow.end()

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
        flow = PerfFlow("PROFILE_RENDER_SIMPLE")
        try:
            with perf_span("PROFILE_RENDER_SIMPLE:account_header"):
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
            with perf_span("PROFILE_RENDER_SIMPLE:base_profile"):
                super()._render_simple_profile(parent)
            try:
                perf(
                    "PROFILE_RENDER_SIMPLE RESULT "
                    f"dysp_total={len(self._dysp_cache)} parent_children={len(parent.winfo_children())}"
                )
            except Exception:
                pass
            flow.mark("simple_ready")
        finally:
            flow.end()

    def _render_profile_body(self, parent) -> None:
        """Pokaż Profil + Kalendarz oraz opcjonalnie Brygadzistę."""
        flow = PerfFlow("PROFILE_RENDER_BODY")
        try:
            try:
                with perf_span("PROFILE_RENDER_BODY:import_gui_profile_calendar"):
                    from gui_profile_calendar import (
                        ProfileCalendarPanel,
                        install_foreman_leave_workflow,
                    )
            except Exception as exc:
                log_akcja(f"[WM-ERR][PROFILE_CAL] Nie udało się załadować kalendarza: {exc}")
                with perf_span("PROFILE_RENDER_BODY:fallback_simple"):
                    self._render_simple_profile(parent)
                return
            flow.mark("calendar_module_ready")

            with perf_span("PROFILE_RENDER_BODY:create_notebook"):
                notebook = ttk.Notebook(parent)
                notebook.pack(fill="both", expand=True)

                profile_tab = ttk.Frame(notebook, style="WM.Container.TFrame")
                calendar_tab = ttk.Frame(notebook, style="WM.Container.TFrame")
                notebook.add(profile_tab, text="Profil")
                notebook.add(calendar_tab, text="Kalendarz")
            flow.mark("notebook_ready")

            with perf_span("PROFILE_RENDER_BODY:profile_card_enabled"):
                profile_card_enabled = self._profile_card_enabled()
            if profile_card_enabled:
                with perf_span("PROFILE_RENDER_BODY:render_profile_tab"):
                    self._render_simple_profile(profile_tab)
            else:
                with perf_span("PROFILE_RENDER_BODY:render_disabled_profile_tab"):
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
            flow.mark("profile_tab_ready")

            foreman_tab = None
            with perf_span("PROFILE_RENDER_BODY:foreman_role_check"):
                is_foreman = self._logged_user_is_brygadzista()
            if is_foreman:
                with perf_span("PROFILE_RENDER_BODY:create_foreman_tab"):
                    foreman_tab = ttk.Frame(notebook, style="WM.Container.TFrame")
                    notebook.add(foreman_tab, text="Brygadzista")
            flow.mark(f"role_ready:is_foreman={is_foreman}")

            state = {"calendar": False, "foreman": False}

            def ensure_calendar() -> None:
                if state["calendar"]:
                    perf("PROFILE_LAZY_CALENDAR SKIP already_loaded=True")
                    return
                lazy_flow = PerfFlow("PROFILE_LAZY_CALENDAR")
                state["calendar"] = True
                try:
                    with perf_span("PROFILE_LAZY_CALENDAR:create_panel"):
                        panel = ProfileCalendarPanel(calendar_tab, login=self.login, owner=self)
                    with perf_span("PROFILE_LAZY_CALENDAR:pack"):
                        panel.pack(fill="both", expand=True)
                    self._wm_profile_calendar = panel
                    lazy_flow.mark("calendar_ready")
                finally:
                    lazy_flow.end()

            def ensure_foreman() -> None:
                if not is_foreman or foreman_tab is None:
                    perf("PROFILE_LAZY_FOREMAN SKIP unavailable=True")
                    return
                if state["foreman"]:
                    perf("PROFILE_LAZY_FOREMAN SKIP already_loaded=True")
                    return
                lazy_flow = PerfFlow("PROFILE_LAZY_FOREMAN")
                state["foreman"] = True
                try:
                    try:
                        with perf_span("PROFILE_LAZY_FOREMAN:import_gui_profile_foreman"):
                            from gui_profile_foreman import ForemanProfilePanel

                        with perf_span("PROFILE_LAZY_FOREMAN:install_leave_workflow"):
                            install_foreman_leave_workflow(ForemanProfilePanel)
                        with perf_span("PROFILE_LAZY_FOREMAN:create_panel"):
                            panel = ForemanProfilePanel(foreman_tab, owner=self)
                        with perf_span("PROFILE_LAZY_FOREMAN:pack"):
                            panel.pack(fill="both", expand=True)
                        self._wm_foreman_panel = panel
                        lazy_flow.mark("foreman_ready")
                    except Exception as exc:
                        log_akcja(
                            f"[WM-ERR][FOREMAN] Nie udało się zbudować panelu brygadzisty: {exc}"
                        )
                        ttk.Label(
                            foreman_tab,
                            text=f"Panel brygadzisty jest niedostępny:\n{exc}",
                            style="WM.Muted.TLabel",
                        ).pack(anchor="w", padx=12, pady=12)
                finally:
                    lazy_flow.end()

            def on_tab_changed(_event=None) -> None:
                try:
                    selected = str(notebook.tab(notebook.select(), "text"))
                except Exception:
                    return
                perf(f"PROFILE_TAB_CHANGE selected={selected!r}")
                self._wm_profile_main_tab = selected
                if selected == "Kalendarz":
                    ensure_calendar()
                elif selected == "Brygadzista":
                    ensure_foreman()

            with perf_span("PROFILE_RENDER_BODY:bind_tab_change"):
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
            flow.mark(f"selection_ready:{previous}")
        finally:
            flow.end()

    def _build_simple_profile(self) -> None:
        flow = PerfFlow("PROFILE_BUILD_SIMPLE")
        try:
            with perf_span("PROFILE_BUILD_SIMPLE:create_body"):
                body = ttk.Frame(self, style="WM.Container.TFrame")
                body.pack(fill="both", expand=True, padx=16, pady=(4, 16))
                self._simple_container = body
            with perf_span("PROFILE_BUILD_SIMPLE:render_body"):
                self._render_profile_body(body)
            flow.mark("body_ready")
        finally:
            flow.end()

    def _refresh_view(self) -> None:
        """Odśwież Profil bez gubienia aktywnej zakładki."""
        flow = PerfFlow("PROFILE_REFRESH_VIEW")
        try:
            with perf_span("PROFILE_REFRESH_VIEW:reload_data"):
                self._reload_profile_data()
            flow.mark("data_reloaded")
            if self._header_container is not None:
                with perf_span("PROFILE_REFRESH_VIEW:destroy_header"):
                    for child in self._header_container.winfo_children():
                        child.destroy()
                with perf_span("PROFILE_REFRESH_VIEW:build_header"):
                    self._build_header(self._header_container)
                flow.mark("header_rebuilt")
            if self._simple_container is not None:
                with perf_span("PROFILE_REFRESH_VIEW:destroy_body"):
                    for child in self._simple_container.winfo_children():
                        child.destroy()
                with perf_span("PROFILE_REFRESH_VIEW:render_body"):
                    self._render_profile_body(self._simple_container)
                flow.mark("body_rebuilt")
        finally:
            flow.end()


# Zachowaj semantykę dawnego `from gui_profile import *`.
_core_all = getattr(_core, "__all__", None)
if _core_all is not None:
    __all__ = list(_core_all)
    if "ProfileView" not in __all__:
        __all__.append("ProfileView")
else:
    __all__ = sorted(name for name in globals() if not name.startswith("_"))
