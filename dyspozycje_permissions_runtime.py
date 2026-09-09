# version: 2.0
"""Spina uprawnienia akcji Dyspozycji z widokiem, kreatorem i Ustawieniami."""
from __future__ import annotations

import logging
import sys
from typing import Any

from dyspozycje_access import (
    ACTION_ADD,
    ACTION_EDIT,
    get_role_actions,
    is_role_action_allowed,
    resolve_role_for_login,
    set_role_actions,
)

_INSTALLED = False
logger = logging.getLogger(__name__)


def _actor_login(master: Any, autor: str = "") -> str:
    candidates = [master]
    try:
        if master is not None and hasattr(master, "winfo_toplevel"):
            candidates.append(master.winfo_toplevel())
    except Exception:
        pass
    for source in candidates:
        if source is None:
            continue
        for attr in ("active_login", "login_sesji", "_wm_login", "login", "current_user"):
            value = str(getattr(source, attr, "") or "").strip()
            if value:
                return value
    return str(autor or "").strip()


def _actor_role(master: Any, autor: str = "") -> str:
    candidates = [master]
    try:
        if master is not None and hasattr(master, "winfo_toplevel"):
            candidates.append(master.winfo_toplevel())
    except Exception:
        pass
    for source in candidates:
        if source is None:
            continue
        for attr in ("active_role", "_wm_role", "rola", "role", "current_role"):
            value = str(getattr(source, attr, "") or "").strip()
            if value:
                try:
                    from wm_access import normalize_role_name
                    return normalize_role_name(value)
                except Exception:
                    return value.lower()
    return resolve_role_for_login(_actor_login(master, autor))


def _show_denied(master: Any, action_label: str) -> None:
    try:
        from tkinter import messagebox
        messagebox.showwarning(
            "Dyspozycje",
            f"Twoja ranga nie ma uprawnienia: {action_label} Dyspozycji.",
            parent=master if getattr(master, "tk", None) is not None else None,
        )
    except Exception:
        pass


def _install_creator_gate() -> None:
    try:
        import gui_dyspozycje_creator as creator
    except Exception as exc:
        logger.exception("[DYSP] Import kreatora nieudany: %s", exc)
        return

    if getattr(creator, "_wm_action_gate_installed", False):
        return

    original_open = creator.open_dyspozycje_creator

    def open_dyspozycje_creator(master=None, *, autor="", context=None):
        ctx = dict(context or {})
        is_edit = bool(ctx.get("edit_mode"))
        action = ACTION_EDIT if is_edit else ACTION_ADD
        role = _actor_role(master, autor)
        if not is_role_action_allowed(role, action):
            _show_denied(master, "edycja" if is_edit else "dodawanie")
            return None
        try:
            return original_open(master, autor=autor, context=ctx)
        except Exception:
            logger.exception(
                "[DYSP] Błąd kreatora; action=%s role=%s login=%s",
                action,
                role,
                _actor_login(master, autor),
            )
            raise

    creator.open_dyspozycje_creator = open_dyspozycje_creator
    creator._wm_action_gate_installed = True

    # Starsze wejścia z Narzędzi używały wm.dyspo_wizard. Kierujemy je do
    # tego samego aktywnego kreatora, aby wszystkie moduły miały identyczne
    # uprawnienia i identyczną logikę zapisu.
    def open_dyspo_wizard(parent, context=None):
        return open_dyspozycje_creator(
            parent,
            autor=_actor_login(parent),
            context=context or {},
        )

    try:
        import wm.dyspo_wizard as old_wizard
        old_wizard.open_dyspo_wizard = open_dyspo_wizard
    except Exception:
        pass
    for module_name in ("gui_narzedzia", "gui_maszyny", "gui_maszyny_legacy"):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "open_dyspo_wizard"):
            try:
                module.open_dyspo_wizard = open_dyspo_wizard
            except Exception:
                pass


