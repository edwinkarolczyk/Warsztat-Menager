
INSTALL (na stałe w Ustawieniach):

1) Podmień w projekcie pliki z tej paczki:
   - ustawienia_systemu.py – funkcja panel_ustawien z kartą „Profile użytkowników” (zastępuje gui_ustawienia.py)
   - gui_uzytkownicy.py – usunięta inicjalizacja injektora (reszta bez zmian)

2) (Opcjonalnie) Usuń plik profiles_settings_injector.py z projektu – nie jest już potrzebny.

3) Uruchom WM → wejdź w „Ustawienia”. Karta „Profile użytkowników” jest w środku Notebooka obok pozostałych.
   Debug w konsoli: „[WM-DBG] dołączam kartę 'Profile użytkowników'” lub ewentualny komunikat błędu.
