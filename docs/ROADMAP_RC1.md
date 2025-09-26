# WM – Roadmapa RC1

Celem jest stworzenie stabilnej wersji **Release Candidate 1**, która "po prostu działa".
Brak nowych ficzerów – tylko naprawy i stabilizacja.

---

## Kryteria „działa”
- Start programu bez wyjątków.
- Zamknięcie programu bez wyjątków.
- Moduły: Ustawienia, Profile, Narzędzia, Zlecenia, Maszyny → działają poprawnie w podstawowym zakresie.

---

## Priorytety napraw
1. **ScrollableFrame / TclError** – Ustawienia (KRYTYCZNY)
2. **Niewidoczne napisy na przyciskach** – Theme/UI (KRYTYCZNY)
3. **Maszyny – jedno źródło danych** (KRYTYCZNY)
4. **Widoczność przycisku „Profil”** – Profile (ŚREDNI)
5. **Zlecenia – niespójne typy/statusy** (ŚREDNI)
6. **Narzędzia – usunięcie możliwości dodawania typu w edycji** (ŚREDNI)
7. **Motywy dodatkowe (Warm, Holiday)** – stabilizacja stylów (NISKI)
8. **Magazyn – niejasne etykiety (tooltipy)** (NISKI)
9. **Hala – renderer opcjonalny** (NISKI)
10. **Git/Auto-update – czytelne komunikaty przy dirty** (NISKI)

---

## Harmonogram (7 dni sprint)
- **Dzień 1–2:** Naprawa krytycznych (1–3).
- **Dzień 3–4:** Naprawa średnich (4–6).
- **Dzień 5–6:** Naprawa niskich (7–10).
- **Dzień 7:** Testy smoke, raport RC1, ewentualne poprawki.

---

## Definicja ukończenia (DoD)
- Brak błędów krytycznych w logach.
- Moduły działają w podstawowym zakresie.
- Dokumentacja uzupełniona (`FILES_UNUSED.md`, `TICKETS_RC1.md`, `ROADMAP_RC1.md`).
