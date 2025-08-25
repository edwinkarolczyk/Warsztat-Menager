# Audyt MW – raport

Katalog: C:\Users\Edwin\Desktop\Nowy folder

Plików .py: 38


## Sugestie

- Ujednolić nagłówki # Plik/# Wersja we wszystkich plikach (generator nagłówka w pre-commit).
- Rozbić cykliczne importy – wydzielić warstwę 'core' (modele, utils), 'gui' (widoki), 'app' (uruchomienie).
- Zamienić gołe 'except' na konkretne wyjątki + logger z poziomami (info/warn/error).
- Zapewnić pojedynczy mainloop, kontrolować .after() (cleanup przy zamknięciu), nie mieszać pack/grid w jednym kontenerze.
- Dodać pre-commit (ruff + black, isort). Włączyć flake nieużytych importów.
- Walidować config.json/maszyny.json/uzytkownicy.json z JSON Schema na starcie aplikacji.
- Moduł serwisowy jako oddzielny pakiet z event-busem (pub/sub) i kolejką zadań – izolacja od GUI.
- Potrójne potwierdzenie usuwania: dialog modalny z 3-krotnym 'OK' + timeout i klawisz ESC – antymisclick.
- Wydzielić ui_theme.py jako jedyne źródło kolorów/typografii; zakaz inline kolorów w GUI.

## Znalezione problemy

