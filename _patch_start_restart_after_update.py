from pathlib import Path

path = Path('start.py')
text = path.read_text(encoding='utf-8')

old_header = """# version: 1.1.7\n# Moduł: start\n# Zmiany 1.1.7:\n"""
new_header = """# version: 1.1.8\n# Moduł: start\n# Zmiany 1.1.8:\n# - Po faktycznym pobraniu aktualizacji WM uruchamia świeży proces zamiast kontynuować na starych modułach w pamięci.\n# - Restart po aktualizacji pomija drugi check Git w nowym procesie.\n# Zmiany 1.1.7:\n"""
assert old_header in text, 'Nie znaleziono nagłówka start.py 1.1.7'
text = text.replace(old_header, new_header, 1)

anchor = """    return result_box[\"value\"]\n\n\n# ====== MAIN ======\n"""
insert = """    return result_box[\"value\"]\n\n\ndef _wm_restart_after_update() -> None:\n    \"\"\"Uruchom świeży proces WM po zmianie plików programu przez Git.\"\"\"\n\n    os.environ[\"WM_RESTARTED_AFTER_UPDATE\"] = \"1\"\n    argv = [sys.executable, *sys.argv]\n    print(\"[WM-DBG][GIT] Restartuję WM po pobranej aktualizacji.\")\n    try:\n        os.execv(sys.executable, argv)\n    except Exception as exc:\n        print(f\"[WM-DBG][GIT] os.execv nieudany: {exc}; próbuję nowego procesu.\")\n        try:\n            subprocess.Popen(argv, cwd=str(APP_ROOT))\n        except Exception as spawn_exc:\n            print(f\"[WM-DBG][GIT] Restart WM nieudany: {spawn_exc}\")\n            raise SystemExit(1) from spawn_exc\n        raise SystemExit(0)\n\n\n# ====== MAIN ======\n"""
assert anchor in text, 'Nie znaleziono końca _wm_git_update_splash'
text = text.replace(anchor, insert, 1)

old_bottom = """    # Przywrócony automatyczny Git check/pull przy starcie.\n    # Na czas tej jednej operacji wyłączamy blokadę bootstrapową z updates_utils,\n    # po czym włączamy ją z powrotem przed budową GUI/logowania.\n    BOOTSTRAP_ACTIVE = False\n    try:\n        _wm_git_update_splash()\n    finally:\n        BOOTSTRAP_ACTIVE = True\n    main()\n"""
new_bottom = """    # Przywrócony automatyczny Git check/pull przy starcie.\n    # Na czas tej jednej operacji wyłączamy blokadę bootstrapową z updates_utils,\n    # po czym włączamy ją z powrotem przed budową GUI/logowania.\n    restarted_after_update = os.environ.pop(\"WM_RESTARTED_AFTER_UPDATE\", \"\") == \"1\"\n    update_result = \"current\"\n    if not restarted_after_update:\n        BOOTSTRAP_ACTIVE = False\n        try:\n            update_result = _wm_git_update_splash()\n        finally:\n            BOOTSTRAP_ACTIVE = True\n        if update_result == \"updated\":\n            _wm_restart_after_update()\n    else:\n        print(\"[WM-DBG][GIT] Świeży proces po aktualizacji — pomijam ponowny check Git.\")\n    main()\n"""
assert old_bottom in text, 'Nie znaleziono bloku __main__ do podmiany'
text = text.replace(old_bottom, new_bottom, 1)

path.write_text(text, encoding='utf-8')
print('start.py patched to 1.1.8')
