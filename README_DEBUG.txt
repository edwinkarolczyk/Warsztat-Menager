# DEBUG PROFILES — co zobaczysz w konsoli

Po podmianie plików i uruchomieniu WM:
- Wejście w Panel → Użytkownicy wypisze:
  [PROFILES-DBG] panel_uzytkownicy: start ...
  [PROFILES-DBG] panel_uzytkownicy: cfg show_tab=... show_head=... fields=...
  [PROFILES-DBG] panel_uzytkownicy: Notebook created
  [PROFILES-DBG] panel_uzytkownicy: tabs added
  [PROFILES-DBG] panel_uzytkownicy: current_user=...
  [PROFILES-DBG] panel_uzytkownicy: render_profile OK

- Wejście w Ustawienia wypisze:
  [PROFILES-DBG] panel_ustawien: start
  [PROFILES-DBG] panel_ustawien: after-calls scheduled
  [PROFILES-DBG] ustawienia: helper start
  [PROFILES-DBG] ustawienia: scanning for Notebook...
  [PROFILES-DBG] ustawienia: Notebook NOT found yet   (jeśli za wcześnie)
  ...po chwili kolejne próby...
  [PROFILES-DBG] ustawienia: tab added

Jeśli zobaczysz ERROR-y, skopiuj je i podeślij — poprawię w punkt.

Aby wyłączyć logi — po testach można przywrócić poprzednie pliki lub usunąć printy.