- **WARN** [HEADER] arch\start_full_1_4_3.py – Brak nagłówka # Plik: ...
- **INFO** [GUI] arch\start_full_1_4_3.py:32 – Wywołanie mainloop() – upewnij się, że tylko jeden raz w całej aplikacji
- **INFO** [GUI] audyt_mw.py:31 – Wywołanie mainloop() – upewnij się, że tylko jeden raz w całej aplikacji
- **INFO** [GUI] audyt_mw.py:69 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] config_manager.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] config_manager.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] config_manager.py:65 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] dashboard_demo_fs.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] dashboard_demo_fs.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] dashboard_demo_fs.py:272 – Wywołanie mainloop() – upewnij się, że tylko jeden raz w całej aplikacji
- **INFO** [GUI] dashboard_demo_fs.py:69 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:71 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:85 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:145 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:147 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:193 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:195 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:197 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:199 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:203 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:204 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:208 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:218 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:219 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:220 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:221 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:225 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:234 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:235 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:243 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:247 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:249 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:252 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:253 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:255 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] dashboard_demo_fs.py:261 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] gui_logowanie.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] gui_logowanie.py:200 – Wywołanie mainloop() – upewnij się, że tylko jeden raz w całej aplikacji
- **INFO** [GUI] gui_logowanie.py:52 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:63 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:66 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:70 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:73 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:75 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:77 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:78 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:82 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:85 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:87 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:93 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:96 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:152 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:155 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:157 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_logowanie.py:136 – Użycie .after(...) – sprawdź, czy nie gubi referencji i czy czyszczone przy zamykaniu
- **INFO** [GUI] gui_logowanie.py:147 – Użycie .after(...) – sprawdź, czy nie gubi referencji i czy czyszczone przy zamykaniu
- **WARN** [HEADER] gui_magazyn.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] gui_magazyn.py:82 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:85 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:88 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:91 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:92 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:93 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:94 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:95 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:96 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:104 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:122 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:182 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:241 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:246 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:262 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:272 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:274 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:280 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:288 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:289 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:290 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:291 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:293 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:294 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:304 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:308 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:320 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:322 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:350 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:352 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:353 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:355 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:357 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:359 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:360 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:362 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:363 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:365 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:366 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:368 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:369 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:372 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:385 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:386 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:396 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:410 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:411 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:412 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:429 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:438 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:442 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:446 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:449 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:451 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:493 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:495 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_magazyn.py:504 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] gui_maszyny.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] gui_maszyny.py:9 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] gui_narzedzia.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] gui_narzedzia.py:248 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:443 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:444 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:447 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:450 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:453 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:463 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:494 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:495 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:497 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:498 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:499 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:500 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:501 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:546 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:553 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:554 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:557 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:563 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:577 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:596 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:597 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:610 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:623 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:636 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:637 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:649 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:661 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:665 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:666 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:673 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:675 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:729 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:732 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:743 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:745 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:748 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:757 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:793 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:795 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:798 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:894 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_narzedzia.py:895 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] gui_panel.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] gui_panel.py:40 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:45 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:49 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:67 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:74 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:81 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:88 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:97 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:138 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:139 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:141 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:142 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:144 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:146 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:148 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:150 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:151 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:154 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:155 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:158 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:159 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:160 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:217 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:245 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:248 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:249 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:250 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:252 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:256 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:259 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:263 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_panel.py:195 – Użycie .after(...) – sprawdź, czy nie gubi referencji i czy czyszczone przy zamykaniu
- **INFO** [GUI] gui_panel.py:204 – Użycie .after(...) – sprawdź, czy nie gubi referencji i czy czyszczone przy zamykaniu
- **WARN** [HEADER] gui_produkty.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] gui_produkty.py:97 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:98 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:100 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:103 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:104 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:105 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:106 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:109 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:112 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:114 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:116 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:118 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:121 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:125 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:126 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:127 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:128 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:131 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:139 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:140 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:141 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:201 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:202 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:207 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:210 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:212 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:214 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:216 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_produkty.py:233 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] gui_profil.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] gui_profil.py:94 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:95 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:96 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:97 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:98 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:99 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:100 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:119 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:121 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:125 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:126 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:127 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:130 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:133 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:134 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_profil.py:141 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] gui_profile.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] gui_profile.py:21 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] gui_ustawienia.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] gui_ustawienia.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] gui_ustawienia.py:16 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:42 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:51 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:52 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:53 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:53 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:54 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:54 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:58 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:67 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:73 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:79 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:91 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:91 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:92 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:92 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:93 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:93 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:95 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:96 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:97 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:98 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:99 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:100 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:101 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:102 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:103 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:105 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:106 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:111 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:111 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:112 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:112 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:126 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_ustawienia.py:133 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] gui_uzytkownicy.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] gui_uzytkownicy.py:19 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_uzytkownicy.py:32 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] gui_zlecenia.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] gui_zlecenia.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] gui_zlecenia.py:77 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:78 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:81 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:82 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:83 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:84 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:86 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:87 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:89 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:90 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:91 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:94 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:96 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:108 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:194 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:196 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:202 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:204 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:206 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:209 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:211 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:213 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:215 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:241 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:242 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:243 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:256 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:257 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:258 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:266 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:271 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] gui_zlecenia.py:272 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] kreator_sprawdzenia.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] kreator_sprawdzenia.py – Brak nagłówka # Wersja: ...
- **INFO** [HEADER] kreator_sprawdzenia_plikow.py – Nagłówek # Plik wskazuje 'kreator_sprawdzenia.py', ale plik to 'kreator_sprawdzenia_plikow.py'
- **WARN** [HEADER] layout_prosty.py – Brak nagłówka # Plik: ...
- **INFO** [GUI] layout_prosty.py:9 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] layout_prosty.py:18 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] layout_prosty.py:22 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] layout_prosty.py:26 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] layout_prosty.py:30 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] layout_prosty.py:34 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] layout_prosty.py:38 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] layout_prosty.py:44 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] leaves.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] leaves.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] leaves.py:41 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] logger.py – Brak nagłówka # Wersja: ...
- **WARN** [HEADER] logika_magazyn.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] logika_magazyn.py:89 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] logika_zadan.py – Brak nagłówka # Wersja: ...
- **WARN** [HEADER] migrate_profiles_config.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] migrate_profiles_config.py – Brak nagłówka # Wersja: ...
- **WARN** [HEADER] migrations.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] migrations.py – Brak nagłówka # Wersja: ...
- **WARN** [HEADER] presence.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] presence.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] presence.py:43 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] presence_watcher.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] presence_watcher.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] presence_watcher.py:45 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] presence_watcher.py:135 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] presence_watcher.py:148 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] presence_watcher.py:148 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] presence_watcher.py:148 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] presence_watcher.py:170 – Użycie .after(...) – sprawdź, czy nie gubi referencji i czy czyszczone przy zamykaniu
- **WARN** [HEADER] profile_utils.py – Brak nagłówka # Wersja: ...
- **WARN** [HEADER] profiles_settings_injector.py – Brak nagłówka # Plik: ...
- **INFO** [GUI] profiles_settings_injector.py:91 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] profiles_settings_injector.py:92 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] profiles_settings_injector.py:93 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] profiles_settings_injector.py:95 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] profiles_settings_injector.py:96 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] profiles_settings_injector.py:97 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] profiles_settings_injector.py:105 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] profiles_settings_injector.py:142 – Użycie .after(...) – sprawdź, czy nie gubi referencji i czy czyszczone przy zamykaniu
- **INFO** [GUI] profiles_settings_injector.py:143 – Użycie .after(...) – sprawdź, czy nie gubi referencji i czy czyszczone przy zamykaniu
- **WARN** [HEADER] start.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] start.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] start.py:135 – Wywołanie mainloop() – upewnij się, że tylko jeden raz w całej aplikacji
- **WARN** [HEADER] test_kreator_gui.py – Brak nagłówka # Wersja: ...
- **WARN** [HEADER] test_kreator_wersji.py – Brak nagłówka # Wersja: ...
- **WARN** [HEADER] ui_theme.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] ui_theme.py – Brak nagłówka # Wersja: ...
- **WARN** [HEADER] updater.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] updater.py:158 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:203 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:206 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:210 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:215 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:217 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:219 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:223 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:228 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:234 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:235 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:236 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:245 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:249 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:368 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:377 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:380 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:391 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] updater.py:392 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] ustawienia_produkty_bom.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] ustawienia_produkty_bom.py:84 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:85 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:86 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:87 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:88 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:89 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:90 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:93 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:95 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:96 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:97 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:98 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:101 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:103 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:104 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:105 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:106 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:108 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:156 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:157 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:160 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:162 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:163 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:164 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:165 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_produkty_bom.py:177 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **WARN** [HEADER] ustawienia_systemu.py – Brak nagłówka # Wersja: ...
- **INFO** [GUI] ustawienia_systemu.py:22 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_systemu.py:29 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_systemu.py:38 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_systemu.py:68 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_systemu.py:73 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [GUI] ustawienia_systemu.py:78 – Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu
- **INFO** [HEADER] wymagane_pliki_version_check.py – Nagłówek # Plik wskazuje 'kreator_sprawdzenia.py', ale plik to 'wymagane_pliki_version_check.py'
- **WARN** [HEADER] zlecenia_logika.py – Brak nagłówka # Plik: ...
- **WARN** [HEADER] zlecenia_logika.py – Brak nagłówka # Wersja: ...
- **WARN** [HEADER] zlecenia_utils.py – Brak nagłówka # Wersja: ...
- **WARN** [IMPORT] gui_panel.py :: gui_uzytkownicy.py :: gui_profil.py :: gui_panel.py – Cykliczne importy (rozważ refaktor)
- **INFO** [STYLE] audyt_mw.py, C:\Users\Edwin\Desktop\Nowy folder\config_manager.py, C:\Users\Edwin\Desktop\Nowy folder\dashboard_demo_fs.py, C:\Users\Edwin\Desktop\Nowy folder\gui_magazyn.py, C:\Users\Edwin\Desktop\Nowy folder\gui_produkty.py, C:\Users\Edwin\Desktop\Nowy folder\layout_prosty.py, C:\Users\Edwin\Desktop\Nowy folder\start.py, C:\Users\Edwin\Desktop\Nowy folder\updater.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_systemu.py – Definicja '__init__' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] audyt_mw.py, C:\Users\Edwin\Desktop\Nowy folder\leaves.py – Definicja '_read' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] config_manager.py, C:\Users\Edwin\Desktop\Nowy folder\gui_produkty.py, C:\Users\Edwin\Desktop\Nowy folder\logika_magazyn.py, C:\Users\Edwin\Desktop\Nowy folder\updater.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_produkty_bom.py, C:\Users\Edwin\Desktop\Nowy folder\zlecenia_logika.py – Definicja '_ensure_dirs' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] config_manager.py, C:\Users\Edwin\Desktop\Nowy folder\profile_utils.py – Definicja '_load_json' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] config_manager.py, C:\Users\Edwin\Desktop\Nowy folder\profile_utils.py – Definicja '_save_json' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] config_manager.py, C:\Users\Edwin\Desktop\Nowy folder\start.py – Definicja 'get' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_logowanie.py, C:\Users\Edwin\Desktop\Nowy folder\gui_panel.py, C:\Users\Edwin\Desktop\Nowy folder\presence.py, C:\Users\Edwin\Desktop\Nowy folder\presence_watcher.py – Definicja '_tick' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_logowanie.py, C:\Users\Edwin\Desktop\Nowy folder\gui_magazyn.py, C:\Users\Edwin\Desktop\Nowy folder\gui_narzedzia.py, C:\Users\Edwin\Desktop\Nowy folder\gui_panel.py, C:\Users\Edwin\Desktop\Nowy folder\gui_produkty.py, C:\Users\Edwin\Desktop\Nowy folder\gui_profil.py, C:\Users\Edwin\Desktop\Nowy folder\gui_profile.py, C:\Users\Edwin\Desktop\Nowy folder\gui_uzytkownicy.py, C:\Users\Edwin\Desktop\Nowy folder\ui_theme.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_produkty_bom.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_systemu.py – Definicja 'apply_theme' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_magazyn.py, C:\Users\Edwin\Desktop\Nowy folder\gui_narzedzia.py – Definicja '_add_type' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_magazyn.py, C:\Users\Edwin\Desktop\Nowy folder\gui_produkty.py – Definicja '_build_ui' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_magazyn.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_produkty_bom.py – Definicja '_load' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_magazyn.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_produkty_bom.py – Definicja '_refresh' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_magazyn.py, C:\Users\Edwin\Desktop\Nowy folder\gui_panel.py – Definicja 'open_panel_magazyn' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_magazyn.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_systemu.py – Definicja 'panel_ustawien_magazyn' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_maszyny.py, C:\Users\Edwin\Desktop\Nowy folder\gui_panel.py – Definicja 'panel_maszyny' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_narzedzia.py, C:\Users\Edwin\Desktop\Nowy folder\gui_panel.py – Definicja 'panel_narzedzia' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_panel.py, C:\Users\Edwin\Desktop\Nowy folder\logger.py – Definicja 'log_akcja' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_panel.py, C:\Users\Edwin\Desktop\Nowy folder\gui_ustawienia.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_systemu.py – Definicja 'panel_ustawien' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_panel.py, C:\Users\Edwin\Desktop\Nowy folder\gui_uzytkownicy.py – Definicja 'panel_uzytkownicy' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_panel.py, C:\Users\Edwin\Desktop\Nowy folder\gui_zlecenia.py – Definicja 'panel_zlecenia' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_panel.py, C:\Users\Edwin\Desktop\Nowy folder\gui_profil.py, C:\Users\Edwin\Desktop\Nowy folder\gui_uzytkownicy.py – Definicja 'uruchom_panel' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_produkty.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_produkty_bom.py – Definicja '_add_row' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_produkty.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_produkty_bom.py – Definicja '_del_row' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_produkty.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_produkty_bom.py – Definicja '_list_produkty' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_produkty.py, C:\Users\Edwin\Desktop\Nowy folder\updater.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_produkty_bom.py – Definicja '_ok' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_produkty.py, C:\Users\Edwin\Desktop\Nowy folder\presence_watcher.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_produkty_bom.py, C:\Users\Edwin\Desktop\Nowy folder\zlecenia_logika.py – Definicja '_read_json' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_produkty.py, C:\Users\Edwin\Desktop\Nowy folder\presence_watcher.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_produkty_bom.py, C:\Users\Edwin\Desktop\Nowy folder\zlecenia_logika.py – Definicja '_write_json' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] gui_ustawienia.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_produkty_bom.py – Definicja '_save' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] kreator_sprawdzenia_plikow.py, C:\Users\Edwin\Desktop\Nowy folder\wymagane_pliki_version_check.py – Definicja 'sprawdz' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] leaves.py, C:\Users\Edwin\Desktop\Nowy folder\presence_watcher.py – Definicja '_cfg' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] leaves.py, C:\Users\Edwin\Desktop\Nowy folder\presence_watcher.py – Definicja '_path' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] logika_magazyn.py, C:\Users\Edwin\Desktop\Nowy folder\start.py – Definicja '_log_info' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] logika_magazyn.py, C:\Users\Edwin\Desktop\Nowy folder\presence_watcher.py – Definicja '_now' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] test_kreator_gui.py, C:\Users\Edwin\Desktop\Nowy folder\test_kreator_wersji.py – Definicja 'zapisz_log' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] updater.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_systemu.py – Definicja 'UpdatesUI' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] updater.py, C:\Users\Edwin\Desktop\Nowy folder\ustawienia_systemu.py – Definicja '_style_exists' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu
- **INFO** [STYLE] audyt_mw.py – Możliwy nieużyty import: Counter
- **INFO** [STYLE] audyt_mw.py – Możliwy nieużyty import: annotations
- **INFO** [STYLE] audyt_mw.py – Możliwy nieużyty import: deque
- **INFO** [STYLE] audyt_mw.py – Możliwy nieużyty import: traceback
- **INFO** [STYLE] config_manager.py – Możliwy nieużyty import: annotations
- **INFO** [STYLE] gui_panel.py – Możliwy nieużyty import: panel_ustawien
- **INFO** [STYLE] gui_profile.py – Możliwy nieużyty import: messagebox
- **INFO** [STYLE] gui_profile.py – Możliwy nieużyty import: tk
- **INFO** [STYLE] gui_uzytkownicy.py – Możliwy nieużyty import: tk
- **INFO** [STYLE] migrations.py – Możliwy nieużyty import: annotations
- **INFO** [STYLE] presence.py – Możliwy nieużyty import: time
- **INFO** [STYLE] presence_watcher.py – Możliwy nieużyty import: time
- **INFO** [STYLE] test_kreator_gui.py – Możliwy nieużyty import: os
- **INFO** [STYLE] test_kreator_gui.py – Możliwy nieużyty import: tk
- **INFO** [STYLE] ui_theme.py – Możliwy nieużyty import: annotations
- **INFO** [STYLE] ustawienia_systemu.py – Możliwy nieużyty import: tk
- **INFO** [STYLE] wymagane_pliki_version_check.py – Możliwy nieużyty import: os
- **INFO** [STYLE] zlecenia_logika.py – Możliwy nieużyty import: os
- **INFO** [TODO] audyt_mw.py:173 – Znacznik TODO/FIXME/HACK – rozważ zaplanowanie zadania
- **INFO** [TODO] audyt_mw.py:173 – Znacznik TODO/FIXME/HACK – rozważ zaplanowanie zadania
- **INFO** [TODO] audyt_mw.py:174 – Znacznik TODO/FIXME/HACK – rozważ zaplanowanie zadania
- **INFO** [TODO] audyt_mw.py:174 – Znacznik TODO/FIXME/HACK – rozważ zaplanowanie zadania
- **INFO** [TODO] audyt_mw.py:174 – Znacznik TODO/FIXME/HACK – rozważ zaplanowanie zadania
- **INFO** [TODO] audyt_mw.py:176 – Znacznik TODO/FIXME/HACK – rozważ zaplanowanie zadania
- **INFO** [TODO] audyt_mw.py:176 – Znacznik TODO/FIXME/HACK – rozważ zaplanowanie zadania
- **INFO** [TODO] audyt_mw.py:176 – Znacznik TODO/FIXME/HACK – rozważ zaplanowanie zadania
- **INFO** [TODO] audyt_mw.py:176 – Znacznik TODO/FIXME/HACK – rozważ zaplanowanie zadania
- **WARN** [ERROR-HANDLING] dashboard_demo_fs.py:182 – Goły except – dodaj konkretny wyjątek i logowanie
- **WARN** [ERROR-HANDLING] gui_panel.py:227 – Goły except – dodaj konkretny wyjątek i logowanie
- **WARN** [ERROR-HANDLING] gui_uzytkownicy.py:28 – Goły except – dodaj konkretny wyjątek i logowanie
- **WARN** [ERROR-HANDLING] gui_uzytkownicy.py:30 – Goły except – dodaj konkretny wyjątek i logowanie
- **WARN** [JSON] config.json – Brak kluczy ['theme', 'start_view', 'pin_required'] w obiekcie 
- **WARN** [JSON] maszyny.json – Brak kluczy ['id', 'hala'] w obiekcie [0]
- **WARN** [JSON] maszyny.json – Brak kluczy ['id', 'hala'] w obiekcie [1]
- **WARN** [JSON] maszyny.json – Brak kluczy ['id', 'hala'] w obiekcie [2]
- **WARN** [JSON] maszyny.json – Brak kluczy ['id', 'hala'] w obiekcie [3]
- **WARN** [JSON] maszyny.json – Brak kluczy ['id', 'hala'] w obiekcie [4]
- **WARN** [JSON] maszyny.json – Brak kluczy ['id', 'hala'] w obiekcie [5]
- **WARN** [JSON] maszyny.json – Brak kluczy ['id', 'hala'] w obiekcie [6]
- **WARN** [JSON] maszyny.json – Brak kluczy ['id', 'hala'] w obiekcie [7]
- **WARN** [JSON] maszyny.json – Brak kluczy ['id', 'hala'] w obiekcie [8]
- **WARN** [JSON] maszyny.json – Brak kluczy ['id', 'hala'] w obiekcie [9]
- **WARN** [JSON] maszyny.json – Brak kluczy ['id', 'hala'] w obiekcie [10]

