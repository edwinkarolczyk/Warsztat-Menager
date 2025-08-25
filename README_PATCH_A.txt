PATCH A – Profil tylko LOGIN (23.08.2025)
========================================
Dla: gui_panel.py 1.6.16 i obecnej struktury wywołań (root, frame, login, rola).

Co jest w paczce:
- gui_profil.py 1.0.6 – minimalny widok, wyświetla WYŁĄCZNIE login zalogowanego użytkownika.

Instalacja:
1) Podmień plik gui_profil.py w katalogu projektu na ten z paczki.
2) Uruchom program, zaloguj się -> w menu (po stronie użytkownika) kliknij „Profil”.
3) Oczekiwany efekt: na ekranie widzisz nagłówek „Profil użytkownika” i pole „Login: <twoj_login>”.

Uwaga:
- Pliku gui_profile.py NIE używamy – pozostaje bez zmian.
- Paczka nie dotyka config.json ani innych modułów.
