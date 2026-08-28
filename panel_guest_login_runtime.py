# version: 1.0
"""Centralna karta logowania dla panelu uruchomionego jako Gość.

Nie zmienia mechanizmu autoryzacji. Korzysta z tych samych profili i funkcji
uwierzytelniania co gui_logowanie.open_login_popup().
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_GUEST_NAMES = {"guest", "gość", "gosc", "niezalogowany", ""}


def _is_guest(root) -> bool:
    for attr in ("active_login", "current_user", "username", "_wm_login"):
        try:
            value = str(getattr(root, attr, "") or "").strip().casefold()
        except Exception:
            value = ""
        if value:
            return value in _GUEST_NAMES
    return True


def _save_last_user(login: str) -> None:
    try:
        from config_manager import ConfigManager

        cfg = ConfigManager()
        cfg.set("ostatni_uzytkownik", login)
        if hasattr(cfg, "save_all"):
            cfg.save_all()
        else:
            cfg.save()
    except Exception:
        logger.exception("[PANEL][LOGIN_CARD] Nie udało się zapisać ostatniego użytkownika.")


def install_guest_login_card(root) -> bool:
    """Pokaż integralny formularz logowania w centrum panelu Gościa."""

    if root is None or not _is_guest(root):
        return False

    content = getattr(root, "content", None) or getattr(root, "main_content", None)
    if content is None:
        return False

    try:
        if not content.winfo_exists():
            return False
    except Exception:
        return False

    try:
        if getattr(content, "_wm_guest_login_card", False):
            return True
    except Exception:
        pass

    try:
        import tkinter as tk
        from tkinter import ttk

        import gui_logowanie
        import gui_panel
    except Exception:
        logger.exception("[PANEL][LOGIN_CARD] Nie udało się załadować modułów logowania.")
        return False

    # W trybie Gościa centralny obszar ma służyć jako wejście do WM, a nie
    # automatycznie otwierać przypadkowy moduł dostępny dla profilu technicznego.
    try:
        for child in content.winfo_children():
            child.destroy()
    except Exception:
        pass

    try:
        source_var = getattr(root, "wm_current_source_var", None)
        if source_var is not None:
            source_var.set("Aktualnie: Logowanie")
    except Exception:
        pass

    host = ttk.Frame(content, style="WM.Card.TFrame")
    host.pack(fill="both", expand=True)

    card = ttk.Frame(host, style="WM.Card.TFrame", padding=(34, 28))
    card.place(relx=0.5, rely=0.46, anchor="center")

    ttk.Label(
        card,
        text="Warsztat Menager",
        style="WM.H1.TLabel",
        anchor="center",
    ).grid(row=0, column=0, sticky="ew", pady=(0, 4))

    ttk.Label(
        card,
        text="Zaloguj się, aby przejść do modułów WM",
        style="WM.Muted.TLabel",
        anchor="center",
    ).grid(row=1, column=0, sticky="ew", pady=(0, 22))

    try:
        ordered_logins, profiles = gui_logowanie._login_profiles_for_popup()
    except Exception:
        ordered_logins, profiles = [], {}

    login_var = tk.StringVar(master=card)
    pin_var = tk.StringVar(master=card)
    status_var = tk.StringVar(master=card, value="")

    ttk.Label(card, text="Użytkownik", style="WM.TLabel").grid(
        row=2, column=0, sticky="w", pady=(0, 4)
    )

    if ordered_logins:
        login_entry = ttk.Combobox(
            card,
            textvariable=login_var,
            values=ordered_logins,
            state="readonly",
            width=32,
        )
        try:
            from config_manager import ConfigManager

            last_user = ConfigManager().get("ostatni_uzytkownik")
        except Exception:
            last_user = ""
        if isinstance(last_user, str) and last_user.strip() in ordered_logins:
            login_var.set(last_user.strip())
        else:
            login_var.set(ordered_logins[0])
    else:
        login_entry = ttk.Entry(card, textvariable=login_var, width=34)

    login_entry.grid(row=3, column=0, sticky="ew", ipady=4, pady=(0, 12))

    ttk.Label(card, text="PIN / hasło", style="WM.TLabel").grid(
        row=4, column=0, sticky="w", pady=(0, 4)
    )
    pin_entry = ttk.Entry(card, textvariable=pin_var, show="*", width=34)
    pin_entry.grid(row=5, column=0, sticky="ew", ipady=4, pady=(0, 8))

    status_label = ttk.Label(
        card,
        textvariable=status_var,
        anchor="center",
        justify="center",
    )
    try:
        status_label.configure(foreground="#e53935")
    except Exception:
        pass
    status_label.grid(row=6, column=0, sticky="ew", pady=(0, 8))

    def _focus_pin(_event=None):
        try:
            pin_entry.focus_set()
            pin_entry.selection_range(0, tk.END)
        except Exception:
            pass

    def _submit(_event=None):
        login_display = login_var.get().strip()
        pin = pin_var.get().strip()
        status_var.set("")

        if not login_display or not pin:
            status_var.set("Podaj użytkownika i PIN / hasło.")
            return "break"

        login_key = login_display.lower()
        try:
            user = gui_logowanie.authenticate(login_key, pin)
        except Exception:
            user = None

        selected_profile = profiles.get(login_display.casefold())
        if not user and isinstance(selected_profile, dict):
            stored_pin = str(selected_profile.get("pin", "") or "").strip()
            stored_password = str(selected_profile.get("haslo", "") or "").strip()
            if pin and (pin == stored_pin or pin == stored_password):
                user = {
                    "login": selected_profile.get("login", login_display),
                    "rola": selected_profile.get("rola", "pracownik"),
                    "status": selected_profile.get("status", ""),
                    "active": selected_profile.get("active", True),
                }

        if not user:
            pin_var.set("")
            status_var.set("Nieprawidłowy login lub PIN.")
            _focus_pin()
            return "break"

        login_final = str(user.get("login", login_display))
        rola = str(user.get("rola", "pracownik"))

        try:
            gui_logowanie.ProfileService.set_active_user(login_final)
        except Exception:
            logger.exception("[PANEL][LOGIN_CARD] Nie udało się ustawić aktywnego użytkownika.")

        _save_last_user(login_final)
        gui_panel.uruchom_panel(root, login_final, rola)
        return "break"

    login_button = ttk.Button(
        card,
        text="Zaloguj",
        command=_submit,
        style="WM.Side.TButton",
    )
    login_button.grid(row=7, column=0, sticky="ew", ipady=4, pady=(2, 10))

    ttk.Label(
        card,
        text="Możesz też użyć przycisku „Zaloguj” w prawym górnym rogu.",
        style="WM.Muted.TLabel",
        anchor="center",
    ).grid(row=8, column=0, sticky="ew")

    card.columnconfigure(0, weight=1)

    try:
        login_entry.bind("<<ComboboxSelected>>", _focus_pin)
    except Exception:
        pass
    pin_entry.bind("<Return>", _submit)

    try:
        if ordered_logins:
            _focus_pin()
        else:
            login_entry.focus_set()
    except Exception:
        pass

    try:
        setattr(content, "_wm_guest_login_card", True)
    except Exception:
        pass
    return True


__all__ = ["install_guest_login_card"]