## Podsumowania plików

### arch\start_full_1_4_3.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: OK
- Deklarowana wersja: 1.4.3
- Składnia: OK
- Importy: gui_logowanie, json, os, tkinter
- Definicje: -

### audyt_mw.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: OK
- Deklarowana nazwa: audyt_mw.py
- Deklarowana wersja: 0.9.0
- Składnia: OK
- Importy: __future__, ast, collections, dataclasses, json, os, re, sys, traceback, typing
- Definicje: AudytMW, FileIssue, FileSummary, __init__, _check_json_file, _collect_defs, _collect_imports, _find_cycles, _find_module_path, _issue, _parse_ast, _read, _read_headers, _render_md, build_suggestions, check_obj, dfs, discover, main, pass_deep, pass_fast, pass_risk, write_reports

### config_manager.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: __future__, datetime, json, os, shutil, typing
- Definicje: ConfigError, ConfigManager, __init__, _audit_change, _ensure_dirs, _load_json, _load_json_or_raise, _merge_all, _prune_rollbacks, _save_json, _schema_index, _validate_all, _validate_value, apply_import, deep_merge, export_public, flatten, get, get_by_key, import_with_dry_run, save_all, set, set_by_key

### dashboard_demo_fs.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: ctypes, json, math, os, sys, tkinter, ui_theme
- Definicje: WMDashboard, WMMiniHala, WMSpark, WMTile, __init__, _enable_dpi_awareness, load_awarie, load_hale, on_click, on_drag, on_release, on_resize, redraw, sample_list_short, sample_orders, save_hale, toggle_edit_mode

