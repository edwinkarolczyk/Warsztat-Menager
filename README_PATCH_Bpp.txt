PATCH B++ – Pełny PROFIL + alias panel_profil (23.08.2025)
==========================================================
Dla: gui_panel.py 1.6.16 (wywołuje panel_profil / uruchom_panel)

Co zawiera:
- gui_profil.py 1.2.0:
  * AVATAR (avatars/<login>.png) z fallbackiem inicjałów,
  * Login, rola, „Zmiana: X (HH:MM–HH:MM)”,
  * Statystyki: Zadania / Otwarte / Pilne / Zrobione,
  * Lista zadań (Treeview) z kolorami statusów,
  * Przycisk „Otwórz Zlecenia” (obsługa różnych nazw funkcji w gui_zlecenia),
  * Theme fix (apply_theme na root i frame),
  * **Alias:** panel_profil = uruchom_panel (fix błędu „no attribute panel_profil”).

Instalacja:
1) Podmień u siebie gui_profil.py na ten z paczki.
2) (Opcjonalnie) dodaj avatars/<login>.png.
3) (Opcjonalnie) dodaj data/zadania_<login>.json lub centralny data/zadania.json.
