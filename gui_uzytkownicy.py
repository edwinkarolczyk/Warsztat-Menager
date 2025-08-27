# Plik: gui_uzytkownicy.py
# Wersja pliku: 1.2.0
# Zmiany 1.2.0 (2025-08-25):
# - Brygadzista edytuje pola innych (bez loginu/hasła/avataru).
# - Admin może dodatkowo dodawać i usuwać konta.
# ⏹ KONIEC KODU

from tkinter import ttk

from ui_theme import apply_theme_safe as apply_theme
import ustawienia_uzytkownicy

def _build_tab_profil(parent, login, rola):
    import gui_profile
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    # Wywołanie nowego panelu profilu w ramach zakładki
    gui_profile.panel_profil(parent, frame, login, rola)
    return frame

def panel_uzytkownicy(root, frame, login=None, rola=None):
    # Czyść
    for w in frame.winfo_children():
        try: w.destroy()
        except: pass
    apply_theme(frame)

    nb = ttk.Notebook(frame); nb.pack(fill="both", expand=True)

    # Zakładka: Profil
    tab_profil = ttk.Frame(nb); nb.add(tab_profil, text="Profil")
    _build_tab_profil(tab_profil, login, rola)

    # Zakładka zarządzania użytkownikami dla brygadzisty/admina
    if str(rola).lower() in ("brygadzista", "admin"):
        tab_users = ttk.Frame(nb); nb.add(tab_users, text="Użytkownicy")
        ustawienia_uzytkownicy.make_tab(tab_users, rola)

    # domyślnie przełącz na Profil dla zwykłego użytkownika
    if str(rola).lower() not in ("brygadzista","admin"):
        nb.select(tab_profil)

    return nb

# Zgodność: jeżeli panel woła uruchom_panel(root, frame, login, rola)
def uruchom_panel(root, frame, login=None, rola=None):
    return panel_uzytkownicy(root, frame, login, rola)