### gui_logowanie.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: gui_logowanie.py
- Składnia: OK
- Importy: PIL, datetime, gui_panel, json, os, tkinter, ui_theme
- Definicje: _on_destroy, _tick, apply_theme, draw_login_shift, ekran_logowania, logowanie, zamknij

### gui_magazyn.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: gui_magazyn.py
- Składnia: OK
- Importy: logika_magazyn, re, tkinter, ui_theme
- Definicje: PanelMagazyn, __init__, _act_rezerwuj, _act_zuzyj, _act_zwolnij, _act_zwrot, _add_type, _ask_float, _build_ui, _color_for, _extract_prefix, _filter, _get_selected_type, _has_priv, _init_lists, _load, _napraw, _refresh, _reload_types, _remove_type, _resolve_role, _sel_id, _show_historia, _submit, _suggest_id, _update_alerts, _update_sum_label, apply_theme, attach_magazyn_button, open_panel_magazyn, panel_ustawien_magazyn

### gui_maszyny.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: gui_maszyny.py
- Składnia: OK
- Importy: tkinter
- Definicje: panel_maszyny

### gui_narzedzia.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: gui_narzedzia.py
- Składnia: OK
- Importy: datetime, json, logika_zadan, os, tkinter, ui_theme
- Definicje: _add_from_template, _add_task, _add_type, _append_type_to_config, _apply_template_for_phase, _band_tag, _bar_text, _can_convert_nn_to_sn, _clean_list, _dbg, _del_sel, _ensure_folder, _existing_numbers, _has_title, _is_taken, _iter_folder_items, _iter_legacy_json_items, _legacy_parse_tasks, _load_all_tools, _load_config, _maybe_seed_config_templates, _next_free_in_range, _normalize_status, _on_status_change, _phase_for_status, _read_tool, _resolve_tools_dir, _save_config, _save_tool, _sel_idx, _stare_convert_templates_from_config, _statusy_for_mode, _suggest_after, _sync_conv_mode, _task_templates_from_config, _tasks_for_type, _toggle_done, _types_from_config, apply_theme, choose_mode_and_add, on_double, open_tool_dialog, panel_narzedzia, refresh_list, repaint_hist, repaint_tasks, row, save, toggle_hist

