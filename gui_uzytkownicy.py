# Plik: gui_uzytkownicy.py
# Wersja pliku: 1.2.0
# Zmiany 1.2.0 (2025-08-25):
# - Brygadzista edytuje pola innych (bez loginu/hasła/avataru).
# - Admin może dodatkowo dodawać i usuwać konta.
# ⏹ KONIEC KODU

import tkinter as tk
from tkinter import ttk

import profile_utils
from ui_theme import apply_theme_safe as apply_theme
from utils.gui_helpers import clear_frame

def _build_tab_profil(parent, login, rola):
    import gui_profile
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    # Wywołanie nowego panelu profilu w ramach zakładki
    gui_profile.panel_profil(parent, frame, login, rola)
    return frame


def _build_tab_visibility(parent, login):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    box = ttk.LabelFrame(frame, text="Widoczność modułów")
    box.pack(fill="both", expand=True, padx=10, pady=10)

    user = profile_utils.get_user(login) or {"login": login, "disabled_modules": []}
    disabled = {str(m).strip().lower() for m in user.get("disabled_modules", [])}

    modules = [
        ("zlecenia", "Zlecenia"),
        ("narzedzia", "Narzędzia"),
        ("maszyny", "Maszyny"),
        ("magazyn", "Magazyn"),
        ("hale", "Hale"),
        ("ustawienia", "Ustawienia"),
        ("uzytkownicy", "Użytkownicy"),
        ("feedback", "Feedback"),
    ]

    vars: dict[str, tk.BooleanVar] = {}

    def _toggle(mod: str) -> None:
        profile_utils.set_module_visibility(login, mod, vars[mod].get())

    for mod, label in modules:
        var = tk.BooleanVar(value=mod not in disabled)
        vars[mod] = var
        ttk.Checkbutton(
            box, text=label, variable=var, command=lambda m=mod: _toggle(m)
        ).pack(anchor="w", padx=4, pady=2)

    return frame

def panel_uzytkownicy(root, frame, login=None, rola=None):
    # Czyść
    clear_frame(frame)
    apply_theme(frame)

    nb = ttk.Notebook(frame); nb.pack(fill="both", expand=True)

    # Zakładka: Profil
    tab_profil = ttk.Frame(nb); nb.add(tab_profil, text="Profil")
    _build_tab_profil(tab_profil, login, rola)

    if login:
        tab_vis = ttk.Frame(nb)
        nb.add(tab_vis, text="Widoczność modułów")
        _build_tab_visibility(tab_vis, login)

    return nb

# Zgodność: jeżeli panel woła uruchom_panel(root, frame, login, rola)
def uruchom_panel(root, frame, login=None, rola=None):
    return panel_uzytkownicy(root, frame, login, rola)
