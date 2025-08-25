PATCH B – Profil (avatar + login + zmiana + zadania) + integracja w Użytkownicy
===============================================================================
Dla: gui_panel.py 1.6.16

Co w paczce:
- gui_profil.py 1.1.0 — nowy widok profilu z avatarem i listą zadań.
- gui_uzytkownicy.py 1.1.0 — zakładka „Profil” woła nowy widok profilu.

Instalacja:
1) Podmień pliki: gui_profil.py i gui_uzytkownicy.py w katalogu projektu.
2) (Opcjonalnie) dodaj avatar PNG: avatars/<login>.png (np. avatars/edwin.png).
3) (Opcjonalnie) dodaj plik z zadaniami: data/zadania_<login>.json, np.:
   [
     {"id":"Z-101","tytul":"Przygotować stanowisko","status":"W toku","termin":"2025-08-24"},
     {"id":"Z-102","tytul":"Sprawdzić narzędzia","status":"Nowe","termin":"2025-08-25"}
   ]
4) Uruchom program → zaloguj się → wejdź: Użytkownicy → zakładka „Profil”
   (dla zwykłego użytkownika panel 1.6.16 i tak kieruje na „Profil”).

Uwagi:
- Nie ruszamy gui_panel.py.
- Nowy widok profilu nie wymaga PIL.
- Jeśli moduł Zlecenia nie ma znanej funkcji, przycisk w profilu pokaże komunikat zamiast crasha.