### gui_panel.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: gui_panel.py
- Składnia: OK
- Importy: datetime, gui_magazyn, gui_maszyny, gui_narzedzia, gui_uzytkownicy, gui_zlecenia, logger, tkinter, traceback, ui_theme, ustawienia_systemu
- Definicje: _is_admin_role, _on_shift_destroy, _open_profil, _shift_bounds, _shift_progress, _tick, apply_theme, draw_shift_bar, log_akcja, open_panel_magazyn, otworz_panel, panel_maszyny, panel_narzedzia, panel_ustawien, panel_uzytkownicy, panel_zlecenia, uruchom_panel, wyczysc_content

### gui_produkty.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: gui_produkty.py
- Składnia: OK
- Importy: glob, json, os, tkinter, ui_theme
- Definicje: ProduktyBOM, __init__, _add_row, _build_ui, _del_row, _delete_product, _ensure_dirs, _get_sel_index, _list_materialy_z_magazynu, _list_produkty, _load_selected, _name_for, _new_product, _ok, _read_json, _reload_lists, _save_current, _write_json, apply_theme, open_panel_produkty

### gui_profil.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: gui_profil.py
- Składnia: OK
- Importy: datetime, gui_panel, gui_zlecenia, json, os, tkinter, ui_theme
- Definicje: _build_header, _build_stats, _build_tasks, _is_open, _is_urgent, _load_avatar, _open_zlecenia, _read_tasks, _safe_theme, _shift_bounds_label, _stats_from_tasks, _tag, apply_theme, chip, uruchom_panel

