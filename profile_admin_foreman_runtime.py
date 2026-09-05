# version: 2.1
"""Ujednolica Profile brygadzisty i podpina aktywne rozszerzenia Profilu."""
from __future__ import annotations

_INSTALLED = False


def _walk_widgets(widget):
    out = []
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        out.append(child)
        out.extend(_walk_widgets(child))
    return out


def _install_profile_entrypoints() -> None:
    """Profil pracownika otwieramy wyłącznie z Obecności/Urlopów, nie z Ruch WM."""
    try:
        from tkinter import messagebox, ttk
        import gui_profile_foreman as foreman
        from services import workforce_profile_service
        from ui_context_help import add_help_button
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] profile entrypoints imports failed: {exc!r}")
        return

    cls = foreman.ForemanProfilePanel
    if getattr(cls, "_wm_profile_entrypoints_v2", False):
        return

    original_team = cls._render_team
    original_leaves = cls._render_leaves

    def _render_team(self, *args, **kwargs):
        result = original_team(self, *args, **kwargs)
        parent = getattr(self, "_tabs", {}).get("Zespół")
        if parent is None:
            return result

        # Ruch WM ma pokazywać wyłącznie aktywność operacyjną. Usuwamy wejście
        # do pełnego profilu pracownika oraz podwójny klik otwierający edytor.
        for widget in _walk_widgets(parent):
            if not isinstance(widget, ttk.Button):
                continue
            try:
                if str(widget.cget("text")) == "Profil pracownika":
                    widget.destroy()
            except Exception:
                pass
        tree = getattr(self, "_wm_ruch_tree", None)
        if tree is not None:
            try:
                tree.unbind("<Double-1>")
            except Exception:
                pass
        return result

    def _render_leaves(self, *args, **kwargs):
        result = original_leaves(self, *args, **kwargs)
        parent = getattr(self, "_tabs", {}).get("Urlopy")
        if parent is None:
            return result

        tree = None
        for widget in _walk_widgets(parent):
            if isinstance(widget, ttk.Treeview):
                tree = widget
                break
        if tree is None:
            return result

        def selected_login() -> str:
            selected = tree.selection()
            if not selected:
                return ""
            try:
                values = tree.item(selected[0], "values") or ()
                display = str(values[0] if values else "").strip().casefold()
            except Exception:
                display = ""
            if not display:
                return ""

            for user in workforce_profile_service.list_users(active_only=False):
                login = str(user.get("login") or "").strip()
                if not login:
                    continue
                shown = workforce_profile_service.display_name(user).strip().casefold()
                if display in {shown, login.casefold()}:
                    return login

            for row in getattr(self, "snapshot", {}).get("team") or []:
                login = str(row.get("login") or "").strip()
                name = str(row.get("name") or login).strip().casefold()
                if login and display in {name, login.casefold()}:
                    return login
            return ""

        def open_leave_profile(_event=None) -> None:
            login = selected_login()
            if not login:
                messagebox.showinfo(
                    "Urlopy",
                    "Wybierz pracownika z listy urlopów.",
                    parent=self.winfo_toplevel(),
                )
                return
            try:
                import profile_foreman_edit_runtime as edit_runtime
                edit_runtime.open_employee_editor(
                    self,
                    login,
                    initial_tab="Urlopy",
                    on_saved=self.refresh_data,
                )
            except Exception as exc:
                messagebox.showerror(
                    "Profil",
                    f"Nie udało się otworzyć profilu:\n{exc}",
                    parent=self.winfo_toplevel(),
                )

        actions = ttk.Frame(parent, style="WM.Container.TFrame")
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(
            actions,
            text="Szczegóły pracownika",
            command=open_leave_profile,
        ).pack(side="left")
        add_help_button(
            actions,
            "Otwiera profil zaznaczonego pracownika bezpośrednio na zakładce Urlopy. Ruch WM pozostaje wyłącznie widokiem aktywności operacyjnej.",
        ).pack(side="left", padx=(6, 0))
        try:
            tree.bind("<Double-1>", open_leave_profile, add="+")
        except Exception:
            pass
        self._wm_leave_tree = tree
        return result

    cls._render_team = _render_team
    cls._render_leaves = _render_leaves
    cls._wm_profile_entrypoints_v2 = True


def _install_workforce_extensions() -> None:
    """Ładuj rozszerzenia po bazowych patchach, żeby nie zmieniać layoutu Profilu."""
    # Najpierw neutralny model płatnych dni. Dzięki temu kolejne warstwy
    # urlopów/obecności zapisują już kod dnia i procent płatności.
    try:
        from profile_payroll_seed_runtime import install as install_payroll_seed
        install_payroll_seed()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] payroll seed install failed: {exc!r}")

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

    # Minimalne przyciski ŚW 50% / Bezpłatny 0% w istniejącym edytorze.
    try:
        from profile_absence_pay_ui_runtime import install as install_absence_pay_ui
        install_absence_pay_ui()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] absence pay UI install failed: {exc!r}")

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

    # Edycja już zapisanego dnia jest małą warstwą nad finalnym widokiem.
    # Pozwala przenieść rekord między RANO/POPO i zachować bieżący rodzaj dniówki.
    try:
        from profile_attendance_edit_runtime import install as install_attendance_edit
        install_attendance_edit()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] attendance edit runtime install failed: {exc!r}")

    # Ostatni krok: przywróć zgodną sygnaturę audytu i zapisuj pełną historię,
    # bez dawnego limitu 5000 wpisów.
    try:
        from profile_audit_finalize_runtime import install as install_audit_finalize
        install_audit_finalize()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] audit finalize runtime install failed: {exc!r}")

    # Wejścia do profilu pracownika są domenowe: Obecność/Urlopy, nie Ruch WM.
    try:
        _install_profile_entrypoints()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] profile entrypoints install failed: {exc!r}")

    # Kalendarz Brygadzisty dostaje przełącznik Mój/Zespół i szczegóły dnia.
    try:
        from profile_calendar_team_runtime import install as install_team_calendar
        install_team_calendar()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] team calendar install failed: {exc!r}")

    # Rzadziej używane widoki pozostają zgrupowane pod Administracja.
    try:
        from profile_foreman_admin_group_runtime import install as install_admin_group
        install_admin_group()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] admin group install failed: {exc!r}")


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
