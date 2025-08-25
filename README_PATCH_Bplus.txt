PATCH B+ – Profil: avatar + licznik + kolory + theme fix (23.08.2025)
====================================================================
Dla Twojego gui_panel.py 1.6.16 (sygnatura: uruchom_panel(root, frame, login, rola))

Co zawiera:
- gui_profil.py 1.1.2:
  * AVATAR z avatars/<login>.png (fallback: inicjały na Canvasie),
  * Login, rola, „Zmiana: X (HH:MM–HH:MM)” z gui_panel._shift_bounds(),
  * „Twoje zadania (N)” – licznik + lista w Treeview,
  * Kolorowanie statusów (NOWE/W TOKU/PILNE/DONE) przez tags,
  * Naprawa motywu: apply_theme(root) oraz apply_theme(frame).

Instalacja:
1) Podmień gui_profil.py w projekcie.
2) (Opcjonalnie) avatars/<login>.png dodaj swój obrazek.
3) (Opcjonalnie) data/zadania_<login>.json lub centralny data/zadania.json.

Test:
- Wejdź w „Profil”: zobaczysz avatar, login/rolę, aktualną zmianę i listę zadań.
- Lista ma kolory statusów i licznik zadań w nagłówku.