### gui_profile.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: gui_profile.py
- Składnia: OK
- Importy: tkinter, ui_theme
- Definicje: apply_theme, panel_profile

### gui_ustawienia.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: json, tkinter
- Definicje: _browse, _get_shift_val, _save, _save_cfg, _wm_build_presence_settings_tab, _wm_build_profiles_settings_tab, panel_ustawien

### gui_uzytkownicy.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: gui_uzytkownicy.py
- Składnia: OK
- Importy: gui_profil, tkinter, ui_theme
- Definicje: _build_tab_profil, apply_theme, panel_uzytkownicy, uruchom_panel

### gui_zlecenia.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: tkinter, ui_theme, zlecenia_logika
- Definicje: _apply_theme, _bar10, _edit_status_dialog, _fmt, _kreator_zlecenia, _match, _maybe_theme, _odswiez, _on_dbl, _popup, _usun_zlecenie, akcept, ok, panel_zlecenia

### kreator_sprawdzenia.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: argparse, datetime, json, os, re
- Definicje: check_config_min_keys, check_file_version, check_required_paths, compare_versions, extract_version_from_text, load_expected_versions, main, parse_args, read_text_head, version_tuple, write_sample_versions

### kreator_sprawdzenia_plikow.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: OK
- Deklarowana nazwa: kreator_sprawdzenia.py
- Deklarowana wersja: 1.0
- Składnia: OK
- Importy: hashlib, os
- Definicje: oblicz_sha256, sprawdz

