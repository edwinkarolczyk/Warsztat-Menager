
WARSZTAT MENAGER – PACZKA 'Profile v2 (read-only + edycja kontaktu)'
====================================================================

Zmiany (tylko to co potrzebne, UI bez ruszania layoutu):
- Usunięto podwójne rysowanie sekcji 'Profil' (zastąpienie całego bloku między markerami).
- Dodano możliwość edycji pól z configu (domyślnie: telefon, email) + przycisk 'Zapisz' zapisujący do profiles.json.
- Reszta pól wyłącznie do odczytu.

Instrukcja:
1) Zatrzymaj aplikację.
2) Podmień plik: gui_uzytkownicy.py (z tej paczki).
3) Upewnij się, że w config.json masz sekcję 'profiles' (zobacz config_profiles_snippet.json).
4) Uruchom program. W zakładce 'Profil' zniknie duplikat, a edytowalne pola pokażą się jako wpisy z przyciskiem Zapisz.
