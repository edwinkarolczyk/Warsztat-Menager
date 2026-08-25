from pathlib import Path

path = Path('_patch_u2a5_dysp.py')
text = path.read_text(encoding='utf-8')
old = r'''f"Nie udało się zaksięgować naddatku w Magazynie:\n{exc}\n\nDyspozycja nie została zamknięta."'''
new = r'''f"Nie udało się zaksięgować naddatku w Magazynie:\\n{exc}\\n\\nDyspozycja nie została zamknięta."'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f'expected one target, got {count}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('U2A-5 escape fixed')
