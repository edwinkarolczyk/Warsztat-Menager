from pathlib import Path

path = Path('_patch_u2a6_reservations.py')
text = path.read_text(encoding='utf-8')
old = '''ui = replace_once(ui, '            return\\n        dysp_id = str(mapped.get("id") or "").strip()\\n', '            return False\\n        dysp_id = str(mapped.get("id") or "").strip()\\n', 'change status missing mapped return')'''
new = '''ui = replace_once(\n    ui,\n    '    def _change_status(self, target: str) -> bool:\\n'\n    '        mapped = self._selected_row()\\n'\n    '        if not mapped:\\n'\n    '            messagebox.showinfo(\\n'\n    '                "Dyspozycje",\\n'\n    '                "Najpierw wybierz Dyspozycję.",\\n'\n    '                parent=self,\\n'\n    '            )\\n'\n    '            return\\n'\n    '        dysp_id = str(mapped.get("id") or "").strip()\\n',\n    '    def _change_status(self, target: str) -> bool:\\n'\n    '        mapped = self._selected_row()\\n'\n    '        if not mapped:\\n'\n    '            messagebox.showinfo(\\n'\n    '                "Dyspozycje",\\n'\n    '                "Najpierw wybierz Dyspozycję.",\\n'\n    '                parent=self,\\n'\n    '            )\\n'\n    '            return False\\n'\n    '        dysp_id = str(mapped.get("id") or "").strip()\\n',\n    'change status missing mapped return',\n)'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f'guard patch expected 1 helper match, got {count}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('U2A-6 helper guard fixed')
