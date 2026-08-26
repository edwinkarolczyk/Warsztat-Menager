from pathlib import Path
import subprocess

PATH = Path('gui_profile.py')
EXPECTED = '9764ef37a84125b79744bf0a3a4f017607b8c17f'
actual = subprocess.check_output(['git','hash-object',str(PATH)], text=True).strip()
if actual != EXPECTED:
    raise SystemExit(f'gui_profile.py changed: expected {EXPECTED}, got {actual}')

text = PATH.read_text(encoding='utf-8')
text = text.replace('# version: 1.7.0\n', '# version: 1.7.1\n', 1)
text = text.replace(
    '# Wersja: 1.7.0\n# Zmiany 1.7.0:\n',
    '# Wersja: 1.7.1\n# Zmiany 1.7.1:\n# - Dwuklik i przycisk Otwórz Dyspozycję otwierają zaznaczony wpis w aktualnym kreatorze edycji.\n# Zmiany 1.7.0:\n',
    1,
)

old = '''        if not active_rows:\n            ttk.Label(\n                box,\n                text="Brak aktywnych Dyspozycji dla tego użytkownika.",\n                style="WM.Muted.TLabel",\n            ).pack(anchor="w", pady=(8, 0))\n\n'''
new = '''        def _open_selected_dyspozycja(_event=None) -> None:\n            selected = tree.selection()\n            if not selected:\n                messagebox.showinfo(\n                    "Profil",\n                    "Zaznacz Dyspozycję, którą chcesz otworzyć.",\n                    parent=self.winfo_toplevel(),\n                )\n                return\n            try:\n                index = tree.index(selected[0])\n                row = active_rows[index]\n            except (IndexError, tk.TclError):\n                return\n            try:\n                from gui_dyspozycje_creator import open_dyspozycje_creator\n\n                context = dict(row)\n                context["edit_mode"] = True\n                open_dyspozycje_creator(\n                    self.winfo_toplevel(),\n                    context=context,\n                )\n            except Exception as exc:\n                messagebox.showerror(\n                    "Profil",\n                    f"Nie udało się otworzyć Dyspozycji:\\n{exc}",\n                    parent=self.winfo_toplevel(),\n                )\n\n        tree.bind("<Double-1>", _open_selected_dyspozycja)\n        ttk.Button(\n            box,\n            text="Otwórz Dyspozycję",\n            command=_open_selected_dyspozycja,\n        ).pack(anchor="w", pady=(8, 0))\n\n        if not active_rows:\n            ttk.Label(\n                box,\n                text="Brak aktywnych Dyspozycji dla tego użytkownika.",\n                style="WM.Muted.TLabel",\n            ).pack(anchor="w", pady=(8, 0))\n\n'''
count = text.count(old)
if count != 1:
    raise SystemExit(f'profile active rows marker count={count}')
text = text.replace(old, new, 1)
PATH.write_text(text, encoding='utf-8')
