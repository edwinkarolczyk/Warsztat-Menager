# Plik: gui_uzytkownicy.py
# Wersja pliku: 1.1.0
# Zmiany 1.1.0 (2025-08-23):
# - Integracja z nowym widokiem ProfiI (avatar+zadania).
# - Jeżeli rola != brygadzista/admin → domyślnie pokazuje zakładkę „Profil”.
# ⏹ KONIEC KODU

import tkinter as tk
from tkinter import ttk

try:
    from ui_theme import apply_theme
except Exception:
    def apply_theme(_): pass

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
    try: apply_theme(frame)
    except: pass

    nb = ttk.Notebook(frame); nb.pack(fill="both", expand=True)

    # Zakładka: Profil
    tab_profil = ttk.Frame(nb); nb.add(tab_profil, text="Profil")
    _build_tab_profil(tab_profil, login, rola)

    # (opcjonalnie) inne zakładki mogą być dodane tutaj...
    # tab_inne = ttk.Frame(nb); nb.add(tab_inne, text="Inne")

    # domyślnie przełącz na Profil dla zwykłego użytkownika
    if str(rola).lower() not in ("brygadzista","admin"):
        nb.select(tab_profil)

    return nb

# Zgodność: jeżeli panel woła uruchom_panel(root, frame, login, rola)
def uruchom_panel(root, frame, login=None, rola=None):
    return panel_uzytkownicy(root, frame, login, rola)
