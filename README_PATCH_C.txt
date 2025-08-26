PATCH C – Profil + Alerty (23.08.2025)
======================================
Pliki:
- gui_profil.py 1.3.0
- ustawienia_systemu.py (zaktualizowany panel_ustawien)

Zmiany:
- Profil: avatar 96x96, lista zadań z kolorami, dwuklik otwiera szczegóły zadania (edycja statusu, opis, zlecenie).
- Ustawienia: zakładka Alerty (dla brygadzisty) pokazuje ile zadań otwartych/pilnych/zrobionych mają użytkownicy.

Instalacja:
1) Podmień gui_profil.py i ustawienia_systemu.py na te z paczki.
2) Upewnij się, że pliki data/zadania_<login>.json zawierają pola id, tytul, status, termin, opcjonalnie opis, zlecenie.
3) Odpal WM:
   - Użytkownik → Profil → avatar + szczegóły/edycja statusu.
   - Brygadzista → Ustawienia → zakładka Alerty z podsumowaniem.
