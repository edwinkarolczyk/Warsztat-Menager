from pathlib import Path

path = Path("start.py")
text = path.read_text(encoding="utf-8")

old_header = '''# WM-VERSION: 0.1
# version: 1.1.5
# Moduł: start
# Zmiany 1.1.5:
'''
new_header = '''# WM-VERSION: 0.1
# version: 1.1.6
# Moduł: start
# Zmiany 1.1.6:
# - Po faktycznej aktualizacji ekran potwierdzenia pozostaje widoczny przez 2,5 s.
# - Gdy repozytorium jest aktualne, szybkie przejście do WM pozostaje bez zmian.
# Zmiany 1.1.5:
'''
if text.count(old_header) != 1:
    raise SystemExit(f"header match count={text.count(old_header)}")
text = text.replace(old_header, new_header, 1)

old_delay = '''                    splash.after(650 if value in {"updated", "current"} else 1000, splash.destroy)
'''
new_delay = '''                    if value == "updated":
                        close_delay_ms = 2500
                    elif value == "current":
                        close_delay_ms = 650
                    else:
                        close_delay_ms = 1000
                    splash.after(close_delay_ms, splash.destroy)
'''
if text.count(old_delay) != 1:
    raise SystemExit(f"delay match count={text.count(old_delay)}")
text = text.replace(old_delay, new_delay, 1)

path.write_text(text, encoding="utf-8")
print("patched start.py update completion delay")