### layout_prosty.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: OK
- Deklarowana wersja: 1.4.4
- Składnia: OK
- Importy: tkinter
- Definicje: LayoutProsty, __init__, filtruj_liste, ustaw_liste, ustaw_szczegoly

### leaves.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: datetime, json, os
- Definicje: _cfg, _path, _read, _read_users, _write, add_entry, entitlements_for, read_all, totals_for

### logger.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: logger.py
- Składnia: OK
- Importy: datetime, json
- Definicje: log_akcja, log_magazyn

### logika_magazyn.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: logika_magazyn.py
- Składnia: OK
- Importy: datetime, json, logger, os, threading
- Definicje: _default_magazyn, _ensure_dirs, _history_entry, _log_info, _log_mag, _now, add_item_type, get_item, get_item_types, historia_item, lista_items, load_magazyn, remove_item_type, rezerwuj, save_magazyn, sprawdz_progi, upsert_item, zuzyj, zwolnij_rezerwacje, zwrot

### logika_zadan.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: logika_zadan.py
- Składnia: OK
- Importy: json, logika_magazyn, os
- Definicje: _load_bom, consume_for_task

### migrate_profiles_config.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: json, os, sys
- Definicje: -

### migrations.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: __future__, typing
- Definicje: migrate, needs_migration