def _install_settings_roles() -> None:
    try:
        import ustawienia_uzytkownicy as settings
    except Exception as exc:
        logger.exception("[DYSP] Nie udało się podpiąć Ustawień rang: %s", exc)
        return

    cls = settings.SettingsProfilesTab
    if getattr(cls, "_wm_dysp_actions_installed", False):
        return

    def _build_roles_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)
        left = settings.ttk.Frame(parent)
        left.grid(row=0, column=0, sticky="ns", padx=(10, 12), pady=10)
        settings.ttk.Label(left, text="Rangi / role").pack(anchor="w", pady=(0, 6))
        roles_list = settings.tk.Listbox(left, height=10, exportselection=False)
        roles_list.pack(fill="y", expand=True)
        for _role_key, role_label in settings.ROLE_LABELS:
            roles_list.insert("end", role_label)

        right = settings.ttk.Frame(parent)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        right.columnconfigure(0, weight=1)
        selected_role_var = settings.tk.StringVar(value="")
        settings.ttk.Label(right, textvariable=selected_role_var).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        checks_frame = settings.ttk.Frame(right)
        checks_frame.grid(row=1, column=0, sticky="nsew")

        module_vars: dict[str, Any] = {}
        for idx, (module_key, module_label) in enumerate(settings.MODULE_LABELS):
            var = settings.tk.BooleanVar(value=False)
            module_vars[module_key] = var
            settings.ttk.Checkbutton(
                checks_frame, text=module_label, variable=var
            ).grid(row=idx, column=0, sticky="w", pady=2)

        action_row = len(settings.MODULE_LABELS)
        settings.ttk.Separator(checks_frame, orient="horizontal").grid(
            row=action_row, column=0, sticky="ew", pady=(10, 8)
        )
        settings.ttk.Label(
            checks_frame, text="Akcje Dyspozycji", font=("Segoe UI", 10, "bold")
        ).grid(row=action_row + 1, column=0, sticky="w", pady=(0, 4))
        add_var = settings.tk.BooleanVar(value=False)
        edit_var = settings.tk.BooleanVar(value=False)
        settings.ttk.Checkbutton(
            checks_frame, text="Dodawanie Dyspozycji", variable=add_var
        ).grid(row=action_row + 2, column=0, sticky="w", pady=2)
        settings.ttk.Checkbutton(
            checks_frame, text="Edycja Dyspozycji", variable=edit_var
        ).grid(row=action_row + 3, column=0, sticky="w", pady=2)

        def selected_role_key() -> str:
            selected = roles_list.curselection()
            return settings.ROLE_LABELS[int(selected[0])][0] if selected else ""

        def load_role(_event=None) -> None:
            role_key = selected_role_key()
            if not role_key:
                return
            selected_role_var.set(
                f"Uprawnienia rangi: {dict(settings.ROLE_LABELS).get(role_key, role_key)}"
            )
            modules = settings.get_role_modules(role_key)
            for module_key, var in module_vars.items():
                var.set(bool(modules.get(settings.normalize_module_name(module_key), False)))
            actions = get_role_actions(role_key)
            add_var.set(bool(actions.get(ACTION_ADD, False)))
            edit_var.set(bool(actions.get(ACTION_EDIT, False)))

        def save_role() -> None:
            role_key = selected_role_key()
            if not role_key:
                settings.messagebox.showwarning("Rangi", "Wybierz rangę do zapisania.")
                return
            modules_map = {
                module_key: bool(var.get()) for module_key, var in module_vars.items()
            }
            normalized_role = settings.normalize_role_name(role_key)
            settings.set_role_modules(normalized_role, modules_map)
            set_role_actions(
                normalized_role,
                {ACTION_ADD: bool(add_var.get()), ACTION_EDIT: bool(edit_var.get())},
            )
            settings.messagebox.showinfo("Rangi", "Zapisano uprawnienia rangi.")

        roles_list.bind("<<ListboxSelect>>", load_role)
        settings.ttk.Button(right, text="Zapisz rangę", command=save_role).grid(
            row=2, column=0, sticky="e", pady=(12, 0)
        )
        roles_list.selection_set(0)
        load_role()

    cls._build_roles_tab = _build_roles_tab
    cls._wm_dysp_actions_installed = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    import gui_zlecenia as dysp

    cls = dysp.ZleceniaView
    if not getattr(cls, "_wm_permissions_runtime_installed", False):
        original_resolve_role = cls._resolve_login_role
        original_build_toolbar = cls._build_toolbar
        original_on_add = cls._on_add
        original_on_edit = cls._on_edit

        def _resolve_login_role(self) -> str:
            role = str(original_resolve_role(self) or "").strip().lower()
            if role:
                return role
            return resolve_role_for_login(str(getattr(self, "_login_user", "") or ""))

        def _build_toolbar(self) -> None:
            original_build_toolbar(self)
            can_add = bool(
                self._open_order_creator
                and is_role_action_allowed(self._login_role, ACTION_ADD)
            )
            can_edit = bool(
                self._open_order_creator
                and is_role_action_allowed(self._login_role, ACTION_EDIT)
            )
            try:
                toolbar = self.winfo_children()[0]
                for child in toolbar.winfo_children():
                    try:
                        text = str(child.cget("text") or "")
                    except Exception:
                        continue
                    if text == "Dodaj Dyspozycję":
                        child.state(["!disabled"] if can_add else ["disabled"])
                        self.btn_add_dyspozycja = child
                    elif text == "Edytuj Dyspozycję":
                        child.state(["!disabled"] if can_edit else ["disabled"])
                        self.btn_edit_dyspozycja = child
            except Exception:
                logger.exception("[DYSP] Nie udało się ustawić praw przycisków")

        def _on_add(self) -> None:
            if not is_role_action_allowed(self._login_role, ACTION_ADD):
                _show_denied(self, "dodawanie")
                return
            return original_on_add(self)

        def _on_edit(self) -> None:
            if not is_role_action_allowed(self._login_role, ACTION_EDIT):
                _show_denied(self, "edycja")
                return
            return original_on_edit(self)

        cls._resolve_login_role = _resolve_login_role
        cls._build_toolbar = _build_toolbar
        cls._on_add = _on_add
        cls._on_edit = _on_edit
        cls._wm_permissions_runtime_installed = True

    # Nie wyłączaj Dodaj/Edytuj tylko dlatego, że import kreatora chwilowo
    # nastąpił w złej kolejności. Import jest wykonywany dopiero po kliknięciu,
    # a pełny traceback trafia do logu.
    def _resolve_creator():
        def _open(*args, **kwargs):
            try:
                from gui_dyspozycje_creator import open_dyspozycje_creator
                return open_dyspozycje_creator(*args, **kwargs)
            except Exception as exc:
                dysp.logger.exception(
                    "[DYSP] Nie udało się otworzyć kreatora Dyspozycji: %s", exc
                )
                raise
        return _open

    dysp._resolve_creator = _resolve_creator
    _install_creator_gate()
    _install_settings_roles()
    _INSTALLED = True


__all__ = ["install"]
