from pathlib import Path

path = Path('gui_narzedzia.py')
text = path.read_text(encoding='utf-8')

old_header = '''# Plik: gui_narzedzia.py\n# version: 1.0\n# Zmiany 1.5.31:\n'''
new_header = '''# Plik: gui_narzedzia.py\n# version: 1.5.32\n# Zmiany 1.5.32:\n# - [NARZĘDZIA] Walidacja przy wejściu nie wymaga wycofanego płaskiego klucza zadań serwisowych.\n# - Zadania serwisowe nadal są pobierane z aktualnych definicji typ/status i istniejących fallbacków.\n#\n# Zmiany 1.5.31:\n'''
if text.count(old_header) != 1:
    raise SystemExit(f'Unexpected header matches: {text.count(old_header)}')
text = text.replace(old_header, new_header, 1)

old_check = '''    if not _clean_list(cfg.get("szablony_zadan_narzedzia_stare")):\n        missing.append("zadania (serwis)")\n'''
new_check = '''    # Zadania serwisowe nie są już wymagane jako płaski klucz\n    # ``szablony_zadan_narzedzia_stare``. Aktualny moduł pobiera je z\n    # definicji typ/status (z zachowaniem istniejących fallbacków), więc brak\n    # starego klucza nie może blokować wejścia do Narzędzi fałszywym popupem.\n'''
if text.count(old_check) != 1:
    raise SystemExit(f'Unexpected legacy service check matches: {text.count(old_check)}')
text = text.replace(old_check, new_check, 1)

path.write_text(text, encoding='utf-8')
print('Patched gui_narzedzia.py service config warning')