### presence.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: atexit, datetime, json, os, platform, tempfile, time
- Definicje: _atomic_write, _cfg_dir, _get_cfg, _now_utc_iso, _on_exit, _presence_path, _read_all, _tick, end_session, heartbeat, read_presence, start_heartbeat

### presence_watcher.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: datetime, json, os, presence, time
- Definicje: _active_shift, _cfg, _ensure_alert, _is_online, _now, _parse_hhmm, _path, _read_json, _shifts_from_cfg, _tick, _today_str, _users_meta, _write_json, run_check, schedule_watcher

### profile_utils.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: profile_utils.py
- Składnia: OK
- Importy: json, os
- Definicje: _load_json, _save_json, ensure_user_fields, find_user_by_pin, get_tasks_for, read_users, write_users

### profiles_settings_injector.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: OK
- Deklarowana wersja: 0.3 — szerokie wykrywanie Ustawień, logi, skrót Ctrl+Alt+U
- Składnia: OK
- Importy: tkinter
- Definicje: _apply, _attach_tab, _candidate_score, _cfg_get, _cfg_set, _find_candidate_notebooks, _get_title, _iter_all_windows, _nb_has_settings_like_tabs, force_attach_to_focused, start, tick

### start.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: config_manager, datetime, gui_logowanie, json, os, sys, tkinter, traceback, uuid
- Definicje: TeeLogger, Tmp, __init__, _excepthook, _log_error, _log_info, _safe_log, flush, get, init_config, main, write

### test_kreator_gui.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: test_kreator_gui.py
- Składnia: OK
- Importy: os, pyautogui, time, tkinter
- Definicje: zapisz_log

### test_kreator_wersji.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: test_kreator_wersji.py
- Składnia: OK
- Importy: os, time
- Definicje: zapisz_log

### ui_theme.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: __future__, tkinter
- Definicje: _init_styles, apply_theme

### updater.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: updater.py
- Składnia: OK
- Importy: datetime, io, os, pathlib, re, shutil, subprocess, sys, tkinter, zipfile
- Definicje: UpdatesUI, __init__, _append_out, _apply_local_theme, _backup_files, _build, _copy_versions, _do_restore, _ensure_dirs, _extract_zip_overwrite, _iter_python_files, _list_backups, _now_stamp, _ok, _on_git_pull, _on_restore, _on_zip_update, _read_head, _refresh_versions, _restart_app, _restore_backup, _run_git_pull, _scan_versions, _style_exists, _theme_colors, _versions_to_text, _write_log

### ustawienia_produkty_bom.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: ustawienia_produkty_bom.py
- Składnia: OK
- Importy: glob, json, os, tkinter, ui_theme
- Definicje: _add_row, _del_row, _delete, _ensure_dirs, _list_materialy, _list_produkty, _load, _new, _ok, _read_json, _refresh, _save, _select_idx, _write_json, apply_theme, make_tab

### ustawienia_systemu.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: ustawienia_systemu.py
- Składnia: OK
- Importy: gui_magazyn, tkinter, ui_theme, updater, ustawienia_produkty_bom
- Definicje: UpdatesUI, __init__, _make_frame, _style_exists, apply_theme, panel_ustawien, panel_ustawien_magazyn, panel_ustawien_produkty

### wymagane_pliki_version_check.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: OK
- Deklarowana nazwa: kreator_sprawdzenia.py
- Deklarowana wersja: 1.1
- Składnia: OK
- Importy: os, re
- Definicje: sprawdz, sprawdz_wersje

### zlecenia_logika.py
- Nagłówek # Plik: BRAK
- Nagłówek # Wersja: BRAK
- Składnia: OK
- Importy: datetime, json, os, pathlib
- Definicje: _ensure_dirs, _next_id, _read_json, _write_json, check_materials, create_zlecenie, delete_zlecenie, list_produkty, list_zlecenia, read_bom, read_magazyn, reserve_materials, update_status

### zlecenia_utils.py
- Nagłówek # Plik: OK
- Nagłówek # Wersja: BRAK
- Deklarowana nazwa: zlecenia_utils.py
- Składnia: OK
- Importy: datetime, json, os
- Definicje: przelicz_zapotrzebowanie, sprawdz_magazyn, zapisz_zlecenie
