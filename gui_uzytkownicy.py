# Plik: gui_uzytkownicy.py
# Wersja pliku: 1.2.0
# Zmiany 1.2.0 (2025-08-25):
# - Brygadzista edytuje pola innych (bez loginu/hasła/avataru).
# - Admin może dodatkowo dodawać i usuwać konta.
# ⏹ KONIEC KODU

from tkinter import ttk

from ui_theme import apply_theme_safe as apply_theme
from utils.gui_helpers import clear_frame

def _build_tab_profil(parent, login, rola):
    import gui_profile
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    # Wywołanie nowego panelu profilu w ramach zakładki
    gui_profile.panel_profil(parent, frame, login, rola)
    return frame

def panel_uzytkownicy(root, frame, login=None, rola=None):
    # Czyść
    clear_frame(frame)
    apply_theme(frame)

    nb = ttk.Notebook(frame); nb.pack(fill="both", expand=True)

    # Zakładka: Profil
    tab_profil = ttk.Frame(nb); nb.add(tab_profil, text="Profil")
    _build_tab_profil(tab_profil, login, rola)


    return nb

# Zgodność: jeżeli panel woła uruchom_panel(root, frame, login, rola)
def uruchom_panel(root, frame, login=None, rola=None):
    return panel_uzytkownicy(root, frame, login, rola)
